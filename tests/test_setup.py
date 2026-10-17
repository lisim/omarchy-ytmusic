import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("music_setup", Path(__file__).resolve().parents[1] / "scripts/ytmusic.py")
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="music-setup-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = music.Paths({"XDG_RUNTIME_DIR": str(self.root)}, user_home=self.root)
        self.paths.bindings.parent.mkdir(parents=True)
        self.original = '-- user settings\no.bind("SUPER + X", "Example", "true")\n'
        self.paths.bindings.write_text(self.original)

    def settings(self, backend="custom"):
        music.atomic_write(self.paths.settings, json.dumps({"backend": backend, "browser": "later", "auto_refresh": False}))
        binary = self.paths.binary(backend)
        binary.parent.mkdir(parents=True)
        binary.write_text("fake")

    def test_choices_keep_binary_and_custom_config_separate(self):
        self.assertNotEqual(self.paths.binary("custom"), self.paths.binary("original"))
        custom = music.player_env(self.paths, "custom")
        original = music.player_env(self.paths, "original")
        self.assertEqual(custom["YTMUSIC_TUI_CONFIG_DIR"], str(self.paths.config / "custom-tui"))
        self.assertNotIn("YTMUSIC_TUI_CONFIG_DIR", original)
        self.assertNotIn("NO_COLOR", custom)
        self.assertNotIn("NO_COLOR", original)

    def test_desktop_rule_round_trip_preserves_existing_bindings(self):
        with patch.object(music, "run", return_value=subprocess.CompletedProcess([], 0, "")):
            music.update_desktop(self.paths, True)
            first = self.paths.bindings.read_text()
            music.update_desktop(self.paths, True)
            self.assertEqual(first, self.paths.bindings.read_text())
            self.assertEqual(first.count(music.BEGIN), 1)
            music.update_desktop(self.paths)
        self.assertEqual(self.paths.bindings.read_text(), self.original)

    def test_failed_desktop_validation_restores_previous_file(self):
        with patch.object(music, "run", return_value=subprocess.CompletedProcess([], 0, "invalid rule")):
            with self.assertRaises(ValueError):
                music.update_desktop(self.paths, False)
        self.assertEqual(self.paths.bindings.read_text(), self.original)

    def test_incomplete_desktop_markers_are_not_rewritten(self):
        self.paths.bindings.write_text(self.original + music.BEGIN)
        with self.assertRaises(ValueError):
            music.update_desktop(self.paths, False)
        self.assertEqual(self.paths.bindings.read_text(), self.original + music.BEGIN)

    def test_new_setup_offers_both_modes_without_changing_original_config(self):
        original_config = self.root / ".config/ytmusic-tui/config.toml"
        original_config.parent.mkdir(parents=True)
        original_config.write_text('[ui]\ntheme = "nord"\n')
        lock = {mode: {"repository": "https://github.com/lisim/ytmusic-tui.git", "commit": "a" * 40} for mode in ("custom", "original")}
        (self.root / "backends.json").write_text(json.dumps(lock))
        for mode_index, mode in enumerate(("custom", "original")):
            with patch.object(music, "ROOT", self.root), patch.object(music, "own_window", return_value=None), \
                 patch.object(music.shutil, "which", return_value="/usr/bin/test"), \
                 patch.object(music, "choose", side_effect=[mode_index, music.BROWSERS.index("later")]), \
                 patch.object(music, "confirm", return_value=False), patch.object(music, "build_backend") as build, \
                 patch.object(music, "update_desktop"):
                music.setup(self.paths)
            self.assertEqual(music.load_settings(self.paths)["backend"], mode)
            self.assertEqual(build.call_args.args[1], mode)
            self.assertEqual(original_config.read_text(), '[ui]\ntheme = "nord"\n')
        self.assertEqual(self.paths.settings.stat().st_mode & 0o777, 0o600)

    def test_build_uses_exact_pin_and_does_not_rebuild_same_revision(self):
        source = {"repository": "https://github.com/lisim/ytmusic-tui.git", "commit": "a" * 40}
        built = self.paths.cache / "target/custom/release/ytmusic-tui"
        built.parent.mkdir(parents=True)
        built.write_text("fake compiled executable")
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "a" * 40 + "\n" if "rev-parse" in args else "")
        with patch.object(music, "run", side_effect=fake_run) as calls:
            music.build_backend(self.paths, "custom", source)
            self.assertTrue(any("fetch" in call.args[0] and "a" * 40 in call.args[0] for call in calls.call_args_list))
            calls.reset_mock()
            music.build_backend(self.paths, "custom", source)
            calls.assert_not_called()
        self.assertEqual(self.paths.binary("custom").read_text(), "fake compiled executable")

    def test_manual_auth_fallback_is_not_overwritten_by_browser_refresh(self):
        (self.root / "backends.json").write_text(json.dumps({"custom":{"commit":"a" * 40}}))
        with patch.object(music, "ROOT", self.root), patch.object(music, "own_window", return_value=None), \
             patch.object(music.shutil, "which", return_value="/usr/bin/test"), \
             patch.object(music, "choose", side_effect=[0, 0]), \
             patch.object(music, "confirm", side_effect=[True, False, True, False]), \
             patch.object(music, "build_backend"), patch.object(music, "update_desktop"), \
             patch.object(music, "run", side_effect=[subprocess.CalledProcessError(1, ["auth"]), subprocess.CompletedProcess([], 0)]):
            music.setup(self.paths)
        state = music.load_settings(self.paths)
        self.assertEqual(state["browser"], "manual")
        self.assertFalse(state["auto_refresh"])

    def test_failed_build_preserves_previous_binary(self):
        self.settings()
        source = {"repository": "https://github.com/lisim/ytmusic-tui.git", "commit": "b" * 40}
        with patch.object(music, "run", side_effect=subprocess.CalledProcessError(1, ["git"])):
            with self.assertRaises(subprocess.CalledProcessError):
                music.build_backend(self.paths, "custom", source)
        self.assertEqual(self.paths.binary("custom").read_text(), "fake")

    def test_hide_restore_and_offscreen_focus_never_show_overlay(self):
        for name, wid, expected in [("1", 1, music.PARKING), (music.PARKING, -98, 'workspace="3"'), ("4", 4, "focus")]:
            window = {"address": "0x123", "workspace": {"name": name, "id": wid}}
            def query(command):
                return {"activeworkspace": {"id": 3}, "monitors": [{"activeWorkspace": {"id": 1}}]}[command]
            with patch.object(music, "own_window", return_value=window), patch.object(music, "hypr_json", side_effect=query), patch.object(music, "run") as calls:
                music.toggle(self.paths)
            actions = " ".join(str(call.args[0]) for call in calls.call_args_list)
            self.assertIn(expected, actions)
            self.assertNotIn("toggle_special", actions)

    def test_unconfigured_click_opens_setup(self):
        with patch.object(music, "own_window", return_value=None), patch.object(music, "configure") as setup:
            music.toggle(self.paths)
        setup.assert_called_once()

    def test_uninstall_keeps_upstream_and_retains_custom_auth_by_default(self):
        self.settings()
        original = self.paths.auth("original")
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text("dummy-original-session")
        custom = self.paths.auth("custom")
        custom.parent.mkdir(parents=True, exist_ok=True)
        custom.write_text("dummy-custom-session")
        with patch.object(music, "own_window", return_value=None), patch.object(music, "confirm", return_value=True), patch.object(music, "update_desktop"):
            music.uninstall(self.paths)
        self.assertFalse(self.paths.data.exists())
        self.assertTrue(custom.exists())
        self.assertEqual(original.read_text(), "dummy-original-session")

    def test_purge_removes_custom_auth_but_not_original(self):
        self.settings()
        original = self.paths.auth("original")
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text("dummy-original")
        with patch.object(music, "own_window", return_value=None), patch.object(music, "confirm", return_value=True), patch.object(music, "update_desktop"):
            music.uninstall(self.paths, purge=True)
        self.assertFalse(self.paths.config.exists())
        self.assertEqual(original.read_text(), "dummy-original")

    def test_cleanup_refuses_symlink_before_changing_desktop(self):
        foreign = self.root / "unrelated"
        foreign.mkdir()
        self.paths.data.parent.mkdir(parents=True, exist_ok=True)
        self.paths.data.symlink_to(foreign)
        with patch.object(music, "own_window", return_value=None), patch.object(music, "confirm", return_value=True), patch.object(music, "update_desktop") as desktop:
            with self.assertRaises(ValueError):
                music.uninstall(self.paths)
            desktop.assert_not_called()
        self.assertTrue(foreign.is_dir())

    def test_invalid_refresh_preference_is_rejected(self):
        music.atomic_write(self.paths.settings, json.dumps({"backend":"custom", "browser":"chrome", "auto_refresh":"yes"}))
        with self.assertRaises(ValueError):
            music.load_settings(self.paths)


if __name__ == "__main__":
    unittest.main()
