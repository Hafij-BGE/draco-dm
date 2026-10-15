# Draco Download Manager

Created by **Md Hafijur Rahman**.

A free download manager for Linux, written from scratch. It speeds up downloads by using several connections per file, can resume broken downloads, catches downloads and videos from your browser, and runs queues on a schedule. There are no accounts, trials or subscriptions.

Built with Python 3 and GTK4/libadwaita, using only the standard library. ffmpeg and yt-dlp are optional extras.

## Features

| Feature | How it works in Draco |
|---|---|
| Faster downloads | Up to 32 connections per file. When one connection finishes, it takes over half of the largest unfinished piece ("dynamic segmentation"), so every connection stays busy until the end. |
| Pause / resume / crash recovery | Each connection's position is saved in the download list. Resuming continues from those positions, including after a crash or reboot. |
| Browser integration | An extension for Chrome, Brave, Edge, Chromium, Vivaldi and Firefox sends downloads to Draco. It passes along cookies and the referrer, so logged-in downloads work. |
| "Download this video" panel | The extension spots video and audio streams on a page and shows a button on the video player. |
| HLS / DASH streams | `.m3u8` streams download in parallel and are joined into one MP4. Encrypted or live streams and `.mpd` go through ffmpeg. |
| YouTube and similar sites | Uses yt-dlp, if installed: right-click the page and choose *Download video from this page*. |
| Categories | Compressed, Documents, Music, Programs, Video and General. Each has its own folder and can be edited in Preferences. |
| Queues and scheduler | Several queues, each with its own number of simultaneous downloads. Start/stop times, weekdays, run-once option, retry of failed files. After a queue finishes, Draco can exit, suspend, hibernate or shut down, with a 60-second cancel window. |
| Speed limiter | A global limit in the status bar and a per-download limit in the progress window. |
| Progress window | Size, speed, time left, resume support, a live map of the connections, and per-connection details. |
| Refresh download address | Give an expired download a new link and keep the data already downloaded. You can paste the link, or click "Wait for browser" and click the link again in your browser. |
| Site grabber | Crawls a site to a chosen depth and lists all files of the chosen types. Pick the ones you want and queue them. |
| Batch download | `https://site/img[001-150].jpg`, `part[a-f].rar`, or `*` with a range. |
| Download all links | From the browser's right-click menu, or by pasting or dropping several links. |
| Clipboard watcher | Copying a link to a file type on the capture list offers to download it. |
| Drag and drop / Ctrl+V | Drop or paste links onto the main window. |
| Site logins | HTTP Basic login per site pattern. |
| Virus scan after download | Runs any command you set, e.g. `clamscan --no-summary {file}`. |
| Notifications and sound | A desktop notification and a sound when a download completes or fails. |
| Import / export | Import links from a text file; export the list. |
| Command line | `draco URL`, `draco --now URL`, `draco --status`. |

## YouTube and quick capture

- **YouTube, Vimeo, TikTok, Facebook, Instagram, X, Reddit, Twitch, SoundCloud and more** are downloaded through yt-dlp, which the .deb pulls in.
- **On the video player:** a **⬇ Download this video** button appears. Pick a quality and Draco shows a confirmation dialog with the title, length and estimated size of every quality. With **Quick capture** on, it starts straight away.
- **Alt+Shift+D (quick capture):** downloads the current page's video at the best quality, with no dialog. On other sites it grabs the largest video the page has played.
- **Quick capture switch** in the extension popup: every download the browser hands to Draco starts instantly, without the file-info dialog.
- **Right-click a link → Quick download with Draco:** the same, for a single link.

## Themes

**View → Theme** (or Preferences → General) switches instantly between: Follow desktop, Draco Classic, Retro Gray, Soft Light, Galaxy, Dark, Midnight Blue, Nightshade, Arctic Frost, Sand Light/Deep Teal, Forest, Sunset and High Contrast. Each theme brings matching icons (colourful, flat, monochrome or accent-coloured). You can override this under **View → Icon Style** or the palette button: *Match theme*, *Colourful*, *Flat*, *Monochrome*, *Accent colour*. To add your own theme, copy an entry in `draco/gui/style.py` (`THEMES`) and change its colours.

## Subtitles

Tick **Include subtitles** in the video button's menu, in the extension popup, or in Draco's download dialog. The subtitles are added to the video as a track you can switch on and off, and also saved as a `.srt` next to it. **Subtitles only (.srt)** fetches just the text. Draco uses your browser's language, falling back to English.

## Windows 11

The code runs on Windows 11 as well. To build `DracoSetup.exe` on a Windows PC, follow [packaging/windows/BUILD-WINDOWS.md](packaging/windows/BUILD-WINDOWS.md): two `winget` installs, then one build script.

## Install from the .deb package (Debian, Ubuntu, Mint, Pop!_OS)

```bash
sh packaging/build-deb.sh                      # creates dist/draco-dm_<version>_all.deb
sudo apt install ./dist/draco-dm_1.4.1_all.deb
```

`apt` installs the GTK dependencies, plus ffmpeg and yt-dlp as recommended packages. Start Draco once from the app menu; it registers the browser connection for your user by itself. Remove it with `sudo apt remove draco-dm`. (The package is called `draco-dm` because Ubuntu already has an unrelated package named `draco`.)

## Install for your user only (no root)

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1   # usually already present on GNOME
./install.sh               # installs to ~/.local, no root needed
./install.sh --autostart   # optional: start hidden at login so scheduled queues run
```

Optional extras:

```bash
sudo apt install ffmpeg    # encrypted/live HLS, DASH, MP4 remux of HLS
pipx install yt-dlp        # YouTube and 1000+ video sites
```

Remove with `./install.sh --uninstall`. Your settings (`~/.config/draco`) and download list (`~/.local/share/draco`) are kept.

### Snap / Flatpak browsers (Ubuntu's Brave, Opera, Chromium, Firefox snaps)

Sandboxed browsers can't start Draco through native messaging, and their file picker can't see hidden folders. Draco handles both:

1. Draco copies the extension to `~/Documents/Draco Browser Extension/` (a visible folder). Load the `chrome` folder from there.
2. Click the Draco button in the browser toolbar, then **Connect to Draco**, and press **Allow** in Draco. This pairs the browser over `127.0.0.1` with a secret token. Web pages can't use this connection: Draco only accepts requests from its own extension.
3. Leave **Start Draco automatically at login** ticked. A snap browser can't launch Draco by itself, so Draco must already be running.

### Browser extension (one time)

`install.sh` registers the native-messaging host and unpacks the extension to `~/.local/share/draco/extension/`.

- **Chrome / Brave / Edge / Chromium / Vivaldi:** open `chrome://extensions`, turn on *Developer mode*, click *Load unpacked*, and choose `~/.local/share/draco/extension/chrome`.
- **Firefox:** open `about:debugging#/runtime/this-firefox`, click *Load Temporary Add-on*, and choose `~/.local/share/draco/extension/firefox/manifest.json`. Regular Firefox removes temporary add-ons on restart. To keep it permanently, use Firefox Developer Edition or ESR with `xpinstall.signatures.required=false`, or sign it for free on addons.mozilla.org.

The toolbar popup shows whether Draco is connected. It also has the capture on/off switch, the list of file types to capture, and the media found on the current page. If Draco isn't running, the browser starts it in the background.

## Changing the icons

- **App icon:** replace `data/draco-source.png` with any square-ish picture on a white background, then run `python3 tools/make_icons.py`. It removes the outer white background and writes every size: the desktop icon, the browser extension icons and the in-app icon.
- **Toolbar and category icons:** these are SVG files in `draco/icons/` (for example `draco-add-url.svg` or `draco-cat-video.svg`). Replace any file with your own artwork under the same name.

Run `./install.sh` again after changing either.

## Run from the source folder

```bash
bin/draco
python3 -m unittest tests.test_engine     # engine tests
```

## Layout

```
draco/engine.py     multi-connection HTTP/FTP engine, dynamic segmentation, rate limiter
draco/media.py      HLS downloader, ffmpeg and yt-dlp bridges
draco/manager.py    download list, queues, scheduler, persistence
draco/grabber.py    site crawler
draco/batch.py      batch pattern expansion
draco/ipc.py        per-user Unix socket (single instance, CLI, browser host)
draco/native.py     native-messaging host registration
draco/gui/          GTK4/libadwaita windows and dialogs
native_host/         the stdio host started by the browser
extension/chrome/    the browser extension (the Firefox variant is generated at install)
```

## Notes and limits

- GTK4 has no tray icon. While downloads are running, closing the window hides it instead. Run `draco` again, or click *Open Draco* in the extension popup, to bring it back.
- On Wayland, the clipboard watcher only sees new links while Draco's window has focus. This is a security rule of the desktop, not a bug.
- FTP downloads use a single connection.
- Downloads that need DRM (Netflix and similar) are not supported.
- The download list holds cookies and is stored with mode 600. Site logins in `settings.json` are not encrypted (also mode 600).

## Credits

Draco Download Manager © 2026 Md Hafijur Rahman. Licensed under the GPL-3.0.
