"""Capture identity, leases, PNG validation, and real MCP image transport."""

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from urllib.request import ProxyHandler, Request, build_opener
import zlib

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from starlette.testclient import TestClient

from cadharness.guidance import authoring_guide, SERVER_INSTRUCTIONS
from cadharness.studio.rendering import RENDER_PROTOCOL, RenderBroker, camera_settings, validate_png
from cadharness.studio.server import create_app
from cadharness.studio.store import Store, save


def png(width=256, height=256):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\x00' + b'\x80\xa0\xb0\xff' * width) * height)) + chunk(b'IEND', b''))


def seed_scene(store):
    """Retained-scene fixture; browser acceptance separately tests actual CAD meshes."""
    design = store.create('Capture fixture')
    component = {'id': 'body', 'role': 'printable-part', 'fingerprint': 'body-shape',
                 'bounds': {'min_mm': [-45, -45, 0], 'max_mm': [45, 45, 96]},
                 'positions': [], 'indices': [], 'volume_mm3': 100}
    for number, count in [(1, 1), (2, 2)]:
        revision_id = f'r{number:03}'
        root = store.design_root(design['id']) / 'revisions' / revision_id
        second = {**component, 'id': 'handle', 'bounds': {'min_mm': [43, -6, 16], 'max_mm': [83, 6, 82]}}
        scene = {'units': 'mm', 'components': [component] + ([second] if count == 2 else [])}
        target = root / 'project/evidence/scene.json'
        save(target, scene)
        save(root / 'run.json', {'artifacts': {'evidence/scene.json': sha256(target.read_bytes()).hexdigest()}})
        design['revisions'].append({'id': revision_id, 'scene': True, 'status': 'ready'})
    design.update(latest_revision='r002', display_revision='r002', status='ready')
    store.put(design)
    return design


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(self.directory.name)
        self.design = seed_scene(self.store)
        self.broker = RenderBroker(self.store, timeout=.3)
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.addCleanup(self.pool.shutdown)

    def begin(self, **kwargs):
        self.broker.poll('renderer-one')
        future = self.pool.submit(self.broker.capture, self.design['id'], width=256, height=256, **kwargs)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            request = self.broker.poll('renderer-one')
            if request:
                return future, request
            time.sleep(.002)
        self.fail('No capture request')

    def result(self, request, **kwargs):
        return {'client_id': request['client_id'], 'lease_token': request['lease_token'],
                'scene_fingerprint': request['scene_fingerprint'],
                'png_base64': base64.b64encode(png()).decode(), **kwargs}

    def test_defaults_history_isolation_focus_and_artifacts_leave_evidence_unchanged(self):
        before = {str(p): p.read_bytes() for p in self.store.root.rglob('run.json')}
        design_before = self.store.get(self.design['id'])
        future, request = self.begin(revision_id='r001', component_ids=['body'],
                                     focus_bounds_mm=[[-5, -5, 70], [5, 5, 90]], view='top')
        self.assertEqual(request['revision_id'], 'r001')
        self.assertEqual([c['id'] for c in request['scene']['components']], ['body'])
        self.assertEqual(request['camera']['projection'], 'orthographic')
        self.assertEqual(request['camera']['target'], [0, 0, 80])
        self.broker.complete(request['id'], self.result(request))
        result = future.result()
        self.assertEqual(result['status'], 'captured')
        self.assertFalse(result['reviewed'])
        self.assertEqual(result['artifact']['sha256'], sha256(png()).hexdigest())
        self.assertEqual((self.store.root / result['artifact']['path']).read_bytes(), png())
        self.assertNotIn('/revisions/', result['artifact']['path'].replace('\\', '/'))
        self.assertEqual(self.store.get(self.design['id']), design_before)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.store.root.rglob('run.json')})
        future, request = self.begin()
        self.assertEqual(request['revision_id'], 'r002')
        self.assertEqual(len(request['scene']['components']), 2)
        self.broker.complete(request['id'], self.result(request))
        self.assertEqual(future.result()['status'], 'captured')

    def test_single_claim_wrong_renderer_mismatch_and_duplicate_rejected(self):
        future, request = self.begin()
        self.assertIsNone(self.broker.poll('renderer-two'))
        with self.assertRaises(PermissionError):
            self.broker.complete(request['id'], self.result(request, client_id='renderer-two'))
        with self.assertRaises(ValueError):
            self.broker.complete(request['id'], self.result(request, scene_fingerprint='stale'))
        self.broker.complete(request['id'], self.result(request))
        future.result()
        with self.assertRaises(ValueError):
            self.broker.complete(request['id'], self.result(request))

    def test_no_browser_timeout_expiry_and_webgl_error(self):
        self.assertEqual(self.broker.capture(self.design['id'])['status'], 'unavailable')
        self.assertFalse(self.broker.pending)
        self.broker.poll('renderer-one')
        started = time.monotonic()
        self.assertIn('timed out', self.broker.capture(self.design['id'])['reason'])
        self.assertLess(time.monotonic()-started, 1)
        future, request = self.begin()
        self.broker.complete(request['id'], self.result(request, error='WebGL unavailable'))
        self.assertEqual(future.result()['reason'], 'WebGL unavailable')
        future, request = self.begin()
        self.assertEqual(future.result()['status'], 'unavailable')
        with self.assertRaises(ValueError):
            self.broker.complete(request['id'], self.result(request))

    def test_invalid_inputs_and_modified_scene(self):
        for kwargs in [{'view': 'unknown'}, {'width': 100000}, {'height': True},
                       {'component_ids': []}, {'component_ids': ['missing']},
                       {'component_ids': ['body', 'body']}, {'revision_id': '../r001'},
                       {'focus_bounds_mm': [[0, 0, 0], [0, 1, 1]]},
                       {'focus_bounds_mm': [[1000, 0, 0], [1001, 1, 1]]},
                       {'focus_bounds_mm': [[0, 0, 0], [float('nan'), 1, 1]]}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.broker.capture(self.design['id'], **kwargs)
        path = self.store.design_root(self.design['id']) / 'revisions/r002/project/evidence/scene.json'
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'evaluated revision'):
            self.broker.capture(self.design['id'])

    def test_png_and_http_guards(self):
        self.assertEqual(validate_png(base64.b64encode(png()).decode(), 256, 256), png())
        for data in [b'not an image', png()[:-1], png() + b'extra', png(257), png()[:45] + b'bad']:
            with self.assertRaises(ValueError):
                validate_png(base64.b64encode(data).decode(), 256, 256)
        with TestClient(create_app(self.store.root)) as client:
            self.assertEqual(client.post('/api/renderers/poll', json={'client_id': 'renderer-one'}).status_code, 403)
            session = client.get('/api/session').json()
            self.assertEqual(session['render_protocol'], RENDER_PROTOCOL)
            token = session['token']
            headers = {'X-Studio-Token': token}
            self.assertEqual(client.post('/api/renderers/poll', json={'client_id': 'renderer-one'},
                                        headers={**headers, 'Origin': 'https://example.com'}).status_code, 403)
            self.assertEqual(client.post('/api/renderers/poll', json={'client_id': 'renderer-one'}, headers=headers).status_code, 200)
            self.assertEqual(client.post('/api/renders/render-dead/result', json={}, headers=headers).status_code, 400)

    def test_camera_fits_each_view_and_aspect(self):
        component = {'bounds': {'min_mm': [-1, -1, -100], 'max_mm': [1, 1, 100]}}
        for view in ['iso', 'top', 'front', 'right', 'left', 'bottom']:
            camera = camera_settings([component], view, 256, 2048, None)
            self.assertAlmostEqual(camera['right']/camera['top'], 256/2048)
            self.assertGreater(camera['far'], camera['near'])
            self.assertGreater(camera['top'], 0)


class RenderingMCPTests(unittest.TestCase):
    def test_real_stdio_guide_and_png_through_owner_and_attached_client(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory) / 'studio'
            # Fixtures contain retained data only, so the server imports no candidate source.
            store = Store(workspace)
            design = seed_scene(store)
            async def exercise():
                args = ['-m', 'cadharness.mcp_server', '--root', directory, '--studio',
                        '--studio-workspace', str(workspace), '--studio-port']
                params = StdioServerParameters(command=sys.executable, args=args + ['0'], cwd=directory)
                async with stdio_client(params) as streams:
                    async with ClientSession(*streams) as owner:
                        init = await owner.initialize()
                        self.assertIn('get_cad_authoring_guide', init.instructions)
                        guide = await owner.call_tool('get_cad_authoring_guide', {})
                        self.assertEqual(guide.structured_content, authoring_guide())
                        self.assertLess(len(SERVER_INSTRUCTIONS), 512)
                        status = (await owner.call_tool('studio_status', {})).structured_content
                        url = status['viewer_url']
                        stop = threading.Event()
                        def browser():
                            opener = build_opener(ProxyHandler({}))
                            with opener.open(url + '/api/session') as r:
                                token = json.load(r)['token']
                            def post(path, body):
                                req = Request(url + path, data=json.dumps(body).encode(), headers={
                                    'Content-Type': 'application/json', 'X-Studio-Token': token})
                                with opener.open(req) as r:
                                    return json.load(r)
                            while not stop.is_set():
                                request = post('/api/renderers/poll', {'client_id': 'transport-test-browser'})['request']
                                if request:
                                    post('/api/renders/' + request['id'] + '/result', {
                                        'client_id': request['client_id'], 'lease_token': request['lease_token'],
                                        'scene_fingerprint': request['scene_fingerprint'],
                                        'png_base64': base64.b64encode(png()).decode()})
                                stop.wait(.02)
                        thread = threading.Thread(target=browser)
                        thread.start()
                        try:
                            for _ in range(100):
                                status = (await owner.call_tool('studio_status', {})).structured_content
                                if status['rendering']['available']:
                                    break
                                await anyio.sleep(.02)
                            second = StdioServerParameters(command=sys.executable, args=args + [url.rsplit(':', 1)[1]], cwd=directory)
                            async with stdio_client(second) as second_streams:
                                async with ClientSession(*second_streams) as attached:
                                    await attached.initialize()
                                    for session in [owner, attached]:
                                        result = await session.call_tool('studio_render_view', {
                                            'design_id': design['id'], 'width': 256, 'height': 256})
                                        self.assertFalse(result.is_error, result)
                                        self.assertEqual(result.structured_content['status'], 'captured')
                                        self.assertNotIn('_png_base64', result.structured_content)
                                        image, = [c for c in result.content if c.type == 'image']
                                        self.assertEqual(image.mime_type, 'image/png')
                                        self.assertEqual(base64.b64decode(image.data), png())
                        finally:
                            stop.set()
                            thread.join(3)
            anyio.run(exercise)


if __name__ == '__main__':
    unittest.main()
