import os
import csv
import json
from datetime import datetime

from config import settings


def get_upload_folder() -> str:
    """Create and return a date_time-based upload folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(settings.upload_dir, timestamp)
    os.makedirs(folder, exist_ok=True)
    return folder


def save_uploaded_file(file_bytes: bytes, filename: str, upload_folder: str) -> str:
    """Save uploaded file bytes to the upload folder. Returns the full path."""
    file_path = os.path.join(upload_folder, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return file_path


def save_results(results: dict, upload_folder: str) -> str:
    """Save evaluation results as JSON in the upload folder."""
    results_path = os.path.join(upload_folder, "evaluation_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    return results_path


def save_single_result(result: dict, upload_folder: str, filename: str) -> str:
    """Save a single resume evaluation result."""
    safe_name = os.path.splitext(filename)[0]
    result_path = os.path.join(upload_folder, f"result_{safe_name}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return result_path


def save_results_csv(ranked_results: list, requisition_data: dict, output_path: str) -> str:
    """
    Save evaluation results as a CSV file.

    Columns: Talent ID, Candidate Name, Email ID, Phone No., Skill,
    Total Experience, Candidate Location, Notice Period,
    Profile Match Score, Summary, Mandatory Skill (Deal Breaker),
    Hard Skill Score, Soft Skill Score
    """
    fieldnames = [
        "Talent ID",
        "Candidate Name",
        "Email ID",
        "Phone No.",
        "Skill",
        "Total Experience",
        "Candidate Location",
        "Notice Period",
        "Profile Match Score",
        "Summary",
        "Mandatory Skill (Deal Breaker)",
        "Hard Skill Score",
        "Soft Skill Score",
    ]

    req_id = requisition_data.get("Requisition ID", "")

    rows = []
    for result in ranked_results:
        contact = result.get("candidate_contact", {})
        eval_ = result.get("candidate_evaluation", {})
        cat_scores = eval_.get("category_scores", {})
        deal_breaker = eval_.get("deal_breaker_check", {})
        deal_str = deal_breaker.get("status", "")
        if deal_breaker.get("explanation"):
            deal_str += " — " + deal_breaker["explanation"]

        row = {
            "Talent ID": req_id,
            "Candidate Name": contact.get("name", ""),
            "Email ID": contact.get("email", ""),
            "Phone No.": contact.get("phone", ""),
            "Skill": contact.get("skill", ""),
            "Total Experience": contact.get("total_experience", ""),
            "Candidate Location": contact.get("location", ""),
            "Notice Period": "",
            "Profile Match Score": eval_.get("overall_score", ""),
            "Summary": eval_.get("summary", ""),
            "Mandatory Skill (Deal Breaker)": deal_str,
            "Hard Skill Score": cat_scores.get("hard_skills_match", ""),
            "Soft Skill Score": cat_scores.get("soft_skills_match", ""),
        }
        rows.append(row)

    # Ensure parent directory exists
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def ensure_directories():
    """Ensure upload and results directories exist."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.results_dir, exist_ok=True)
