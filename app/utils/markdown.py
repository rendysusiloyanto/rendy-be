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


def _is_heading_bullet(line: str) -> bool:
    """True if section heading: '- **Tujuan:**', '- Tujuan:', '**Tujuan:**', or 'Tujuan:' (line ends at colon)."""
    s = line.strip()
    if re.match(r"^[-*]\s+\*\*[^*]+\*\*:\s*$", s):
        return True
    if re.match(r"^[-*]\s+[^:\n]+:\s*$", s):
        return True
    if re.match(r"^\*\*[^*]+\*\*:\s*$", s):
        return True
    return bool(re.match(r"^[^:\n]+:\s*$", s))


def _is_top_level_bullet(line: str) -> bool:
    """True if line is a top-level bullet (no leading spaces, '- ' or '* ' but not '* **')."""
    if line.startswith((" ", "\t")):
        return False
    if line.startswith("- "):
        return True
    if line.startswith("* ") and not line.startswith("* *"):
        return True
    return False


def _indent_sublists_under_headings(text: str) -> str:
    """Indent bullets that follow a section heading so they render as sub-list."""
    lines = text.split("\n")
    out = []
    in_subsection = False
    for line in lines:
        if _is_heading_bullet(line):
            in_subsection = True
            out.append(line)
            continue
        if in_subsection and _is_top_level_bullet(line):
            out.append("  " + line)
            continue
        if line.strip() != "":
            in_subsection = False
        out.append(line)
    return "\n".join(out)


def normalize_markdown(text: str) -> str:
    """
    Normalize Markdown for frontend rendering:
    - Blank line before list after colon.
    - One bullet per line; do not break mid-phrase "X - jika relevan" (only " - " before A-Z/0-9).
    - Single asterisk list marker (not **bold**) on own line.
    """
    if not text or not text.strip():
        return text
    # Blank line before first "-" when it follows colon; preserve indent so sublists stay (e.g. ":\n  -" → ":\n\n  -")
    text = re.sub(r":\s*\n?\s*(\s*)\-", r":\n\n\1-", text)
    # Blank line before first "*" when it follows colon; single * only (not **bold**); preserve indent
    text = re.sub(r":\s*\n?\s*(\s*)\*(?!\*)", r":\n\n\1*", text)
    # " - " → newline + "- " only when followed by uppercase or digit (don't break "X - jika relevan").
    # Do not replace when bullet is already at line start (preserves nested lists like "  - subitem").
    text = re.sub(r"(?<!\n)\s+\-\s+(?=[A-Z0-9])", "\n- ", text)
    # " * " (single asterisk, not **) → newline + "* "
    text = re.sub(r"(?<!\n)\s+\*(?!\*)\s+", "\n* ", text)
    # Bullets under "**Title:**" become sub-list (indent by 2 spaces)
    text = _indent_sublists_under_headings(text)
    # Closing question on its own line (ID + EN: "Apakah ada...?", "Do you have any...?", etc.)
    text = re.sub(
        r"\.\s*(Apakah ada [^.?]*\?|Do you have any [^.?]*\?|Would you like to [^.?]*\?|Is there anything [^.?]*\?)",
        r".\n\n\1",
        text,
        flags=re.IGNORECASE,
    )
    return text
