import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """Raised when llama-server is not reachable or unavailable."""

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = (
                f"llama-server is not reachable at {settings.LLM_SERVER_URL}. "
                "Please start llama-server before making LLM requests."
            )
        super().__init__(message)


def is_server_ready(client: httpx.Client | None = None) -> bool:
    """Check if llama-server is running and ready. Returns True only for HTTP 200."""
    url = f"{settings.LLM_SERVER_URL.rstrip('/')}/health"
    try:
        if client is not None:
            resp = client.get(url)
            return resp.status_code == 200
        with httpx.Client(timeout=5.0) as c:
            resp = c.get(url)
            return resp.status_code == 200
    except httpx.RequestError:
        return False


def count_tokens(text: str, client: httpx.Client | None = None) -> int:
    """Tokenize text using llama-server and return token count."""
    url = f"{settings.LLM_SERVER_URL.rstrip('/')}/tokenize"
    try:
        if client is not None:
            resp = client.post(url, json={"content": text})
            if resp.status_code == 503:
                raise LLMUnavailable(f"llama-server returned 503 at {settings.LLM_SERVER_URL}")
            resp.raise_for_status()
            data = resp.json()
            return len(data.get("tokens", []))
        with httpx.Client(timeout=float(settings.LLM_TIMEOUT_SECONDS)) as c:
            resp = c.post(url, json={"content": text})
            if resp.status_code == 503:
                raise LLMUnavailable(f"llama-server returned 503 at {settings.LLM_SERVER_URL}")
            resp.raise_for_status()
            data = resp.json()
            return len(data.get("tokens", []))
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as exc:
        raise LLMUnavailable() from exc


def _validate_parsed_dict(data: Any, schema: dict[str, Any] | type[BaseModel]) -> None:
    """Validate parsed JSON dictionary against schema or Pydantic model."""
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        schema.model_validate(data)
        return

    if not isinstance(data, dict):
        raise TypeError(f"Expected dict from LLM, got {type(data).__name__}")

    required_keys = schema.get("required", [])
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key in LLM JSON output: '{key}'")

    properties = schema.get("properties", {})
    for prop_name, prop_spec in properties.items():
        if prop_name in data and data[prop_name] is not None:
            expected_type = prop_spec.get("type")
            val = data[prop_name]
            if expected_type == "string" and not isinstance(val, str):
                raise ValueError(f"Field '{prop_name}' must be string, got {type(val).__name__}")
            elif expected_type == "array" and not isinstance(val, list):
                raise ValueError(f"Field '{prop_name}' must be list, got {type(val).__name__}")
            elif expected_type == "object" and not isinstance(val, dict):
                raise ValueError(f"Field '{prop_name}' must be dict, got {type(val).__name__}")


def generate_json(
    system_prompt: str,
    user_prompt: str,
    schema: dict[str, Any],
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Generate structured JSON from llama-server using constrained response_format.

    Tries standard OpenAI-compatible json_schema format first, falling back to
    json_object with schema if rejected.
    """
    url = f"{settings.LLM_SERVER_URL.rstrip('/')}/v1/chat/completions"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    formats_to_try = [
        ("json_schema", {"type": "json_schema", "json_schema": {"name": "notes", "schema": schema}}),
        ("json_object", {"type": "json_object", "schema": schema}),
    ]

    response_data: dict[str, Any] | None = None
    last_error: Exception | None = None
    used_format: str | None = None

    for fmt_name, fmt_spec in formats_to_try:
        payload = {
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "response_format": fmt_spec,
        }

        try:
            if client is not None:
                resp = client.post(url, json=payload)
            else:
                with httpx.Client(timeout=float(settings.LLM_TIMEOUT_SECONDS)) as c:
                    resp = c.post(url, json=payload)

            if resp.status_code == 503:
                raise LLMUnavailable(f"llama-server returned 503 at {settings.LLM_SERVER_URL}")

            if resp.status_code in (400, 422):
                last_error = RuntimeError(
                    f"llama-server rejected '{fmt_name}': {resp.status_code} {resp.text}"
                )
                continue

            resp.raise_for_status()
            response_data = resp.json()
            used_format = fmt_name
            logger.info("generate_json succeeded using response_format: %s", used_format)
            break
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as exc:
            raise LLMUnavailable() from exc
        except LLMUnavailable:
            raise
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_error = exc
            continue

    if response_data is None:
        if last_error:
            raise last_error
        raise RuntimeError("No response received from LLM server.")

    choices = response_data.get("choices")
    if not choices or not isinstance(choices, list):
        raise ValueError(f"Invalid response from LLM (missing 'choices'): {response_data}")

    choice = choices[0]
    finish_reason = choice.get("finish_reason")
    if finish_reason == "length":
        raise RuntimeError(
            "LLM output cut off: finish_reason is 'length'. "
            "Output was truncated; please increase LLM_MAX_TOKENS or shorten chunk text."
        )

    message = choice.get("message", {})
    content = message.get("content", "")
    if not content or not content.strip():
        raise ValueError("LLM returned empty content in message.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse LLM response as JSON: {content}") from exc

    _validate_parsed_dict(parsed, schema)
    return parsed
