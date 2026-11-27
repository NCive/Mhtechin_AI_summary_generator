"""Investigation script for Whisper silence filtering and live stream buffer boundary."""
from __future__ import annotations

import array
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

# Set working directory context to backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.core.config import settings
from app.services.live_stream import is_pcm_silent
from app.services.transcription import get_whisper_model


def main():
    print("=== Step 1: Locating and copying clip ===")
    media_dir = Path(settings.MEDIA_DIR)
    # The uploaded meeting WIN_20261125_18_06_51_Pro
    meeting_rel_path = Path("3ad44b6f-f369-4549-9a91-25ed5bb27091") / "original.mp4"
    src_file = media_dir / meeting_rel_path
    if not src_file.exists():
        src_file = Path("backend") / "media" / meeting_rel_path
    if not src_file.exists():
        print(f"ERROR: Media file could not be found at {src_file}")
        sys.exit(1)

    print(f"Source file found: {src_file} (size: {src_file.stat().st_size} bytes)")

    temp_dir = Path(tempfile.mkdtemp(prefix="whisper_investigation_"))
    temp_mp4 = temp_dir / "clip.mp4"
    shutil.copy2(src_file, temp_mp4)
    print(f"Copied to temporary path: {temp_mp4}")

    print("\n=== Step 2: Converting to 16 kHz mono PCM16 ===")
    temp_pcm = temp_dir / "clip.raw"
    ffmpeg_cmd = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    cmd = [
        ffmpeg_cmd,
        "-y",
        "-i",
        str(temp_mp4),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(temp_pcm),
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        print(f"FFmpeg error: {proc.stderr.decode('utf-8', errors='replace')}")
        sys.exit(1)

    pcm_bytes = temp_pcm.read_bytes()
    total_samples = len(pcm_bytes) // 2
    total_seconds = total_samples / 16000.0
    print(f"PCM size: {len(pcm_bytes)} bytes ({total_samples} samples, {total_seconds:.2f} s)")

    print("\n=== Step 3: Preparing ~30s buffers (Live Stream buffer layout) ===")
    chunk_bytes = 32000  # 1s chunk in live ingestion
    max_buf_bytes = 30 * chunk_bytes  # 30s buffer limit (960,000 bytes)

    # Buffer 1: 0 to 30s
    buf1 = pcm_bytes[0:max_buf_bytes]
    # Buffer 2: 30s to 60s
    buf2 = pcm_bytes[max_buf_bytes : max_buf_bytes * 2]
    # Buffer 3: 60s to end
    buf3 = pcm_bytes[max_buf_bytes * 2 :]

    buffer_slices = [
        {"id": 1, "start_s": 0.0, "end_s": len(buf1) / 32000.0, "pcm": buf1},
        {"id": 2, "start_s": 30.0, "end_s": 30.0 + len(buf2) / 32000.0, "pcm": buf2},
        {"id": 3, "start_s": 60.0, "end_s": 60.0 + len(buf3) / 32000.0, "pcm": buf3},
    ]

    print("\n=== Step 4: Testing PCM Silence Check on each buffer ===")
    for b in buffer_slices:
        b_pcm = b["pcm"]
        even_len = len(b_pcm) - (len(b_pcm) % 2)
        samples = array.array("h", b_pcm[:even_len])
        max_s = max(samples) if samples else 0
        min_s = min(samples) if samples else 0
        peak_abs = max(abs(max_s), abs(min_s))
        avg_abs = sum(abs(s) for s in samples) / len(samples) if samples else 0
        silent = is_pcm_silent(b_pcm, threshold=100)
        print(f"Buffer {b['id']} ({b['start_s']:.1f}s - {b['end_s']:.1f}s, {len(b_pcm)} bytes):")
        print(f"  Max sample: {max_s}, Min sample: {min_s}, Peak abs: {peak_abs}, Mean abs: {avg_abs:.2f}")
        print(f"  is_pcm_silent(threshold=100): {silent}")

    print("\n=== Step 5: Running Whisper Transcription ===")
    model = get_whisper_model()

    raw_segments_all = []
    current_filtered_all = []
    disabled_filtered_all = []

    for b in buffer_slices:
        b_id = b["id"]
        b_start_s = b["start_s"]
        b_pcm = b["pcm"]

        # Write buffer to temporary WAV
        temp_wav = temp_dir / f"buffer_{b_id}.wav"
        with wave.open(str(temp_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b_pcm)

        segments_gen, _ = model.transcribe(
            str(temp_wav),
            language="en",
            vad_filter=True,
        )

        for seg in segments_gen:
            raw_prob = getattr(seg, "no_speech_prob", 0.0)
            no_speech_prob = float(raw_prob) if raw_prob is not None else 0.0
            avg_logprob = float(getattr(seg, "avg_logprob", 0.0))
            text = str(seg.text).strip()

            meeting_start = round(b_start_s + float(seg.start), 2)
            meeting_end = round(b_start_s + float(seg.end), 2)

            seg_info = {
                "buffer_id": b_id,
                "buf_start_s": round(float(seg.start), 2),
                "buf_end_s": round(float(seg.end), 2),
                "meeting_start": meeting_start,
                "meeting_end": meeting_end,
                "text": text,
                "no_speech_prob": round(no_speech_prob, 4),
                "avg_logprob": round(avg_logprob, 4),
            }
            raw_segments_all.append(seg_info)

            # Current filter condition
            is_empty_or_marker = (not text) or text in (
                ".",
                "...",
                "!",
                "?",
                "Thank you.",
                "Thanks for watching!",
                "Subtitles by",
                "[BLANK_AUDIO]",
            )
            drops_current = (no_speech_prob > 0.6 and avg_logprob < -1.0) or is_empty_or_marker
            drops_disabled = is_empty_or_marker

            if not drops_current:
                current_filtered_all.append(seg_info)
            if not drops_disabled:
                disabled_filtered_all.append(seg_info)

    print("\n" + "=" * 80)
    print("ALL RAW SEGMENTS EMITTED BY WHISPER:")
    print("=" * 80)
    for s in raw_segments_all:
        drop_mark = (
            " [DROPPED by nsp>0.6 and avg_logprob<-1.0]"
            if (s["no_speech_prob"] > 0.6 and s["avg_logprob"] < -1.0)
            else ""
        )
        print(
            f"Buf {s['buffer_id']} | Mtg: {s['meeting_start']:5.2f} - {s['meeting_end']:5.2f}s | "
            f"nsp: {s['no_speech_prob']:.4f} | avg_logprob: {s['avg_logprob']:.4f} | "
            f"text: {s['text']}{drop_mark}"
        )

    print("\n" + "=" * 80)
    print("CURRENT FILTERED SEGMENTS:")
    print("=" * 80)
    for s in current_filtered_all:
        print(f"{s['meeting_start']:5.2f} - {s['meeting_end']:5.2f}s: {s['text']}")

    # Save results to json
    out_json = temp_dir / "investigation_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "raw_segments": raw_segments_all,
                "current_filtered": current_filtered_all,
                "disabled_filtered": disabled_filtered_all,
            },
            f,
            indent=2,
        )
    print(f"\nDetailed JSON results saved to: {out_json}")


if __name__ == "__main__":
    main()
