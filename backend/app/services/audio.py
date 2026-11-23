"""Audio extraction and duration detection service using FFmpeg and FFprobe."""
from __future__ import annotations

import logging
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_media_duration(file_path: Path) -> float:
    """Detect duration of a media file in seconds using ffprobe.

    Raises:
        FileNotFoundError: If ffprobe binary is not found.
        RuntimeError: If ffprobe fails or duration cannot be extracted.
    """
    cmd = [
        settings.FFPROBE_PATH,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"ffprobe binary not found at '{settings.FFPROBE_PATH}'. Please ensure FFmpeg is installed."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffprobe timed out reading '{file_path}'.") from exc

    if proc.returncode != 0:
        err = proc.stderr.strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"ffprobe failed for '{file_path}': {err}")

    output = proc.stdout.strip()
    try:
        return max(0.0, float(output))
    except ValueError as exc:
        raise RuntimeError(f"Could not parse duration from ffprobe output: '{output}'") from exc


def extract_audio_to_wav(
    media_path: Path,
    output_wav_path: Path | None = None,
) -> Path:
    """Extract 16 kHz mono 16-bit PCM WAV from media_path using ffmpeg.

    Preserves original media file. Does not load media into RAM.

    Raises:
        ValueError: If media_path does not exist or escapes MEDIA_DIR.
        FileNotFoundError: If ffmpeg binary is not found.
        RuntimeError: If ffmpeg conversion fails.
    """
    media_root = Path(settings.MEDIA_DIR).resolve()
    resolved_input = media_path.resolve()

    if not resolved_input.is_relative_to(media_root) and not resolved_input.exists():
        raise ValueError(f"Media file '{media_path}' is outside MEDIA_DIR or does not exist.")

    if not resolved_input.is_file():
        raise ValueError(f"Media path '{media_path}' is not a valid file.")

    if output_wav_path is None:
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_wav_path = Path(temp_file.name)
        temp_file.close()

    cmd = [
        settings.FFMPEG_PATH,
        "-y",
        "-i",
        str(resolved_input),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_wav_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            check=False,
        )
    except FileNotFoundError as exc:
        if output_wav_path.exists():
            output_wav_path.unlink(missing_ok=True)
        raise FileNotFoundError(
            f"ffmpeg binary not found at '{settings.FFMPEG_PATH}'. Please ensure FFmpeg is installed."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        if output_wav_path.exists():
            output_wav_path.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg conversion timed out for '{media_path}'.") from exc

    if proc.returncode != 0:
        if output_wav_path.exists():
            output_wav_path.unlink(missing_ok=True)
        err = proc.stderr.strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"ffmpeg extraction failed for '{media_path}': {err}")

    return output_wav_path


@contextmanager
def extract_temporary_wav(media_path: Path) -> Generator[tuple[Path, float], None, None]:
    """Context manager that extracts 16 kHz mono WAV and duration, cleaning up on exit.

    Yields:
        (wav_path: Path, duration_seconds: float)
    """
    wav_path: Path | None = None
    try:
        duration = get_media_duration(media_path)
        wav_path = extract_audio_to_wav(media_path)
        yield wav_path, duration
    finally:
        if wav_path and wav_path.exists():
            try:
                wav_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to remove temporary WAV file '%s': %s", wav_path, exc)
