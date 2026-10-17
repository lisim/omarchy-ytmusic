# YouTube Music TUI (lisim)

Omarchy bar integration for [lisim's customised fork](https://github.com/lisim/ytmusic-tui) of [WakaTaira's ytmusic-tui](https://github.com/WakaTaira/ytmusic-tui). The floating terminal player can be hidden while music keeps playing. **This plugin installs only the customised fork**, including its cookie-domain security fixes. WakaTaira is the original TUI author; the original MIT licence and attribution are preserved.

> **Read before installing: this player uses YouTube session cookies, not Google OAuth.** Browser sign-in reads the selected browser's local cookie store and saves a plaintext session copy. Manual sign-in also uses cookies. Cookie access and automatic renewal are explained during setup and require your choice. See [Authentication and privacy](#authentication-and-privacy).

![Home cards — sample content](preview.png)

## Install

Requires **Omarchy 4 with its Quickshell plugin system and Lua Hyprland configuration**. The runtime targets the interfaces tested on Omarchy/Quickshell 0.3.1; older Waybar setups are not supported.

```sh
omarchy plugin add https://github.com/lisim/omarchy-ytmusic.git --enable
```

Click the new bar item to open first-run setup. It will:

1. Explain cookie access and ask for consent, offering browser extraction, manual cookie-header paste or setup later. Automatic renewal is a separate opt-in, defaulting to No.
2. Build the customised fork from the pinned source revision in `backends.json`.
3. Add the floating-window rule and optionally bind **Super+Shift+M**.

First build usually takes **2–10 minutes**. Setup never installs system packages or runs sudo automatically. If prerequisites are missing:

```sh
omarchy pkg add rustup base-devel mpv yt-dlp
rustup toolchain install stable
```

On a fresh Omarchy installation, complete its normal `omarchy update` first so package databases and the system are ready for additional packages.

The plugin install command only clones/enables files. Source building and account setup happen after you explicitly open first-run setup.

## Included player and security improvements

The customised fork includes Home cards, personalised mixes, terminal colours, F1 shortcut help, a vertical volume slider, Up Next, and Like/Dislike controls with recorded ratings shown in red.

This edition makes specific security improvements over the upstream revision previously offered:

- **Strict domain filtering before requests:** only cookie rows from `youtube.com` and its dot-delimited subdomains reach the cookie-name filter, session validation or saved authentication. Lookalikes such as `youtube.com.example.invalid` and `notyoutube.com` are rejected. Initial import and automatic renewal use this check.
- **Validated, bounded renewal:** fresh cookies must pass a signed-in account check before replacing existing auth. A rejected request is retried once; transport failures are not retried as writes. Rating reads require a signed-in account check.
- **Private atomic storage and fixed API destination:** auth writes use owner-only permissions and atomic replacement; authenticated API calls do not follow HTTP redirects. Cookies still remain plaintext on disk.
- **One maintained player:** the vulnerable Original source pin and install option have been removed. Legacy Original settings cannot launch or rate through this plugin. A missing or outdated build receipt requires setup before launch/rating; migration requires fresh sign-in and does not import upstream auth. Alternate auth paths and auth/config symlinks are rejected in plugin-managed configuration.

These are targeted protections, not a security certification. See the [fork's security details](https://github.com/lisim/ytmusic-tui#security-improvements-in-this-fork). The cookie-domain regression tests use synthetic credentials and verify that unrelated cookies never reach validation or disk.

## Authentication and privacy

**This player does not offer Google OAuth sign-in.** It reuses a signed-in YouTube browser session. These cookies are credentials, not narrowly scoped music-only tokens; someone with a working copy can act as that session. Only authenticate if you trust the player with it.

- **Browser extraction:** after your explicit consent, the player's `rookie` dependency reads/decrypts the selected browser's cookie store, requesting YouTube cookies. Our customised fork additionally filters exact YouTube domains and allowed cookie names. It does not read your saved Google password.
- **Local storage:** The fork saves plaintext cookies/headers to `${XDG_CONFIG_HOME:-$HOME/.config}/lisim-ytmusic/custom-tui/browser.json` by default, using owner-only permissions (`0600`) and atomic writes. Plugin-managed configuration must use this auth path; remove any external `browser_auth_path` override before setup. Standalone fork installations can still configure their own paths. File permissions are not encryption: never share auth files, raw headers or backups containing them.
- **Network use:** the player sends session authentication to YouTube Music. There is no plugin-author login server or cookie-upload/telemetry service. This remains an unofficial integration that Google may change or invalidate.
- **Your choices:** manual header-paste avoids direct browser-store access but still copies and uses cookies. Domain provenance is lost in a pasted header: paste only a request from the actual `music.youtube.com` site. Choose **later** to skip importing cookies on a new setup or an already-current customised installation; its saved authentication is retained. Migrating Original or replacing an outdated/unverified build requires fresh sign-in instead. Without a saved session, account features such as your library, personalised mixes and ratings will not work. Declining the consent prompt cancels setup before any browser access.
- **Renewal and removal:** The fork can optionally re-read the selected browser when the session expires, including in the running TUI and mini-player rating actions. It validates the replacement, saves it atomically and retries once; failure preserves existing auth. New setups default to **No**. To turn it off, close the player, open **Player setup**, and decline automatic renewal. To stop using saved cookies, quit the player, disable renewal and remove the selected auth file. Uninstall with `--purge` removes plugin-owned custom sign-in; normal uninstall retains it. Upstream auth files outside this plugin are always left untouched. Deleting a file does not revoke copies elsewhere.

Existing users who enabled automatic refresh now also get renewal during use, rather than only at launch. Restart the TUI after updating its build. Chrome must still have a valid accessible YouTube session; this does not bypass sign-in or guarantee sessions never expire.

## Controls

The bar shows a bundled SVG icon, so it does not depend on an icon font. It stays icon-only when idle and shows the track title/artist when music is loaded.

| Gesture | Action |
| --- | --- |
| Left-click | Launch, hide or restore the TUI |
| Middle-click | Play/pause the music player |
| Right-click | Now-playing panel and player setup |
| Play in the panel while the player is closed | Launch and play the first Home recommendation |
| Wheel over the bar | Previous/next track |
| Wheel above Up Next / drag the vertical slider | Music-only volume |

The Up Next list scrolls independently. The slider is on the right: bottom 0%, top 100%. Your system volume and browser video are separate.

A hidden player stays running in a parked workspace. Restoring moves the floating window to the current normal workspace; it never opens a full-workspace overlay. Closing the terminal or pressing **Q** stops playback. If a TUI is already running outside this plugin, close that instance before launching a second one.

**F1** shows/hides keyboard help, **1** opens Home, **2** Search, **3** Library, **5** Queue and **8** Lyrics. **f** toggles Like and **Shift+F** toggles Dislike for the current song. Tab switches cards/panes; arrows select, Enter plays/opens. After submitting a search, Esc returns to result navigation. Mouse selection inside the TUI is not supported.

The mini player's thumbs read the signed-in account's saved rating when opened or when the song changes. The recorded thumb turns YouTube red; click it again to remove that rating. Requests use the player's private configuration and the exact song shown when clicked; failures are displayed without pretending the rating changed. If YouTube does not report a rating, the panel says so. No ratings are sent merely by opening the panel.

## Setup, updates and removal

Open **Player setup** in the now-playing panel to change browser/renewal/shortcut settings. Close the music window first. Setup installs only plugin-owned binaries and does not replace a user’s existing `ytmusic-tui` executable.

```sh
omarchy plugin update lisim.ytmusic
```

Then open Player setup to build the fork revision pinned by that plugin update. An existing matching build is reused; a failed build leaves the previous binary in place. The plugin will not launch or rate with a build whose source receipt differs from the current pin. Replacing an outdated or unverified installation also requires fresh sign-in, including older customised builds, so an old imported cookie file is not silently reused.

**Updating from Original (v1.2.1 or earlier):** close the old TUI with **Q**, update the plugin, then click the bar or open **Player setup**. Original is no longer selectable or launched; setup installs the fork and requires fresh browser/manual sign-in before saving the migration. Choosing later, declining consent or a failed sign-in leaves migration incomplete and Original disabled. Upstream config/cookies and old binaries are not imported or automatically deleted. Do not reuse an old Original `browser.json`: cookie domain provenance is not available after import. If custom configuration points at an external auth path or uses auth/config symlinks, setup stops with instructions rather than following them.

**Updating from 1.0.0:** version 1.0.1 moves this plugin's storage to `lisim-ytmusic` directories. Close the player, then click the bar to run setup again and rebuild/sign in. The old `omarchy-ytmusic` directories are left untouched because other players also use them; they are not automatically imported, moved or removed. Do not run the old 1.0.0 uninstaller or delete those shared directories as a cleanup step. Original upstream TUI settings remain in their existing location.

To uninstall, close the player and run:

```sh
python3 "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/lisim.ytmusic/scripts/ytmusic.py" uninstall
```

This asks for confirmation, removes the owned builds/cache and managed desktop-rule block, and removes the plugin through Omarchy. Saved sign-in/settings are kept for reinstalling. Add `--purge` to also delete the custom player’s saved sign-in/settings. The original upstream configuration, other applications and shared system packages are always retained. Do not remove the plugin directory first if you also want its helper to clean up desktop rules/builds.

## What changes on disk

- `${XDG_CONFIG_HOME:-~/.config}/lisim-ytmusic/`: setup preferences, custom-player config/sign-in and the initial desktop-bindings backup.
- `${XDG_DATA_HOME:-~/.local/share}/lisim-ytmusic/`: the owned customised-player build and source receipt. Legacy Original binaries may remain here until uninstall but are never selected or executed.
- `${XDG_CACHE_HOME:-~/.cache}/lisim-ytmusic/`: compiler cache; temporary source checkouts are removed after each build.
- `~/.config/hypr/bindings.lua` (under XDG_CONFIG_HOME when set): one marked block for floating-window behaviour and the optional shortcut. Failed validation restores the previous file.

Authentication files are runtime data outside the source checkout. See [Authentication and privacy](#authentication-and-privacy) before choosing a sign-in method.

## Validation and limits

The setup tests use temporary config/data roots and fake commands; they cover fork-only setup, blocked legacy launches/ratings, fresh-sign-in migration, exact source receipts, auth-path isolation, build-failure preservation, desktop rollback, hide/show and uninstall ownership. Coexistence tests verify that normal uninstall and purge preserve other players' files in the old shared directories, with both default and custom XDG locations. The QML test loads the actual widget with fake players, checks SVG loading, icon-only idle display, volume isolation, vertical-slider direction, queue scrolling and blocking controls for a saved legacy Original selection.

Historical version 1.0.2 clean-install checks passed in an Omarchy 4.0.4 KVM guest after the normal Omarchy update and Rust prerequisite installation: both setup choices built their pinned players, the customised player opened/floated/hid/restored, and actual uninstall/purge preserved foreign test files and restored desktop bindings. All 16 setup tests and QML checks also passed in the guest. Google sign-in and audible playback were not repeated in that VM; customised-player playback and ratings were checked separately on the maintainer's laptop. Version 1.3.0 migration/security-path tests run with isolated synthetic files; this release has not been rerun in the clean VM.

```sh
python3 -m unittest discover -s tests -p test_setup.py -v
python3 tests/test_panel.py
omarchy plugin validate .
```

The customised player currently loads at most ten Home pages, the first batch of personal mixes (usually 100 tracks), and the next 100 queue entries. See its repository for tests and details. YouTube’s unofficial interface can change.

## Licence and credit

[MIT](LICENSE). Derived widget code credits **David Heinemeier Hansson / Omarchy**; player code credits **WakaTaira**. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Source is distributed here; no prebuilt player binary is bundled. Runtime dependencies retain their own licences.

Maintained by [lisim](https://github.com/lisim). Independent of Google/YouTube, Omarchy and the upstream TUI author. This repository is installable directly; marketplace inclusion is a separate review process.
