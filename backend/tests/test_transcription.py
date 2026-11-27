"""Tests for Whisper transcription service and dropped-speech filtering."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.core.config import settings
from app.services.transcription import (
    set_whisper_model,
    transcribe_audio,
)


class TestTranscriptionFilteringUnit:
    """Unit tests using fake segment objects (no real Whisper model inference)."""

    def test_filter_high_nsp_high_logprob_is_kept(self, tmp_path):
        """A segment with high no_speech_prob but high confidence logprob is REAL speech and must be kept."""
        wav_file = tmp_path / "fake.wav"
        wav_file.write_bytes(b"RIFF....WAVE")

        # Fake segment: high nsp (0.85) but high confidence logprob (-0.31)
        fake_seg = MagicMock()
        fake_seg.start = 23.90
        fake_seg.end = 29.90
        fake_seg.text = "Maybe you want to open your data safely to the club or use smart AI."
        fake_seg.no_speech_prob = 0.8522
        fake_seg.avg_logprob = -0.3135

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([fake_seg], MagicMock())
        set_whisper_model(mock_model)

        results = transcribe_audio(wav_file, language="en")

        assert len(results) == 1
        assert results[0]["start_time"] == 23.90
        assert results[0]["end_time"] == 29.90
        assert "open your data safely" in results[0]["text"]

    def test_filter_high_nsp_low_logprob_is_dropped_and_logged(self, tmp_path, caplog):
        """A segment with high no_speech_prob AND low confidence logprob is dropped and logged at INFO."""
        wav_file = tmp_path / "fake.wav"
        wav_file.write_bytes(b"RIFF....WAVE")

        # Fake segment: high nsp (0.85) AND low confidence logprob (-1.5)
        fake_seg = MagicMock()
        fake_seg.start = 10.0
        fake_seg.end = 15.0
        fake_seg.text = "hallucinated murmuring or background rustle"
        fake_seg.no_speech_prob = 0.85
        fake_seg.avg_logprob = -1.50

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([fake_seg], MagicMock())
        set_whisper_model(mock_model)

        with caplog.at_level(logging.INFO):
            results = transcribe_audio(wav_file, language="en")

        assert results == []

        # Verify logged at INFO with time range, no_speech_prob, avg_logprob, and text
        drop_logs = [record for record in caplog.records if "Dropping segment" in record.message]
        assert len(drop_logs) == 1
        msg = drop_logs[0].message
        assert "10.00 - 15.00" in msg
        assert "no_speech_prob=0.8500" in msg
        assert "avg_logprob=-1.5000" in msg
        assert "hallucinated murmuring" in msg

    def test_filter_low_nsp_is_kept(self, tmp_path):
        """A segment with low no_speech_prob is kept even if avg_logprob is low."""
        wav_file = tmp_path / "fake.wav"
        wav_file.write_bytes(b"RIFF....WAVE")

        fake_seg = MagicMock()
        fake_seg.start = 5.0
        fake_seg.end = 8.0
        fake_seg.text = "quiet but clearly spoken sentence"
        fake_seg.no_speech_prob = 0.20
        fake_seg.avg_logprob = -1.50

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([fake_seg], MagicMock())
        set_whisper_model(mock_model)

        results = transcribe_audio(wav_file, language="en")

        assert len(results) == 1
        assert results[0]["text"] == "quiet but clearly spoken sentence"


class TestRealWhisperRegression:
    """Regression test running real Whisper model once on the investigation audio clip."""

    def test_real_whisper_retains_open_your_data_safely(self, tmp_path):
        """Verify real Whisper retains 'open your data safely' (previously dropped by no_speech_prob > 0.6)."""
        backend_dir = Path(__file__).resolve().parent.parent
        meeting_rel = Path("3ad44b6f-f369-4549-9a91-25ed5bb27091") / "original.mp4"
        candidate_paths = [
            backend_dir / "media" / meeting_rel,
            Path("backend/media") / meeting_rel,
            Path("media") / meeting_rel,
            Path(settings.MEDIA_DIR) / meeting_rel,
        ]
        src_file = next((p for p in candidate_paths if p.is_file()), None)
        if not src_file:
            pytest.skip(f"Investigation media clip not found in {candidate_paths}")

        # Copy clip read-only to tmp_path
        clip_copy = tmp_path / "clip.mp4"
        shutil.copy2(src_file, clip_copy)

        # Convert first 30 seconds (Buffer 1 where the segment occurs) to 16 kHz mono WAV
        wav_file = tmp_path / "buffer1.wav"
        ffmpeg_cmd = getattr(settings, "FFMPEG_PATH", "ffmpeg")
        cmd = [
            ffmpeg_cmd,
            "-y",
            "-i",
            str(clip_copy),
            "-t",
            "30",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(wav_file),
        ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        assert proc.returncode == 0, f"FFmpeg failed: {proc.stderr.decode('utf-8', errors='replace')}"

        # Reset singleton to ensure real WhisperModel is loaded
        set_whisper_model(None)

        results = transcribe_audio(wav_file, language="en")
        combined_text = " ".join(s["text"] for s in results)

        # The previously dropped segment must now be present
        assert "open your data safely" in combined_text, (
            f"Expected 'open your data safely' in transcript, but got: {combined_text}"
        )
