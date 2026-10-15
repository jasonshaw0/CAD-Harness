"""On-demand browser rendering of retained scenes, independent of the viewport.

Only this broker creates capture requests. CAD builds do not instantiate renderers
or generate images. Captures live outside revision evidence and never imply review.
"""

import base64
from hashlib import sha256
from itertools import product
import json
from math import isfinite, sqrt
import secrets
import struct
import threading
import time
import zlib

from ..workflow.brief import read_json
from .store import contained, new_id, now, save

VIEWS = {"iso": (1, -1.5, 1.1), "front": (0, -1, 0), "right": (1, 0, 0),
         "left": (-1, 0, 0), "top": (0, 0, 1), "bottom": (0, 0, -1)}
RENDER_PROTOCOL = "cadharness-studio-render/1"
MAX_PNG_BYTES = 8 * 1024 * 1024


def _vector(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not isfinite(v) for v in value)):
        raise ValueError("Bounds must contain finite three-coordinate vectors")
    return list(value)


def _unit(v):
    length = sqrt(sum(x * x for x in v))
    return [x / length for x in v]


def _cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def camera_settings(components, view, width, height, focus_bounds_mm):
    lower = [min(c["bounds"]["min_mm"][i] for c in components) for i in range(3)]
    upper = [max(c["bounds"]["max_mm"][i] for c in components) for i in range(3)]
    bounds = [lower, upper]
    if focus_bounds_mm is not None:
        if not isinstance(focus_bounds_mm, (list, tuple)) or len(focus_bounds_mm) != 2:
            raise ValueError("focus_bounds_mm must be [min_xyz, max_xyz]")
        bounds = [_vector(v) for v in focus_bounds_mm]
        if any(bounds[0][i] >= bounds[1][i] for i in range(3)):
            raise ValueError("Focus bounds must have positive extents")
        if any(bounds[1][i] < lower[i] or bounds[0][i] > upper[i] for i in range(3)):
            raise ValueError("Focus bounds do not intersect the selected component bounds")
    target = [(a+b)/2 for a, b in zip(*bounds)]
    direction = _unit(VIEWS[view])
    up = [0, 1, 0] if view in {"top", "bottom"} else [0, 0, 1]
    right = _unit(_cross(up, direction))
    vertical = _cross(direction, right)
    corners = [[x-target[0], y-target[1], z-target[2]] for x, y, z in product(*zip(*bounds))]
    span_x = 2 * max(abs(sum(a*b for a, b in zip(c, right))) for c in corners)
    span_y = 2 * max(abs(sum(a*b for a, b in zip(c, vertical))) for c in corners)
    half_height = max(span_y, span_x * height/width, .1) * .56
    half_width = half_height * width/height
    reach = max(sqrt(sum((upper[i]-lower[i])**2 for i in range(3))), 1)
    distance = reach * 2 + sqrt(sum((target[i]-(lower[i]+upper[i])/2)**2 for i in range(3)))
    return {"projection": "orthographic", "position": [target[i]+direction[i]*distance for i in range(3)],
            "target": target, "up": up, "near": .001, "far": distance + reach * 2,
            "left": -half_width, "right": half_width, "top": half_height, "bottom": -half_height}


def validate_png(encoded, width, height):
    """Bound and validate PNG structure, CRCs and decompressed scanlines."""
    if not isinstance(encoded, str) or len(encoded) > (MAX_PNG_BYTES + 2) // 3 * 4:
        raise ValueError("PNG payload exceeds the capture size limit")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("Invalid PNG base64") from exc
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > MAX_PNG_BYTES:
        raise ValueError("Invalid PNG image")
    offset, compressed, channels, ended = 8, bytearray(), None, False
    while offset + 12 <= len(data):
        length, kind = struct.unpack('>I4s', data[offset:offset+8])
        chunk = data[offset+8:offset+8+length]
        end = offset + 12 + length
        if end > len(data) or zlib.crc32(kind + chunk) != struct.unpack('>I', data[end-4:end])[0]:
            raise ValueError("Invalid PNG chunk")
        if offset == 8:
            if kind != b'IHDR' or length != 13:
                raise ValueError("Invalid PNG header")
            w, h, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunk)
            if (w, h) != (width, height) or depth != 8 or color not in {2, 6} or (compression, filtering, interlace) != (0, 0, 0):
                raise ValueError("PNG dimensions or encoding do not match the request")
            channels = 3 if color == 2 else 4
        elif kind == b'IHDR':
            raise ValueError("Duplicate PNG header")
        if kind == b'IDAT':
            compressed.extend(chunk)
        if kind == b'IEND':
            ended = length == 0 and end == len(data)
            break
        offset = end
    if not ended or channels is None:
        raise ValueError("Incomplete PNG image")
    expected = height * (1 + width * channels)
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(compressed, expected + 1)
    except zlib.error as exc:
        raise ValueError("Invalid PNG pixels") from exc
    stride = 1 + width * channels
    if (len(pixels) != expected or not decoder.eof or decoder.unused_data
            or any(pixels[i] > 4 for i in range(0, expected, stride))):
        raise ValueError("Invalid PNG scanlines")
    return data


class RenderBroker:
    def __init__(self, store, *, timeout=10):
        self.store, self.timeout = store, timeout
        self.lock = threading.Lock()
        self.clients, self.pending = {}, {}

    def availability(self):
        with self.lock:
            current = time.monotonic()
            self.clients = {k: v for k, v in self.clients.items() if current-v < 5}
            return {"available": bool(self.clients), "connected_renderers": len(self.clients),
                    "views": list(VIEWS), "default_size": [1024, 768], "timeout_seconds": self.timeout,
                    "requires": "Open Studio tab with working WebGL; no desktop control", "review_required": False}

    def capture(self, design_id, revision_id=None, view="iso", component_ids=None,
                focus_bounds_mm=None, width=1024, height=768):
        if view not in VIEWS:
            raise ValueError(f"Unknown view; choose {', '.join(VIEWS)}")
        if any(type(v) is not int or not 256 <= v <= 2048 for v in (width, height)):
            raise ValueError("Image width and height must be integers between 256 and 2048")
        design = self.store.get(design_id)
        rows = [r for r in design['revisions'] if r.get('scene')]
        if revision_id is None:
            revision_id = rows[-1]['id'] if rows else None
        if not revision_id or not any(r['id'] == revision_id for r in rows):
            raise ValueError("Choose a revision with built geometry")
        revision = contained(self.store.design_root(design_id) / 'revisions', revision_id)
        path = contained(revision, 'project/evidence/scene.json')
        raw = path.read_bytes()
        fingerprint = sha256(raw).hexdigest()
        report = read_json(revision / 'run.json')
        if report.get('artifacts', {}).get('evidence/scene.json') != fingerprint:
            raise ValueError("Retained scene no longer matches the evaluated revision")
        scene = json.loads(raw)
        ids = [c['id'] for c in scene['components']]
        selected = ids if component_ids is None else component_ids
        if (not isinstance(selected, list) or not selected or any(not isinstance(i, str) for i in selected)
                or len(set(selected)) != len(selected) or set(selected) - set(ids)):
            raise ValueError("Select distinct existing component IDs")
        components = [c for c in scene['components'] if c['id'] in selected]
        camera = camera_settings(components, view, width, height, focus_bounds_mm)
        metadata = {"design_id": design_id, "revision_id": revision_id, "scene_fingerprint": fingerprint,
                    "component_ids": selected, "view": view, "width": width, "height": height,
                    "focus_bounds_mm": focus_bounds_mm, "camera": camera, "reviewed": False}
        if not self.availability()['available']:
            return {"status": "unavailable", "reason": "Open Studio with working WebGL to capture this view.", **metadata}
        request_id = new_id('render')
        entry = {"id": request_id, **metadata, "scene": {**scene, "components": components},
                 "deadline": time.monotonic() + self.timeout, "event": threading.Event(),
                 "client_id": None, "lease_token": None, "result": None}
        with self.lock:
            self.pending[request_id] = entry
        entry['event'].wait(self.timeout)
        with self.lock:
            self.pending.pop(request_id, None)
            result = entry['result']
        return result or {"status": "unavailable", "reason": "Studio capture timed out; no image was returned.", **metadata}

    def poll(self, client_id):
        if not isinstance(client_id, str) or not 8 <= len(client_id) <= 100 or not client_id.isascii():
            raise ValueError("Invalid renderer client ID")
        with self.lock:
            self.clients[client_id] = time.monotonic()
            for entry in self.pending.values():
                if entry['client_id'] is None and time.monotonic() < entry['deadline']:
                    entry.update(client_id=client_id, lease_token=secrets.token_urlsafe(24))
                    return {k: v for k, v in entry.items() if k not in {'event', 'deadline', 'result'}}
        return None

    def complete(self, request_id, body):
        with self.lock:
            entry = self.pending.get(request_id)
            if entry is None or entry['result'] is not None or time.monotonic() >= entry['deadline']:
                raise ValueError("Capture is expired, unknown, or already completed")
            if (body.get('client_id') != entry['client_id'] or not entry['lease_token']
                    or body.get('lease_token') != entry['lease_token']):
                raise PermissionError("Capture belongs to a different renderer")
            if body.get('scene_fingerprint') != entry['scene_fingerprint']:
                raise ValueError("Capture scene fingerprint does not match")
            metadata = {k: entry[k] for k in ('design_id', 'revision_id', 'scene_fingerprint', 'component_ids',
                                              'view', 'width', 'height', 'focus_bounds_mm', 'camera', 'reviewed')}
            if body.get('error'):
                entry['result'] = {"status": "unavailable", "reason": str(body['error'])[:500], **metadata}
            else:
                data = validate_png(body.get('png_base64'), entry['width'], entry['height'])
                root = contained(self.store.design_root(entry['design_id']), 'renders')
                root.mkdir(exist_ok=True)
                target = contained(root, request_id + '.png')
                with target.open('xb') as stream:
                    stream.write(data)
                artifact = {"id": request_id, "mime_type": "image/png", "bytes": len(data),
                            "sha256": sha256(data).hexdigest(),
                            "path": str(target.relative_to(self.store.root))}
                saved = {"status": "captured", **metadata, "created": now(), "artifact": artifact}
                save(contained(root, request_id + '.json'), saved)
                entry['result'] = {**saved, "_png_base64": base64.b64encode(data).decode('ascii')}
            entry['event'].set()
