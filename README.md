# ytdld

Not just a `yt-dlp` wrapper. A mission control dashboard for downloading music.

Dump your links, hit enter, and watch your terminal turn into a live operations center — every thread tracked, every byte counted, every completion logged in real time.

---

## What it looks like

![ytdld TUI dashboard](assets/demo.png)

The dashboard takes over your full terminal (alternate buffer — no scroll artifacts when it exits). Each thread gets its own live row. When a download finishes, it flips to a post-processing indicator while ffmpeg converts to MP3 and embeds the cover art. Then it's done and the next one starts.

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/himudigonda/ytdld/main/install.sh | bash
```

That's it. The script installs `uv` if you don't have it, then registers `ytdld` as a system binary. No virtualenv to activate, no `python -m` prefix, no PATH nonsense.

**Also needs ffmpeg** (for MP3 conversion + cover art embedding):

```bash
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Ubuntu/Debian
```

---

## Workflow

### Step 1 — collect your links into a text file

Paste anything. YouTube URLs, playlist links, Google search result URLs, raw text with links buried in it — `ytdld` pulls out every valid YouTube ID automatically and deduplicates.

```text
# links.txt — paste whatever, one per line or all mixed together
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/playlist?list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-
https://www.google.com/search?q=hardwell+spaceman&v%3DdQw4w9WgXcQ...
```

### Step 2 (optional) — pick exactly what you want

```bash
ytdld -i links.txt --select
```

Before downloading anything, you get an interactive checkbox list — every track shown with its duration and uploader, all pre-checked. Untick what you don't want, hit enter.

```
Select tracks (42 found, space to toggle, enter to confirm):
❯ ◉   3:54  Tsunami (Original Mix)  — DVBBS
  ◉   5:12  Animals  — Martin Garrix
  ◉   4:01  Spaceman  — Hardwell
  ◯   1:23  some annoying intro  — RandomChannel
  ◉   6:44  Internet Friends  — Knife Party
```

### Step 3 — run it and watch

```bash
ytdld -i links.txt
```

The TUI takes over. Come back when it's done.

---

## Usage

```bash
ytdld -i links.txt                          # MP3, 3 threads, ~/Music/Downloads
ytdld -i links.txt --threads 6              # faster, more concurrent downloads
ytdld -i links.txt --mode mp4               # video instead of audio
ytdld -i links.txt --select                 # interactive picker first
ytdld -i links.txt --out ~/Desktop/Music    # custom output directory
```

| Flag | Default | Description |
|---|---|---|
| `-i`, `--input` | required | text file of URLs (messy is fine) |
| `--threads` | `3` | parallel download workers |
| `--mode` | `mp3` | `mp3` or `mp4` |
| `--out` | `~/Music/Downloads` | output directory |
| `--select` | off | interactive picker before downloading |

---

## The TUI in detail

**Header** — one global progress bar across the full width. Shows a spinner, overall % complete, and time remaining for the whole batch.

**Worker Threads** — one live row per active download. Each row shows the track title, a download progress bar, bytes downloaded so far, and current transfer speed. When a download finishes and ffmpeg kicks in, the row switches to a post-processing indicator (`⚙`) until the MP3 is written.

**Telemetry** — running counters: how many completed successfully, how many errored, how many are actively downloading right now.

**Events** — a live log of the last 8 completions (green) or errors (red). Lets you see what finished while you weren't watching.

When the batch completes, the TUI exits cleanly and returns your terminal exactly as it was.

---

## Output

Files land at `<out>/<uploader>/<title>.mp3` (or `.mp4`). MP3 files include embedded cover art (the YouTube thumbnail) and full ID3 metadata. Organized by uploader automatically — no manual sorting.

```
~/Music/Downloads/
  Martin Garrix/
    Animals.mp3
    Forbidden Voices.mp3
  Hardwell/
    Spaceman.mp3
  DVBBS/
    Tsunami (Original Mix).mp3
```

---

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/himudigonda/ytdld/main/uninstall.sh | bash
```
