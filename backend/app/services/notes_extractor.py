import re
from typing import Any

from pydantic import BaseModel, Field

from app.services.llm import generate_json

CHUNK_NOTES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "2-3 short sentences summarizing key points of the chunk.",
        },
        "project_progress": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of progress updates or completed items mentioned.",
        },
        "challenges": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of challenges, blockers, or problems mentioned.",
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "owner": {"type": ["string", "null"]},
                    "deadline": {"type": ["string", "null"]},
                    "source_time": {"type": ["string", "null"]},
                },
                "required": ["text"],
            },
            "description": "List of action items with explicit owner, deadline, and source_time if stated.",
        },
        "next_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of next steps or future plans discussed.",
        },
    },
    "required": [
        "summary",
        "project_progress",
        "challenges",
        "action_items",
        "next_steps",
    ],
}


class ActionItemNote(BaseModel):
    text: str
    owner: str | None = None
    deadline: str | None = None
    source_time: str | None = None


class ChunkNotes(BaseModel):
    summary: str
    project_progress: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    action_items: list[ActionItemNote] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are a strict, factual meeting notes extractor.
Input lines have the format `[mm:ss] Speaker: text`. The name before the colon is the speaker.

Rules:
1. Use ONLY what is explicitly stated in the transcript. Do NOT invent anything.
2. Write progress only for things already done. Do not turn plans into finished work.
3. Action Items vs Next Steps:
   - Action items are tasks an individual person commits to do or is assigned to do.
   - Next steps are ONLY general team plans or group goals with no specific person assigned.
4. Owner and Source Time Rule:
   - For every action item, set source_time to the [mm:ss] of the line where that person says they will do it, or agrees to do it. Copy it exactly from the text.
   - If a speaker says "I will / I'll / I can / I am going to" about a task, the owner is THAT speaker's name.
   - If Person A asks Person B to do a task (e.g. "Sarah, can you...") and Person B agrees, the owner is Person B (the assignee), NEVER Person A (the requester).
   - Do NOT set owner if a speaker merely asks a question ("Should we..."), or says "we will", "let us", or "someone needs to": owner must be null.
   - If no specific individual committed or was assigned, owner must be null. Never invent names.
5. Deadline Rule:
   - Use only explicit deadline words from the text (e.g. "by Friday", "tomorrow"). Otherwise null.
6. Summary: 2-3 short, plain sentences.
7. Empty lists are fine if a category was not mentioned.

Example:
Transcript:
[01:00] Dan: Elena, can you reserve the table at Bistro by Thursday?
[01:10] Elena: Sure, I will book the table by Thursday.
[01:20] Frank: I'll collect dietary restrictions from everyone.
[01:30] Dan: Great, someone should print menus, and the whole team will walk over together next Friday.
JSON:
{
  "summary": "The team coordinated lunch plans. Elena agreed to reserve the table and Frank offered to gather dietary restrictions.",
  "project_progress": [],
  "challenges": [],
  "action_items": [
    {"text": "Reserve the table at Bistro", "owner": "Elena", "deadline": "by Thursday", "source_time": "[01:10]"},
    {"text": "Collect dietary restrictions from everyone", "owner": "Frank", "deadline": null, "source_time": "[01:20]"},
    {"text": "Print menus", "owner": null, "deadline": null, "source_time": "[01:30]"}
  ],
  "next_steps": ["Whole team will walk over together next Friday"]
}"""

COMMITMENT_PATTERNS = [
    r"\bi will\b",
    r"\bi['’]ll\b",
    r"\bi am going to\b",
    r"\bi['’]m going to\b",
    r"\blet me\b",
    r"\bi can\b(?!\s*['’]t|\s+not)",
]

FILLER_PATTERNS = [
    r"^none[\.\!]?$",
    r"^n/a[\.\!]?$",
    r"^nothing[\.\!]?$",
    r"^not specified[\.\!]?$",
    r"\bno\s+.*(mentioned|specified|discussed|found|noted)[\.\!]?$",
]


def _has_commitment(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in COMMITMENT_PATTERNS)


def _is_filler(s: str) -> bool:
    cleaned = s.strip()
    if not cleaned:
        return True
    return any(re.search(p, cleaned, re.IGNORECASE) for p in FILLER_PATTERNS)


def _parse_chunk_lines(chunk_text: str) -> dict[str, tuple[str, str]]:
    """Parse transcript chunk lines into mapping: normalized time -> (speaker, text)."""
    parsed: dict[str, tuple[str, str]] = {}
    for line in chunk_text.splitlines():
        line = line.strip()
        m = re.match(r"^\[?(\d{1,2}:\d{2})\]?\s*([^:]+):\s*(.*)$", line)
        if m:
            t_str, speaker, text = m.group(1), m.group(2).strip(), m.group(3).strip()
            parsed[t_str] = (speaker, text)
            parsed[f"[{t_str}]"] = (speaker, text)
    return parsed


def verify_notes(
    notes: dict[str, Any],
    chunk_text: str,
    speaker_names: list[str],
) -> dict[str, Any]:
    """Verify notes against chunk text:
    - Evidence check using source_time:
      - Line parsed to (time, speaker, text). If source_time is null or line not found: owner = null.
      - If line contains commitment phrase: owner = that line's speaker (overrides model).
      - If line has no commitment phrase: owner = null.
      - If cited line contains '?' and has no commitment phrase: drop item.
    - Keep deadline check unchanged.
    - Remove filler strings from project_progress, challenges, and next_steps.
    """
    chunk_lower = chunk_text.lower()
    parsed_lines = _parse_chunk_lines(chunk_text)

    raw_items = notes.get("action_items", [])
    verified_items: list[dict[str, Any]] = []

    for item in raw_items:
        if isinstance(item, dict):
            text = item.get("text", "")
            deadline = item.get("deadline")
            source_time = item.get("source_time")
        elif isinstance(item, ActionItemNote):
            text = item.text
            deadline = item.deadline
            source_time = item.source_time
        else:
            continue

        if not text or not str(text).strip():
            # Drop empty action items
            continue

        # 1. Deadline check (existing logic unchanged)
        verified_deadline: str | None = None
        if deadline and str(deadline).strip():
            deadline_clean = str(deadline).strip()
            if deadline_clean.lower() in chunk_lower:
                verified_deadline = deadline_clean

        # 2. Evidence check for owner via source_time
        norm_source_time = str(source_time).strip() if source_time else None
        line_info = parsed_lines.get(norm_source_time) if norm_source_time else None

        if not line_info:
            owner = None
        else:
            line_speaker, line_text = line_info
            has_commit = _has_commitment(line_text)
            if "?" in line_text and not has_commit:
                # If line addresses a named person (e.g. requester line), keep item with owner null
                # If it's a general question without addressing anyone, drop item
                addresses_person = any(
                    re.search(rf"\b{re.escape(s)}\b", line_text, re.IGNORECASE)
                    for s in speaker_names
                )
                if not addresses_person:
                    continue
                owner = None
            elif has_commit:
                owner = line_speaker
            else:
                owner = None

        verified_items.append({
            "text": str(text).strip(),
            "owner": owner,
            "deadline": verified_deadline,
            "source_time": norm_source_time,
        })

    verified_notes = dict(notes)
    verified_notes["action_items"] = verified_items

    # 3. Remove filler strings from lists
    for key in ("project_progress", "challenges", "next_steps"):
        val = verified_notes.get(key, [])
        if isinstance(val, list):
            verified_notes[key] = [
                str(s).strip()
                for s in val
                if s and str(s).strip() and not _is_filler(str(s))
            ]
        else:
            verified_notes[key] = []

    # Ensure summary is string
    verified_notes["summary"] = str(verified_notes.get("summary", "")).strip()

    return verified_notes


def extract_chunk_notes(
    chunk_text: str,
    speaker_names: list[str],
    client: Any | None = None,
) -> dict[str, Any]:
    """Extract structured notes for one transcript chunk and verify them."""
    speakers_str = ", ".join(speaker_names) if speaker_names else "None listed"
    user_prompt = (
        f"Known speakers in this meeting: {speakers_str}\n\n"
        f"Transcript chunk:\n{chunk_text}\n\n"
        "Extract the structured meeting notes JSON now."
    )

    raw_notes = generate_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=CHUNK_NOTES_SCHEMA,
        client=client,
    )

    # Validate with Pydantic model
    validated = ChunkNotes.model_validate(raw_notes).model_dump()

    # Post-process with verify_notes
    return verify_notes(validated, chunk_text, speaker_names)
