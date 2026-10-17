# YouTube Music TUI (lisim)

Omarchy bar integration for [WakaTaira's ytmusic-tui](https://github.com/WakaTaira/ytmusic-tui), with a choice of the original player or lisim's customised fork. The floating terminal player can be hidden while music keeps playing.

> **Read before installing: both player choices use YouTube session cookies, not Google OAuth.** Browser sign-in reads the selected browser's local cookie store and saves a plaintext session copy. Manual sign-in also uses cookies. Cookie access and automatic renewal are explained during setup and require your choice. See [Authentication and privacy](#authentication-and-privacy).

![Home cards — sample content](preview.png)

## Install

Requires **Omarchy 4 with its Quickshell plugin system and Lua Hyprland configuration**. The runtime targets the interfaces tested on Omarchy/Quickshell 0.3.1; older Waybar setups are not supported.

```sh
omarchy plugin add https://github.com/lisim/omarchy-ytmusic.git --enable
```

Click the new bar item to open first-run setup. It will:

1. Offer **Customised** (recommended) or **Original upstream**.
2. Explain cookie access and ask for consent, offering browser extraction, manual cookie-header paste or setup later. Automatic renewal is a separate opt-in, defaulting to No.
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
| Mini-player Like / Dislike buttons | Yes, with saved rating and clear-on-second-click | Hidden |
| Configuration | Separate plugin-owned directory | Existing upstream configuration, preserved |

The customised player is a separate [fork of WakaTaira’s TUI](https://github.com/lisim/ytmusic-tui). Both choices are source-built and pinned. Original uses upstream’s sign-in flow; browser extraction may require its manual fallback. Selecting Original does not install our patches or overwrite its existing theme/keymap.

## Authentication and privacy

**Neither player offers Google OAuth sign-in.** Both reuse a signed-in YouTube browser session. These cookies are credentials, not narrowly scoped music-only tokens; someone with a working copy can act as that session. Only authenticate if you trust the selected player with it.

- **Browser extraction:** after your explicit consent, the selected player's `rookie` dependency reads/decrypts the selected browser's cookie store, requesting YouTube cookies. Our customised fork additionally filters exact YouTube domains and allowed cookie names. It does not read your saved Google password. Original runs its pinned upstream implementation; our renewal and hardening changes do not apply to it.
- **Local storage:** Customised saves plaintext cookies/headers to `${XDG_CONFIG_HOME:-$HOME/.config}/lisim-ytmusic/custom-tui/browser.json` by default, using owner-only permissions (`0600`) and atomic writes. Original uses `~/.config/ytmusic-tui/browser.json`. Explicit player auth-path overrides take precedence. File permissions are not encryption: never share auth files, raw headers or backups containing them.
- **Network use:** the player sends session authentication to YouTube Music. There is no plugin-author login server or cookie-upload/telemetry service. This remains an unofficial integration that Google may change or invalidate.
- **Your choices:** manual header-paste avoids direct browser-store access but still copies and uses cookies. Choose **later** to skip importing cookies; existing saved authentication is retained. Without a saved session, account features such as your library, personalised mixes and ratings will not work. Declining the consent prompt cancels setup before any browser access.
- **Renewal and removal:** Customised can optionally re-read the selected browser when the session expires, including in the running TUI and mini-player rating actions. It validates the replacement, saves it atomically and retries once; failure preserves existing auth. New setups default to **No**. To turn it off, close the player, open **Player setup**, and decline automatic renewal. To stop using saved cookies, quit the player, disable renewal and remove the selected auth file. Uninstall with `--purge` removes plugin-owned custom sign-in; normal uninstall retains it, and Original's auth is always retained. Deleting a file does not revoke copies elsewhere.

Existing users who enabled automatic refresh now also get renewal during use, rather than only at launch. Restart the TUI after updating its build. Chrome must still have a valid accessible YouTube session; this does not bypass sign-in or guarantee sessions never expire.

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

In Customised mode, **F1** shows/hides keyboard help, **1** opens Home, **2** Search, **3** Library, **5** Queue and **8** Lyrics. **f** toggles Like and **Shift+F** toggles Dislike for the current song. Tab switches cards/panes; arrows select, Enter plays/opens. After submitting a search, Esc returns to result navigation. Mouse selection inside the TUI is not supported.

The mini player's thumbs read the signed-in account's saved rating when opened or when the song changes. The recorded thumb turns YouTube red; click it again to remove that rating. Requests use the selected custom player's private configuration and the exact song shown when clicked; failures are displayed without pretending the rating changed. If YouTube does not report a rating, the panel says so. No ratings are sent merely by opening the panel.

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

Authentication files are runtime data outside the source checkout. See [Authentication and privacy](#authentication-and-privacy) before choosing a sign-in method.

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
