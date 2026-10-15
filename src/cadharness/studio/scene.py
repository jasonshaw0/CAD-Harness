"""Display-only meshes from copies of evaluated native shapes."""

from copy import deepcopy
from pathlib import Path

from ..workflow.brief import digest, read_json
from ..workflow.runner import write_json

SETTINGS = {"linear_mm": 0.05, "angular": 0.1}


def write_scene(document, inspection, target: Path, cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    components = []
    for component_id, component in document.components.items():
        metrics = inspection["components"][component_id]["geometry"]
        key = digest({"fingerprint": metrics["fingerprint"], "settings": SETTINGS})
        mesh_file = cache / f"{key}.json"
        if mesh_file.exists():
            mesh = read_json(mesh_file)
        else:
            shape = deepcopy(component.shape)
            vertices, triangles = shape.tessellate(SETTINGS["linear_mm"], SETTINGS["angular"])
            mesh = {"positions": [float(value) for vertex in vertices for value in vertex],
                    "indices": [index for triangle in triangles for index in triangle]}
            write_json(mesh_file, mesh)
        components.append({"id": component_id, "role": component.role,
                           "fingerprint": metrics["fingerprint"], "bounds": metrics["bounding_box"],
                           "volume_mm3": metrics["volume_mm3"], **mesh})
    scene = {"schema": "designworkflow.scene", "schema_version": "1", "units": "mm",
             "up": "Z", "settings": SETTINGS, "components": components}
    write_json(target, scene)
    return scene
