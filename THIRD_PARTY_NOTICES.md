# Third-party notices

The plugin is MIT licensed. Its now-playing widget derives from Omarchy's `shell/plugins/services/media/BarWidget.qml`; the original copyright notice for David Heinemeier Hansson remains in [LICENSE](LICENSE). The plugin also uses installed Omarchy UI components under their upstream licence; it does not bundle them.

The player is separate software:

- [WakaTaira/ytmusic-tui](https://github.com/WakaTaira/ytmusic-tui): MIT, copyright © 2026 WakaTaira.
- [lisim/ytmusic-tui](https://github.com/lisim/ytmusic-tui): customised fork retaining the original MIT notice and upstream history.

No player executable is included in this repository. Setup installs only lisim's customised fork, checking out the exact source revision in `backends.json` and building locally. Cargo dependencies and system packages (including libmpv/mpv, Qt/Quickshell, FFmpeg and yt-dlp) retain their respective licences. See the fork's [dependency note](https://github.com/lisim/ytmusic-tui/blob/omarchy/DEPENDENCIES.md) before redistributing a compiled player. Source licence declarations are not a claim that every linked dependency is MIT.

This plugin is independent of Google/YouTube, Omarchy and the upstream TUI author.
