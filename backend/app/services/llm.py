"""Optional OpenAI access. Returns None when unavailable or invalid so callers fall back to rules.

Everything an LLM returns is treated as untrusted input and validated by the caller. It cannot create
action types, change numbers or authorize anything.
"""
import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ..config import get_settings

log = logging.getLogger("nexus.llm")
T = TypeVar("T", bound=BaseModel)
_client = None


def available() -> bool:
    return bool(get_settings().openai_api_key)


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        settings = get_settings()
        _client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds, max_retries=1)
    return _client


def complete_json(system: str, user: str, schema: type[T]) -> T | None:
    if not available():
        return None
    try:
        response = _get_client().chat.completions.create(
            model=get_settings().openai_model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": f"{system}\nReply with JSON matching this schema:\n{json.dumps(schema.model_json_schema())}"},
                {"role": "user", "content": user},
            ],
        )
        return schema.model_validate_json(response.choices[0].message.content or "")
    except ValidationError as exc:
        log.warning("LLM returned invalid structure: %s", exc.error_count())
    except Exception as exc:  # Network, auth, quota: the investigation must still complete.
        log.warning("LLM call failed: %s", type(exc).__name__)
    return None


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[float]:
    return {float(m.replace(",", "")) for m in _NUMBER.findall(text)}


def only_known_numbers(narrative: str, facts_text: str) -> bool:
    """True when every number in the narrative also appears in the facts."""
    return numbers_in(narrative) <= numbers_in(facts_text)
