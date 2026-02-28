"""
Markdown normalization for AI assistant output.
Fixes inline bullet lists so the frontend can render them correctly.
Output format: intro text, blank line, then one bullet per line (- or *).
Apply only to final accumulated message (e.g. before saving); do not normalize partial stream chunks.
"""
import re


def normalize_markdown(text: str) -> str:
    """
    Ensure bullet lists are properly formatted for frontend Markdown rendering:
    - Blank line before first bullet (after colon or at start of list).
    - Each bullet on its own line. Supports both hyphen (-) and asterisk (*) bullets.
    """
    if not text or not text.strip():
        return text
    # Hyphen lists: add blank line before first "-" when it follows colon (e.g. "intro:\n- Item" or "intro: - Item")
    text = re.sub(r":\s*\n?\s*\-", ":\n\n-", text)
    # Asterisk lists: add blank line before first "*" when it follows colon
    text = re.sub(r":\s*\*", ":\n\n*", text)
    # Ensure each " - " (space-hyphen-space) starts a new line
    text = re.sub(r"\s+\-\s+", "\n- ", text)
    # Ensure each " * " (space-asterisk-space) starts a new line
    text = re.sub(r"\s+\*\s+", "\n* ", text)
    return text
