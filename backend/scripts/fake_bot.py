"""Simulation script (fake_bot.py) for Step 5A live ingestion.
Takes a meeting_id and two WAV files (or generates them with ffmpeg when --synthetic is used),
streams them as two different speakers over WebSocket with realistic timing,
then sends {"type":"end"}.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

# Add parent directory to path so modules can be imported if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def convert_to_pcm(wav_path: str | Path) -> bytes:
    """Convert an audio file to 16 kHz mono 16-bit PCM using FFmpeg.

    Exits with error if file does not exist, ffmpeg fails, or output < 1s.
    """
    path = Path(wav_path)
    if not path.is_file():
        print(f"Error: Input audio file does not exist: {wav_path}", file=sys.stderr)
        sys.exit(1)

    ffmpeg_cmd = "ffmpeg"
    try:
        from app.core.config import settings

        ffmpeg_cmd = settings.FFMPEG_PATH
    except Exception:  # noqa: BLE001, S110
        pass

    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as raw_out:
        out_path = raw_out.name

    try:
        cmd = [
            ffmpeg_cmd,
            "-y",
            "-i",
            str(path),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            print(f"Error: FFmpeg audio conversion failed for '{wav_path}': {err}", file=sys.stderr)
            sys.exit(1)

        pcm = Path(out_path).read_bytes()
        if len(pcm) < 32000:
            dur = len(pcm) / 32000.0
            print(
                f"Error: Converted audio from '{wav_path}' is empty or shorter than 1 second ({dur:.2f} s).",
                file=sys.stderr,
            )
            sys.exit(1)
        return pcm
    finally:
        Path(out_path).unlink(missing_ok=True)


def generate_synthetic_pcm(default_freq: int = 440, duration_s: int = 4) -> bytes:
    """Generate synthetic sine tone PCM (16 kHz mono 16-bit) using FFmpeg lavfi."""
    ffmpeg_cmd = "ffmpeg"
    try:
        from app.core.config import settings

        ffmpeg_cmd = settings.FFMPEG_PATH
    except Exception:  # noqa: BLE001, S110
        pass

    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as raw_out:
        out_path = raw_out.name

    try:
        cmd = [
            ffmpeg_cmd,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={default_freq}:duration={duration_s}",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            print(f"Error: FFmpeg synthetic audio generation failed: {err}", file=sys.stderr)
            sys.exit(1)

        pcm = Path(out_path).read_bytes()
        if len(pcm) < 32000:
            print("Error: Generated synthetic audio is shorter than 1 second.", file=sys.stderr)
            sys.exit(1)
        return pcm
    finally:
        Path(out_path).unlink(missing_ok=True)


def convert_or_generate_pcm(
    wav_path: str | Path | None,
    default_freq: int = 440,
    duration_s: int = 4,
    synthetic: bool = False,
) -> bytes:
    """Load audio or generate synthetic if explicitly requested."""
    if synthetic:
        if wav_path and Path(wav_path).is_file():
            return convert_to_pcm(wav_path)
        return generate_synthetic_pcm(default_freq=default_freq, duration_s=duration_s)

    if not wav_path:
        print("Error: Audio file path is required. Use --synthetic for synthetic audio.", file=sys.stderr)
        sys.exit(1)
    return convert_to_pcm(wav_path)


def stream_audio(ws, pcm1: bytes, pcm2: bytes, args: argparse.Namespace) -> None:
    """Stream audio chunks over the connected WebSocket."""
    bytes_per_chunk = int(16000 * 2 * (args.chunk_ms / 1000.0))
    if bytes_per_chunk <= 0:
        bytes_per_chunk = 32000

    chunks1 = [pcm1[i : i + bytes_per_chunk] for i in range(0, len(pcm1), bytes_per_chunk)]
    chunks2 = [pcm2[i : i + bytes_per_chunk] for i in range(0, len(pcm2), bytes_per_chunk)]

    if args.sequential:
        # Sequential mode: Speaker 1 then Speaker 2
        print(f"Streaming audio sequentially for speaker 1 ({args.name1})...")
        current_ms = 0
        for chunk in chunks1:
            meta = {
                "type": "chunk",
                "speaker_id": "bot_speaker_1",
                "speaker_name": args.name1,
                "start_ms": current_ms,
            }
            ws.send(json.dumps(meta))
            ws.send(chunk)
            current_ms += int(len(chunk) / 32)
            if not args.fast:
                time.sleep(args.chunk_ms / 1000.0)

        current_ms += 500

        print(f"Streaming audio sequentially for speaker 2 ({args.name2})...")
        for chunk in chunks2:
            meta = {
                "type": "chunk",
                "speaker_id": "bot_speaker_2",
                "speaker_name": args.name2,
                "start_ms": current_ms,
            }
            ws.send(json.dumps(meta))
            ws.send(chunk)
            current_ms += int(len(chunk) / 32)
            if not args.fast:
                time.sleep(args.chunk_ms / 1000.0)
    else:
        # Interleaved mode: concurrent streaming
        print(f"Streaming interleaved audio for {args.name1} and {args.name2}...")
        total_steps = max(len(chunks1), len(chunks2))
        for step in range(total_steps):
            start_ms = step * args.chunk_ms

            if step < len(chunks1):
                chunk1 = chunks1[step]
                meta1 = {
                    "type": "chunk",
                    "speaker_id": "bot_speaker_1",
                    "speaker_name": args.name1,
                    "start_ms": start_ms,
                }
                ws.send(json.dumps(meta1))
                ws.send(chunk1)

            if step < len(chunks2):
                chunk2 = chunks2[step]
                meta2 = {
                    "type": "chunk",
                    "speaker_id": "bot_speaker_2",
                    "speaker_name": args.name2,
                    "start_ms": start_ms,
                }
                ws.send(json.dumps(meta2))
                ws.send(chunk2)

            if not args.fast:
                time.sleep(args.chunk_ms / 1000.0)

    # End stream
    print("Sending end of meeting frame...")
    ws.send(json.dumps({"type": "end"}))
    print("Live streaming completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate live bot streaming audio chunks over WebSocket.")
    parser.add_argument("meeting_id", nargs="?", help="Meeting ID (source='join')")
    parser.add_argument("--meeting-id", dest="opt_meeting_id", help="Meeting ID")
    parser.add_argument("--wav1", help="Path to WAV audio file for speaker 1")
    parser.add_argument("--speaker1", "--name1", dest="name1", default="Alice", help="Display name for speaker 1")
    parser.add_argument("--wav2", help="Path to WAV audio file for speaker 2")
    parser.add_argument("--speaker2", "--name2", dest="name2", default="Bob", help="Display name for speaker 2")
    parser.add_argument("--silent2", action="store_true", help="Send digital silence for speaker 2")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Generate synthetic tone audio instead of requiring input audio files",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Stream speakers sequentially instead of interleaved concurrently",
    )
    parser.add_argument("--url", default="ws://127.0.0.1:8000", help="Base WebSocket URL or endpoint")
    parser.add_argument("--token", default=None, help="Shared bot ingest secret token (or set BOT_INGEST_TOKEN env)")
    parser.add_argument("--chunk-ms", type=int, default=1000, help="Chunk duration in ms (default 1000 ms)")
    parser.add_argument("--fast", action="store_true", help="Send chunks immediately without sleeping")

    args = parser.parse_args()
    meeting_id = args.meeting_id or args.opt_meeting_id
    if not meeting_id:
        print("Error: meeting_id is required.", file=sys.stderr)
        sys.exit(1)

    token = (args.token or os.environ.get("BOT_INGEST_TOKEN", "")).strip()
    if not token or token == "change-me":
        print(
            "Error: BOT_INGEST_TOKEN is not set. Please set the BOT_INGEST_TOKEN environment variable or pass --token <token>.",
            file=sys.stderr,
        )
        sys.exit(1)

    # 1. Prepare audio streams
    if args.synthetic:
        pcm1 = convert_or_generate_pcm(args.wav1, default_freq=440, duration_s=4, synthetic=True)
        if args.silent2:
            pcm2 = b"\x00" * len(pcm1)
        else:
            pcm2 = convert_or_generate_pcm(args.wav2, default_freq=880, duration_s=4, synthetic=True)
    else:
        if not args.wav1:
            print("Error: --wav1 audio file is required (or pass --synthetic).", file=sys.stderr)
            sys.exit(1)
        pcm1 = convert_to_pcm(args.wav1)

        if args.silent2:
            pcm2 = b"\x00" * len(pcm1)
        else:
            if not args.wav2:
                print("Error: --wav2 audio file is required (or pass --synthetic or --silent2).", file=sys.stderr)
                sys.exit(1)
            pcm2 = convert_to_pcm(args.wav2)

    # Print real stream durations before sending
    dur1 = len(pcm1) / 32000.0
    dur2 = len(pcm2) / 32000.0
    print(f"Speaker 1 ({args.name1}) stream duration: {dur1:.2f} s")
    print(f"Speaker 2 ({args.name2}) stream duration: {dur2:.2f} s")

    # 2. Prepare WebSocket URL
    base_url = args.url.rstrip("/")
    if base_url.startswith("http://"):
        base_url = "ws://" + base_url[7:]
    elif base_url.startswith("https://"):
        base_url = "wss://" + base_url[8:]

    if "/stream" in base_url:
        stream_url = base_url
    else:
        stream_url = f"{base_url}/api/v1/meetings/{meeting_id}/stream"

    # Only print meeting ID and "Connecting..." (NEVER print token or URL containing it)
    print(f"Meeting ID: {meeting_id}")
    print("Connecting...")

    headers = {"x-bot-token": token}

    try:
        with connect(stream_url, additional_headers=headers) as ws:
            print("Connected successfully!")
            stream_audio(ws, pcm1, pcm2, args)
    except ConnectionClosed as exc:
        code = exc.rcvd.code if getattr(exc, "rcvd", None) else getattr(exc, "code", "unknown")
        reason = exc.rcvd.reason if getattr(exc, "rcvd", None) else getattr(exc, "reason", "")
        print(f"Connection closed by server: code={code}, reason={reason}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code:
            print(f"Connection rejected by server: status_code={status_code}")
        else:
            print(f"Connection error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
