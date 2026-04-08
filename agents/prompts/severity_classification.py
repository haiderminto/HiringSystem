SEVERITY_CLASSIFICATION_SYSTEM = """You are an evaluation quality analyst. You assess the impact of unsupported claims on resume evaluation accuracy."""

SEVERITY_CLASSIFICATION_PROMPT = """You are given a list of claims from a resume evaluation that were verified as UNSUPPORTED (not backed by evidence in the resume). Your task is to classify each claim's severity based on its impact on the evaluation score and hiring decision.

## Severity Levels

### CRITICAL
The unsupported claim, if removed, would change the hiring recommendation or drop the score by 2+ points. Examples:
- A fabricated hard skill that is a deal-breaker requirement
- Invented years of experience that meet a minimum threshold
- A made-up certification that is listed as required
- A claimed achievement that is the primary basis for a high score

### MODERATE
The unsupported claim inflates the score by 1-2 points but would not alone change the overall recommendation. Examples:
- An overstated proficiency level for a required skill (e.g., "expert" when resume says "familiar")
- A claimed soft skill with no resume evidence that contributed to category scoring
- An exaggerated scope of responsibility

### MINOR
The unsupported claim has minimal impact on the score (less than 0.5 points). Examples:
- A preferred (not required) skill that was incorrectly marked as matched
- A slight overstatement in the summary that doesn't affect category scores
- An unsupported claim about a non-essential qualification

## Output Format
Return a JSON array:

[
  {{
    "claim": "string (the unsupported claim)",
    "severity": "CRITICAL" | "MODERATE" | "MINOR",
    "reasoning": "string (why this severity level — reference the scoring rubric and JD requirements)",
    "estimated_score_impact": number (estimated points this claim inflated the score),
    "affected_category": "string (which category score is affected: hard_skills_match, soft_skills_match, experience_relevance, education_certifications, achievement_quality)"
  }}
]

## Unsupported Claims to Classify
{unsupported_claims}

## Original Evaluation (for context on how claims affected scoring)
{evaluation}

## Job Requirements (for context on priority of affected requirements)
{jd_requirements}"""
