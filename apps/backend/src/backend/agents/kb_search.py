from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

KB_DIR = Path(__file__).resolve().parents[3] / "kb"


@dataclass
class KBSection:
    file: str
    heading: str
    content: str
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "heading": self.heading,
            "content": self.content,
        }


def load_kb_sections(team: str = "default") -> list[KBSection]:
    """Load all KB markdown files and split by ## headings into sections."""
    default_dir = KB_DIR / "default"
    team_dir = KB_DIR / team

    if not default_dir.exists():
        return []

    files: dict[str, Path] = {}
    for md_file in sorted(default_dir.glob("*.md")):
        files[md_file.name] = md_file
    if team != "default" and team_dir.exists():
        for md_file in sorted(team_dir.glob("*.md")):
            files[md_file.name] = md_file

    sections: list[KBSection] = []
    for name in sorted(files):
        content = files[name].read_text()
        parts = re.split(r"^(## .+)$", content, flags=re.MULTILINE)

        # Handle preamble (content before first ##)
        if parts[0].strip():
            sections.append(
                KBSection(
                    file=name,
                    heading=name.removesuffix(".md").replace("_", " ").title(),
                    content=parts[0].strip(),
                    keywords=_extract_keywords(parts[0]),
                )
            )

        for i in range(1, len(parts), 2):
            heading = parts[i].lstrip("# ").strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            sections.append(
                KBSection(
                    file=name,
                    heading=heading,
                    content=body,
                    keywords=_extract_keywords(f"{heading} {body}"),
                )
            )

    return sections


def _extract_keywords(text: str) -> list[str]:
    return list(set(re.findall(r"[a-z0-9]+", text.lower())))


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def search_knowledge_base(
    query: str, team: str = "default", top_k: int = 5
) -> list[KBSection]:
    """Search KB sections by keyword overlap with query."""
    sections = load_kb_sections(team=team)
    query_tokens = _tokenize(query)

    if not query_tokens:
        return sections[:top_k]

    scored: list[tuple[float, int, KBSection]] = []
    for idx, section in enumerate(sections):
        section_tokens = set(section.keywords)
        overlap = len(query_tokens & section_tokens)
        if overlap > 0:
            scored.append((overlap, -idx, section))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [section for _, _, section in scored[:top_k]]
