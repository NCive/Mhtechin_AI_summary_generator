"""Test script to extract notes from a transcript text file using llama-server."""
import json
import re
import sys
import time
from pathlib import Path

# Add backend directory to sys.path so app packages import cleanly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.llm import is_server_ready
from app.services.notes_extractor import extract_chunk_notes


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/try_notes.py <path_to_transcript_text_file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    if not is_server_ready():
        print(
            f"Error: llama-server is not reachable at {settings.LLM_SERVER_URL}.\n"
            "Please start llama-server before running this script."
        )
        sys.exit(1)

    chunk_text = file_path.read_text(encoding="utf-8")

    # Detect speaker names matching [mm:ss] Speaker Name: ...
    speaker_matches = re.findall(r"\[\d+:\d+\]\s*([^:]+):", chunk_text)
    speakers = list(dict.fromkeys(s.strip() for s in speaker_matches if s.strip()))

    print(f"Server ready at {settings.LLM_SERVER_URL}.")
    print(f"Reading {file_path.name} ({len(chunk_text)} chars, detected speakers: {speakers})...")

    t0 = time.perf_counter()
    notes = extract_chunk_notes(chunk_text, speakers)
    duration = time.perf_counter() - t0

    print("\n--- Extracted Notes (JSON) ---")
    print(json.dumps(notes, indent=2))
    print(f"\nCall completed in {duration:.2f} seconds.")


if __name__ == "__main__":
    main()
