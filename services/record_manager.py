"""
Record Manager Service.

Tracks generated and exported lab records so users can view, re-download,
or inspect them inside the "My Records" tab.
"""

import os
import json
import uuid
from datetime import datetime


def _get_records_file(storage_dir: str) -> str:
    return os.path.join(storage_dir, "records.json")


def get_all_records(storage_dir: str) -> list[dict]:
    """
    Returns list of all saved records, sorted by creation date descending.
    """
    records_file = _get_records_file(storage_dir)
    if not os.path.exists(records_file):
        return []

    try:
        with open(records_file, "r", encoding="utf-8") as f:
            records = json.load(f)
            if isinstance(records, list):
                # Sort newest first
                records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
                return records
    except Exception:
        pass

    return []


def save_record(
    storage_dir: str,
    filename: str,
    title: str,
    language: str,
    sections: list[str],
    saved_path: str,
    file_size_kb: float,
    meta: dict | None = None
) -> dict:
    """
    Adds a newly exported record entry to records.json.
    """
    records = get_all_records(storage_dir)

    record_id = f"rec_{uuid.uuid4().hex[:8]}"
    now = datetime.now()

    new_record = {
        "id": record_id,
        "title": title or os.path.splitext(filename)[0],
        "filename": filename,
        "language": language or "Unknown",
        "sections": sections or [],
        "created_at": now.isoformat(),
        "display_date": now.strftime("%b %d, %Y • %I:%M %p"),
        "saved_path": saved_path,
        "file_size_kb": round(file_size_kb, 1),
        "download_url": f"/api/download/{filename}",
        "meta": meta or {}
    }

    records.insert(0, new_record)

    records_file = _get_records_file(storage_dir)
    with open(records_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    return new_record


def delete_record(storage_dir: str, record_id: str) -> bool:
    """
    Deletes a record from records.json and optionally deletes the exported file.
    """
    records = get_all_records(storage_dir)
    target = None
    remaining = []

    for r in records:
        if r.get("id") == record_id:
            target = r
        else:
            remaining.append(r)

    if not target:
        return False

    records_file = _get_records_file(storage_dir)
    with open(records_file, "w", encoding="utf-8") as f:
        json.dump(remaining, f, indent=2)

    # Clean up generated file if it exists in uploads/generated
    try:
        saved_path = target.get("saved_path")
        if saved_path and os.path.exists(saved_path) and "uploads" in saved_path:
            os.remove(saved_path)
    except Exception:
        pass

    return True
