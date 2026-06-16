"""Text cleaning, tokenization, section parsing.

Unicode-safe — handles š, č, ž, đ, etc. for Bosnian/Serbian/Croatian.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Section header like "[Chorus]", "[Verse 1]", "[Bridge: Jala Brat]"
SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$", re.MULTILINE)
# Tokens: runs of letters (any unicode), apostrophes inside
TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
# Lines to drop entirely (Genius adds these sometimes)
JUNK_LINE_RE = re.compile(
    r"^\s*(?:\d+ Contributors?.*|.*Lyrics$|.*Translations?.*|Embed\s*$|You might also like.*)$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class Section:
    name: str  # "Chorus", "Verse 1", "Intro", "" if untagged
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def kind(self) -> str:
        """Coarse classification: chorus/verse/bridge/intro/outro/other.

        Recognises both English and BHS labels (Refren, Uvod, Strofa, etc.).
        """
        n = self.name.lower()
        # BHS → EN mapping
        bhs_map = {
            "refren": "chorus",
            "hook": "chorus",
            "stih": "verse",
            "strofa": "verse",
            "uvod": "intro",
            "kraj": "outro",
            "most": "bridge",
        }
        for k, v in bhs_map.items():
            if k in n:
                return v
        for key in ("chorus", "verse", "bridge", "intro", "outro", "refrain", "pre-chorus"):
            if key in n:
                return key
        return "other"


def clean_raw(raw: str) -> str:
    """Strip Genius cruft like '12 ContributorsSong Title Lyrics' prefix and 'Embed' suffix."""
    if not raw:
        return ""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Drop leading "<n> Contributors...Lyrics" preamble
    text = re.sub(r"^.*?Lyrics\s*\n", "", text, count=1, flags=re.DOTALL)
    # Drop trailing "<n>Embed" or "Embed"
    text = re.sub(r"\d*Embed\s*$", "", text.strip())
    # Drop junk lines
    text = "\n".join(line for line in text.splitlines() if not JUNK_LINE_RE.match(line))
    return text.strip()


_TITLE_MARKER_RE = re.compile(r"^(tekst pesme|tekst|lyrics for|.*lyrics)\b", re.IGNORECASE)


def parse_sections(text: str) -> list[Section]:
    """Split lyrics into sections by [Header] markers."""
    text = clean_raw(text)
    if not text:
        return []
    parts: list[Section] = []
    current = Section(name="", lines=[])
    for line in text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            if current.lines:
                parts.append(current)
            current = Section(name=m.group(1).strip(), lines=[])
            continue
        # Skip placeholder / unknown lines Genius sometimes leaves: "[?]"
        stripped = line.strip()
        if not stripped or stripped == "[?]":
            continue
        current.lines.append(line.rstrip())
    if current.lines:
        parts.append(current)
    # Drop title-marker sections like [Tekst pesme "X"] or [Song Title Lyrics]
    parts = [p for p in parts if not _TITLE_MARKER_RE.match(p.name)]
    return parts


def all_lines(text: str) -> list[str]:
    """All non-empty content lines, with section headers stripped."""
    return [line for sec in parse_sections(text) for line in sec.lines]


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, unicode-aware."""
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def char_count(text: str, *, include_spaces: bool = False) -> int:
    if include_spaces:
        return len(text)
    return sum(1 for c in text if not c.isspace())
