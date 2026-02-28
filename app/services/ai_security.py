"""
Filter secrets and credentials from text before sending to AI.
Do NOT send passwords, tokens, or sensitive paths to Gemini.
"""
import re
from typing import Any


# Patterns and replacement for sensitive data (redact, do not send)
SECRET_PATTERNS = [
    (re.compile(r'(password|passwd|pwd|secret|token|api_key|apikey)\s*[:=]\s*["\']?[^\s"\']+', re.I), r'\1=***REDACTED***'),
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '***.***.***.***'),  # IPs optional: could allow for config context
    (re.compile(r'(?:root|mysql|admin|ubuntu)\s*:\s*[^\s]+', re.I), '***:***REDACTED***'),
]

# Keys to strip from dict/JSON when building context (never send these values)
SENSITIVE_KEYS = {
    "password", "passwd", "pwd", "secret", "token", "credentials",
    "api_key", "apikey", "authorization", "auth", "private_key",
}


def filter_secrets_from_text(text: str) -> str:
    """Redact obvious secrets in a string. Returns safe text for AI."""
    if not text or not isinstance(text, str):
        return ""
    out = text
    for pattern, repl in SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def filter_secrets_from_dict(obj: Any) -> Any:
    """Recursively redact dict values for sensitive keys. Returns safe structure for AI."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return filter_secrets_from_text(obj)
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***" if (isinstance(k, str) and k.lower() in SENSITIVE_KEYS) else filter_secrets_from_dict(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [filter_secrets_from_dict(i) for i in obj]
    return obj
