# ytdld

Parallel YouTube → MP3/MP4 downloader with a real-time TUI dashboard.

Paste a file of links (individual videos, playlists, Google search results — any format), pick what you want, and walk away. Threads handle the rest.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/himudigonda/ytdld/main/install.sh | bash
```

Requires **ffmpeg** on your PATH for MP3 conversion and thumbnail embedding.

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

## Usage

```bash
# Download everything in a link file as MP3
ytdld -i links.txt

# Video mode, 6 parallel threads
ytdld -i links.txt --mode mp4 --threads 6

# Interactive picker — deselect tracks before downloading
ytdld -i links.txt --select

# Custom output directory
ytdld -i links.txt --out ~/Downloads/Music
```

### Options

| Flag | Default | Description |
|---|---|---|
| `-i`, `--input` | required | path to a text file of URLs |
| `-o`, `--out` | `~/Music/Downloads` | output directory |
| `--mode` | `mp3` | `mp3` or `mp4` |
| `--threads` | `3` | parallel download workers |
| `--select` | off | interactive checkbox picker |

### Link file format

The input file can be messy — raw text, Google search result URLs, YouTube playlist URLs, video URLs. `ytdld` extracts and deduplicates all valid YouTube IDs automatically.

```text
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/playlist?list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-
https://www.google.com/search?q=...&v%3DdQw4w9WgXcQ...
```

## Output structure

Files are saved as `<out>/<uploader>/<title>.mp3` (or `.mp4`). MP3 downloads include embedded cover art and ID3 metadata from YouTube.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/himudigonda/ytdld/main/uninstall.sh | bash
```

## How it works

- **URL sanitizer** — regex-extracts clean YouTube video/playlist IDs from any input format, including Google-wrapped URLs
- **Playlist expander** — resolves playlist IDs into individual video entries via `yt-dlp` flat extraction
- **Parallel engine** — `ThreadPoolExecutor` with configurable worker count; each thread has its own progress bar in the TUI
- **Rich TUI** — fullscreen live dashboard: global progress, per-thread download speed, event log, telemetry

## Requirements

- Python 3.11+
- ffmpeg (system dependency)
- macOS or Linux
