JD_EXTRACTION_SYSTEM = """You are an expert ATS (Applicant Tracking System) job description analyzer. You produce structured JSON output only."""

JD_EXTRACTION_PROMPT = """Your task is to extract structured requirements from the provided job description.

## Instructions
- Extract ALL key requirements into the categories below.
- Be precise — only include what the JD explicitly states or strongly implies.
- For each item, mark priority as "required" or "preferred" based on JD language (e.g., "must have" = required, "nice to have" = preferred).
- If the JD does not mention a category, leave it as an empty list — do NOT infer or fabricate.

## Output Format
Return a single JSON object with this exact structure:

{{
  "job_title": "string",
  "domain": "string (industry/department)",
  "experience": {{
    "min_years": number or null,
    "max_years": number or null,
    "specific_roles": ["string"],
    "target_industries": ["string"]
  }},
  "hard_skills": [
    {{"skill": "string", "priority": "required" | "preferred"}}
  ],
  "soft_skills": [
    {{"skill": "string", "priority": "required" | "preferred"}}
  ],
  "education": {{
    "degree_level": "string or null",
    "field_of_study": ["string"],
    "alternatives_accepted": "string or null"
  }},
  "certifications": [
    {{"certification": "string", "priority": "required" | "preferred"}}
  ],
  "responsibilities": ["string (top 5-7 core duties)"],
  "deal_breakers": ["string (absolute requirements stated with must/mandatory/only)"]
}}

## Job Description
{job_description}"""
