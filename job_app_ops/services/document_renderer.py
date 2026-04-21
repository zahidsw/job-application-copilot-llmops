from __future__ import annotations

import html
import re
from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from job_app_ops.schemas import GeneratedArtifact


class DocumentRenderer:
    def render_derivatives(self, artifact: GeneratedArtifact, target: Path) -> list[GeneratedArtifact]:
        if artifact.artifact_type not in {"cv", "motivation_letter"}:
            return []

        docx_path = target.with_suffix(".docx")
        pdf_path = target.with_suffix(".pdf")

        self._render_docx(artifact.content, docx_path)
        self._render_pdf(artifact.content, pdf_path)

        return [
            GeneratedArtifact(
                artifact_type=f"{artifact.artifact_type}_docx",
                file_name=docx_path.name,
                content=artifact.content,
                path=str(docx_path),
            ),
            GeneratedArtifact(
                artifact_type=f"{artifact.artifact_type}_pdf",
                file_name=pdf_path.name,
                content=artifact.content,
                path=str(pdf_path),
            ),
        ]

    def _render_docx(self, content: str, target: Path) -> None:
        document = Document()
        for block in _parse_blocks(content):
            block_type = block["type"]
            if block_type == "heading1":
                document.add_heading(block["text"], level=1)
            elif block_type == "heading2":
                document.add_heading(block["text"], level=2)
            elif block_type == "bullet":
                document.add_paragraph(block["text"], style="List Bullet")
            elif block_type == "paragraph":
                document.add_paragraph(block["text"])
            else:
                document.add_paragraph("")
        document.save(target)

    def _render_pdf(self, content: str, target: Path) -> None:
        styles = getSampleStyleSheet()
        story: list[object] = []
        bullet_buffer: list[str] = []

        def flush_bullets() -> None:
            nonlocal bullet_buffer
            if not bullet_buffer:
                return
            items = [ListItem(Paragraph(html.escape(item), styles["BodyText"])) for item in bullet_buffer]
            story.append(ListFlowable(items, bulletType="bullet"))
            story.append(Spacer(1, 8))
            bullet_buffer = []

        for block in _parse_blocks(content):
            block_type = block["type"]
            if block_type == "bullet":
                bullet_buffer.append(block["text"])
                continue

            flush_bullets()
            if block_type == "heading1":
                story.append(Paragraph(html.escape(block["text"]), styles["Heading1"]))
            elif block_type == "heading2":
                story.append(Paragraph(html.escape(block["text"]), styles["Heading2"]))
            elif block_type == "paragraph":
                story.append(Paragraph(html.escape(block["text"]), styles["BodyText"]))
            story.append(Spacer(1, 8))

        flush_bullets()
        document = SimpleDocTemplate(str(target), pagesize=A4)
        document.build(story)


def _parse_blocks(content: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for line in content.splitlines():
        text = re.sub(r"\s+", " ", line).strip()
        if not text:
            blocks.append({"type": "spacer", "text": ""})
        elif text.startswith("# "):
            blocks.append({"type": "heading1", "text": text[2:].strip()})
        elif text.startswith("## "):
            blocks.append({"type": "heading2", "text": text[3:].strip()})
        elif text.startswith("- "):
            blocks.append({"type": "bullet", "text": text[2:].strip()})
        else:
            blocks.append({"type": "paragraph", "text": text})
    return blocks
