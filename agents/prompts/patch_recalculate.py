PATCH_RECALCULATE_SYSTEM = """You are performing a surgical correction on a resume evaluation. You can only REMOVE unsupported claims and RECALCULATE scores. You cannot add new claims or change verified information."""

PATCH_RECALCULATE_PROMPT = """You are performing a correction pass on a resume evaluation. The following claims were verified as UNSUPPORTED by the resume — they are not backed by any direct evidence.

## Unsupported Claims (with severity)
{unsupported_claims}

## Correction Rules (follow exactly)
1. REMOVE every unsupported claim from "matched_requirements"
2. MOVE any falsely matched requirement to "gaps" with its correct priority
3. RECALCULATE each category score using the original rubric, based ONLY on verified claims
4. RECALCULATE overall score as the weighted result of updated category scores
5. Do NOT add any new claims that were not in the original evaluation
6. Do NOT change any claim that was verified as SUPPORTED
7. UPDATE the deal-breaker check if any removed claim affected a deal-breaker requirement
8. REWRITE the summary to reflect the corrected evaluation — do not reference the correction process itself

## Scoring Adjustments
- For each CRITICAL claim removed: reduce affected category by 2-3 points
- For each MODERATE claim removed: reduce affected category by 1-2 points
- For each MINOR claim removed: reduce affected category by 0-0.5 points
- Recalculate overall score from updated category scores
- If a deal-breaker requirement was only "matched" via an unsupported claim, set deal_breaker_check to FAIL

## Output Format
Return a JSON object with the corrected evaluation (same structure as original):

{{
  "overall_score": number,
  "category_scores": {{
    "hard_skills_match": number,
    "soft_skills_match": number,
    "experience_relevance": number,
    "education_certifications": number,
    "achievement_quality": number
  }},
  "matched_requirements": [
    {{
      "requirement": "string",
      "evidence": "string (exact quote from resume)"
    }}
  ],
  "gaps": [
    {{
      "requirement": "string",
      "priority": "required" | "preferred",
      "impact": "string"
    }}
  ],
  "deal_breaker_check": {{
    "status": "PASS" | "FAIL",
    "explanation": "string"
  }},
  "summary": "string (2-3 sentence corrected verdict)",
  "corrections_applied": [
    {{
      "claim_removed": "string",
      "moved_to_gaps": true | false,
      "score_impact": "string"
    }}
  ]
}}

## Original Evaluation (to be corrected)
{evaluation}

## Verified Claims (keep these unchanged)
{supported_claims}

## Job Requirements (for reference)
{jd_requirements}"""
