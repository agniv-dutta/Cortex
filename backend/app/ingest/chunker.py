"""Content-aware chunker (ingestion-system.md §3.1).

Splits normalized documents into retrieval/citation atoms. Boundaries depend on
doc_type; token counts are approximate (len(text.split())).
"""

from dataclasses import dataclass

# (target_tokens, overlap_tokens) per doc_type
CHUNK_CONFIG: dict[str, tuple[int, int]] = {
    "meeting": (500, 50),
    "meeting_summary": (800, 0),
    "playbook": (300, 30),
    "guideline": (300, 30),
    "decision": (500, 0),
    "contract": (350, 40),
    "template": (400, 50),
    "postmortem": (350, 30),
    "learning": (150, 0),
    "email": (500, 30),
    "action_item": (150, 0),
    "slack_digest": (800, 0),
    "vendor": (400, 40),
    "negotiation": (400, 40),
    "launch": (400, 40),
    "feedback_summary": (400, 40),
}

DEFAULT_CONFIG = (400, 50)


@dataclass
class ChunkSpec:
    content: str
    role: str = "body"
    section_path: list[str] | None = None

    @property
    def tokens(self) -> int:
        return len(self.content.split())


def _split_by_tokens(text: str, target: int, overlap: int) -> list[str]:
    paragraphs = [p for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []
    if sum(len(p.split()) for p in paragraphs) <= target:
        return [text.strip()]
    windows: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for para in paragraphs:
        para_tokens = len(para.split())
        if current and current_tokens + para_tokens > target:
            windows.append("\n".join(current).strip())
            # carry-over overlap = last paragraphs up to `overlap` tokens
            carry: list[str] = []
            carry_tokens = 0
            for prev in reversed(current):
                if carry_tokens + len(prev.split()) > overlap:
                    break
                carry.insert(0, prev)
                carry_tokens += len(prev.split())
            current = carry
            current_tokens = carry_tokens
        current.append(para)
        current_tokens += para_tokens
    if current:
        windows.append("\n".join(current).strip())
    return [w for w in windows if w]


def _role_lines(text: str) -> tuple[list[str], list[str]]:
    """Very light role tagging: lines starting with markers become 'title' chunks."""
    titles, body = [], []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and (stripped.startswith("#") or stripped.isupper() and len(stripped) < 80):
            titles.append(stripped)
        elif stripped:
            body.append(stripped)
    return titles, body


def chunk_text(text: str, doc_type: str) -> list[ChunkSpec]:
    target, overlap = CHUNK_CONFIG.get(doc_type, DEFAULT_CONFIG)
    if doc_type == "decision" or doc_type == "learning" or doc_type == "action_item":
        # keep self-contained, single chunk
        return [ChunkSpec(content=text.strip(), role=doc_type)]
    titles, body = _role_lines(text)
    sections = _split_by_tokens("\n".join(body), target, overlap)
    specs: list[ChunkSpec] = []
    for i, section in enumerate(sections):
        specs.append(ChunkSpec(content=section, role="body", section_path=[f"{i}" if not titles else titles[0]]))
    return specs or [ChunkSpec(content=text.strip())]
