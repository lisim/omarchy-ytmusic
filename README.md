# YouTube Music TUI (lisim)

Omarchy bar integration for [WakaTaira's ytmusic-tui](https://github.com/WakaTaira/ytmusic-tui), with a choice of the original player or lisim's customised fork. The floating terminal player can be hidden while music keeps playing.

![Home cards — sample content](preview.png)

## Install

Requires **Omarchy 4 with its Quickshell plugin system and Lua Hyprland configuration**. The runtime targets the interfaces tested on Omarchy/Quickshell 0.3.1; older Waybar setups are not supported.

```sh
omarchy plugin add https://github.com/lisim/omarchy-ytmusic.git --enable
```

Click the new bar item to open first-run setup. It will:

1. Offer **Customised** (recommended) or **Original upstream**.
2. Ask which browser is signed into YouTube Music (or offer manual sign-in / setup later).
3. Build the selected player from the pinned source revision in `backends.json`.
4. Add the floating-window rule and optionally bind **Super+Shift+M**.

First build usually takes **2–10 minutes**. Setup never installs system packages or runs sudo automatically. If prerequisites are missing:

```sh
omarchy pkg add rustup base-devel mpv yt-dlp
rustup toolchain install stable
```

On a fresh Omarchy installation, complete its normal `omarchy update` first so package databases and the system are ready for additional packages.

The plugin install command only clones/enables files. Source building and account setup happen after you explicitly open first-run setup.

## Choose your player

| | Customised | Original upstream |
| --- | --- | --- |
| Play/pause, previous/next, show/hide | Yes | Yes |
| Search-style Home cards, terminal palette, F1 helper | Yes | Upstream appearance/keys |
| Later Home sections / personalised mix fixes | Yes | Upstream behaviour |
| Panel volume slider and Up Next | Yes | Hidden; the inspected upstream volume setter does nothing |
| Configuration | Separate plugin-owned directory | Existing upstream configuration, preserved |

The customised player is a separate [fork of WakaTaira’s TUI](https://github.com/lisim/ytmusic-tui). Both choices are source-built and pinned. Original uses upstream’s sign-in flow; browser extraction may require its manual fallback. Selecting Original does not install our patches or overwrite its existing theme/keymap.

## Controls

The bar shows a bundled SVG icon, so it does not depend on an icon font. It stays icon-only when idle and shows the track title/artist when music is loaded.

| Gesture | Action |
| --- | --- |
| Left-click | Launch, hide or restore the TUI |
| Middle-click | Play/pause the music player |
| Right-click | Now-playing panel and player setup |
| Play in the panel while the player is closed | Launch and play the first Home recommendation (Customised); open the player to select a song (Original) |
| Wheel over the bar | Previous/next track |
| Wheel above Up Next / drag the vertical slider | Music-only volume (Customised) |

The Up Next list scrolls independently. The slider is on the right: bottom 0%, top 100%. Your system volume and browser video are separate.

A hidden player stays running in a parked workspace. Restoring moves the floating window to the current normal workspace; it never opens a full-workspace overlay. Closing the terminal or pressing **Q** stops playback. If a TUI is already running outside this plugin, close that instance before launching a second one.

In Customised mode, **F1** shows/hides keyboard help, **1** opens Home, **2** Search, **3** Library, **5** Queue and **8** Lyrics. Tab switches cards/panes; arrows select, Enter plays/opens. After submitting a search, Esc returns to result navigation. Mouse selection inside the TUI is not supported.

## Setup, updates and removal

Open **Player setup** in the now-playing panel to change backend/browser/shortcut. Close the music window first. Setup installs only plugin-owned binaries and does not replace a user’s existing `ytmusic-tui` executable.

```sh
omarchy plugin update lisim.ytmusic
```

Then open Player setup to build the backend revision pinned by that plugin update. An existing matching build is reused; a failed build leaves the previous binary in place.

**Updating from 1.0.0:** version 1.0.1 moves this plugin's storage to `lisim-ytmusic` directories. Close the player, then click the bar to run setup again and rebuild/sign in. The old `omarchy-ytmusic` directories are left untouched because other players also use them; they are not automatically imported, moved or removed. Do not run the old 1.0.0 uninstaller or delete those shared directories as a cleanup step. Original upstream TUI settings remain in their existing location.

To uninstall, close the player and run:

```sh
python3 "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/lisim.ytmusic/scripts/ytmusic.py" uninstall
```

This asks for confirmation, removes the owned builds/cache and managed desktop-rule block, and removes the plugin through Omarchy. Saved sign-in/settings are kept for reinstalling. Add `--purge` to also delete the custom player’s saved sign-in/settings. The original upstream configuration, other applications and shared system packages are always retained. Do not remove the plugin directory first if you also want its helper to clean up desktop rules/builds.

## What changes on disk

- `${XDG_CONFIG_HOME:-~/.config}/lisim-ytmusic/`: setup preferences, custom-player config/sign-in and the initial desktop-bindings backup.
- `${XDG_DATA_HOME:-~/.local/share}/lisim-ytmusic/`: separately owned Customised/Original player builds and source receipts.
- `${XDG_CACHE_HOME:-~/.cache}/lisim-ytmusic/`: compiler cache; temporary source checkouts are removed after each build.
- `~/.config/hypr/bindings.lua` (under XDG_CONFIG_HOME when set): one marked block for floating-window behaviour and the optional shortcut. Failed validation restores the previous file.

First-run setup asks before reading a browser’s YouTube session. Optional automatic refresh reads that selected browser on future player launches; choose manual/later to avoid it. Auth is sent to YouTube by the selected player. No account data is sent to the plugin author, written into the source checkout or included in this repository.

## Validation and limits

The setup tests use temporary config/data roots and fake commands; they cover both choices, exact source pins, build-failure preservation, desktop rollback, hide/show and uninstall ownership. Coexistence tests verify that normal uninstall and purge preserve other players' files in the old shared directories, with both default and custom XDG locations. The QML test loads the actual widget with fake players, checks SVG loading, icon-only idle display, volume isolation, vertical-slider direction, queue scrolling and Original-mode capability gating.

Version 1.0.2 clean-install checks passed in an Omarchy 4.0.4 KVM guest after the normal Omarchy update and Rust prerequisite installation: both setup choices built their pinned players, the customised player opened/floated/hid/restored, and actual uninstall/purge preserved foreign test files and restored desktop bindings. All 16 setup tests and QML checks also passed in the guest. Google sign-in and audible playback were not repeated in that VM; customised-player playback was checked separately on the maintainer's laptop.

```sh
python3 -m unittest discover -s tests -p test_setup.py -v
python3 tests/test_panel.py
omarchy plugin validate .
```

The customised player currently loads at most ten Home pages, the first batch of personal mixes (usually 100 tracks), and the next 100 queue entries. See its repository for tests and details. YouTube’s unofficial interface can change.

## Licence and credit

[MIT](LICENSE). Derived widget code credits **David Heinemeier Hansson / Omarchy**; player code credits **WakaTaira**. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Source is distributed here; no prebuilt player binary is bundled. Runtime dependencies retain their own licences.

Maintained by [lisim](https://github.com/lisim). Independent of Google/YouTube, Omarchy and the upstream TUI author. This repository is installable directly; marketplace inclusion is a separate review process.
