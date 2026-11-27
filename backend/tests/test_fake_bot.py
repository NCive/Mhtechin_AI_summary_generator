"""Unit tests for scripts/fake_bot.py.
Verifies argument handling, missing file errors, duration output,
token privacy, interleaving order of chunks, and clean server disconnects.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from scripts.fake_bot import (
    convert_to_pcm,
    main,
    stream_audio,
)
from websockets.exceptions import ConnectionClosed
from websockets.frames import Close


class TestFakeBotScript:
    def test_argument_handling_missing_meeting_id(self, capsys):
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": "some-token"}), \
             patch("sys.argv", ["fake_bot.py"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "meeting_id is required" in captured.err

    def test_argument_handling_missing_token(self, capsys):
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": ""}, clear=True), \
             patch("sys.argv", ["fake_bot.py", "mtg-123"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "BOT_INGEST_TOKEN is not set" in captured.err

    def test_argument_handling_change_me_token(self, capsys):
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": "change-me"}), \
             patch("sys.argv", ["fake_bot.py", "mtg-123"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "BOT_INGEST_TOKEN is not set" in captured.err

    def test_missing_wav1_without_synthetic_exits(self, capsys):
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": "valid-token"}), \
             patch("sys.argv", ["fake_bot.py", "mtg-123"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--wav1 audio file is required" in captured.err

    def test_missing_wav2_without_synthetic_exits(self, capsys, tmp_path):
        dummy_wav = tmp_path / "valid.wav"
        dummy_wav.write_bytes(b"dummy")
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": "valid-token"}), \
             patch("sys.argv", ["fake_bot.py", "mtg-123", "--wav1", str(dummy_wav)]), \
             patch("scripts.fake_bot.convert_to_pcm", return_value=b"\x01\x02" * 16000), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--wav2 audio file is required" in captured.err

    def test_nonexistent_audio_file_exits(self, capsys):
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": "valid-token"}), \
             patch("sys.argv", ["fake_bot.py", "mtg-123", "--wav1", "nonexistent_file_xyz.wav"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    def test_audio_shorter_than_1s_exits(self, capsys, tmp_path):
        tiny_wav = tmp_path / "short.wav"
        tiny_wav.write_bytes(b"RIFF....WAVE")
        # 16000 samples/sec * 2 bytes = 32000 bytes per second. 500 bytes is < 1s
        with patch("scripts.fake_bot.subprocess.run") as mock_run, \
             patch("pathlib.Path.read_bytes", return_value=b"\x00" * 500), \
             pytest.raises(SystemExit) as exc_info:
            mock_run.return_value = MagicMock(returncode=0)
            convert_to_pcm(str(tiny_wav))
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "empty or shorter than 1 second" in captured.err

    def test_never_prints_token_in_stdout_or_stderr(self, capsys):
        secret_token = "SUPER_SECRET_TOKEN_XYZ_987654321"
        mock_ws = MagicMock()
        mock_ws.__enter__.return_value = mock_ws

        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": secret_token}), \
             patch("sys.argv", ["fake_bot.py", "mtg-token-test", "--synthetic", "--fast"]), \
             patch("scripts.fake_bot.generate_synthetic_pcm", return_value=b"\x01\x02" * 16000), \
             patch("scripts.fake_bot.connect", return_value=mock_ws) as mock_conn:
            main()

        captured = capsys.readouterr()
        all_output = captured.out + captured.err
        assert secret_token not in all_output
        assert "mtg-token-test" in captured.out
        assert "Connecting..." in captured.out

        # Check token was sent in headers
        mock_conn.assert_called_once()
        _, kwargs = mock_conn.call_args
        assert kwargs["additional_headers"]["x-bot-token"] == secret_token

    def test_never_prints_token_on_server_disconnect(self, capsys):
        secret_token = "SECRET_TOKEN_ON_FAIL"
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": secret_token}), \
             patch("sys.argv", ["fake_bot.py", "mtg-fail-test", "--synthetic", "--fast"]), \
             patch("scripts.fake_bot.generate_synthetic_pcm", return_value=b"\x01\x02" * 16000), \
             patch("scripts.fake_bot.connect", side_effect=ConnectionClosed(Close(1008, "Policy Violation"), None)), \
             pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        all_output = captured.out + captured.err
        assert secret_token not in all_output
        assert "Connection closed by server: code=1008, reason=Policy Violation" in captured.out

    def test_interleaving_order_of_chunks(self):
        """By default, chunks from speaker 1 and speaker 2 should interleave ~1s chunks."""
        mock_ws = MagicMock()
        args = MagicMock(chunk_ms=1000, fast=True, sequential=False, name1="Alice", name2="Bob")
        # 2 seconds each = 2 chunks each (64000 bytes each)
        pcm1 = b"\x01\x00" * 32000
        pcm2 = b"\x02\x00" * 32000

        stream_audio(mock_ws, pcm1, pcm2, args)

        # Collect text and binary frames
        sent_items = [call_args[0][0] for call_args in mock_ws.send.call_args_list]
        meta_items = [json.loads(item) for item in sent_items if isinstance(item, str) and item.startswith("{")]

        # Expected interleaving:
        # Step 0: Spk1 (start_ms=0), Spk2 (start_ms=0)
        # Step 1: Spk1 (start_ms=1000), Spk2 (start_ms=1000)
        # End: type="end"
        assert len(meta_items) == 5
        assert meta_items[0]["speaker_id"] == "bot_speaker_1"
        assert meta_items[0]["start_ms"] == 0
        assert meta_items[1]["speaker_id"] == "bot_speaker_2"
        assert meta_items[1]["start_ms"] == 0
        assert meta_items[2]["speaker_id"] == "bot_speaker_1"
        assert meta_items[2]["start_ms"] == 1000
        assert meta_items[3]["speaker_id"] == "bot_speaker_2"
        assert meta_items[3]["start_ms"] == 1000
        assert meta_items[4]["type"] == "end"

    def test_sequential_order_of_chunks(self):
        """When --sequential is specified, all speaker 1 chunks are sent before speaker 2."""
        mock_ws = MagicMock()
        args = MagicMock(chunk_ms=1000, fast=True, sequential=True, name1="Alice", name2="Bob")
        pcm1 = b"\x01\x00" * 32000
        pcm2 = b"\x02\x00" * 32000

        stream_audio(mock_ws, pcm1, pcm2, args)

        sent_items = [call_args[0][0] for call_args in mock_ws.send.call_args_list]
        meta_items = [json.loads(item) for item in sent_items if isinstance(item, str) and item.startswith("{")]

        assert len(meta_items) == 5
        assert meta_items[0]["speaker_id"] == "bot_speaker_1"
        assert meta_items[1]["speaker_id"] == "bot_speaker_1"
        assert meta_items[2]["speaker_id"] == "bot_speaker_2"
        assert meta_items[3]["speaker_id"] == "bot_speaker_2"
        assert meta_items[4]["type"] == "end"

    def test_silent2_flag(self):
        mock_ws = MagicMock()
        mock_ws.__enter__.return_value = mock_ws
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": "valid-tok"}), \
             patch("sys.argv", ["fake_bot.py", "mtg-silent-test", "--silent2", "--fast", "--synthetic"]), \
             patch("scripts.fake_bot.connect", return_value=mock_ws), \
             patch("scripts.fake_bot.generate_synthetic_pcm", return_value=b"\x01\x02" * 16000):
            main()

        # Binary frames sent to ws.send
        binary_frames = [call_args[0][0] for call_args in mock_ws.send.call_args_list if isinstance(call_args[0][0], bytes)]
        # Speaker 2 sends silence (all 0x00)
        assert any(frame == b"\x00" * len(frame) for frame in binary_frames)

    def test_durations_printed_before_sending(self, capsys):
        mock_ws = MagicMock()
        mock_ws.__enter__.return_value = mock_ws
        with patch.dict(os.environ, {"BOT_INGEST_TOKEN": "valid-tok"}), \
             patch("sys.argv", ["fake_bot.py", "mtg-dur-test", "--synthetic", "--fast"]), \
             patch("scripts.fake_bot.connect", return_value=mock_ws), \
             patch("scripts.fake_bot.generate_synthetic_pcm", return_value=b"\x01\x02" * 16000):
            main()

        captured = capsys.readouterr()
        assert "Speaker 1 (Alice) stream duration: 1.00 s" in captured.out
        assert "Speaker 2 (Bob) stream duration: 1.00 s" in captured.out
