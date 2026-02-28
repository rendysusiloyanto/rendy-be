"""
Markdown normalization for AI assistant output.
Fixes inline bullet lists so the frontend can render them correctly.
Apply only to final accumulated message (e.g. before saving); do not normalize partial stream chunks.
"""
import re


def normalize_markdown(text: str) -> str:
    """
    Ensure bullet lists are properly formatted: blank line before first bullet,
    each bullet on its own line. Fixes inline patterns like "intro: * A * B".
    """
    if not text or not text.strip():
        return text
    # Add newline before first bullet when it appears inline after colon (e.g. "need: * Item")
    text = re.sub(r":\s*\*", ":\n\n*", text)
    # Ensure each " * " (space-asterisk-space) starts a new line so bullets are not on one line
    text = re.sub(r"\s+\*\s+", "\n* ", text)
    return text
