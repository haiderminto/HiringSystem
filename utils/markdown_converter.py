"""
Convert resume files (PDF, DOCX) to Markdown format for OpenAI API consumption.
"""

import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def convert_pdf_to_markdown(file_path: str) -> str:
    """
    Convert a PDF file to Markdown by extracting structured text with PyMuPDF.
    Preserves headings, bold/italic, and list structures where detectable.
    """
    try:
        doc = fitz.open(file_path)
        md_parts = []

        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            for block in blocks:
                if block["type"] != 0:  # skip image blocks
                    continue

                for line in block.get("lines", []):
                    line_text = ""
                    is_bold = False
                    is_large = False

                    for span in line.get("spans", []):
                        text = span["text"]
                        if not text.strip():
                            line_text += text
                            continue

                        font_size = span.get("size", 12)
                        flags = span.get("flags", 0)
                        span_bold = bool(flags & 2 ** 4)  # bit 4 = bold
                        span_italic = bool(flags & 2 ** 1)  # bit 1 = italic

                        if font_size >= 16:
                            is_large = True
                            is_bold = True
                        elif span_bold:
                            is_bold = True

                        if span_bold and span_italic:
                            line_text += f"***{text}***"
                        elif span_bold:
                            line_text += f"**{text}**"
                        elif span_italic:
                            line_text += f"*{text}*"
                        else:
                            line_text += text

                    line_text = line_text.strip()
                    if not line_text:
                        continue

                    # Detect heading-like lines (large font, bold, short)
                    if is_large and len(line_text) < 100:
                        md_parts.append(f"\n## {line_text.replace('**', '').replace('*', '')}\n")
                    elif is_bold and len(line_text) < 80 and not line_text.startswith(("•", "-", "●")):
                        md_parts.append(f"\n### {line_text.replace('**', '').replace('*', '')}\n")
                    elif line_text.startswith(("•", "●", "○", "▪")):
                        md_parts.append(f"- {line_text[1:].strip()}")
                    else:
                        md_parts.append(line_text)

            if page_num < len(doc) - 1:
                md_parts.append("\n---\n")

        doc.close()

        markdown = "\n".join(md_parts).strip()

        # Clean up excessive blank lines
        while "\n\n\n" in markdown:
            markdown = markdown.replace("\n\n\n", "\n\n")

        return markdown

    except Exception as e:
        logger.error(f"PDF to Markdown conversion failed: {e}")
        return ""


def convert_docx_to_markdown(file_path: str) -> str:
    """
    Convert a DOCX file to Markdown using mammoth library.
    Falls back to basic python-docx extraction if mammoth is unavailable.
    """
    try:
        import mammoth
        with open(file_path, "rb") as f:
            result = mammoth.convert_to_markdown(f)
            markdown = result.value.strip()
            if markdown:
                return markdown
    except ImportError:
        logger.warning("mammoth not installed, falling back to python-docx extraction")
    except Exception as e:
        logger.warning(f"mammoth conversion failed: {e}, falling back to python-docx")

    # Fallback: basic markdown from python-docx
    try:
        from docx import Document
        doc = Document(file_path)
        md_parts = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                md_parts.append("")
                continue

            style_name = (para.style.name or "").lower()

            if "heading 1" in style_name:
                md_parts.append(f"# {text}")
            elif "heading 2" in style_name:
                md_parts.append(f"## {text}")
            elif "heading 3" in style_name:
                md_parts.append(f"### {text}")
            elif "list" in style_name:
                md_parts.append(f"- {text}")
            else:
                # Check for bold runs
                if para.runs and all(r.bold for r in para.runs if r.text.strip()):
                    md_parts.append(f"**{text}**")
                else:
                    md_parts.append(text)

        markdown = "\n".join(md_parts).strip()
        while "\n\n\n" in markdown:
            markdown = markdown.replace("\n\n\n", "\n\n")
        return markdown

    except Exception as e:
        logger.error(f"DOCX to Markdown fallback failed: {e}")
        return ""
