"""
Gemini (Vertex AI) service for jns23lab AI Analyze and AI Assistant.
Uses google-genai client with Vertex AI.
"""
import json
import logging
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings
from app.services.ai_security import filter_secrets_from_text, filter_secrets_from_dict

logger = logging.getLogger(__name__)

# Lazy client to avoid import/credentials errors at import time
_gemini_client = None


def _get_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    try:
        from google import genai
        from google.oauth2 import service_account
    except ImportError as e:
        raise RuntimeError(
            "Google GenAI not installed. pip install google-genai google-auth"
        ) from e

    settings = get_settings()
    if not settings.vertex_project_id:
        raise RuntimeError("vertex_project_id is not configured")

    credentials = None
    if settings.vertex_credentials_path:
        path = Path(settings.vertex_credentials_path)
        if path.is_file():
            credentials = service_account.Credentials.from_service_account_file(
                str(path),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

    _gemini_client = genai.Client(
        vertexai=True,
        project=settings.vertex_project_id,
        location=settings.vertex_location,
        credentials=credentials,
    )
    return _gemini_client


# ---- Analyze: failure analysis ----

ANALYZE_SYSTEM_INSTRUCTION = """You are an expert assistant for the jns23lab UKK evaluation platform.
You help students understand why their server configuration or exam step failed.
You receive:
1) Exam result details (failed step: category, step_code, step_name, status, message, raw output).
2) Optional: related config snippets (e.g. Nginx config, logs) — these may be redacted for security.

Your task:
- Explain in simple terms what went wrong.
- Suggest a concrete fix (steps or config change).
- Be educational, concise, and supportive.
- Do not make up credentials or sensitive data; if something is redacted, say "check your configuration" instead.
- Answer in the same language as the user's question if possible, otherwise English."""


def build_analyze_prompt(exam_result_details: list[dict], config_snippets: dict[str, str] | None) -> str:
    """Build the user prompt for analyze. Inputs are filtered for secrets."""
    parts = ["## Failed exam steps\n"]
    safe_details = filter_secrets_from_dict(exam_result_details)
    parts.append(json.dumps(safe_details, indent=2, default=str))

    if config_snippets:
        parts.append("\n## Related config / logs (for context)\n")
        for name, content in config_snippets.items():
            parts.append(f"### {name}\n")
            parts.append(filter_secrets_from_text(str(content)))
            parts.append("\n")

    parts.append("\nPlease explain why this step failed and suggest a fix.")
    return "".join(parts)


def generate_analyze(exam_result_details: list[dict], config_snippets: dict[str, str] | None = None) -> str:
    """
    Call Gemini for failure analysis. Returns explanation + suggested fix.
    Raises on API or model errors.
    """
    client = _get_client()
    settings = get_settings()
    user_prompt = build_analyze_prompt(exam_result_details, config_snippets or {})

    from google.genai.types import GenerateContentConfig

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_prompt,
        config=GenerateContentConfig(
            system_instruction=ANALYZE_SYSTEM_INSTRUCTION,
            temperature=0.3,
            max_output_tokens=2048,
        ),
    )

    if not response or not response.candidates:
        raise ValueError("Empty response from model")
    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        raise ValueError("No text in model response")
    return getattr(response, "text", None) or candidate.content.parts[0].text


# ---- Assistant: chat ----

ASSISTANT_SYSTEM_PROMPT = """You are the AI assistant of jns23lab, a DevOps and UKK evaluation platform for vocational high school students.

Your role:
- Help students understand server configuration (Proxmox, Ubuntu, Nginx, MySQL, WordPress, DNS/BIND9) and UKK exam preparation.
- Explain platform features: auto VM checking, Nginx/MySQL/DNS validation, leaderboard, learning materials, VPN access.
- Guide students on how to use jns23lab and why their configuration might have failed.
- Provide clear, step-by-step explanations. Be educational, concise, and supportive.

Rules:
- Do not provide harmful or insecure advice (e.g. disabling security, exposing credentials).
- Do not invent credentials or secrets; if something is redacted, say to check their own configuration.
- If the user uploads a screenshot (error, Nginx config, terminal), describe what you see and suggest fixes.
- Answer in the same language as the user when possible; otherwise use English."""


def generate_chat(messages: list[dict], new_message: str) -> tuple[str, int, int]:
    """
    messages: list of {"role": "user"|"assistant", "content": "..."}
    new_message: latest user message.
    Returns (assistant_text, input_tokens, output_tokens). Token counts may be 0 if unavailable.
    """
    client = _get_client()
    settings = get_settings()
    from google.genai import types

    contents = []
    for m in messages:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
        else:
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=new_message)]))

    from google.genai.types import GenerateContentConfig
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=GenerateContentConfig(
            system_instruction=ASSISTANT_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )
    if not response or not response.candidates:
        raise ValueError("Empty response from model")
    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        raise ValueError("No text in model response")
    text = getattr(response, "text", None) or candidate.content.parts[0].text
    usage = getattr(response, "usage_metadata", None)
    input_tokens = _token_count(usage, "prompt_token_count")
    output_tokens = _token_count(usage, "candidates_token_count")
    return text, input_tokens, output_tokens


def generate_chat_stream(messages: list[dict], new_message: str) -> Iterator[str]:
    """
    Stream chat response from Gemini. Yields text deltas as they arrive.
    Caller should collect full text for saving history and usage (streaming may not provide usage_metadata).
    """
    client = _get_client()
    settings = get_settings()
    from google.genai import types
    from google.genai.types import GenerateContentConfig

    contents = []
    for m in messages:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
        else:
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=new_message)]))

    stream = client.models.generate_content_stream(
        model=settings.gemini_model,
        contents=contents,
        config=GenerateContentConfig(
            system_instruction=ASSISTANT_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )
    for chunk in stream:
        if not chunk:
            continue
        text = getattr(chunk, "text", None)
        if text:
            yield text
            continue
        if chunk.candidates:
            c = chunk.candidates[0]
            if c.content and c.content.parts:
                text = getattr(c.content.parts[0], "text", None)
                if text:
                    yield text


def _token_count(usage: Any, key: str) -> int:
    """Get token count from usage_metadata (dict or Pydantic model)."""
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(key) or 0)
    return int(getattr(usage, key, 0) or 0)


def generate_chat_with_image(
    messages: list[dict], new_message: str, image_bytes: bytes, mime_type: str = "image/png"
) -> tuple[str, int, int]:
    """Same as generate_chat but the new message includes an image. mime_type e.g. image/png, image/jpeg."""
    client = _get_client()
    settings = get_settings()
    from google.genai import types

    contents = []
    for m in messages:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
        else:
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))

    # Last turn: image + text
    parts = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        types.Part.from_text(text=new_message or "What do you see in this image? Please explain."),
    ]
    contents.append(types.Content(role="user", parts=parts))

    from google.genai.types import GenerateContentConfig
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=GenerateContentConfig(
            system_instruction=ASSISTANT_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )
    if not response or not response.candidates:
        raise ValueError("Empty response from model")
    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        raise ValueError("No text in model response")
    text = getattr(response, "text", None) or candidate.content.parts[0].text
    usage = getattr(response, "usage_metadata", None)
    input_tokens = _token_count(usage, "prompt_token_count")
    output_tokens = _token_count(usage, "candidates_token_count")
    return text, input_tokens, output_tokens
