from pathlib import Path

from yt_dld.core import (
    DownloadOptions,
    LinkProcessor,
    _format_string,
    build_ydl_opts,
)


def _opts(**kw):
    return DownloadOptions(out_dir=Path("/tmp/ytdld-test"), **kw)


def test_sanitize_extracts_and_dedupes():
    raw = """
    https://www.youtube.com/watch?v=dQw4w9WgXcQ
    https://youtu.be/9bZkp7q19f0
    https://www.youtube.com/playlist?list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-
    https://www.youtube.com/shorts/abcdefghijk
    https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-
    not a url at all
    """
    links = LinkProcessor.sanitize(raw)
    assert any("playlist?list=PLrEnWoR732" in l for l in links)
    assert any("v=dQw4w9WgXcQ" in l for l in links)
    assert any("v=9bZkp7q19f0" in l for l in links)
    assert any("v=abcdefghijk" in l for l in links)
    # appears twice in input, once in output
    assert sum("v=dQw4w9WgXcQ" in l for l in links) == 1


def test_sanitize_ignores_garbage():
    assert LinkProcessor.sanitize("just some text\nno links here") == []


def test_format_strings():
    assert _format_string(_opts(mode="mp3")) == "bestaudio/best"
    assert _format_string(_opts(mode="flac")) == "bestaudio/best"
    assert _format_string(_opts(mode="mp4", quality="best")) == "bestvideo+bestaudio/best"
    assert "height<=720" in _format_string(_opts(mode="mp4", quality="720p"))
    assert "height<=1080" in _format_string(_opts(mode="mp4", quality="1080p"))


def test_mp3_postprocessors():
    o = build_ydl_opts(_opts(mode="mp3"))
    keys = [pp["key"] for pp in o["postprocessors"]]
    assert keys == ["FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"]
    assert o["writethumbnail"] is True
    assert "merge_output_format" not in o


def test_mp4_full_options():
    o = build_ydl_opts(
        _opts(
            mode="mp4",
            quality="1080p",
            sponsorblock="skip",
            cookies_from_browser="firefox",
            archive=True,
            archive_path=Path("/tmp/arch.txt"),
        )
    )
    keys = [pp["key"] for pp in o["postprocessors"]]
    assert keys[0] == "SponsorBlock"
    assert "ModifyChapters" in keys
    assert o["merge_output_format"] == "mp4"
    assert o["cookiesfrombrowser"] == ("firefox",)
    assert o["download_archive"] == "/tmp/arch.txt"


def test_toggles_off():
    o = build_ydl_opts(_opts(mode="mp3", embed_thumbnail=False, embed_metadata=False))
    keys = [pp["key"] for pp in o["postprocessors"]]
    assert keys == ["FFmpegExtractAudio"]
    assert "writethumbnail" not in o


def test_sponsorblock_mark_no_modify():
    o = build_ydl_opts(_opts(mode="mp3", sponsorblock="mark"))
    keys = [pp["key"] for pp in o["postprocessors"]]
    assert "SponsorBlock" in keys
    assert "ModifyChapters" not in keys


def test_resilience_and_template_opts():
    o = build_ydl_opts(_opts(mode="mp3"))
    assert o["noprogress"] is True
    assert o["retries"] >= 1
    assert o["fragment_retries"] >= 1
    # uploader falls back to channel, then a literal, so no blank folders
    assert "uploader,channel|Unknown Uploader" in o["outtmpl"]


def test_options_from_config_roundtrip():
    from yt_dld.config import DEFAULTS

    opts = DownloadOptions.from_config(dict(DEFAULTS), Path("/tmp/out"))
    assert opts.mode == "mp3"
    assert opts.workers == 3
    assert opts.out_dir == Path("/tmp/out")
