from __future__ import annotations

import io
from zipfile import ZipFile

from job_app_ops.services.document_renderer import _parse_blocks
from job_app_ops.services.profile_vault import _extract_odt_text


def test_parse_blocks_handles_markdown_that_llms_commonly_emit():
    blocks = _parse_blocks(
        """**Zahid Muhammad**
**AI Software Engineer**
**Professional Summary:**
### Trading Desk Engineer
* Python and Azure delivery
- SQL validation
1. Availability by agreement
[zahidkhan27@gmail.com](mailto:zahidkhan27@gmail.com)
"""
    )

    assert blocks[0] == {"type": "heading1", "text": "Zahid Muhammad"}
    assert {"type": "paragraph", "text": "AI Software Engineer"} in blocks
    assert {"type": "heading2", "text": "Professional Summary"} in blocks
    assert {"type": "heading3", "text": "Trading Desk Engineer"} in blocks
    assert {"type": "bullet", "text": "Python and Azure delivery"} in blocks
    assert {"type": "bullet", "text": "SQL validation"} in blocks
    assert {"type": "numbered", "text": "Availability by agreement"} in blocks
    assert {"type": "paragraph", "text": "zahidkhan27@gmail.com"} in blocks


def test_extract_odt_text_reads_motivation_letter_samples():
    payload = io.BytesIO()
    content_xml = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
  <office:body>
    <office:text>
      <text:h>Motivation Letter</text:h>
      <text:p>Dear Hiring Team,</text:p>
      <text:p>I am interested in the ML Operations Engineer role.</text:p>
    </office:text>
  </office:body>
</office:document-content>
"""
    with ZipFile(payload, "w") as archive:
        archive.writestr("content.xml", content_xml)

    extracted = _extract_odt_text(payload.getvalue())

    assert "Motivation Letter" in extracted
    assert "Dear Hiring Team" in extracted
    assert "ML Operations Engineer" in extracted
