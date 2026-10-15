"""Setup stays repeatable, fails early, and preserves explicit trust/config."""

import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

import bootstrap


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.calls = []

    def args(self, **overrides):
        return argparse.Namespace(**{**dict(framework_only=False, check=False, root=None,
                                           workspace=None, port=8741, config=None, overwrite_config=False), **overrides})

    def run_setup(self, args=None, *, runner=None, which=lambda name: name):
        with redirect_stdout(StringIO()):
            bootstrap.prepare(args or self.args(), checkout=self.root,
                              runner=runner or self.runner, which=which)

    def runner(self, command, **kwargs):
        command = list(map(str, command))
        self.calls.append(command)
        output = ""
        if "--version" in command:
            output = "v22.12.0"
        elif "-c" in command:
            output = "3.12"
        elif "venv" in command:
            env = Path(command[-1])
            python = env / ("Scripts/python.exe" if bootstrap.sys.platform == "win32" else "bin/python")
            python.parent.mkdir(parents=True)
            python.touch()
            (env / "pyvenv.cfg").write_text("version = 3.12\n", encoding="utf-8")
        elif "mcp-config" in command:
            output = json.dumps({"mcpServers": {"cadharness": {"command": command[0], "args": command[4:]}}})
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    def test_setup_creates_environment_and_config_then_reuses_them(self):
        self.run_setup()
        config_path = self.root / ".cadharness/mcp.json"
        first = config_path.read_bytes()
        self.assertIn(str(self.root), json.loads(first)["mcpServers"]["cadharness"]["args"])
        self.assertEqual(sum("venv" in call for call in self.calls), 1)
        self.run_setup()
        self.assertEqual(config_path.read_bytes(), first)
        self.assertEqual(sum("venv" in call for call in self.calls), 1)

    def test_missing_node_and_check_only_leave_checkout_untouched(self):
        with self.assertRaisesRegex(ValueError, "Node.js"):
            self.run_setup(which=lambda name: None)
        self.assertFalse(list(self.root.iterdir()))
        self.run_setup(self.args(check=True))
        self.assertFalse(list(self.root.iterdir()))

    def test_workspace_cannot_expand_trust_and_broken_environment_is_kept(self):
        with self.assertRaisesRegex(ValueError, "explicit --root"):
            self.run_setup(self.args(root=[str(self.root / "trusted")], workspace=str(self.root / "outside")))
        self.assertFalse(self.calls)
        (self.root / ".venv").mkdir()
        marker = self.root / ".venv/user-file"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not a usable virtual environment"):
            self.run_setup()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_dependency_failure_stops_before_build_and_config(self):
        def fail(command, **kwargs):
            if "pip" in command:
                raise subprocess.CalledProcessError(1, command)
            return self.runner(command, **kwargs)
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_setup(runner=fail)
        self.assertFalse((self.root / ".cadharness").exists())
        self.assertFalse(any("ci" in call for call in self.calls))

    def test_custom_config_requires_explicit_overwrite(self):
        config = self.root / "host.json"
        original = '{"mcpServers":{"other":{"command":"keep"}}}'
        config.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Keeping existing config"):
            self.run_setup(self.args(config=str(config)))
        self.assertEqual(config.read_text(encoding="utf-8"), original)
        self.run_setup(self.args(config=str(config), overwrite_config=True))
        self.assertIn("cadharness", json.loads(config.read_text(encoding="utf-8"))["mcpServers"])

    def test_framework_only_does_not_need_node_or_generate_mcp_config(self):
        self.run_setup(self.args(framework_only=True), which=lambda name: None)
        self.assertFalse((self.root / ".cadharness").exists())
        self.assertFalse(any("ci" in call for call in self.calls))
        self.assertFalse(any("[mcp,studio]" in value for call in self.calls for value in call))


if __name__ == "__main__":
    unittest.main()
