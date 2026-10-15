"""Keep shared CLI onboarding and explicit Studio trust roots working."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cadharness.cli import main
from cadharness.mcp_config import mcp_client_config


class ProductEntrypointTests(unittest.TestCase):
    def test_generated_studio_config_preserves_roots_and_contains_workspace(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            workspace = root / "designs"
            config = mcp_client_config([root], studio=True, studio_workspace=workspace, studio_port=8742)
            args = config["mcpServers"]["cadharness"]["args"]
            self.assertEqual(args, ["-m", "cadharness.mcp_server", "--root", str(root),
                                    "--studio", "--studio-workspace", str(workspace), "--studio-port", "8742"])
            with self.assertRaisesRegex(ValueError, "explicit trusted root"):
                mcp_client_config([root], studio=True, studio_workspace=root.parent)
            with self.assertRaisesRegex(ValueError, "requires --studio"):
                mcp_client_config([root], studio_workspace=workspace)
            with self.assertRaisesRegex(ValueError, "port"):
                mcp_client_config([root], studio=True, studio_port=65536)

    def test_unified_design_command_creates_a_scaffold_from_installed_resources(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.txt"
            prompt.write_text("Create a plate; ask about unspecified dimensions.", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(["design", "init", "--id", "first-design", "--root", str(root / "runs"),
                             "--prompt-file", str(prompt)])
            self.assertEqual(code, 0)
            revision = Path(json.loads(output.getvalue())["revision"])
            self.assertTrue((revision / "project/cadharness.toml").is_file())
            self.assertTrue((revision / "project/project.py").is_file())
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["design", "check", str(revision), "--review-hashes"]), 0)

    def test_standalone_command_forwards_workspace_without_starting_mcp(self):
        with patch("cadharness.studio.server.serve") as serve:
            self.assertEqual(main(["studio", "--workspace", "local-designs", "--port", "8742"]), 0)
            serve.assert_called_once_with(workspace=Path("local-designs"), port=8742, model=None, designer="mcp")


if __name__ == "__main__":
    unittest.main()
