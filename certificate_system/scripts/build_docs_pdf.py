#!/usr/bin/env python3
"""Build a single PDF containing all project documentation.

This script merges:
- README.md
- docs/*.md (in a defined order)

Output:
- docs/CertificatePlatform_Documentation.pdf

It intentionally implements a small, dependency-light Markdown renderer using
ReportLab (already used in this project) rather than requiring pandoc/WeasyPrint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)


ROOT = Path(__file__).resolve().parents[1]


DOC_ORDER = [
    ROOT / "README.md",
    ROOT / "docs" / "USER_GUIDE.md",
    ROOT / "docs" / "ADMIN_GUIDE.md",
    ROOT / "docs" / "DEVELOPER_GUIDE.md",
    ROOT / "docs" / "API_INTEGRATION.md",
    ROOT / "docs" / "DEPLOYMENT.md",
    ROOT / "docs" / "CONFIG_REFERENCE.md",
    ROOT / "docs" / "TROUBLESHOOTING.md",
]


OUTPUT_PDF = ROOT / "docs" / "CertificatePlatform_Documentation.pdf"


@dataclass(frozen=True)
class RenderStyles:
    h1: ParagraphStyle
    h2: ParagraphStyle
    h3: ParagraphStyle
    body: ParagraphStyle
    bullet: ParagraphStyle
    code: ParagraphStyle
    link: ParagraphStyle


def _make_styles() -> RenderStyles:
    styles = getSampleStyleSheet()

    h1 = ParagraphStyle(
        "DocH1",
        parent=styles["Heading1"],
        fontSize=18,
        spaceBefore=8,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "DocH2",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=10,
        spaceAfter=6,
    )
    h3 = ParagraphStyle(
        "DocH3",
        parent=styles["Heading3"],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "DocBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=13,
        spaceBefore=0,
        spaceAfter=4,
    )
    bullet = ParagraphStyle(
        "DocBullet",
        parent=body,
        leftIndent=14,
        bulletIndent=6,
    )
    code = ParagraphStyle(
        "DocCode",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#1f2937"),
        backColor=colors.HexColor("#f3f4f6"),
        borderPadding=6,
        leftIndent=0,
        rightIndent=0,
        spaceBefore=4,
        spaceAfter=6,
    )
    link = ParagraphStyle(
        "DocLink",
        parent=body,
        textColor=colors.HexColor("#1d4ed8"),
    )

    return RenderStyles(h1=h1, h2=h2, h3=h3, body=body, bullet=bullet, code=code, link=link)


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _escape_for_paragraph(text: str) -> str:
    """Escape minimal XML entities used by ReportLab Paragraph."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _format_inline(text: str) -> str:
    """Handle a small subset of inline formatting.

    - inline code: `code`
    - links: [text](url) -> text (url)
    """
    text = _escape_for_paragraph(text)

    # Links -> 'label (url)'
    def repl_link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        return f"{label} ({url})"

    text = _MD_LINK_RE.sub(repl_link, text)

    # Inline code: wrap in <font face="Courier">...</font>
    parts: list[str] = []
    in_code = False
    buf = []
    for ch in text:
        if ch == "`":
            segment = "".join(buf)
            buf = []
            if in_code:
                parts.append(f'<font face="Courier">{segment}</font>')
            else:
                parts.append(segment)
            in_code = not in_code
            continue
        buf.append(ch)
    # Remaining buffer
    segment = "".join(buf)
    if in_code:
        parts.append(f'<font face="Courier">{segment}</font>')
    else:
        parts.append(segment)

    return "".join(parts)


def _render_markdown(md: str, styles: RenderStyles):
    """Very small Markdown-to-platypus renderer.

    Supports:
    - # / ## / ### headings
    - bullet lines starting with '- '
    - fenced code blocks (```)
    - paragraphs
    """
    story = []

    lines = md.splitlines()
    i = 0
    in_code = False
    code_lines: list[str] = []

    paragraph_lines: list[str] = []

    def flush_paragraph():
        nonlocal paragraph_lines
        text = " ".join([ln.strip() for ln in paragraph_lines]).strip()
        paragraph_lines = []
        if not text:
            return
        story.append(Paragraph(_format_inline(text), styles.body))

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            if in_code:
                # close
                story.append(Preformatted("\n".join(code_lines).rstrip("\n"), styles.code))
                code_lines = []
                in_code = False
            else:
                flush_paragraph()
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        stripped = line.rstrip()

        # Headings
        if stripped.startswith("# "):
            flush_paragraph()
            story.append(Paragraph(_format_inline(stripped[2:].strip()), styles.h1))
            i += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            story.append(Paragraph(_format_inline(stripped[3:].strip()), styles.h2))
            i += 1
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            story.append(Paragraph(_format_inline(stripped[4:].strip()), styles.h3))
            i += 1
            continue

        # Bullet list
        if stripped.lstrip().startswith("- "):
            flush_paragraph()
            bullet_text = stripped.lstrip()[2:].strip()
            story.append(Paragraph(_format_inline(bullet_text), styles.bullet, bulletText="•"))
            i += 1
            continue

        # Blank line -> paragraph break
        if not stripped.strip():
            flush_paragraph()
            story.append(Spacer(1, 6))
            i += 1
            continue

        paragraph_lines.append(stripped)
        i += 1

    flush_paragraph()
    if in_code and code_lines:
        story.append(Preformatted("\n".join(code_lines).rstrip("\n"), styles.code))

    return story


def build_pdf(*, input_files: list[Path], output_file: Path) -> None:
    styles = _make_styles()

    doc = SimpleDocTemplate(
        str(output_file),
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="Certificate Platform Documentation",
    )

    story = []

    for idx, path in enumerate(input_files):
        if not path.exists():
            raise FileNotFoundError(f"Missing doc file: {path}")

        md = path.read_text(encoding="utf-8")
        if idx > 0:
            story.append(PageBreak())

        story.append(Paragraph(_format_inline(path.name), styles.h3))
        story.append(Spacer(1, 6))
        story.extend(_render_markdown(md, styles))

    output_file.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)


def main() -> int:
    build_pdf(input_files=DOC_ORDER, output_file=OUTPUT_PDF)
    print(f"Wrote: {OUTPUT_PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
