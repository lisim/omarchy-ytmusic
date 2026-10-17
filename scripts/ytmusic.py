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
import tomllib

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
        if backend != "custom":
            raise ValueError("Original is no longer supported. Run Player setup to migrate.")
        return self.data / backend / "bin/ytmusic-tui"

    def auth(self):
        return self.config / "custom-tui/browser.json"


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


def player_env(paths, backend, state=None):
    paths.binary(backend)  # Reject legacy backends before constructing any auth command.
    env = dict(os.environ)
    env.pop("NO_COLOR", None)
    env.pop("YTMUSIC_TUI_CONFIG_DIR", None)
    env.pop("YTMUSIC_TUI_AUTH_BROWSER", None)
    check_auth_path(paths)
    env["YTMUSIC_TUI_CONFIG_DIR"] = str(paths.config / "custom-tui")
    if state and state.get("auto_refresh") and state["browser"] not in ("manual", "later"):
        env["YTMUSIC_TUI_AUTH_BROWSER"] = state["browser"]
    return env


def check_auth_path(paths):
    # An old override or symlink must not reconnect the fork to Original's cookies.
    auth = paths.auth()
    config = auth.parent / "config.toml"
    if auth.parent.is_symlink() or auth.is_symlink() or config.is_symlink():
        raise ValueError("Player setup requires regular files in custom-tui; remove its symlink before continuing.")
    if config.exists():
        override = tomllib.loads(config.read_text()).get("auth", {}).get("browser_auth_path")
        if override is not None and Path(override).expanduser().resolve() != auth.resolve():
            raise ValueError("Remove the browser_auth_path override from custom-tui/config.toml; this plugin uses only its own browser.json.")


def player_ready(paths, state):
    if not state or state["backend"] != "custom" or state.get("auth_pending"):
        return False
    binary = paths.binary("custom")
    try:
        spec = json.loads((ROOT / "backends.json").read_text())["custom"]
        receipt = json.loads((binary.parent / "source.json").read_text())
        return binary.is_file() and receipt == spec and state.get("commit") == spec["commit"]
    except (OSError, ValueError, KeyError):
        return False


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


def toggle(paths, autoplay=False):
    if paths.runtime is None:
        raise ValueError("Open this from your Omarchy desktop session.")
    with (paths.runtime / "lisim-ytmusic-launch.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        state = load_settings(paths)
        if not player_ready(paths, state):
            configure()
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
            elif not autoplay and any(m["activeWorkspace"]["id"] == window["workspace"]["id"] for m in hypr_json("monitors")):
                run(["hyprctl", "dispatch", f'hl.dsp.window.move({{window={selector}, workspace="{PARKING}", follow=false}})'], stdout=subprocess.DEVNULL)
                return
            run(["hyprctl", "dispatch", f'hl.dsp.focus({{window={selector}}})'], stdout=subprocess.DEVNULL)
            return
        # MPRIS has a single name: do not start a second, unrelated player.
        bus = subprocess.run(["busctl", "--user", "--timeout=2", "get-property",
                              "org.mpris.MediaPlayer2.ytmusic_tui", "/org/mpris/MediaPlayer2",
                              "org.mpris.MediaPlayer2", "Identity"], capture_output=True, timeout=5)
        if bus.returncode == 0:
            launch_terminal([sys.executable, __file__, "running-message"], APP_ID + "-notice")
            return
        launch_terminal([sys.executable, __file__, "play", *(["--autoplay"] if autoplay else [])], APP_ID)


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
    if spec["repository"] != "https://github.com/lisim/ytmusic-tui.git":
        raise ValueError("Unexpected source repository")
    binary = paths.binary(backend)
    receipt = binary.parent / "source.json"
    try:
        installed = json.loads(receipt.read_text())
    except (OSError, ValueError):
        installed = None
    if binary.exists() and installed == spec:
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
    backend = "custom"
    previous = load_settings(paths)
    migrating = previous is not None and not player_ready(paths, previous)
    print("Installs lisim's customised fork of WakaTaira's ytmusic-tui, including stricter cookie-domain filtering.")
    if migrating:
        print("This installation needs the current fork and fresh sign-in. Original is no longer supported; old cookies are not imported or reused for migration.")
    check_auth_path(paths)
    print("\nAUTHENTICATION: this player uses YouTube session cookies, not Google OAuth.")
    print("Browser selection reads its local cookie store and copies YouTube cookies to browser.json.")
    print("Manual sign-in avoids reading the browser store, but still saves cookies you paste.")
    print("The local file is plaintext: treat it like a password. The player sends auth to YouTube, not the plugin author.")
    print("Fresh sign-in is required for this migration." if migrating else "Choose 'later' to skip importing cookies. Existing saved sign-in is kept.")
    browser = BROWSERS[choose("Which browser is signed into YouTube Music?", list(BROWSERS), 0)]
    if migrating and browser == "later":
        raise ValueError("Migration requires fresh sign-in. Old builds remain disabled; saved files are untouched.")
    if browser != "later" and not confirm("Allow copying YouTube session cookies for this player?", False):
        raise ValueError("Sign-in cancelled; no cookies were read. Migration stays disabled until fresh sign-in." if migrating else "Sign-in cancelled; no cookies were read. Run setup and choose 'later' to skip sign-in.")
    refresh = browser not in ("manual", "later") and confirm("Allow re-reading this browser's YouTube cookies when the session expires (including while playing or using ratings)?", False)
    shortcut = confirm("Use Super+Shift+M for show/hide? This replaces its current Music shortcut.")
    specs = json.loads((ROOT / "backends.json").read_text())
    paths.config.mkdir(parents=True, exist_ok=True, mode=0o700)
    if migrating and previous["backend"] == "custom":
        # Building can finish before auth fails; keep every retry blocked until sign-in succeeds.
        atomic_write(paths.settings, json.dumps(dict(previous, auth_pending=True), indent=2) + "\n")
    build_backend(paths, backend, specs[backend])
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
            if browser == "manual" or not confirm("Browser sign-in failed. Paste fresh YouTube request headers manually now?"):
                raise ValueError("Sign-in was not completed. Run setup again to retry.")
            run([paths.binary(backend), "auth"], env=player_env(paths, backend), timeout=600)
            browser, refresh = "manual", False
    update_desktop(paths, shortcut)
    state = {"backend": backend, "browser": browser, "auto_refresh": refresh, "shortcut": shortcut, "commit": specs[backend]["commit"]}
    atomic_write(paths.settings, json.dumps(state, indent=2) + "\n")
    print("\nReady. Left-click the bar to open/hide; right-click for controls; middle-click to play/pause.")
    if confirm("Open the player now?", True):
        toggle(paths)


def play(paths, autoplay=False):
    state = load_settings(paths)
    if not player_ready(paths, state):
        raise ValueError("Run Player setup to install the current customised player. Original is no longer supported.")
    backend = state["backend"]
    binary = paths.binary(backend)
    env = player_env(paths, backend, state)
    args = [str(binary)]
    if autoplay:
        args.append("--autoplay")
    os.execve(binary, args, env)


def rating(paths, action, video_id):
    if action not in ("get", "LIKE", "DISLIKE", "INDIFFERENT") or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", video_id):
        raise ValueError("Invalid rating action or video ID")
    state = load_settings(paths)
    if not player_ready(paths, state):
        raise ValueError("Rating controls require the current customised player. Run Player setup.")
    return subprocess.run([str(paths.binary("custom")), "rating", action, video_id],
                          env=player_env(paths, "custom", state), timeout=65).returncode


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
    parser.add_argument("action", choices=("toggle", "start-play", "configure", "setup", "play", "rating", "uninstall", "running-message"))
    parser.add_argument("rating_args", nargs="*")
    parser.add_argument("--autoplay", action="store_true", help="Start a recommendation with the customised player")
    parser.add_argument("--purge", action="store_true", help="Also delete custom settings/sign-in during uninstall")
    args = parser.parse_args()
    if (args.action == "rating" and len(args.rating_args) != 2) or (args.action != "rating" and args.rating_args):
        parser.error("rating takes an action and video ID; other actions take no positional arguments")
    paths = Paths()
    os.umask(0o077)
    try:
        if args.action == "toggle": toggle(paths)
        elif args.action == "start-play": toggle(paths, autoplay=True)
        elif args.action == "configure": configure()
        elif args.action == "setup": setup(paths)
        elif args.action == "play": play(paths, autoplay=args.autoplay)
        elif args.action == "rating": return rating(paths, *args.rating_args)
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
