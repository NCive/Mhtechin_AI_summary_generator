import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.core.config import settings
from app.services.llm import (
    LLMUnavailable,
    count_tokens,
    generate_json,
    is_server_ready,
)
from app.services.notes_extractor import (
    CHUNK_NOTES_SCHEMA,
    extract_chunk_notes,
    verify_notes,
)


def test_verify_notes_owner_overrides_and_evidence():
    chunk_text = (
        "[01:00] David: Sarah, can you review the pricing?\n"
        "[01:10] Sarah: Yes, I can take that on.\n"
        "[01:20] Bob: I will finish the database migration by Friday.\n"
        "[02:00] Alice: I can't do that today.\n"
        "[02:10] Charlie: Should we also prepare the social media posts?\n"
        "[02:20] Priya: We will all review it together.\n"
    )
    speaker_names = ["David", "Sarah", "Bob", "Alice", "Charlie", "Priya"]

    raw_notes = {
        "summary": "Team meeting discussions.",
        "project_progress": ["Completed branding assets.", "None", "no progress mentioned."],
        "challenges": ["N/A", "nothing", "   "],
        "action_items": [
            # 1. Agreeing line -> owner Sarah
            {"text": "Review pricing", "owner": "David", "deadline": None, "source_time": "[01:10]"},
            # 2. Requester line cited -> owner null
            {"text": "Check pricing numbers", "owner": "David", "deadline": None, "source_time": "[01:00]"},
            # 3. Model wrong owner overridden by cited speaker with commitment -> owner Bob
            {"text": "Finish database migration", "owner": "David", "deadline": "by Friday", "source_time": "[01:20]"},
            # 4. "I can't" does not count as commitment -> owner null
            {"text": "Help with auth", "owner": "Alice", "deadline": None, "source_time": "[02:00]"},
            # 5. Question line without commitment -> dropped completely
            {"text": "Prepare social media posts", "owner": "Charlie", "deadline": None, "source_time": "[02:10]"},
            # 6. "We will all review it together" -> owner null
            {"text": "Final review", "owner": "Priya", "deadline": None, "source_time": "[02:20]"},
            # 7. Non-existent source_time -> owner null, item kept
            {"text": "Draft docs", "owner": "Alice", "deadline": None, "source_time": "[99:99]"},
            # 8. Null source_time -> owner null, item kept
            {"text": "Refactor router", "owner": "Bob", "deadline": None, "source_time": None},
            # 9. Empty text -> dropped
            {"text": "", "owner": "Bob", "deadline": None, "source_time": "[01:20]"},
            {"text": "   ", "owner": None, "deadline": None, "source_time": None},
        ],
        "next_steps": ["Deploy next sprint", "No specific next steps mentioned", "not specified"],
    }

    verified = verify_notes(raw_notes, chunk_text, speaker_names)

    # Filler removal check
    assert verified["project_progress"] == ["Completed branding assets."]
    assert verified["challenges"] == []
    assert verified["next_steps"] == ["Deploy next sprint"]

    items = verified["action_items"]
    # 9 items submitted: #5 dropped (question line without commitment), #9 & #10 dropped (empty text)
    # Remaining: 7 items
    assert len(items) == 7

    # Item 1: Cited agreeing line gives owner Sarah
    assert items[0]["text"] == "Review pricing"
    assert items[0]["owner"] == "Sarah"
    assert items[0]["source_time"] == "[01:10]"

    # Item 2: Cited requester line gives owner null
    assert items[1]["text"] == "Check pricing numbers"
    assert items[1]["owner"] is None
    assert items[1]["source_time"] == "[01:00]"

    # Item 3: Owner comes from cited line's speaker (Bob) overriding wrong model owner (David)
    assert items[2]["text"] == "Finish database migration"
    assert items[2]["owner"] == "Bob"
    assert items[2]["deadline"] == "by Friday"
    assert items[2]["source_time"] == "[01:20]"

    # Item 4: "I can't" does not count as commitment -> owner null
    assert items[3]["text"] == "Help with auth"
    assert items[3]["owner"] is None

    # Item 5: "We will all review it together" gives owner null
    assert items[4]["text"] == "Final review"
    assert items[4]["owner"] is None

    # Item 6: Non-existent source_time gives owner null but keeps item
    assert items[5]["text"] == "Draft docs"
    assert items[5]["owner"] is None
    assert items[5]["source_time"] == "[99:99]"

    # Item 7: Null source_time gives owner null but keeps item
    assert items[6]["text"] == "Refactor router"
    assert items[6]["owner"] is None
    assert items[6]["source_time"] is None


def test_generate_json_success():
    expected_dict = {
        "summary": "Discussed migration.",
        "project_progress": ["Progress item"],
        "challenges": [],
        "action_items": [{"text": "Task A", "owner": "Bob", "deadline": None, "source_time": "[01:00]"}],
        "next_steps": [],
    }

    recorded_request: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_request["url"] = str(request.url)
        body = json.loads(request.content.decode("utf-8"))
        recorded_request["body"] = body
        response_payload = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(expected_dict),
                    },
                }
            ]
        }
        return httpx.Response(200, json=response_payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        res = generate_json(
            system_prompt="Test system prompt",
            user_prompt="Test user prompt",
            schema=CHUNK_NOTES_SCHEMA,
            client=client,
        )

    assert res == expected_dict
    assert "/v1/chat/completions" in recorded_request["url"]
    req_body = recorded_request["body"]
    assert "response_format" in req_body
    fmt = req_body["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["schema"] == CHUNK_NOTES_SCHEMA


def test_generate_json_finish_reason_length():
    def handler(request: httpx.Request) -> httpx.Response:
        response_payload = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": '{"summary": "Incomplete text that was cut',
                    },
                }
            ]
        }
        return httpx.Response(200, json=response_payload)

    transport = httpx.MockTransport(handler)
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(RuntimeError, match="finish_reason is 'length'"),
    ):
        generate_json(
            system_prompt="System",
            user_prompt="User",
            schema=CHUNK_NOTES_SCHEMA,
            client=client,
        )


def test_generate_json_unreachable_server():
    def handler_503(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    transport_503 = httpx.MockTransport(handler_503)
    with (
        httpx.Client(transport=transport_503) as client,
        pytest.raises(LLMUnavailable),
    ):
        generate_json(
            system_prompt="System",
            user_prompt="User",
            schema=CHUNK_NOTES_SCHEMA,
            client=client,
        )

    def handler_connect_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport_err = httpx.MockTransport(handler_connect_error)
    with (
        httpx.Client(transport=transport_err) as client,
        pytest.raises(LLMUnavailable),
    ):
        generate_json(
            system_prompt="System",
            user_prompt="User",
            schema=CHUNK_NOTES_SCHEMA,
            client=client,
        )


def test_count_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/tokenize" in str(request.url)
        payload = json.loads(request.content.decode("utf-8"))
        assert payload.get("content") == "Hello world"
        return httpx.Response(200, json={"tokens": [101, 7592, 2088, 102]})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        token_count = count_tokens("Hello world", client=client)

    assert token_count == 4


def test_extract_chunk_notes_integration():
    if not is_server_ready():
        pytest.skip(f"llama-server is not running at {settings.LLM_SERVER_URL}")

    fixture_path = Path(__file__).parent / "fixtures" / "sample_transcript.txt"
    assert fixture_path.exists(), "Sample transcript fixture missing"
    chunk_text = fixture_path.read_text(encoding="utf-8")
    speakers = ["Alice", "Bob", "Charlie"]

    notes = extract_chunk_notes(chunk_text, speakers)

    assert isinstance(notes, dict)
    for required_key in CHUNK_NOTES_SCHEMA["required"]:
        assert required_key in notes
    assert isinstance(notes["summary"], str)
    assert isinstance(notes["action_items"], list)


def test_extract_chunk_notes_integration_fixture_2():
    if not is_server_ready():
        pytest.skip(f"llama-server is not running at {settings.LLM_SERVER_URL}")

    fixture_path = Path(__file__).parent / "fixtures" / "sample_transcript_2.txt"
    assert fixture_path.exists(), "Sample transcript 2 fixture missing"
    chunk_text = fixture_path.read_text(encoding="utf-8")
    speakers = ["David", "Sarah", "Michael", "Priya"]

    notes = extract_chunk_notes(chunk_text, speakers)

    assert isinstance(notes, dict)
    for required_key in CHUNK_NOTES_SCHEMA["required"]:
        assert required_key in notes
    assert isinstance(notes["summary"], str)
    assert isinstance(notes["action_items"], list)
