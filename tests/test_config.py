import importlib


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    import yt_dld.config as cfgmod

    importlib.reload(cfgmod)

    data = cfgmod.load_config()
    assert data["mode"] == "mp3"  # default

    data["mode"] = "mp4"
    data["threads"] = 6
    data["archive"] = True
    data["out_dir"] = "~/Videos/yt"
    path = cfgmod.save_config(data)
    assert path.exists()

    again = cfgmod.load_config()
    assert again["mode"] == "mp4"
    assert again["threads"] == 6
    assert again["archive"] is True
    assert again["out_dir"] == "~/Videos/yt"


def test_unknown_keys_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    import yt_dld.config as cfgmod

    importlib.reload(cfgmod)

    p = cfgmod.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('mode = "flac"\nbogus_key = "x"\n')

    data = cfgmod.load_config()
    assert data["mode"] == "flac"
    assert "bogus_key" not in data
