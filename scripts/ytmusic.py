#!/usr/bin/env python3
"""First-run setup and window control for the Omarchy YouTube Music plugin."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ID = "lisim.ytmusic"
APP_ID = "lisim-ytmusic"
PARKING = "special:lisim-ytmusic-hidden"
BEGIN = "-- BEGIN lisim.ytmusic"
END = "-- END lisim.ytmusic"
BROWSERS = ("chrome", "chromium", "brave", "firefox", "librewolf", "zen", "edge", "vivaldi", "opera", "manual", "later")


class Paths:
    def __init__(self, env=None, user_home=None):
        env = os.environ if env is None else env
        self.user_home = Path.home() if user_home is None else Path(user_home)
        self.config_root = Path(env.get("XDG_CONFIG_HOME") or self.user_home / ".config")
        self.config = self.config_root / "lisim-ytmusic"
        self.data = Path(env.get("XDG_DATA_HOME") or self.user_home / ".local/share") / "lisim-ytmusic"
        self.cache = Path(env.get("XDG_CACHE_HOME") or self.user_home / ".cache") / "lisim-ytmusic"
        self.runtime = Path(env["XDG_RUNTIME_DIR"]) if env.get("XDG_RUNTIME_DIR") else None
        self.settings = self.config / "settings.json"
        self.bindings = self.config_root / "hypr/bindings.lua"

    def binary(self, backend):
        if backend not in ("custom", "original"):
            raise ValueError("Unknown player choice")
        return self.data / backend / "bin/ytmusic-tui"

    def auth(self, backend):
        directory = self.config / "custom-tui" if backend == "custom" else self.user_home / ".config/ytmusic-tui"
        return directory / "browser.json"


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, timeout=kwargs.pop("timeout", 30), **kwargs)


def atomic_write(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        os.chmod(temporary, mode)
        file.write(content.encode())
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_settings(paths):
    if not paths.settings.exists():
        return None
    state = json.loads(paths.settings.read_text())
    if state.get("backend") not in ("custom", "original") or state.get("browser") not in BROWSERS:
        raise ValueError("Invalid saved setup. Run the setup command again.")
    if not isinstance(state.get("auto_refresh", False), bool):
        raise ValueError("Invalid automatic sign-in preference. Run setup again.")
    return state


def player_env(paths, backend):
    env = dict(os.environ)
    env.pop("NO_COLOR", None)
    env.pop("YTMUSIC_TUI_CONFIG_DIR", None)
    if backend == "custom":
        env["YTMUSIC_TUI_CONFIG_DIR"] = str(paths.config / "custom-tui")
    return env


def hypr_json(command):
    return json.loads(run(["hyprctl", command, "-j"], capture_output=True, text=True, timeout=5).stdout)


def own_window():
    return next((c for c in hypr_json("clients") if c["class"] == APP_ID), None)


def launch_terminal(command, app_id):
    subprocess.Popen(["omarchy", "launch", "tui", "--app-id=" + app_id, *map(str, command)],
                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if any(c["class"] == app_id for c in hypr_json("clients")):
            return
        time.sleep(0.1)
    raise ValueError("The player/setup terminal did not appear within 5 seconds.")


def toggle(paths):
    if paths.runtime is None:
        raise ValueError("Open this from your Omarchy desktop session.")
    with (paths.runtime / "lisim-ytmusic-launch.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        window = own_window()
        if window:
            address = window["address"]
            if not re.fullmatch(r"0x[0-9a-fA-F]+", address):
                raise ValueError("Invalid window address")
            selector = '"address:' + address + '"'
            if window["workspace"]["name"] == PARKING:
                target = hypr_json("activeworkspace")["id"]
                if not isinstance(target, int) or target <= 0:
                    raise ValueError("Select a normal workspace first.")
                run(["hyprctl", "dispatch", f'hl.dsp.window.move({{window={selector}, workspace="{target}", follow=false}})'], stdout=subprocess.DEVNULL)
            elif any(m["activeWorkspace"]["id"] == window["workspace"]["id"] for m in hypr_json("monitors")):
                run(["hyprctl", "dispatch", f'hl.dsp.window.move({{window={selector}, workspace="{PARKING}", follow=false}})'], stdout=subprocess.DEVNULL)
                return
            run(["hyprctl", "dispatch", f'hl.dsp.focus({{window={selector}}})'], stdout=subprocess.DEVNULL)
            return
        state = load_settings(paths)
        if not state or not paths.binary(state["backend"]).is_file():
            configure()
            return
        # MPRIS has a single name: do not start a second, unrelated player.
        bus = subprocess.run(["busctl", "--user", "--timeout=2", "get-property",
                              "org.mpris.MediaPlayer2.ytmusic_tui", "/org/mpris/MediaPlayer2",
                              "org.mpris.MediaPlayer2", "Identity"], capture_output=True, timeout=5)
        if bus.returncode == 0:
            launch_terminal([sys.executable, __file__, "running-message"], APP_ID + "-notice")
            return
        launch_terminal([sys.executable, __file__, "play"], APP_ID)


def configure():
    if not any(c["class"] == APP_ID + "-setup" for c in hypr_json("clients")):
        launch_terminal([sys.executable, __file__, "setup"], APP_ID + "-setup")


def choose(prompt, options, default=0):
    print("\n" + prompt)
    for i, label in enumerate(options, 1):
        print(f"  {i}. {label}")
    while True:
        value = input(f"Choice [{default + 1}]: ").strip()
        if not value:
            return default
        if value.isdigit() and 1 <= int(value) <= len(options):
            return int(value) - 1
        print("Enter one of the numbers above.")


def confirm(prompt, default=False):
    reply = input(prompt + (" [Y/n]: " if default else " [y/N]: ")).strip().lower()
    return default if not reply else reply in ("y", "yes")


def build_backend(paths, backend, spec):
    if not re.fullmatch(r"[0-9a-f]{40}", spec["commit"]):
        raise ValueError("Invalid pinned source revision")
    allowed = {"https://github.com/lisim/ytmusic-tui.git", "https://github.com/WakaTaira/ytmusic-tui.git"}
    if spec["repository"] not in allowed:
        raise ValueError("Unexpected source repository")
    binary = paths.binary(backend)
    receipt = binary.parent / "source.json"
    if binary.exists() and receipt.exists() and json.loads(receipt.read_text()).get("commit") == spec["commit"]:
        print("This player version is already built.")
        return
    paths.cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="source-", dir=paths.cache) as directory:
        source = Path(directory)
        run(["git", "init", "--quiet", source])
        run(["git", "-C", source, "remote", "add", "origin", spec["repository"]])
        run(["git", "-C", source, "fetch", "--quiet", "--depth=1", "origin", spec["commit"]], timeout=120)
        run(["git", "-C", source, "checkout", "--quiet", "--detach", "FETCH_HEAD"])
        revision = run(["git", "-C", source, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if revision != spec["commit"]:
            raise ValueError("Source revision did not match the release pin")
        env = dict(os.environ, CARGO_TARGET_DIR=str(paths.cache / "target" / backend))
        run(["cargo", "build", "--release", "--locked", "-p", "ytmusic-tui", "-j", "2"], cwd=source, env=env, timeout=1800)
        binary.parent.mkdir(parents=True, exist_ok=True)
        temporary = binary.with_suffix(".new")
        shutil.copy2(paths.cache / "target" / backend / "release/ytmusic-tui", temporary)
        temporary.chmod(0o755)
        temporary.replace(binary)
        atomic_write(receipt, json.dumps(spec, indent=2) + "\n")


def strip_desktop_block(text):
    if BEGIN not in text and END not in text:
        return text
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("Desktop rules have duplicate/incomplete plugin markers; no file changed.")
    start = text.index(BEGIN)
    end = text.index(END, start) + len(END)
    if end < len(text) and text[end] == "\n":
        end += 1
    return text[:start] + text[end:]


def desktop_block(shortcut):
    lines = [BEGIN]
    if shortcut:
        command = shlex.join([sys.executable, str(Path(__file__).resolve()), "toggle"])
        lines += ['hl.unbind("SUPER + SHIFT + M")',
                  'o.bind("SUPER + SHIFT + M", "YouTube Music TUI (lisim)", ' + json.dumps(command, ensure_ascii=False) + ')']
    lines += ['o.window({ class = "^lisim-ytmusic$" }, { float = true, center = true, size = { "monitor_w * 0.75", "monitor_h * 0.75" } })', END]
    return "\n".join(lines) + "\n"


def update_desktop(paths, shortcut=None):
    if not paths.bindings.is_file():
        raise ValueError("Omarchy's ~/.config/hypr/bindings.lua was not found.")
    target = paths.bindings.resolve()
    previous = target.read_text()
    content = strip_desktop_block(previous)
    if shortcut is not None:
        content += ("" if not content or content.endswith("\n") else "\n") + desktop_block(shortcut)
    if content == previous:
        return
    backup = paths.config / "bindings-before-setup.lua"
    if not backup.exists():
        atomic_write(backup, previous)
    mode = target.stat().st_mode & 0o777
    atomic_write(target, content, mode)
    try:
        run(["hyprctl", "reload"], stdout=subprocess.DEVNULL)
        errors = run(["hyprctl", "configerrors"], capture_output=True, text=True).stdout.strip()
        if errors:
            raise ValueError("Hyprland rejected the desktop rule")
    except Exception:
        atomic_write(target, previous, mode)
        run(["hyprctl", "reload"], stdout=subprocess.DEVNULL)
        raise


def setup(paths):
    print("YouTube Music TUI (lisim)\n")
    print("Builds a pinned player from source. No prebuilt executable is downloaded.")
    print("First build: usually 2–10 minutes. Existing upstream settings are preserved.")
    if own_window():
        raise ValueError("Close the music window with Q before changing its setup.")
    missing = [tool for tool in ("git", "cargo", "cc", "pkg-config", "mpv", "yt-dlp", "omarchy", "hyprctl") if not shutil.which(tool)]
    if missing:
        print("Missing: " + ", ".join(missing))
        raise ValueError("Install prerequisites: omarchy pkg add rustup base-devel mpv yt-dlp")
    backend = ("custom", "original")[choose("Choose your player", [
        "Customised (recommended): helper, Home cards/mixes, terminal colours, volume and Up Next",
        "Original upstream: basic controls; no custom helper, panel volume or Up Next"])]
    print("\nBrowser sign-in reads that browser's YouTube session locally and sends it only to YouTube.")
    browser = BROWSERS[choose("Which browser is signed into YouTube Music?", list(BROWSERS), 0)]
    refresh = browser not in ("manual", "later") and backend == "custom" and confirm("Refresh YouTube sign-in from this browser on future launches?", True)
    shortcut = confirm("Use Super+Shift+M for show/hide? This replaces its current Music shortcut.")
    specs = json.loads((ROOT / "backends.json").read_text())
    paths.config.mkdir(parents=True, exist_ok=True, mode=0o700)
    build_backend(paths, backend, specs[backend])
    if backend == "custom":
        config = paths.config / "custom-tui/config.toml"
        if not config.exists():
            atomic_write(config, '[player]\nvolume = 40\naudio_quality = "high"\n\n[ui]\ntheme = "terminal"\n')
    if browser != "later":
        command = [paths.binary(backend), "auth"]
        if browser != "manual":
            command += ["--from-browser", browser]
        try:
            run(command, env=player_env(paths, backend), timeout=600 if browser == "manual" else 45)
        except subprocess.CalledProcessError:
            if browser == "manual" or not confirm("Browser sign-in failed. Use the upstream manual header-paste method now?"):
                raise ValueError("Sign-in was not completed. Run setup again to retry.")
            run([paths.binary(backend), "auth"], env=player_env(paths, backend), timeout=600)
            browser, refresh = "manual", False
    update_desktop(paths, shortcut)
    state = {"backend": backend, "browser": browser, "auto_refresh": refresh, "shortcut": shortcut, "commit": specs[backend]["commit"]}
    atomic_write(paths.settings, json.dumps(state, indent=2) + "\n")
    print("\nReady. Left-click the bar to open/hide; right-click for controls; middle-click to play/pause.")
    if confirm("Open the player now?", True):
        toggle(paths)


def play(paths):
    state = load_settings(paths)
    if not state:
        raise ValueError("Run setup first.")
    backend = state["backend"]
    binary = paths.binary(backend)
    env = player_env(paths, backend)
    if state.get("auto_refresh") and state["browser"] not in ("manual", "later"):
        try:
            run([binary, "auth", "--from-browser", state["browser"]], env=env, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print("Browser refresh failed; trying the saved session.")
    os.execve(binary, [str(binary)], env)


def uninstall(paths, purge=False):
    if own_window():
        raise ValueError("Close the music window with Q before removing the plugin.")
    if not confirm("Remove this plugin's player builds and desktop rules?" + (" Custom sign-in will also be deleted." if purge else " Saved sign-in will be kept.")):
        return
    owned_paths = (paths.data, paths.cache, *([paths.config] if purge else []))
    for path in owned_paths:
        if path.name != "lisim-ytmusic" or path.is_symlink():
            raise ValueError("Refusing an unexpected cleanup path")
    update_desktop(paths)
    for path in owned_paths:
        if path.exists():
            shutil.rmtree(path)
    installed = paths.config_root / "omarchy/plugins" / PLUGIN_ID
    if installed.exists():
        run(["omarchy", "plugin", "remove", PLUGIN_ID, "--yes"])
    print("Removed plugin-owned files. Original upstream config and shared system packages were kept.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("toggle", "configure", "setup", "play", "uninstall", "running-message"))
    parser.add_argument("--purge", action="store_true", help="Also delete custom settings/sign-in during uninstall")
    args = parser.parse_args()
    paths = Paths()
    os.umask(0o077)
    try:
        if args.action == "toggle": toggle(paths)
        elif args.action == "configure": configure()
        elif args.action == "setup": setup(paths)
        elif args.action == "play": play(paths)
        elif args.action == "uninstall": uninstall(paths, args.purge)
        else:
            print("A YouTube Music TUI is already running outside this plugin. Close it before launching another.")
            input("Press Enter to close this message.")
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"YouTube Music: {error}", file=sys.stderr)
        if sys.stdin.isatty(): input("Press Enter to close.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
