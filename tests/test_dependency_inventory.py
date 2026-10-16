"""License directories can contain legal texts without LICENSE in their names."""

from email.message import Message
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.dependency_inventory import inventory


class DependencyInventoryTests(unittest.TestCase):
    def test_records_all_license_directory_texts_and_native_provenance(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            terms = Path("example-1.dist-info/licenses/kernel/TERMS.txt")
            (root / terms).parent.mkdir(parents=True)
            (root / terms).write_bytes(b"upstream legal text")
            headers = Message()
            headers["Name"] = "example"
            headers["License-Expression"] = "Apache-2.0"
            distribution = SimpleNamespace(
                metadata=headers, version="1", requires=["kernel>=1"],
                files=[terms, Path("example/libkernel.so.8"), Path("example/__init__.py")],
                locate_file=lambda path: root / path)
            with patch("scripts.dependency_inventory.metadata.distributions", return_value=[distribution]):
                result = inventory()
            package, = result["packages"]
            self.assertEqual(package["license_files"], [{
                "path": terms.as_posix(), "sha256": hashlib.sha256(b"upstream legal text").hexdigest()}])
            self.assertEqual(package["native_files"], ["example/libkernel.so.8"])
            self.assertEqual(package["requires"], ["kernel>=1"])
            self.assertEqual(package["license_expression"], "Apache-2.0")
            json.dumps(result)  # The retained evidence must be portable JSON.


if __name__ == "__main__":
    unittest.main()
