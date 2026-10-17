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
    for module in ("Ui", "Commons"):
        (target / module).symlink_to(Path("/usr/share/omarchy/shell") / module)
    config = target / "config/omarchy-ytmusic"
    config.mkdir(parents=True)
    (config / "settings.json").write_text('{"backend":"custom","browser":"later"}')
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(target / "config"))
    env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(["quickshell", "-p", str(target), "--no-color"],
                            env=env, capture_output=True, text=True, timeout=12, check=True)
    output = result.stdout + result.stderr
    assert "PASS: actual widget" in output, output
    assert "TypeError" not in output and "ReferenceError" not in output, output
    print("PASS: real panel loads; music-only volume, clamping and queue parsing")
    (config / "settings.json").unlink()
    result = subprocess.run(["quickshell", "-p", str(target), "--no-color"],
                            env=dict(env, TEST_FIRST_RUN="1"), capture_output=True, text=True, timeout=12, check=True)
    output = result.stdout + result.stderr
    assert "PASS: actual widget" in output, output
    print("PASS: settings created during first-run setup are detected without a shell restart")
