"""Windows-only integration checks for the native MCI audio backend."""

import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camfrog_music_gui as c


def test_dj_windows_mci_reads_wav_duration(tmp_path, caplog):
    if sys.platform != "win32":
        pytest.fail("This integration test must run on Windows.")

    song = tmp_path / "MCI audio integration test.wav"
    with wave.open(str(song), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 800)

    with caplog.at_level("DEBUG", logger="camfrog_music"):
        duration = c.dj_audio_duration(song)

    assert duration is not None, (
        "[DBG-MCI-4f1c] The native Windows MCI backend could not read the WAV file. "
        f"MCI diagnostic: {caplog.text.strip() or 'no debug detail was recorded'}"
    )
    assert duration == pytest.approx(0.1, abs=0.02)
