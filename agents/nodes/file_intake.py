import os
import time
import logging

from agents.state import AgentState
from config import settings
from utils.pdf_utils import validate_pdf, extract_text_from_pdf, encode_pdf_base64
from utils.file_converter import validate_docx, convert_docx_to_pdf, extract_text_from_docx
from utils.markdown_converter import convert_pdf_to_markdown, convert_docx_to_markdown

logger = logging.getLogger(__name__)

NODE_NAME = "FILE_INTAKE"


def run(state: AgentState) -> AgentState:
    """
    Node 1: Accept the raw resume file, detect its type, produce appropriate format.

    Anthropic flow:
      - PDF: validate, encode base64, extract text
      - DOCX: convert to PDF, encode base64, extract text

    OpenAI flow:
      - PDF: validate, convert to markdown, extract text
      - DOCX: convert to markdown, extract text
    """
    start = time.time()
    state.current_node = NODE_NAME
    state.path_taken.append(NODE_NAME)

    file_path = state.resume_file_path
    file_type = state.resume_file_type
    use_anthropic = settings.is_anthropic

    print(f"[TRACE]   FILE_INTAKE: file_path={file_path}, file_type={file_type}, provider={'anthropic' if use_anthropic else 'openai'}")

    conversion_performed = False
    conversion_success = False
    page_count = 0
    fallback_mode = False
    text_length = 0
    markdown_length = 0

    try:
        if file_type == "pdf":
            # Validate PDF
            validation = validate_pdf(file_path)
            if not validation["valid"]:
                raise ValueError(f"Invalid PDF: {validation['error']}")

            page_count = validation["page_count"]
            if validation["unusual"]:
                logger.warning(f"Resume has {page_count} pages (unusual for a resume)")

            if use_anthropic:
                # Anthropic: send PDF as base64 document block
                state.resume_pdf_path = file_path
                state.resume_base64 = encode_pdf_base64(file_path)
                state.resume_extracted_text = extract_text_from_pdf(file_path)
                text_length = len(state.resume_extracted_text)
            else:
                # OpenAI: convert PDF to markdown
                state.resume_markdown = convert_pdf_to_markdown(file_path)
                markdown_length = len(state.resume_markdown)
                # Also extract plain text as fallback
                state.resume_extracted_text = extract_text_from_pdf(file_path)
                text_length = len(state.resume_extracted_text)

                if not state.resume_markdown and state.resume_extracted_text:
                    # Fallback: use plain text as markdown
                    state.resume_markdown = state.resume_extracted_text
                    markdown_length = len(state.resume_markdown)
                    logger.warning("PDF to markdown conversion produced empty result, using plain text")

        elif file_type == "docx":
            # Validate DOCX
            validation = validate_docx(file_path)
            if not validation["valid"]:
                raise ValueError(f"Invalid DOCX: {validation['error']}")

            if use_anthropic:
                # Anthropic: convert DOCX to PDF, then send as base64
                conversion_performed = True
                conversion_result = convert_docx_to_pdf(file_path)

                if conversion_result["success"]:
                    conversion_success = True
                    state.resume_pdf_path = conversion_result["pdf_path"]
                    state.resume_base64 = encode_pdf_base64(conversion_result["pdf_path"])

                    pdf_validation = validate_pdf(conversion_result["pdf_path"])
                    page_count = pdf_validation["page_count"]
                else:
                    # Fallback to text-only mode
                    logger.warning(f"PDF conversion failed: {conversion_result['error']}. Using text-only mode.")
                    fallback_mode = True
                    state.resume_base64 = None

                # Always extract text as fallback
                state.resume_extracted_text = extract_text_from_docx(file_path)
                text_length = len(state.resume_extracted_text)
            else:
                # OpenAI: convert DOCX to markdown
                conversion_performed = True
                state.resume_markdown = convert_docx_to_markdown(file_path)
                markdown_length = len(state.resume_markdown)

                # Also extract plain text as fallback
                state.resume_extracted_text = extract_text_from_docx(file_path)
                text_length = len(state.resume_extracted_text)

                if state.resume_markdown:
                    conversion_success = True
                elif state.resume_extracted_text:
                    # Fallback: use plain text as markdown
                    state.resume_markdown = state.resume_extracted_text
                    markdown_length = len(state.resume_markdown)
                    logger.warning("DOCX to markdown conversion produced empty result, using plain text")
                    fallback_mode = True

        else:
            state.error = f"Unsupported file format: '{file_type}'. Please upload PDF or DOCX."
            return state

        # Verify we have content
        if use_anthropic:
            if not state.resume_base64 and not state.resume_extracted_text:
                state.error = "Could not extract any content from the resume file."
                return state
        else:
            if not state.resume_markdown and not state.resume_extracted_text:
                state.error = "Could not extract any content from the resume file."
                return state

    except Exception as e:
        logger.error(f"FILE_INTAKE error: {e}")
        state.error = str(e)
        return state

    latency_ms = int((time.time() - start) * 1000)

    print(f"[TRACE]   FILE_INTAKE results: text_len={text_length}, markdown_len={markdown_length}, "
          f"has_base64={bool(state.resume_base64)}, pages={page_count}, "
          f"conversion={'yes' if conversion_performed else 'no'}, fallback={fallback_mode}, latency={latency_ms}ms")

    state.log_node({
        "node": NODE_NAME,
        "timestamp": time.time(),
        "input_file_type": file_type,
        "llm_provider": settings.llm_provider,
        "conversion_performed": conversion_performed,
        "conversion_success": conversion_success,
        "page_count": page_count,
        "text_extraction_length": text_length,
        "markdown_length": markdown_length,
        "fallback_mode": fallback_mode,
        "latency_ms": latency_ms,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_estimate": 0.0,
    })

    return state
