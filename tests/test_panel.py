"""Load the real panel with fake players; never touch live audio."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="music-panel-test-") as directory:
    target = Path(directory)
    shutil.copy2(root / "panel.qml", target / "shell.qml")
    shutil.copy2(root.parent / "MusicWidget.qml", target / "MusicWidget.qml")
    shutil.copy2(root.parent / "music.svg", target / "music.svg")
    shutil.copy2(root.parent / "RatingControls.qml", target / "RatingControls.qml")
    (target / "scripts").mkdir()
    (target / "scripts/ytmusic.py").write_text('''import json, sys, time
from pathlib import Path
args = sys.argv[2:]
if args[0] == "--": args = args[1:]
action, video = args
path = Path(__file__).with_name("ratings.json")
states = json.loads(path.read_text()) if path.exists() else {"song-one": "LIKE", "slow-song": "LIKE", "new-song": "DISLIKE", "mutation-failure": "DISLIKE"}
if video == "slow-song": time.sleep(0.2)
if video == "failure" or (video == "mutation-failure" and action != "get"):
    print("Test network failure", file=sys.stderr)
    raise SystemExit(1)
if action != "get":
    states[video] = action
    path.write_text(json.dumps(states))
print(json.dumps({"video_id": video, "status": states.get(video, "INDIFFERENT")}))
''')
    for module in ("Ui", "Commons"):
        (target / module).symlink_to(Path("/usr/share/omarchy/shell") / module)
    config = target / "config/lisim-ytmusic"
    config.mkdir(parents=True)
    (config / "settings.json").write_text('{"backend":"custom","browser":"later"}')
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(target / "config"))
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(target), "--no-color"],
                            env=env, capture_output=True, text=True, timeout=12, check=True)
    output = result.stdout + result.stderr
    assert "PASS: actual widget" in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS: real panel loads; volume, queue, SVG icons and ratings (toggle, pending, stale response, failure)")
    (config / "settings.json").unlink()
    (target / "scripts/ratings.json").unlink(missing_ok=True)
    result = subprocess.run(["quickshell", "-p", str(target), "--no-color"],
                            env=dict(env, TEST_FIRST_RUN="1"), capture_output=True, text=True, timeout=12, check=True)
    output = result.stdout + result.stderr
    assert "PASS: actual widget" in output, output
    print("PASS: settings created during first-run setup are detected without a shell restart")
