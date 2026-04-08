import json
import time
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Lazy-initialized clients
_anthropic_client = None
_openai_client = None


def get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


# Approximate cost per 1K tokens
COST_PER_1K = {
    # Anthropic models
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    # OpenAI models
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
    "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    default_key = "claude-sonnet-4-6" if settings.is_anthropic else "gpt-4o"
    rates = COST_PER_1K.get(model, COST_PER_1K[default_key])
    return round((input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"], 6)


def _call_anthropic(
    prompt: str,
    model: str,
    max_tokens: int,
    pdf_base64: Optional[str],
    system_prompt: Optional[str],
) -> dict:
    """Call the Anthropic API with a text prompt and optional PDF document."""
    import anthropic
    client = get_anthropic_client()

    print(f"\n[TRACE] ~~~ LLM CALL (Anthropic) ~~~")
    print(f"[TRACE]   Model           : {model}")
    print(f"[TRACE]   Max tokens      : {max_tokens}")
    print(f"[TRACE]   Prompt length   : {len(prompt)} chars")
    print(f"[TRACE]   Prompt preview  : {prompt[:200]}...")
    print(f"[TRACE]   Has PDF base64  : {bool(pdf_base64)} {'(' + str(len(pdf_base64)) + ' chars)' if pdf_base64 else ''}")
    print(f"[TRACE]   System prompt   : {system_prompt[:150] + '...' if system_prompt else 'None'}")

    content = []
    if pdf_base64:
        content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_base64,
            },
        })
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    start = time.time()
    try:
        kwargs["timeout"] = 120.0  # 2 minute timeout per LLM call
        response = client.messages.create(**kwargs)
    except anthropic.APIError as e:
        print(f"[TRACE]   !!! Anthropic API ERROR: {e}")
        logger.error(f"Anthropic API error: {e}")
        raise

    latency_ms = int((time.time() - start) * 1000)

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    text = response.content[0].text if response.content else ""

    print(f"[TRACE]   <<< LLM RESPONSE (Anthropic)")
    print(f"[TRACE]   Input tokens    : {input_tokens}")
    print(f"[TRACE]   Output tokens   : {output_tokens}")
    print(f"[TRACE]   Cost estimate   : ${estimate_cost(model, input_tokens, output_tokens):.6f}")
    print(f"[TRACE]   Latency         : {latency_ms}ms")
    print(f"[TRACE]   Response length : {len(text)} chars")
    print(f"[TRACE]   Response preview: {text[:200]}...")

    return {
        "content": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_estimate": estimate_cost(model, input_tokens, output_tokens),
        "latency_ms": latency_ms,
        "model": model,
    }


def _call_openai(
    prompt: str,
    model: str,
    max_tokens: int,
    resume_markdown: Optional[str],
    system_prompt: Optional[str],
) -> dict:
    """Call the OpenAI API with a text prompt and optional resume markdown."""
    from openai import OpenAIError
    client = get_openai_client()

    print(f"\n[TRACE] ~~~ LLM CALL (OpenAI) ~~~")
    print(f"[TRACE]   Model           : {model}")
    print(f"[TRACE]   Max tokens      : {max_tokens}")
    print(f"[TRACE]   Prompt length   : {len(prompt)} chars")
    print(f"[TRACE]   Prompt preview  : {prompt[:200]}...")
    print(f"[TRACE]   Has markdown    : {bool(resume_markdown)} {'(' + str(len(resume_markdown)) + ' chars)' if resume_markdown else ''}")
    print(f"[TRACE]   System prompt   : {system_prompt[:150] + '...' if system_prompt else 'None'}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Build user message: include resume markdown before the prompt if provided
    user_content = ""
    if resume_markdown:
        user_content += f"## Resume (Markdown)\n\n{resume_markdown}\n\n---\n\n"
    user_content += prompt

    messages.append({"role": "user", "content": user_content})

    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            timeout=120.0,  # 2 minute timeout per LLM call
        )
    except OpenAIError as e:
        print(f"[TRACE]   !!! OpenAI API ERROR: {e}")
        logger.error(f"OpenAI API error: {e}")
        raise

    latency_ms = int((time.time() - start) * 1000)

    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    text = response.choices[0].message.content if response.choices else ""

    print(f"[TRACE]   <<< LLM RESPONSE (OpenAI)")
    print(f"[TRACE]   Input tokens    : {input_tokens}")
    print(f"[TRACE]   Output tokens   : {output_tokens}")
    print(f"[TRACE]   Cost estimate   : ${estimate_cost(model, input_tokens, output_tokens):.6f}")
    print(f"[TRACE]   Latency         : {latency_ms}ms")
    print(f"[TRACE]   Response length : {len(text)} chars")
    print(f"[TRACE]   Response preview: {text[:200]}...")

    return {
        "content": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_estimate": estimate_cost(model, input_tokens, output_tokens),
        "latency_ms": latency_ms,
        "model": model,
    }


def call_llm(
    prompt: str,
    model: str = None,
    max_tokens: int = 4096,
    pdf_base64: Optional[str] = None,
    resume_markdown: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> dict:
    """
    Call the configured LLM provider with a text prompt.

    For Anthropic: sends optional PDF as a document block.
    For OpenAI: sends optional resume markdown as text content.

    Returns:
        dict with keys: content, input_tokens, output_tokens, cost_estimate, latency_ms, model
    """
    if settings.is_openai:
        model = model or settings.openai_default_model
        return _call_openai(prompt, model=model, max_tokens=max_tokens,
                            resume_markdown=resume_markdown, system_prompt=system_prompt)
    else:
        model = model or settings.default_model
        return _call_anthropic(prompt, model=model, max_tokens=max_tokens,
                               pdf_base64=pdf_base64, system_prompt=system_prompt)


def call_llm_json(
    prompt: str,
    model: str = None,
    max_tokens: int = 4096,
    pdf_base64: Optional[str] = None,
    resume_markdown: Optional[str] = None,
    system_prompt: Optional[str] = None,
    retry_on_parse_fail: bool = True,
) -> dict:
    """
    Call LLM and parse response as JSON. Retries once on parse failure.

    Returns:
        dict with keys: parsed (the JSON object), raw (raw text), + token/cost info
    """
    print(f"[TRACE]   call_llm_json: retry_on_parse_fail={retry_on_parse_fail}")
    result = call_llm(prompt, model=model, max_tokens=max_tokens,
                      pdf_base64=pdf_base64, resume_markdown=resume_markdown,
                      system_prompt=system_prompt)
    text = result["content"]

    parsed = _try_parse_json(text)
    if parsed is not None:
        print(f"[TRACE]   JSON parse: SUCCESS on first attempt")
        result["parsed"] = parsed
        return result

    # Retry with stricter instruction
    if retry_on_parse_fail:
        print(f"[TRACE]   JSON parse: FAILED on first attempt, retrying with strict instruction")
        logger.warning("JSON parse failed, retrying with strict instruction")
        retry_prompt = prompt + "\n\nCRITICAL: Output ONLY valid JSON. No markdown fences, no preamble, no trailing text. Start with { and end with }."
        retry_result = call_llm(retry_prompt, model=model, max_tokens=max_tokens,
                                pdf_base64=pdf_base64, resume_markdown=resume_markdown,
                                system_prompt=system_prompt)

        # Merge token counts
        result["content"] = retry_result["content"]
        result["input_tokens"] += retry_result["input_tokens"]
        result["output_tokens"] += retry_result["output_tokens"]
        result["cost_estimate"] += retry_result["cost_estimate"]
        result["latency_ms"] += retry_result["latency_ms"]

        parsed = _try_parse_json(retry_result["content"])
        if parsed is not None:
            print(f"[TRACE]   JSON parse: SUCCESS on retry attempt")
            result["parsed"] = parsed
            return result

    # Both attempts failed
    print(f"[TRACE]   JSON parse: FAILED on all attempts")
    result["parsed"] = None
    return result


def _try_parse_json(text: str):
    """Try to parse JSON from LLM output, handling markdown fences."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Try to find JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None
