import os
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


def ensure_directories():
    """Ensure upload and results directories exist."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.results_dir, exist_ok=True)
