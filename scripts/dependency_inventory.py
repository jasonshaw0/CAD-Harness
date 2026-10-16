"""Record installed distribution metadata and license/native file provenance.

Run with the fresh smoke environment's interpreter. This is an inventory of
that environment, not a license compatibility verdict or a dependency lock.
"""

import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import sys


def inventory():
    packages = []
    for distribution in metadata.distributions():
        headers = distribution.metadata
        licenses, native = [], []
        for path in distribution.files or []:
            name = str(path).replace("\\", "/")
            if (any(word in path.name.lower() for word in ("license", "notice", "copying"))
                    or any(part.lower() in {"license", "licenses"} for part in path.parts)):
                absolute = distribution.locate_file(path)
                if absolute.is_file():
                    licenses.append({"path": name, "sha256": hashlib.sha256(absolute.read_bytes()).hexdigest()})
            if path.suffix.lower() in {".dll", ".pyd", ".so", ".dylib"} or ".so." in path.name.lower():
                native.append(name)
        packages.append({
            "name": headers["Name"], "version": distribution.version,
            "license_expression": headers.get("License-Expression"),
            "legacy_license": headers.get("License"),
            "license_classifiers": [value for value in headers.get_all("Classifier", [])
                                    if value.startswith("License ::")],
            "project_urls": headers.get_all("Project-URL", []),
            "requires": distribution.requires or [],
            "license_files": sorted(licenses, key=lambda item: item["path"]),
            "native_files": sorted(native),
        })
    return {"schema": "cadharness.dependency-inventory", "version": 1,
            "python": platform.python_version(), "platform": sys.platform,
            "machine": platform.machine(),
            "scope": "Installed environment, including installer tooling; metadata is not a compliance verdict.",
            "packages": sorted(packages, key=lambda item: item["name"].lower())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Refuse to replace retained evidence.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(inventory(), stream, indent=2)
        stream.write("\n")
