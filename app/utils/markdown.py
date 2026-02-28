"""
Markdown normalization for AI assistant output.
Synced with frontend v0-frontend/lib/markdown.ts so lists, bold, and line breaks render correctly.
Apply only to final accumulated message (before saving); do not normalize partial stream chunks.

Rules:
- After colon: blank line before first bullet (":\\n\\n-" or ":\\n\\n*").
- Single " - " → newline + "- " only when followed by A-Z or digit (avoid "X - jika relevan").
- Single " * " (not "**") → newline + "* ".
"""
import re


def normalize_markdown(text: str) -> str:
    """
    Normalize Markdown for frontend rendering:
    - Blank line before list after colon.
    - One bullet per line; do not break mid-phrase "X - jika relevan" (only " - " before A-Z/0-9).
    - Single asterisk list marker (not **bold**) on own line.
    """
    if not text or not text.strip():
        return text
    # Blank line before first "-" when it follows colon (e.g. "intro:\n- Item" or "intro: - Item")
    text = re.sub(r":\s*\n?\s*\-", ":\n\n-", text)
    # Blank line before first "*" when it follows colon; single * only (not **bold**)
    text = re.sub(r":\s*\*(?!\*)", ":\n\n*", text)
    # " - " → newline + "- " only when followed by uppercase or digit (don't break "X - jika relevan")
    text = re.sub(r"\s+\-\s+(?=[A-Z0-9])", "\n- ", text)
    # " * " (single asterisk, not **) → newline + "* "
    text = re.sub(r"\s+\*(?!\*)\s+", "\n* ", text)
    return text
