# ytdld

> Parallel YouTube → **MP3 or MP4** downloader with a real-time TUI dashboard.

Dump your links, hit enter, and watch your terminal turn into a live operations center — every thread tracked, every byte counted, every completion logged in real time.

---

## Table of contents

- [What it does](#what-it-does)
- [What it looks like](#what-it-looks-like)
- [Prerequisites](#prerequisites)
- [Install](#install)
- [Quick start](#quick-start)
- [How to write a links file](#how-to-write-a-links-file)
- [All flags & options](#all-flags--options)
- [Formats: MP3 vs MP4](#formats-mp3-vs-mp4)
- [Interactive picker](#interactive-picker)
- [Output layout](#output-layout)
- [TUI in detail](#tui-in-detail)
- [Safety & legal](#safety--legal)
- [Responsible use](#responsible-use)
- [Troubleshooting](#troubleshooting)
- [Uninstall](#uninstall)

---

## What it does

ytdld is a CLI tool that reads a text file of YouTube URLs (messy is fine — it parses out all valid IDs automatically), expands any playlists, and downloads everything in parallel with a live terminal dashboard.

**Supported output formats:**

| Mode | Flag | What you get |
|------|------|--------------|
| MP3 (default) | `--mode mp3` | Audio-only, highest quality, embedded cover art + ID3 tags |
| MP4 | `--mode mp4` | Best available video + audio, merged into a single `.mp4` |

Both modes embed metadata (title, uploader, etc.) and the YouTube thumbnail as cover art. Files are organized into `<uploader>/<title>.<ext>` automatically.

---

## What it looks like

![ytdld TUI dashboard](assets/demo.png)

The dashboard takes over your full terminal (alternate screen buffer — your shell history is exactly where you left it when it exits). Each parallel thread gets its own live progress row showing download speed, bytes, and status. When a download finishes, the row switches to a post-processing indicator (`⚙`) while ffmpeg does its work, then flips to done (`✓`).

---

## Prerequisites

Before installing ytdld, make sure you have:

### 1. Python 3.11+

```bash
python3 --version   # need 3.11 or newer
```

If you're on macOS and don't have it:
```bash
brew install python@3.11
```

### 2. ffmpeg

Required for MP3 conversion, video/audio merging, and thumbnail embedding. Without it, downloads will either fail or produce raw files without cover art.

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Arch / Manjaro
sudo pacman -S ffmpeg

# Windows (via scoop)
scoop install ffmpeg
```

Verify it's on your PATH:
```bash
ffmpeg -version   # should print version info
```

### 3. uv (installed automatically)

`ytdld` uses [uv](https://github.com/astral-sh/uv) to manage its own Python environment. The install script installs uv for you if it's not already present.

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/himudigonda/ytdld/main/install.sh | bash
```

The script:
1. Installs `uv` if not present
2. Warns if `ffmpeg` is missing
3. Installs `ytdld` as a system-wide binary via `uv tool install`
4. Tells you if you need to add `~/.local/bin` to your PATH

After install, verify:
```bash
ytdld --help
```

### PATH setup (if needed)

If your shell reports `ytdld: command not found` after install, add this to your `~/.zshrc` or `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then reload:
```bash
source ~/.zshrc   # or source ~/.bashrc
```

---

## Quick start

**Step 1** — create a links file:

```bash
# links.txt
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/playlist?list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-
```

**Step 2** — download as MP3:

```bash
ytdld -i links.txt
```

**Step 3** — or download as MP4 (video):

```bash
ytdld -i links.txt --mode mp4
```

Files land in `~/Music/Downloads/<uploader>/<title>.mp3` (or `.mp4`).

---

## How to write a links file

The input file is intentionally forgiving — paste raw YouTube URLs in any format, one per line. `ytdld` extracts all valid YouTube video IDs and playlist IDs automatically, deduplicates them, and expands any playlists into individual tracks.

**Any of these work:**

```text
# Single video
https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Short URL
https://youtu.be/dQw4w9WgXcQ

# Playlist
https://www.youtube.com/playlist?list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-

# Video inside a playlist (just the video is downloaded, not the whole list)
https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-

# Messy copy-paste from a search page — IDs are still extracted
https://www.google.com/search?q=hardwell+spaceman&v%3DdQw4w9WgXcQ...

# Blank lines and comments are fine — just paste freely
https://www.youtube.com/watch?v=9bZkp7q19f0
```

**What gets deduped:** if the same video ID appears multiple times (e.g., once as a standalone URL and once as part of a playlist), it is only downloaded once.

**What is ignored:** non-YouTube URLs, malformed IDs, comments, blank lines.

---

## All flags & options

```
ytdld -i <file> [options]
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--input` | `-i` | required | Path to text file containing YouTube URLs |
| `--mode` | | `mp3` | Output format: `mp3` (audio only) or `mp4` (video + audio) |
| `--out` | `-o` | `~/Music/Downloads` | Output directory |
| `--threads` | | `3` | Number of parallel download workers |
| `--select` | | off | Show interactive checkbox picker before downloading |

### Common examples

```bash
# Download a playlist as MP3, 3 parallel threads
ytdld -i links.txt

# Download everything as MP4 (video)
ytdld -i links.txt --mode mp4

# Speed up with more threads (see Responsible Use section first)
ytdld -i links.txt --threads 5

# Save to a custom folder
ytdld -i links.txt --out ~/Desktop/Music

# Open the interactive picker to deselect tracks before downloading
ytdld -i links.txt --select

# Combine: MP4, custom output, 4 threads, with picker
ytdld -i links.txt --mode mp4 --out ~/Videos/YouTube --threads 4 --select
```

---

## Formats: MP3 vs MP4

### `--mode mp3` (default)

- Downloads the **best available audio stream** (no video)
- Converts to MP3 at the highest quality setting (VBR 0, ~320 kbps equivalent)
- Embeds the YouTube thumbnail as cover art
- Embeds ID3 metadata: title, uploader, upload date, description

Best for: music, podcasts, lectures, anything you want in a media library.

### `--mode mp4`

- Downloads the **best available video stream + best available audio stream**, then merges them with ffmpeg
- Output is a single `.mp4` container (H.264/VP9 video + AAC/Opus audio, depending on what YouTube offers)
- Embeds metadata and thumbnail
- Files are larger — typically 100 MB–2 GB for a 10-minute video at 1080p

Best for: music videos, tutorials, talks — anything where you want visuals.

> **On file size:** a 3-minute song at best audio quality is ~5–10 MB as MP3. The same song as MP4 at 1080p is ~150–400 MB. Plan your disk space accordingly.

---

## Interactive picker

Add `--select` to inspect and trim your track list before anything downloads:

```bash
ytdld -i links.txt --select
```

ytdld first resolves all URLs (expanding playlists), then shows a checkbox list:

```
Select tracks (42 found, space to toggle, enter to confirm):
❯ ◉   3:54  Tsunami (Original Mix)  — DVBBS
  ◉   5:12  Animals  — Martin Garrix
  ◉   4:01  Spaceman  — Hardwell
  ◯   1:23  some annoying intro  — RandomChannel
  ◉   6:44  Internet Friends  — Knife Party
```

- All tracks are pre-checked
- `Space` to toggle a track on/off
- Arrow keys to navigate
- `Enter` to confirm and start downloading
- `Ctrl+C` to abort without downloading anything

This is useful when you paste a full playlist but only want certain tracks.

---

## Output layout

Files are organized by uploader automatically:

```
~/Music/Downloads/          (or whatever you pass to --out)
  Martin Garrix/
    Animals.mp3
    Forbidden Voices.mp3
    Tremor.mp3
  Hardwell/
    Spaceman.mp3
    Apollo.mp3
  DVBBS/
    Tsunami (Original Mix).mp3
```

For `--mode mp4`:

```
~/Music/Downloads/
  Kurzgesagt – In a Nutshell/
    Why Earth Is A Prison and How To Escape It.mp4
  Veritasium/
    The Most Misunderstood Concept in Physics.mp4
```

File names are sanitized automatically for cross-platform compatibility (special characters that are invalid on Windows are replaced).

---

## TUI in detail

The dashboard has four zones:

```
┌─────────────────────────────────────────────────────┐
│  [HEADER] Global progress bar — total % + ETA        │
├─────────────────────────────────────────────────────┤
│  [BODY] Worker Threads                               │
│  ⇣ Animals                  ████████░░  4.2MB/s     │
│  ⇣ Spaceman                 ███░░░░░░░  6.1MB/s     │
│  ✓ Tsunami (Original Mix)   ██████████  done        │
├──────────────────┬──────────────────────────────────┤
│  [STATS]         │  [EVENTS LOG]                     │
│  Success: 12     │  • Finished: Animals              │
│  Errors:   1     │  • Finished: Spaceman             │
│  Active:   2     │  • Error: some private video      │
└──────────────────┴──────────────────────────────────┘
```

**Header** — one global progress bar with a spinner, overall percentage, and estimated time remaining for the whole batch.

**Worker Threads** — one live row per active download. Track title, download progress bar, bytes transferred, and current speed. When a download finishes and ffmpeg starts post-processing, the icon changes from `⇣` (downloading) to `⚙` (processing) until the output file is written.

**Telemetry** — live counters: successes, errors, currently active workers.

**Events** — a rolling log of the last 8 completions and errors. Green for success, red for errors.

When all downloads complete, the TUI exits cleanly and your terminal returns to exactly its prior state (alternate buffer mode — no leftover output, no scroll artifacts).

---

## Safety & legal

**Please read this section before using ytdld.**

### Personal use only

ytdld is intended for downloading content for **personal, offline use** — for example, listening to music without an internet connection, or archiving a lecture you own the right to access. It is not intended to facilitate redistribution, commercial use, or any activity that infringes on creators' rights.

### Copyright

Downloaded content is protected by copyright. Downloading a video or audio track does **not** transfer any rights to you. You may not:

- Re-upload downloaded content to any platform
- Sell or distribute downloaded files
- Use downloaded content in your own videos or projects without proper licensing
- Strip and re-publish audio from music videos

Doing any of these things violates copyright law in most jurisdictions.

### YouTube's Terms of Service

Automated downloading of YouTube content is [against YouTube's Terms of Service](https://www.youtube.com/t/terms) (Section 5.B). By using ytdld, you acknowledge:

- Your YouTube account (if applicable) could be suspended
- YouTube may block your IP address if it detects excessive download traffic
- You use this software at your own risk

### What ytdld cannot bypass

- **DRM (Digital Rights Management)** — content protected with DRM (paid channels, YouTube Premium exclusives, etc.) cannot be downloaded. yt-dlp will report an error and skip these.
- **Private videos** — videos set to Private are inaccessible. Unlisted videos are accessible by URL only.
- **Age-restricted content** — may require a logged-in yt-dlp session (cookie export). ytdld does not handle this automatically.
- **Geo-restricted content** — videos unavailable in your region will fail with an error. A VPN can help, but that is outside the scope of ytdld.

### Best practices

- Download content you have a legitimate right to access
- Do not download entire channels or libraries en masse
- Do not use downloaded content commercially
- If you enjoy a creator's work, support them directly — YouTube Premium shares revenue with creators

---

## Responsible use

### Thread count

The default is 3 parallel threads. Higher values download faster but put more load on YouTube's servers and are more likely to trigger rate limits or temporary IP bans.

**Recommended limits:**

| Situation | `--threads` |
|-----------|-------------|
| A few tracks | `3` (default) |
| A large playlist (100+ tracks) | `4–5` |
| Multiple full playlists | `3` and be patient |
| Never | `10+` — you will get rate-limited |

If you see repeated errors or dramatically slowed downloads, reduce the thread count.

### Rate limits and errors

If ytdld starts getting consistent errors like `HTTP Error 429` or `Too Many Requests`, YouTube is rate-limiting your IP. Stop, wait 15–30 minutes, then retry with fewer threads.

### Bandwidth

Each active thread typically uses 1–10 MB/s depending on the video quality and your connection. For MP4 downloads at best quality, that can add up quickly. Be mindful on metered connections.

---

## Troubleshooting

### `ytdld: command not found`

The binary was installed but isn't on your PATH. Add this to your shell config:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then run `source ~/.zshrc` (or `~/.bashrc`) and try again.

### `ffmpeg not found` or cover art not embedded

Install ffmpeg for your platform (see [Prerequisites](#prerequisites)). Without it, MP3 conversion will fail and MP4 merging won't work.

```bash
which ffmpeg   # should print a path
ffmpeg -version
```

### Downloads fail with `ERROR: Sign in to confirm you're not a bot`

YouTube is blocking the download request. Options:

1. Wait and retry — often resolves itself in 10–30 minutes
2. Reduce `--threads` to 1 or 2
3. Export your YouTube cookies and configure yt-dlp to use them (advanced — see the [yt-dlp cookie documentation](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp))

### `ERROR: This video is not available` or `Private video`

The video is private, deleted, or geo-restricted. ytdld will skip it and continue with the rest of the batch — check the Events log in the TUI or the final output for which URLs failed.

### Output files have no cover art

This requires both `ffmpeg` installed and the `EmbedThumbnail` postprocessor running successfully. If thumbnails are missing, verify ffmpeg is installed and on PATH.

### `uv tool install` fails

Make sure you have internet access and that `uv` is installed and up to date:

```bash
uv self update
uv tool install "ytdld @ git+https://github.com/himudigonda/ytdld"
```

### The TUI exits immediately with no output

This usually means no valid YouTube URLs were found in your input file. Double check your links file — paste a raw URL into it and run again.

---

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/himudigonda/ytdld/main/uninstall.sh | bash
```

This runs `uv tool uninstall ytdld`. It removes the binary and its isolated environment. Your downloaded files are not touched.

To also remove `uv` itself:

```bash
uv self uninstall
```

---

## License

MIT. See [LICENSE](LICENSE) if present.

ytdld builds on [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense), [rich](https://github.com/Textualize/rich) (MIT), and [questionary](https://github.com/tmbo/questionary) (MIT).
