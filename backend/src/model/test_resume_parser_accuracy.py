import json
import os
import sys
from collections import defaultdict

import pandas as pd

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, BACKEND_DIR)

from src.preprocessing.resume_parser import detect_format, parse_resume

DATA_DIR = os.path.join(BACKEND_DIR, "data")
MODEL_DIR = os.path.join(BACKEND_DIR, "models")
RESUME_DIRS = [
    os.path.join(DATA_DIR, "resumes"),
    os.path.join(BACKEND_DIR, "resumes"),
]
FORMAT_TYPES = ["standard_single_column", "two_column", "table_heavy", "latex_generated", "scanned_ocr"]


def _resume_files():
    files = []
    for directory in RESUME_DIRS:
        if os.path.isdir(directory):
            files.extend(
                os.path.join(directory, name)
                for name in os.listdir(directory)
                if name.lower().endswith(".pdf")
            )
    return sorted(set(files))


def _student_id_from_path(path):
    base = os.path.basename(path)
    return base.split("_")[0]


def main():
    students = pd.read_csv(os.path.join(DATA_DIR, "students.csv")).set_index("student_id")
    skills = pd.read_csv(os.path.join(DATA_DIR, "skills.csv"))
    skill_counts = skills.groupby("student_id")["skill_name"].nunique().to_dict()

    grouped = defaultdict(list)
    for pdf_path in _resume_files():
        student_id = _student_id_from_path(pdf_path)
        if student_id not in students.index:
            continue
        result, confidence = parse_resume(pdf_path)
        fmt = confidence.get("format_type") or detect_format(pdf_path)
        true_cgpa = float(students.loc[student_id, "cgpa"])
        true_skill_count = int(skill_counts.get(student_id, 0))
        extracted_skill_count = len(result.get("skills", []))
        grouped[fmt].append({
            "cgpa_abs_error": abs(float(result.get("cgpa", 0.0)) - true_cgpa),
            "skill_recall": min(extracted_skill_count / true_skill_count, 1.0) if true_skill_count else 1.0,
        })

    summary = {}
    for fmt in FORMAT_TYPES:
        rows = grouped.get(fmt, [])
        if rows:
            summary[fmt] = {
                "cgpa_mae": round(sum(row["cgpa_abs_error"] for row in rows) / len(rows), 4),
                "skills_recall": round(sum(row["skill_recall"] for row in rows) / len(rows), 4),
                "n": len(rows),
            }
        else:
            summary[fmt] = {"cgpa_mae": None, "skills_recall": None, "n": 0}

    summary["note"] = (
        "Synthetic ReportLab resumes are expected to be mostly standard_single_column; "
        "non-standard buckets may have n=0 until targeted fixtures are added."
    )
    os.makedirs(MODEL_DIR, exist_ok=True)
    out = os.path.join(MODEL_DIR, "resume_parser_accuracy.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
