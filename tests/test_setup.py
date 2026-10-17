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
             patch.object(music, "confirm", side_effect=[True, True, False, True, False]), \
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

    def test_declining_cookie_consent_never_reads_browser_or_builds(self):
        with patch.object(music, "own_window", return_value=None), \
             patch.object(music.shutil, "which", return_value="/usr/bin/test"), \
             patch.object(music, "choose", side_effect=[0, 0]), \
             patch.object(music, "confirm", return_value=False), \
             patch.object(music, "build_backend") as build, patch.object(music, "run") as run:
            with self.assertRaisesRegex(ValueError, "no cookies were read"):
                music.setup(self.paths)
        build.assert_not_called()
        run.assert_not_called()
        self.assertFalse(self.paths.settings.exists())

    def test_refresh_requires_saved_opt_in_and_ignores_inherited_environment(self):
        with patch.dict(music.os.environ, {"YTMUSIC_TUI_AUTH_BROWSER": "firefox"}):
            for backend, browser, enabled in [("custom", "chrome", True), ("custom", "chrome", False),
                                              ("custom", "manual", True), ("custom", "later", True),
                                              ("original", "chrome", True)]:
                state = {"backend": backend, "browser": browser, "auto_refresh": enabled}
                env = music.player_env(self.paths, backend, state)
                self.assertEqual(env.get("YTMUSIC_TUI_AUTH_BROWSER"),
                                 "chrome" if backend == "custom" and browser == "chrome" and enabled else None)
            self.assertNotIn("YTMUSIC_TUI_AUTH_BROWSER", music.player_env(self.paths, "custom"))

    def test_play_and_rating_share_the_selected_refresh_browser(self):
        self.settings()
        state = {"backend": "custom", "browser": "chrome", "auto_refresh": True}
        music.atomic_write(self.paths.settings, json.dumps(state))
        with patch.object(music.os, "execve") as execute:
            music.play(self.paths)
        with patch.object(music.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as request:
            music.rating(self.paths, "get", "test-song")
        self.assertEqual(execute.call_args.args[2]["YTMUSIC_TUI_AUTH_BROWSER"], "chrome")
        self.assertEqual(request.call_args.kwargs["env"]["YTMUSIC_TUI_AUTH_BROWSER"], "chrome")

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

    def test_start_play_launches_with_autoplay_request(self):
        self.settings()
        with patch.object(music, "own_window", return_value=None), \
             patch.object(music.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)), \
             patch.object(music, "launch_terminal") as launch:
            music.toggle(self.paths, autoplay=True)
        self.assertEqual(launch.call_args.args[0][-2:], ["play", "--autoplay"])

    def test_start_play_does_not_hide_a_window_that_is_still_starting(self):
        window = {"address": "0x123", "workspace": {"name": "1", "id": 1}}
        with patch.object(music, "own_window", return_value=window), patch.object(music, "run") as calls:
            music.toggle(self.paths, autoplay=True)
        self.assertEqual(len(calls.call_args_list), 1)
        self.assertIn("focus", str(calls.call_args.args[0]))

    def test_autoplay_flag_only_reaches_customised_player(self):
        for mode in ("custom", "original"):
            self.settings(mode)
            with patch.object(music.os, "execve") as execute:
                music.play(self.paths, autoplay=True)
            expected = [str(self.paths.binary(mode)), *(["--autoplay"] if mode == "custom" else [])]
            self.assertEqual(execute.call_args.args[1], expected)

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

    def test_uninstall_preserves_other_players_in_shared_legacy_directories(self):
        for use_xdg in (False, True):
            for purge in (False, True):
                with self.subTest(xdg=use_xdg, purge=purge), tempfile.TemporaryDirectory() as directory:
                    home = Path(directory)
                    roots = {"XDG_CONFIG_HOME": home / "config", "XDG_DATA_HOME": home / "data",
                             "XDG_CACHE_HOME": home / "cache"} if use_xdg else {}
                    paths = music.Paths({k: str(v) for k, v in roots.items()}, user_home=home)
                    foreign = {
                        roots.get("XDG_CONFIG_HOME", home / ".config") / "omarchy-ytmusic/browser.json": b"dummy-damir-auth",
                        roots.get("XDG_CACHE_HOME", home / ".cache") / "omarchy-ytmusic/session.json": b"dummy-damir-queue",
                        roots.get("XDG_DATA_HOME", home / ".local/share") / "omarchy-ytmusic/venv/foreign-runtime": b"dummy-pradeep-runtime",
                    }
                    for path, content in foreign.items():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(content)
                    for owned in (paths.config, paths.data, paths.cache):
                        owned.mkdir(parents=True, exist_ok=True)
                        (owned / "owned-sentinel").write_text("ours")
                    with patch.object(music, "own_window", return_value=None), \
                         patch.object(music, "confirm", return_value=True), patch.object(music, "update_desktop"):
                        music.uninstall(paths, purge=purge)
                    for path, content in foreign.items():
                        self.assertTrue(path.is_file(), f"Removed another player's file: {path}")
                        self.assertEqual(path.read_bytes(), content)
                    self.assertFalse(paths.data.exists())
                    self.assertFalse(paths.cache.exists())
                    self.assertEqual(paths.config.exists(), not purge)

    def test_legacy_shared_settings_do_not_configure_new_install(self):
        legacy = self.root / ".config/omarchy-ytmusic/settings.json"
        legacy.parent.mkdir(parents=True)
        content = '{"backend":"custom","browser":"later","auto_refresh":false}'
        legacy.write_text(content)
        self.assertIsNone(music.load_settings(self.paths))
        with patch.object(music, "own_window", return_value=None), patch.object(music, "configure") as setup:
            music.toggle(self.paths)
        setup.assert_called_once()
        self.assertEqual(legacy.read_text(), content)

    def test_invalid_refresh_preference_is_rejected(self):
        music.atomic_write(self.paths.settings, json.dumps({"backend":"custom", "browser":"chrome", "auto_refresh":"yes"}))
        with self.assertRaises(ValueError):
            music.load_settings(self.paths)

    def test_ratings_use_selected_custom_account_and_exact_track(self):
        self.settings()
        with patch.object(music.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as execute:
            self.assertEqual(music.rating(self.paths, "DISLIKE", "video_123-45"), 0)
        self.assertEqual(execute.call_args.args[0], [str(self.paths.binary("custom")), "rating", "DISLIKE", "video_123-45"])
        self.assertEqual(execute.call_args.kwargs["env"]["YTMUSIC_TUI_CONFIG_DIR"], str(self.paths.config / "custom-tui"))

    def test_ratings_reject_original_mode_and_invalid_input_before_execution(self):
        self.settings("original")
        with patch.object(music.subprocess, "run") as execute:
            for action, video in [("LIKE", "video"), ("DELETE", "video"), ("LIKE", "../file")]:
                with self.assertRaises(ValueError):
                    music.rating(self.paths, action, video)
            execute.assert_not_called()

    def test_rating_cli_accepts_a_video_id_starting_with_a_dash(self):
        result = subprocess.run([music.sys.executable, music.__file__, "rating", "--", "LIKE", "-video"],
                                env=dict(music.os.environ, XDG_CONFIG_HOME=str(self.root)), capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("require the customised player", result.stderr)


if __name__ == "__main__":
    unittest.main()
