"""Offline DJ tests: queue engine, commands, validation, music profile."""
import copy
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camfrog_music_gui as c  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg():
    x = c.load_cfg(ROOT / "config.example.json")
    x["dry_run"] = True
    x["status"]["enabled"] = False
    x["autoreply"]["enabled"] = True
    x["autoreply"]["own_nickname"] = "DJBot"
    x["autoreply"]["rules"] = []
    x["dj"]["enabled"] = True
    return x


@pytest.fixture(autouse=True)
def _base(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "BASE", tmp_path)
    c.LANG = "en"
    yield
    c.LANG = "en"


def _dj_runner(cfg, monkeypatch, lines):
    r = c.Runner(cfg)
    r.history, r.input, r.chat_win = object(), object(), object()
    sent = []
    monkeypatch.setattr(r, "send", lambda ctrl, text, btn=None, win=None: sent.append(text) or True)
    monkeypatch.setattr(c, "read_chat", lambda hist, tail: "\n".join(lines))
    return r, sent


def test_dj_request_queues_and_persists(cfg, monkeypatch, tmp_path):
    r, sent = _dj_runner(cfg, monkeypatch, ["Ann: !request hello world"])
    r.do_dj(True)
    assert any("Now playing" in s and "hello world" in s for s in sent)
    raw = json.loads((tmp_path / "dj_queue.json").read_text(encoding="utf-8"))
    assert raw["current"] == {"title": "hello world", "user": "Ann"}
    r2, sent2 = _dj_runner(cfg, monkeypatch, ["Bob: !request second song"])
    r2.dj_prev = []
    r2.do_dj(True)
    assert any("Queued #1" in s for s in sent2)


def test_dj_first_request_starts_playing_immediately(cfg, monkeypatch):
    r, sent = _dj_runner(cfg, monkeypatch, ["Ann: !request song a"])
    r.do_dj(True)
    assert any("Now playing" in s for s in sent)


def test_dj_caps_and_duplicates(cfg, monkeypatch):
    r, sent = _dj_runner(cfg, monkeypatch, [
        "Ann: !request one", "Ann: !request two", "Ann: !request three",
        "Ann: !request four"])
    r.do_dj(True)
    assert len([s for s in sent if "Queued" in s or "Now playing" in s]) == 4
    r2, sent2 = _dj_runner(cfg, monkeypatch, ["Ann: !request five"])
    r2.dj_prev = []
    # same persisted queue file: reload state then exceed cap
    r2.do_dj(True)
    assert any("already has 3 songs" in s for s in sent2)
    r3, sent3 = _dj_runner(cfg, monkeypatch, ["Bob: !request ONE"])
    r3.dj_prev = []
    r3.do_dj(True)
    assert any("playing now" in s for s in sent3)
    r4, sent4 = _dj_runner(cfg, monkeypatch, ["Bob: !request"])
    r4.dj_prev = []
    r4.do_dj(True)
    assert any("give a song name" in s for s in sent4)


def test_dj_queue_current_help(cfg, monkeypatch):
    r, sent = _dj_runner(cfg, monkeypatch, ["Ann: !request song a"])
    r.do_dj(True)
    r2, sent2 = _dj_runner(cfg, monkeypatch, ["Bob: !queue", "Bob: !current", "Bob: !help"])
    r2.dj_prev = []
    r2.do_dj(True)
    assert any("queue is empty" in s for s in sent2)
    assert any("current: song a" in s for s in sent2)
    assert any("!request" in s for s in sent2)


def test_dj_skip_rules(cfg, monkeypatch):
    r, sent = _dj_runner(cfg, monkeypatch,
                         ["Ann: !request song a", "Bob: !request song b"])
    r.do_dj(True)
    stranger, stranger_sent = _dj_runner(cfg, monkeypatch, ["Zed: !skip"])
    stranger.dj_prev = []
    stranger.do_dj(True)
    assert any("only the requester" in s for s in stranger_sent)
    owner, owner_sent = _dj_runner(cfg, monkeypatch, ["DJBot: !skip"])
    owner.dj_prev = []
    owner.do_dj(True)  # own nick lines are never acted on
    assert owner_sent == []
    req, req_sent = _dj_runner(cfg, monkeypatch, ["Ann: !skip"])
    req.dj_prev = []
    req.do_dj(True)
    assert any("Now playing: song b" in s for s in req_sent)


def test_dj_ignores_plain_lines_and_unknown_commands(cfg, monkeypatch):
    r, sent = _dj_runner(cfg, monkeypatch, ["Ann: hello there", "Bob: !dance"])
    r.do_dj(True)
    assert sent == []


def test_dj_does_not_run_when_disabled_or_idle(cfg, monkeypatch):
    cfg["dj"]["enabled"] = False
    r, sent = _dj_runner(cfg, monkeypatch, ["Ann: !request x"])
    r.do_dj(True)
    assert sent == []
    cfg["dj"]["enabled"] = True
    r2, sent2 = _dj_runner(cfg, monkeypatch, ["Ann: !request x"])
    r2.do_dj(False)
    assert sent2 == []


def test_do_chat_yields_dj_lines_to_dj(cfg, monkeypatch):
    cfg["autoreply"]["rules"] = [{"pattern": "!request", "reply": "ROOM"}]
    r = c.Runner(cfg)
    r.history, r.input, r.chat_win = object(), object(), object()
    sent = []
    monkeypatch.setattr(r, "send", lambda ctrl, text, btn=None, win=None: sent.append(text) or True)
    monkeypatch.setattr(c, "read_chat", lambda hist, tail: "Ann: !request song a")
    r.do_chat(True)
    assert "ROOM" not in sent


def test_dj_local_backend_needs_mp3_file(cfg, monkeypatch, tmp_path):
    cfg["dj"]["audio_backend"] = "local"
    music = tmp_path / "music"
    music.mkdir()
    (music / "mysong.mp3").write_bytes(b"id3")
    cfg["dj"]["music_dir"] = str(music)
    r, sent = _dj_runner(cfg, monkeypatch, ["Ann: !request nosuch"])
    r.do_dj(True)
    assert any("no supported audio file found" in s for s in sent)
    r2, sent2 = _dj_runner(cfg, monkeypatch, ["Ann: !request mysong"])
    r2.dj_prev = []
    r2.do_dj(True)
    assert any("Now playing: mysong" in s for s in sent2)


def test_dj_audio_duration_reads_mci_length(tmp_path, monkeypatch):
    commands = []

    def fake_mci(command):
        commands.append(command)
        return "1250" if command.endswith("length") else ""

    monkeypatch.setattr(c, "_dj_windows_audio", lambda: True)
    monkeypatch.setattr(c, "_dj_mci_command", fake_mci)
    path = tmp_path / "My Song.mp3"

    assert c.dj_audio_duration(path) == 1.25
    assert any(command.startswith('open "') and " alias " in command
               and " type " not in command for command in commands)
    assert any("time format milliseconds" in command for command in commands)
    assert commands[-1].startswith("close ")


@pytest.mark.skipif(os.name != "nt", reason="needs Windows MCI audio")
def test_dj_windows_mci_reads_wav_duration(tmp_path):
    import wave

    song = tmp_path / "MCI audio test.wav"
    with wave.open(str(song), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 800)

    assert c.dj_audio_duration(song) == pytest.approx(0.1, abs=0.02)


@pytest.mark.parametrize("extension", ["wav", "mp3", "flac", "mid"])
def test_dj_playback_uses_mci_auto_type_and_closes_previous_track(
        extension, tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(c, "_dj_windows_audio", lambda: True)
    monkeypatch.setattr(c, "_dj_mci_command", lambda command: commands.append(command) or "")
    path = tmp_path / "Music Folder" / f"My Song.{extension}"

    assert c.dj_play(path) is True
    assert any(command.startswith("close ") for command in commands)
    assert any(command.startswith('open "') and f"My Song.{extension}" in command
               and " alias " in command and " type " not in command
               for command in commands)
    assert any(command.startswith("play ") for command in commands)
    c.dj_stop()
    assert commands[-2].startswith("stop ")
    assert commands[-1].startswith("close ")


def test_dj_local_request_plays_matching_mp3(cfg, monkeypatch, tmp_path):
    cfg["dry_run"] = False
    cfg["dj"]["audio_backend"] = "local"
    music = tmp_path / "music"
    music.mkdir()
    song = music / "requested song.mp3"
    song.write_bytes(b"id3")
    cfg["dj"]["music_dir"] = str(music)
    played = []
    monkeypatch.setattr(c, "dj_audio_duration", lambda path: 42.0)
    monkeypatch.setattr(c, "dj_play", lambda path: played.append(path) or True)
    runner, sent = _dj_runner(cfg, monkeypatch, ["Ann: !request requested song"])

    runner.do_dj(True)

    assert played == [song]
    assert runner.dj_length == 42.0
    assert any("Now playing: requested song" in line for line in sent)


def test_dj_auto_advance_moves_on_after_duration(cfg, monkeypatch):
    r, sent = _dj_runner(cfg, monkeypatch, ["Ann: !request a", "Bob: !request b"])
    r.do_dj(True)
    assert r.dj_started == 0.0  # dry-run never arms audio timers
    r.dj_started = time.monotonic() - 60
    r.dj_length = 30.0
    r2, sent2 = _dj_runner(cfg, monkeypatch, [])
    # carry runtime state across instances like consecutive ticks would
    r2.dj_started, r2.dj_length, r2.dj_prev = r.dj_started, r.dj_length, []
    r2.do_dj(True)
    assert any("Now playing: b" in s for s in sent2)


def test_dj_find_song_matching(tmp_path):
    music = tmp_path / "m"
    music.mkdir()
    (music / "Hello World.MP3").write_bytes(b"id3")
    (music / "other.mp3").write_bytes(b"id3")
    assert c.dj_find_song(music, "hello").name == "Hello World.MP3"
    assert c.dj_find_song(music, "missing") is None
    assert c.dj_find_song(tmp_path / "nodir", "x") is None


def test_dj_find_song_matches_supported_audio_files(tmp_path):
    music = tmp_path / "audio"
    music.mkdir()
    (music / "not audio.txt").write_text("not audio", encoding="utf-8")

    for extension in c.DJ_AUDIO_EXTENSIONS:
        for old_file in music.glob("Hello World.*"):
            old_file.unlink()
        expected = music / f"Hello World{extension}"
        expected.write_bytes(b"audio")
        assert c.dj_find_song(music, "hello") == expected
    assert c.dj_find_song(music, "not audio") is None


def test_dj_local_play_failure_does_not_announce_now_playing(cfg, monkeypatch, tmp_path):
    cfg["dry_run"] = False
    cfg["dj"]["audio_backend"] = "local"
    music = tmp_path / "music"
    music.mkdir()
    (music / "silent failure.mp3").write_bytes(b"audio")
    cfg["dj"]["music_dir"] = str(music)
    monkeypatch.setattr(c, "dj_audio_duration", lambda _path: None)
    monkeypatch.setattr(c, "dj_play", lambda _path: False)
    runner, sent = _dj_runner(cfg, monkeypatch, ["Ann: !request silent failure"])

    runner.do_dj(True)

    assert any("could not start local audio" in line for line in sent)
    assert not any("Now playing" in line for line in sent)


def test_dj_validation(cfg):
    cfg["autoreply"]["enabled"] = False
    errs, _ = c.validate(cfg)
    assert any("autoreply.enabled" in e for e in errs)
    cfg["autoreply"]["enabled"] = True
    for bad in ({"prefix": ""}, {"prefix": "/x"}, {"max_per_user": 0},
                {"audio_backend": "mp3"}, {"announce_now": ""}, {"queue_file": ""}):
        bad_cfg = copy.deepcopy(cfg)
        bad_cfg["dj"].update(bad)
        assert c.validate(bad_cfg)[0], bad
    assert c.validate(cfg)[0] == []


def test_music_profile_disables_status_and_im(monkeypatch):
    monkeypatch.setattr(c, "APP_PROFILE", "music")
    out = c.apply_app_profile(copy.deepcopy(c.DEFAULTS))
    assert out["status"]["enabled"] is False
    assert out["autoreply_im"]["enabled"] is False
    assert out["autoreply"]["enabled"] is True
    assert "run" in c.PROFILE_COMMANDS["music"]
    assert "marquee" not in c.PROFILE_COMMANDS["music"]


def test_dj_queue_persist_roundtrip(tmp_path):
    q = c.DJQueue(tmp_path / "q.json")
    q.load()
    assert q.current is None and q.queue == []
    assert q.add("Song", "Ann") == 1
    q.save()
    q2 = c.DJQueue(tmp_path / "q.json")
    q2.load()
    assert q2.queue == [{"title": "Song", "user": "Ann"}]


def test_dj_skip_semantics():
    q = c.DJQueue(Path("nope.json"))
    with pytest.raises(c.DJError):
        q.skip("Ann", "owner")
    q.current = {"title": "Song", "user": "Ann"}
    q.queue = [{"title": "Next", "user": "Bob"}]
    with pytest.raises(c.DJError):
        q.skip("Zed", "owner")
    assert q.skip("ANN", "someone") == {"title": "Next", "user": "Bob"}
    assert q.skip("owner", "owner") is None
    assert q.current is None
