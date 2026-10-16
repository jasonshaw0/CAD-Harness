"""Host config changes are explicit, additive, and independent of host cwd."""

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
import unittest
from unittest.mock import patch

from cadharness.cli import main
from cadharness.host_setup import _apply, _config_path, _read, check_connection, setup_host
from cadharness.paths import STUDIO_WEB


class HostSetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        # Spaces, Unicode and shell metacharacters must stay argv values.
        self.projects = self.root / "CAD space & café"
        self.projects.mkdir()
        self.config = self.root / "profile" / "desktop.json"

    def setup(self, **kwargs):
        return setup_host([self.projects], host="claude-desktop", config=self.config, **kwargs)

    def write(self, data):
        self.config.parent.mkdir(exist_ok=True)
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.config.write_bytes(raw)
        return raw

    def test_preview_has_exact_paths_and_creates_nothing(self):
        result = self.setup(studio=True, studio_workspace=self.projects / "workspace")
        self.assertTrue(result["ready"])
        self.assertFalse(result["changed"])
        self.assertIsNone(result["connection"])
        self.assertEqual(result["entry"]["command"], sys.executable)
        self.assertEqual(result["trusted_roots"], [str(self.projects)])
        self.assertIn(str(self.projects / "workspace"), result["entry"]["args"])
        self.assertFalse(self.config.parent.exists())
        self.assertFalse((self.projects / "workspace").exists())

    def test_apply_preserves_unrelated_settings_backup_and_idempotence(self):
        original = {"theme": "café", "mcpServers": {"other": {"command": "other", "env": {"PRIVATE": "preserve"}}}}
        raw = self.write(original)
        result = self.setup(apply=True)
        self.assertTrue(result["changed"])
        self.assertEqual(Path(result["backup"]).read_bytes(), raw)
        updated = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(updated["theme"], original["theme"])
        self.assertEqual(updated["mcpServers"]["other"], original["mcpServers"]["other"])
        first = self.config.read_bytes()
        again = self.setup(apply=True)
        self.assertTrue(again["ready"])
        self.assertFalse(again["changed"])
        self.assertEqual(again["existing_entry"], "already-configured")
        self.assertIsNone(again["backup"])
        self.assertEqual(self.config.read_bytes(), first)

    def test_conflicting_entry_is_never_replaced_or_checked(self):
        raw = self.write({"mcpServers": {"cadharness": {"command": "different"}}})
        with patch("cadharness.host_setup.check_connection") as check:
            result = self.setup(check=True, apply=True)
        check.assert_not_called()
        self.assertFalse(result["ready"])
        self.assertEqual(result["existing_entry"], "conflict")
        self.assertEqual(self.config.read_bytes(), raw)
        self.assertEqual(len(list(self.config.parent.iterdir())), 1)
        self.assertTrue(self.setup(name="cadharness-new", apply=True)["changed"])

    def test_environment_or_disabled_entry_requires_manual_review(self):
        entry = self.setup()["entry"]
        self.write({"mcpServers": {"cadharness": {**entry, "env": {"PYTHONPATH": "different"}}}})
        self.assertEqual(self.setup()["existing_entry"], "conflict")

    def test_rejects_malformed_or_ambiguous_configuration(self):
        self.config.parent.mkdir()
        for value in ('[]', '{"mcpServers": []}', '{"mcpServers":{},"mcpServers":{}}', '{"bad": NaN}', '{oops'):
            with self.subTest(value=value):
                self.config.write_text(value, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.setup(apply=True)
                self.assertEqual(self.config.read_text(encoding="utf-8"), value)

    def test_requires_explicit_existing_roots_and_valid_workspace(self):
        with self.assertRaisesRegex(ValueError, "explicit --root"):
            setup_host([], host="claude-desktop", config=self.config)
        result = setup_host([self.root / "missing"], host="claude-desktop", config=self.config, apply=True)
        self.assertFalse(result["ready"])
        self.assertFalse(self.config.exists())
        with self.assertRaisesRegex(ValueError, "explicit trusted root"):
            self.setup(studio=True, studio_workspace=self.root)
        with self.assertRaisesRegex(ValueError, "Server name"):
            self.setup(name="bad.name")

    def test_missing_dependency_blocks_check_and_write(self):
        with patch("cadharness.host_setup.importlib.util.find_spec", return_value=None):
            result = self.setup(check=True, apply=True)
        self.assertFalse(result["ready"])
        self.assertIn("Missing mcp", result["blockers"][0])
        self.assertFalse(self.config.exists())

    def test_failed_connection_does_not_write(self):
        with patch("cadharness.host_setup.check_connection", return_value={"passed": False, "error": "port in use"}):
            result = self.setup(check=True, apply=True)
        self.assertFalse(result["ready"])
        self.assertFalse(self.config.exists())

    def test_real_failed_startup_retains_server_stderr(self):
        result = check_connection({"command": sys.executable,
                                   "args": ["-c", "import sys; sys.stderr.write('startup sentinel'); sys.exit(7)"]})
        self.assertFalse(result["passed"])
        self.assertIn("startup sentinel", result["stderr"])

    def test_discovery_does_not_read_configs_or_claim_a_connection(self):
        with patch("cadharness.host_setup._read", side_effect=AssertionError("must not read settings")):
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(main(["setup"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual([host["host"] for host in report["hosts"]], ["codex", "claude-desktop"])
        self.assertTrue(all(host["connected"] == "unknown" for host in report["hosts"]))

    def test_default_desktop_paths_and_missing_directory(self):
        with patch("cadharness.host_setup.sys.platform", "win32"), patch.dict(os.environ, {"APPDATA": str(self.root)}):
            self.assertEqual(_config_path("claude-desktop", None), self.root / "Claude/claude_desktop_config.json")
            result = setup_host([self.projects], host="claude-desktop", apply=True)
            self.assertFalse(result["ready"])
            self.assertFalse((self.root / "Claude").exists())
        with patch("cadharness.host_setup.sys.platform", "darwin"):
            self.assertEqual(_config_path("claude-desktop", None), Path.home() / "Library/Application Support/Claude/claude_desktop_config.json")
        with patch("cadharness.host_setup.sys.platform", "linux"):
            with self.assertRaisesRegex(ValueError, "--config"):
                _config_path("claude-desktop", None)

    def test_concurrent_edit_and_symlink_are_refused(self):
        raw = self.write({"theme": "before"})
        _, data = _read(self.config, "claude-desktop")
        self.config.write_text('{"theme":"after"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed during setup"):
            _apply(self.config, "claude-desktop", "cadharness", {}, raw, data, None)
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.setup(apply=True)

    def test_codex_uses_native_cli_argv_and_preserves_other_tables(self):
        profile = self.root / "codex-profile"
        profile.mkdir()
        path = profile / "config.toml"
        raw = 'model = "retain-me"\n[mcp_servers.other]\ncommand = "other"\n'
        path.write_text(raw, encoding="utf-8")
        with patch.dict(os.environ, {"CODEX_HOME": str(profile)}), patch("cadharness.host_setup._codex_command", return_value=["codex-native"]):
            preview = setup_host([self.projects], host="codex")
            argv = preview["host_command_argv"]
            self.assertEqual(argv[:6], ["codex-native", "mcp", "add", "cadharness", "--", sys.executable])
            self.assertIn(str(self.projects), argv)
            self.assertEqual(path.read_text(encoding="utf-8"), raw)

            def save(command, **kwargs):
                self.assertEqual(command, argv)
                self.assertNotIn("shell", kwargs)
                self.assertEqual(kwargs["env"]["CODEX_HOME"], str(profile))
                entry = preview["entry"]
                path.write_text(raw + '\n[mcp_servers.cadharness]\ncommand = ' + json.dumps(entry["command"]) + '\nargs = ' + json.dumps(entry["args"]) + '\n', encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "added", "")

            with patch("cadharness.host_setup.subprocess.run", side_effect=save) as run:
                result = setup_host([self.projects], host="codex", apply=True)
            self.assertTrue(result["changed"])
            self.assertEqual(tomllib.loads(path.read_text(encoding="utf-8"))["model"], "retain-me")
            self.assertEqual(Path(result["backup"]).read_text(encoding="utf-8"), raw)
            with patch("cadharness.host_setup.subprocess.run") as run:
                self.assertFalse(setup_host([self.projects], host="codex", apply=True)["changed"])
                run.assert_not_called()

    def test_codex_home_is_canonicalized_before_changing_subprocess_cwd(self):
        with patch.dict(os.environ, {"CODEX_HOME": "relative-profile"}):
            self.assertEqual(_config_path("codex", None), Path.cwd() / "relative-profile/config.toml")
        with patch.dict(os.environ, {"CODEX_HOME": ""}):
            with self.assertRaisesRegex(ValueError, "CODEX_HOME is empty"):
                _config_path("codex", None)

    def test_codex_failure_reports_backup_without_overwriting_settings(self):
        profile = self.root / "codex-profile"
        profile.mkdir()
        path = profile / "config.toml"
        raw = b'model = "retain"\n'
        path.write_bytes(raw)
        with patch.dict(os.environ, {"CODEX_HOME": str(profile)}), patch("cadharness.host_setup._codex_command", return_value=["codex-native"]):
            with patch("cadharness.host_setup.subprocess.run", return_value=subprocess.CompletedProcess([], 7, "", "host refused")):
                with self.assertRaisesRegex(RuntimeError, "backup:.*host refused"):
                    setup_host([self.projects], host="codex", apply=True)
        self.assertEqual(path.read_bytes(), raw)
        backup, = profile.glob("*.bak")
        self.assertEqual(backup.read_bytes(), raw)

    def test_cli_preview_summary_and_conflict_exit_codes(self):
        args = ["setup", "--host", "claude-desktop", "--root", str(self.projects), "--config", str(self.config)]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main([*args, "--summary"]), 0)
        self.assertIn("Review this entry", output.getvalue())
        self.write({"mcpServers": {"cadharness": {"command": "other"}}})
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main([*args, "--compact", "--apply"]), 2)
        self.assertFalse(json.loads(output.getvalue())["changed"])

    def test_real_stdio_check_from_unrelated_directory(self):
        result = self.setup(check=True)
        self.assertTrue(result["ready"], result["connection"])
        self.assertEqual(result["connection"]["status"]["roots"], [{"path": str(self.projects), "exists": True}])
        self.assertFalse(result["connection"]["host_reloaded"])
        self.assertFalse(self.config.exists())

    @unittest.skipUnless((STUDIO_WEB / "index.html").is_file(), "Build frontend or test the full wheel for Studio acceptance")
    def test_real_studio_check_from_unrelated_directory(self):
        result = self.setup(studio=True, studio_workspace=self.projects / "workspace", studio_port=0, check=True)
        self.assertTrue(result["ready"], result["connection"])
        connection = result["connection"]
        self.assertFalse(connection["host_reloaded"])
        self.assertTrue(connection["studio"]["frontend_available"])
        self.assertEqual(connection["studio"]["workspace"], str(self.projects / "workspace"))
        self.assertEqual(connection["status"]["roots"], [{"path": str(self.projects), "exists": True}])
        self.assertFalse(self.config.exists())


if __name__ == "__main__":
    unittest.main()
