"""
Paper Intermediate Representation (IR)

Single source of truth for paper content.
All agents write to IR. Renderers read from IR.

Usage:
    ir = PaperIR()
    ir.set_title("基于声呐定位模型的水下目标探测与定位研究")
    ir.add_section("摘要", level=1, content=[...])
    ir.save(project_dir / "paper_ir.json")
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class ContentBlock:
    """A single content block in the paper."""
    type: str  # "paragraph", "equation", "figure", "table", "list", "heading"
    text: str = ""  # for paragraph: text with $...$ inline math
    latex: str = ""  # for equation: display LaTeX
    label: str = ""  # for equation: "(1)", "(2)", etc.
    path: str = ""  # for figure: image path
    caption: str = ""  # for figure/table: caption
    ref: str = ""  # for figure: "图1", "图2", etc.
    headers: list = field(default_factory=list)  # for table
    rows: list = field(default_factory=list)  # for table
    items: list = field(default_factory=list)  # for list
    ordered: bool = False  # for list
    level: int = 1  # for heading

    def to_dict(self) -> dict:
        d = {"type": self.type}
        if self.text: d["text"] = self.text
        if self.latex: d["latex"] = self.latex
        if self.label: d["label"] = self.label
        if self.path: d["path"] = self.path
        if self.caption: d["caption"] = self.caption
        if self.ref: d["ref"] = self.ref
        if self.headers: d["headers"] = self.headers
        if self.rows: d["rows"] = self.rows
        if self.items: d["items"] = self.items
        if self.ordered: d["ordered"] = self.ordered
        if self.level != 1: d["level"] = self.level
        return d


@dataclass
class Section:
    """A paper section with heading and content blocks."""
    heading: str
    level: int = 1
    content: list = field(default_factory=list)  # list of ContentBlock

    def to_dict(self) -> dict:
        return {
            "heading": self.heading,
            "level": self.level,
            "content": [c.to_dict() if isinstance(c, ContentBlock) else c for c in self.content],
        }


@dataclass
class PaperIR:
    """
    Paper Intermediate Representation.

    This is the single source of truth for all paper content.
    Agents write to it. Renderers read from it.
    """
    title: str = ""
    subtitle: str = ""
    abstract: str = ""
    keywords: list = field(default_factory=list)
    sections: list = field(default_factory=list)  # list of Section
    references: list = field(default_factory=list)
    figures_dir: str = ""
    metadata: dict = field(default_factory=dict)

    # ──────────────── Builder Methods ────────────────

    def set_title(self, title: str):
        self.title = title

    def set_subtitle(self, subtitle: str):
        self.subtitle = subtitle

    def set_abstract(self, abstract: str, keywords: list[str] = None):
        self.abstract = abstract
        if keywords:
            self.keywords = keywords

    def add_section(self, heading: str, level: int = 1) -> Section:
        sec = Section(heading=heading, level=level)
        self.sections.append(sec)
        return sec

    def add_references(self, refs: list[str]):
        self.references.extend(refs)

    # ──────────────── Content Helpers ────────────────

    @staticmethod
    def para(text: str) -> ContentBlock:
        """Paragraph with inline $...$ math."""
        return ContentBlock(type="paragraph", text=text)

    @staticmethod
    def eq(latex: str, label: str = "") -> ContentBlock:
        """Display equation."""
        return ContentBlock(type="equation", latex=latex, label=label)

    @staticmethod
    def fig(path: str, caption: str, ref: str = "") -> ContentBlock:
        """Figure with caption."""
        return ContentBlock(type="figure", path=path, caption=caption, ref=ref)

    @staticmethod
    def tbl(headers: list, rows: list, caption: str = "") -> ContentBlock:
        """Table."""
        return ContentBlock(type="table", headers=headers, rows=rows, caption=caption)

    @staticmethod
    def lst(items: list[str], ordered: bool = False) -> ContentBlock:
        """List."""
        return ContentBlock(type="list", items=items, ordered=ordered)

    @staticmethod
    def h2(text: str) -> ContentBlock:
        """Sub-heading within a section."""
        return ContentBlock(type="heading", text=text, level=2)

    # ──────────────── Serialization ────────────────

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "sections": [s.to_dict() if isinstance(s, Section) else s for s in self.sections],
            "references": self.references,
            "figures_dir": self.figures_dir,
            "metadata": self.metadata,
        }

    def save(self, path: Path):
        """Save IR to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Path) -> "PaperIR":
        """Load IR from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ir = cls()
        ir.title = data.get("title", "")
        ir.subtitle = data.get("subtitle", "")
        ir.abstract = data.get("abstract", "")
        ir.keywords = data.get("keywords", [])
        ir.references = data.get("references", [])
        ir.figures_dir = data.get("figures_dir", "")
        ir.metadata = data.get("metadata", {})
        for sec_data in data.get("sections", []):
            sec = Section(
                heading=sec_data["heading"],
                level=sec_data.get("level", 1),
            )
            for cb in sec_data.get("content", []):
                sec.content.append(ContentBlock(**{k: v for k, v in cb.items() if k in ContentBlock.__dataclass_fields__}))
            ir.sections.append(sec)
        return ir
