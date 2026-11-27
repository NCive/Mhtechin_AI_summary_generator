"""Simulation script (fake_bot.py) for Step 5A live ingestion.
Takes a meeting_id and two WAV files (or generates them with ffmpeg),
streams them as two different speakers over WebSocket with realistic timing,
then sends {"type":"end"}.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

# Add parent directory to path so modules can be imported if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class SimpleWebSocketClient:
    """Minimal RFC-6455 compliant WebSocket client using standard library sockets."""

    def __init__(self, url: str) -> None:
        self.url = url
        parsed = urlparse(url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        self.resource = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
        self.sock: socket.socket | None = None

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        sec_key = base64.b64encode(os.urandom(16)).decode("ascii")

        req = (
            f"GET {self.resource} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {sec_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        self.sock.sendall(req.encode("ascii"))

        # Read response headers
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            response += chunk

        status_line = response.split(b"\r\n")[0].decode("latin-1", errors="replace")
        if not status_line.startswith("HTTP/1.1 101"):
            raise ConnectionError(f"WebSocket handshake failed: {status_line}")

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if not self.sock:
            raise ConnectionError("Socket is not connected")

        length = len(payload)
        mask_key = os.urandom(4)

        header = bytearray()
        # Fin bit = 1, RSV = 0, Opcode
        header.append(0x80 | opcode)

        # Mask bit = 1 (client frames MUST be masked)
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))

        header.extend(mask_key)

        # Mask payload
        masked = bytearray(length)
        for i in range(length):
            masked[i] = payload[i] ^ mask_key[i % 4]

        self.sock.sendall(header + masked)

    def send_text(self, text: str) -> None:
        self._send_frame(opcode=0x1, payload=text.encode("utf-8"))

    def send_bytes(self, data: bytes) -> None:
        self._send_frame(opcode=0x2, payload=data)

    def close(self) -> None:
        if self.sock:
            try:
                # Send close frame
                self._send_frame(opcode=0x8, payload=b"")
                self.sock.close()
            except Exception:  # noqa: BLE001, S110
                pass
            finally:
                self.sock = None


def convert_or_generate_pcm(wav_path: str | None, default_freq: int = 440, duration_s: int = 4) -> bytes:
    """Convert an audio file to 16 kHz mono 16-bit PCM using FFmpeg, or generate a tone if no file provided."""
    ffmpeg_cmd = "ffmpeg"
    try:
        from app.core.config import settings
        ffmpeg_cmd = settings.FFMPEG_PATH
    except Exception:  # noqa: BLE001, S110
        pass

    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as raw_out:
        out_path = raw_out.name

    try:
        if wav_path and Path(wav_path).is_file():
            cmd = [
                ffmpeg_cmd, "-y", "-i", str(wav_path),
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1", out_path,
            ]
        else:
            # Generate synthetic tone
            cmd = [
                ffmpeg_cmd, "-y", "-f", "lavfi",
                "-i", f"sine=frequency={default_freq}:duration={duration_s}",
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1", out_path,
            ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {proc.stderr.decode('utf-8', errors='replace')}")

        return Path(out_path).read_bytes()
    finally:
        Path(out_path).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate live bot streaming audio chunks over WebSocket.")
    parser.add_argument("meeting_id", nargs="?", help="Meeting ID (source='join')")
    parser.add_argument("--meeting-id", dest="opt_meeting_id", help="Meeting ID")
    parser.add_argument("--wav1", help="Path to WAV audio file for speaker 1")
    parser.add_argument("--speaker1", "--name1", dest="name1", default="Alice", help="Display name for speaker 1")
    parser.add_argument("--wav2", help="Path to WAV audio file for speaker 2")
    parser.add_argument("--speaker2", "--name2", dest="name2", default="Bob", help="Display name for speaker 2")
    parser.add_argument("--silent2", action="store_true", help="Send digital silence for speaker 2")
    parser.add_argument("--url", default="ws://127.0.0.1:8000", help="Base WebSocket URL or endpoint")
    parser.add_argument("--token", default=None, help="Shared bot ingest secret token (or set BOT_INGEST_TOKEN env)")
    parser.add_argument("--chunk-ms", type=int, default=1000, help="Chunk duration in ms (default 1000 ms)")
    parser.add_argument("--fast", action="store_true", help="Send chunks immediately without sleeping")

    args = parser.parse_args()
    meeting_id = args.meeting_id or args.opt_meeting_id
    if not meeting_id:
        print("Error: meeting_id is required.")
        sys.exit(1)

    token = (args.token or os.environ.get("BOT_INGEST_TOKEN", "")).strip()
    if not token or token == "change-me":
        print("Error: BOT_INGEST_TOKEN is not set. Please set the BOT_INGEST_TOKEN environment variable or pass --token <token>.")
        sys.exit(1)

    # Prepare stream URL
    base_url = args.url.rstrip("/")
    if "/stream" in base_url:
        stream_url = f"{base_url}?token={token}"
    else:
        stream_url = f"{base_url}/api/v1/meetings/{meeting_id}/stream?token={token}"

    print(f"Connecting to {stream_url}...")
    client = SimpleWebSocketClient(stream_url)
    client.connect()
    print("Connected successfully!")

    print("Preparing audio streams...")
    pcm1 = convert_or_generate_pcm(args.wav1, default_freq=440, duration_s=4)
    if args.silent2:
        print(f"Generating digital silence for speaker 2 ({args.name2})...")
        pcm2 = b"\x00\x00" * (16000 * 4)
    else:
        pcm2 = convert_or_generate_pcm(args.wav2, default_freq=880, duration_s=4)

    bytes_per_chunk = int(16000 * 2 * (args.chunk_ms / 1000.0))  # 32 bytes per ms
    current_ms = 0

    try:
        # Stream Speaker 1
        print(f"Streaming audio for speaker 1 ({args.name1})...")
        for offset in range(0, len(pcm1), bytes_per_chunk):
            chunk = pcm1[offset : offset + bytes_per_chunk]
            meta = {
                "type": "chunk",
                "speaker_id": "bot_speaker_1",
                "speaker_name": args.name1,
                "start_ms": current_ms,
            }
            client.send_text(json.dumps(meta))
            client.send_bytes(chunk)
            current_ms += int(len(chunk) / 32)
            if not args.fast:
                time.sleep(args.chunk_ms / 1000.0)

        # Brief gap
        current_ms += 500

        # Stream Speaker 2
        print(f"Streaming audio for speaker 2 ({args.name2})...")
        for offset in range(0, len(pcm2), bytes_per_chunk):
            chunk = pcm2[offset : offset + bytes_per_chunk]
            meta = {
                "type": "chunk",
                "speaker_id": "bot_speaker_2",
                "speaker_name": args.name2,
                "start_ms": current_ms,
            }
            client.send_text(json.dumps(meta))
            client.send_bytes(chunk)
            current_ms += int(len(chunk) / 32)
            if not args.fast:
                time.sleep(args.chunk_ms / 1000.0)

        # End stream
        print("Sending end of meeting frame...")
        client.send_text(json.dumps({"type": "end"}))
        print("Live streaming completed successfully.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
