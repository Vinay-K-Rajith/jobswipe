"""
Build an isolated real-world resume dataset from combined_resumes.zip.

The output intentionally mirrors backend/data so the existing feature,
label, and portal code can consume it without schema drift.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from src.preprocessing.feature_engineering import build_pair_features, build_student_features
from src.preprocessing.resume_parser import parse_resume

DEFAULT_ZIP = Path(r"c:\Users\Asus\Downloads\combined_resumes (1).zip")
DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = DATA_DIR / "resume_realworld_raw"
PARSED_DIR = DATA_DIR / "resume_realworld_parsed"
NORMALIZED_DIR = DATA_DIR / "resume_realworld_normalized"
RNG = random.Random(42)

DEPARTMENT_MAP = {
    "computer science and engineering (ai & ml)": "AIML",
    "computer science and engineering": "CSE",
    "information technology": "IT",
    "artificial intelligence": "AIML",
    "ai & ml": "AIML",
    "aiml": "AIML",
    "aids": "AIDS",
    "ece": "ECE",
    "eee": "EEE",
    "mechanical": "MECH",
    "civil": "CIVIL",
}

SKILL_PROFICIENCIES = ["Beginner", "Intermediate", "Advanced"]
PROJECT_COMPLEXITIES = ["Basic", "Intermediate", "Advanced"]
CERT_TIERS = ["Local", "National", "Global_Standard", "Global_Premium"]
INTERNSHIP_TIERS = ["Startup", "Tier3", "Tier2", "Tier1"]
PAPER_TIERS = ["Conference", "Q3", "Q2", "Q1"]


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text and text.lower() != "nan" else fallback


def as_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        normalized = []
        for item in value:
            if isinstance(item, dict):
                item = (
                    item.get("skill_name")
                    or item.get("cert_name")
                    or item.get("project_title")
                    or item.get("title")
                    or item.get("name")
                    or ""
                )
            text = clean_text(item)
            if text:
                normalized.append(text)
        return normalized
    return [item.strip() for item in re.split(r"[,;|]", str(value)) if item.strip()]


def normalize_department(value: Any) -> str:
    text = clean_text(value).lower()
    for key, dept in DEPARTMENT_MAP.items():
        if key in text:
            return dept
    token = re.sub(r"[^A-Z]", "", clean_text(value).upper())
    if token in {"CSE", "IT", "AIML", "AIDS", "ECE", "EEE", "MECH", "CIVIL"}:
        return token
    return RNG.choice(["CSE", "IT", "AIML", "AIDS", "ECE"])


def normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z]+", " ", clean_text(value).lower()).strip()


def extract_zip(zip_path: Path) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if any(RAW_DIR.iterdir()):
        return
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(RAW_DIR)


def iter_ground_truth(root: Path) -> Dict[str, Dict[str, Any]]:
    truth_dir = root / "combined_resumes" / "ground_truth"
    records: Dict[str, Dict[str, Any]] = {}
    for path in truth_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        sid = payload.get("student_id")
        if sid:
            records[sid] = payload
    return records


def iter_pdfs(root: Path) -> Iterable[Tuple[Path, str, str, str]]:
    base = root / "combined_resumes"
    for folder in ["standard", "two_column", "table_heavy", "dense_text", "latex_style"]:
        for path in sorted((base / folder).glob("*.pdf")):
            match = re.match(r"(SRM_[A-Z]+_\d+)_resume(_v2)?", path.name)
            if not match:
                continue
            truth_id = match.group(1)
            student_id = truth_id + ("_V2" if match.group(2) else "")
            yield path, student_id, truth_id, folder


def sample_distribution(values: List[Any], fallback: Any) -> Any:
    cleaned = [value for value in values if value not in (None, "", [], 0, 0.0)]
    return RNG.choice(cleaned) if cleaned else fallback


def build_samplers(ground_truth: Dict[str, Dict[str, Any]]) -> Dict[str, List[Any]]:
    fields = {
        "cgpa": [],
        "10th_marks": [],
        "12th_marks": [],
        "department": [],
        "year_of_study": [],
        "active_backlogs": [],
        "skills": [],
        "certifications": [],
        "cert_count": [],
        "internship_count": [],
        "project_count": [],
    }
    for payload in ground_truth.values():
        gt = payload.get("ground_truth", {})
        for key in fields:
            value = gt.get(key)
            if key == "skills":
                value = gt.get("all_skills_flat", [])
            fields[key].append(value)
    return fields


def randomized_truth(student_id: str, parsed: Dict[str, Any], samplers: Dict[str, List[Any]], fmt: str) -> Dict[str, Any]:
    skills = as_list(parsed.get("skills")) or list(sample_distribution(samplers["skills"], ["Python", "SQL", "Git"]))
    certs = as_list(parsed.get("certifications")) or list(sample_distribution(samplers["certifications"], []))
    project_count = len(as_list(parsed.get("projects"))) or int(sample_distribution(samplers["project_count"], 2))
    internship_count = len(as_list(parsed.get("internships"))) or int(sample_distribution(samplers["internship_count"], 1))
    cert_count = len(certs) or int(sample_distribution(samplers["cert_count"], max(len(certs), 1)))
    while len(certs) < cert_count:
        certs.append(RNG.choice(["NPTEL - Machine Learning", "AWS Certified Cloud Practitioner", "Oracle Certified Professional: Java SE 11"]))

    return {
        "student_id": student_id,
        "format_type": fmt,
        "synthetic_ground_truth": True,
        "ground_truth": {
            "name": clean_text(parsed.get("name"), f"Realworld Student {student_id[-3:]}"),
            "cgpa": float(parsed.get("cgpa") or sample_distribution(samplers["cgpa"], 7.5)),
            "10th_marks": float(parsed.get("10th_marks") or sample_distribution(samplers["10th_marks"], 75.0)),
            "10th_board": clean_text(parsed.get("10th_board"), RNG.choice(["CBSE", "ICSE", "State Board"])),
            "12th_marks": float(parsed.get("12th_marks") or sample_distribution(samplers["12th_marks"], 75.0)),
            "12th_board": clean_text(parsed.get("12th_board"), RNG.choice(["CBSE", "ICSE", "State Board"])),
            "department": clean_text(parsed.get("department"), sample_distribution(samplers["department"], "Computer Science and Engineering")),
            "year_of_study": int(parsed.get("year_of_study") or sample_distribution(samplers["year_of_study"], 3)),
            "active_backlogs": int(parsed.get("active_backlogs") or sample_distribution(samplers["active_backlogs"], 0)),
            "all_skills_flat": skills[:8],
            "certifications": certs[:5],
            "cert_count": cert_count,
            "internship_count": internship_count,
            "project_count": project_count,
            "phone": "",
            "email": f"{student_id.lower()}@srmist.edu.in",
        },
    }


def record_from_truth(student_id: str, truth_payload: Dict[str, Any], parsed: Dict[str, Any], confidence: Dict[str, Any]) -> Dict[str, Any]:
    gt = truth_payload["ground_truth"]
    return {
        "student_id": student_id,
        "full_name": clean_text(gt.get("name"), clean_text(parsed.get("name"), student_id)),
        "gender": "Prefer not to say",
        "department": normalize_department(gt.get("department") or parsed.get("department")),
        "10th_marks": float(gt.get("10th_marks") or parsed.get("10th_marks") or 0),
        "10th_board": clean_text(gt.get("10th_board") or parsed.get("10th_board"), "NA"),
        "12th_marks": float(gt.get("12th_marks") or parsed.get("12th_marks") or 0),
        "12th_board": clean_text(gt.get("12th_board") or parsed.get("12th_board"), "NA"),
        "cgpa": float(gt.get("cgpa") or parsed.get("cgpa") or 0),
        "backlogs_history": 0,
        "active_backlogs": int(gt.get("active_backlogs") or parsed.get("active_backlogs") or 0),
        "year_of_study": int(gt.get("year_of_study") or parsed.get("year_of_study") or 3),
        "register_number": student_id,
        "email": clean_text(gt.get("email"), f"{student_id.lower()}@srmist.edu.in"),
        "resume_format": truth_payload.get("format_type") or confidence.get("format_type"),
        "parser_confidence": confidence.get("overall", "low"),
        "synthetic_ground_truth": bool(truth_payload.get("synthetic_ground_truth", False)),
        "_skills": as_list(gt.get("all_skills_flat") or parsed.get("skills")),
        "_certifications": as_list(gt.get("certifications") or parsed.get("certifications")),
        "_project_count": int(gt.get("project_count") or len(as_list(parsed.get("projects"))) or 0),
        "_internship_count": int(gt.get("internship_count") or len(as_list(parsed.get("internships"))) or 0),
        "_paper_count": int(len(as_list(parsed.get("research_papers")))),
    }


def build_child_rows(students: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], ...]:
    skills, certs, projects, internships, papers = [], [], [], [], []
    for student in students:
        sid = student["student_id"]
        for idx, skill in enumerate(student.pop("_skills", [])[:10], 1):
            skills.append({
                "student_id": sid,
                "skill_name": skill,
                "proficiency": RNG.choice(SKILL_PROFICIENCIES),
                "verified": RNG.random() > 0.35,
            })
        for idx, cert in enumerate(student.pop("_certifications", [])[:6], 1):
            certs.append({
                "cert_id": f"RW-CERT-{sid}-{idx:02d}",
                "student_id": sid,
                "cert_name": cert,
                "issuing_body": cert.split("-")[0].strip() if "-" in cert else "Issuer",
                "tier": RNG.choice(CERT_TIERS),
                "domain": RNG.choice(["Programming", "Cloud", "Data", "AI", "Web"]),
                "year_obtained": RNG.randint(2022, 2026),
            })
        for idx in range(max(1, student.pop("_project_count", 0))):
            projects.append({
                "project_id": f"RW-PROJ-{sid}-{idx + 1:02d}",
                "student_id": sid,
                "project_title": RNG.choice(["Resume Intelligence Dashboard", "Placement Eligibility Engine", "Skill Gap Analyzer", "Candidate Ranking System"]),
                "domain": RNG.choice(["AI", "Web", "Data", "Cloud", "IoT"]),
                "tech_stack": ",".join(RNG.sample(["Python", "React", "SQL", "Pandas", "FastAPI", "AWS", "Docker"], k=3)),
                "complexity": RNG.choice(PROJECT_COMPLEXITIES),
                "team_size": str(RNG.randint(1, 4)),
                "has_deployment": RNG.random() > 0.45,
                "has_github": RNG.random() > 0.25,
                "duration_weeks": RNG.randint(3, 12),
                "year": RNG.randint(2022, 2026),
            })
        for idx in range(student.pop("_internship_count", 0)):
            internships.append({
                "internship_id": f"RW-INT-{sid}-{idx + 1:02d}",
                "student_id": sid,
                "company_name": RNG.choice(["CodeWave", "DataNest", "CloudBridge", "Nexora", "FinSight"]),
                "company_tier": RNG.choice(INTERNSHIP_TIERS),
                "role": RNG.choice(["SDE Intern", "Data Analyst Intern", "ML Intern", "Web Developer Intern"]),
                "domain": RNG.choice(["AI", "Web", "Data", "Cloud"]),
                "duration_months": RNG.choice([1.0, 2.0, 3.0, 6.0]),
                "stipend": RNG.random() > 0.5,
                "mode": RNG.choice(["Remote", "Hybrid", "On-site"]),
                "year": RNG.randint(2022, 2026),
            })
        for idx in range(student.pop("_paper_count", 0)):
            papers.append({
                "paper_id": f"RW-PAPER-{sid}-{idx + 1:02d}",
                "student_id": sid,
                "title": "Applied machine learning for placement analytics",
                "publication_venue": "Student Research Conference",
                "tier": RNG.choice(PAPER_TIERS),
                "domain": "AI",
                "year_published": RNG.randint(2022, 2026),
                "is_first_author": RNG.random() > 0.4,
                "co_authors_count": RNG.randint(1, 4),
            })
    return skills, certs, projects, internships, papers


def parser_metrics(rows: List[Dict[str, Any]], parsed_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    backed = [row for row in rows if not row["synthetic_ground_truth"]]
    by_format: Dict[str, Dict[str, Any]] = {}
    parsed_by_id = {item["student_id"]: item for item in parsed_records}
    cgpa_mismatches: List[Dict[str, Any]] = []
    identity_mismatches: List[Dict[str, Any]] = []
    for row in backed:
        parsed = parsed_by_id.get(row["student_id"], {}).get("parsed", {})
        fmt = row["resume_format"]
        stats = by_format.setdefault(fmt, {
            "count": 0,
            "evaluated_count": 0,
            "identity_mismatch": 0,
            "cgpa_exact": 0,
            "cgpa_zero": 0,
            "department_exact": 0,
            "skills_overlap": [],
        })
        stats["count"] += 1
        parsed_name = parsed.get("name", "")
        truth_name = row.get("full_name", "")
        if normalize_name(parsed_name) != normalize_name(truth_name):
            stats["identity_mismatch"] += 1
            if len(identity_mismatches) < 20:
                identity_mismatches.append({
                    "student_id": row["student_id"],
                    "format": fmt,
                    "parsed_name": parsed_name,
                    "truth_name": truth_name,
                })
            continue

        stats["evaluated_count"] += 1
        parsed_cgpa = round(float(parsed.get("cgpa") or 0), 2)
        truth_cgpa = round(float(row["cgpa"] or 0), 2)
        if parsed_cgpa == 0.0:
            stats["cgpa_zero"] += 1
        if parsed_cgpa == truth_cgpa:
            stats["cgpa_exact"] += 1
        elif len(cgpa_mismatches) < 20:
            cgpa_mismatches.append({
                "student_id": row["student_id"],
                "format": fmt,
                "parsed_cgpa": parsed_cgpa,
                "truth_cgpa": truth_cgpa,
                "parsed_name": parsed.get("name", ""),
                "truth_name": row.get("full_name", ""),
            })
        if normalize_department(parsed.get("department")) == row["department"]:
            stats["department_exact"] += 1
        parsed_skills = {s.lower() for s in as_list(parsed.get("skills"))}
        truth_skills = {s.lower() for s in as_list(row.get("_skills"))}
        if truth_skills:
            stats["skills_overlap"].append(len(parsed_skills & truth_skills) / len(truth_skills))
    for stats in by_format.values():
        evaluated_count = max(stats["evaluated_count"], 1)
        stats["identity_mismatch_rate"] = round(stats["identity_mismatch"] / max(stats["count"], 1), 4)
        stats["cgpa_accuracy"] = round(stats.pop("cgpa_exact") / evaluated_count, 4)
        stats["cgpa_zero_rate"] = round(stats.pop("cgpa_zero") / evaluated_count, 4)
        stats["department_accuracy"] = round(stats.pop("department_exact") / evaluated_count, 4)
        overlaps = stats.pop("skills_overlap")
        stats["avg_skill_recall"] = round(sum(overlaps) / len(overlaps), 4) if overlaps else 0.0
    return {
        "ground_truth_backed_resumes": len(backed),
        "by_format": by_format,
        "debug": {
            "identity_mismatch_samples": identity_mismatches,
            "cgpa_mismatch_samples": cgpa_mismatches,
        },
    }


def save_csvs(students: List[Dict[str, Any]], child_rows: Tuple[List[Dict[str, Any]], ...]) -> None:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    student_cols = [
        "student_id", "full_name", "gender", "department", "10th_marks", "10th_board",
        "12th_marks", "12th_board", "cgpa", "backlogs_history", "active_backlogs",
        "year_of_study", "register_number", "email", "resume_format",
        "parser_confidence", "synthetic_ground_truth",
    ]
    pd.DataFrame(students)[student_cols].to_csv(NORMALIZED_DIR / "students.csv", index=False)
    schemas = {
        "skills": ["student_id", "skill_name", "proficiency", "verified"],
        "certifications": ["cert_id", "student_id", "cert_name", "issuing_body", "tier", "domain", "year_obtained"],
        "projects": ["project_id", "student_id", "project_title", "domain", "tech_stack", "complexity", "team_size", "has_deployment", "has_github", "duration_weeks", "year"],
        "internships": ["internship_id", "student_id", "company_name", "company_tier", "role", "domain", "duration_months", "stipend", "mode", "year"],
        "research_papers": ["paper_id", "student_id", "title", "publication_venue", "tier", "domain", "year_published", "is_first_author", "co_authors_count"],
    }
    for name, rows in zip(schemas, child_rows):
        pd.DataFrame(rows, columns=schemas[name]).to_csv(NORMALIZED_DIR / f"{name}.csv", index=False)
    shutil.copyfile(DATA_DIR / "companies.csv", NORMALIZED_DIR / "companies.csv")


def build_features_and_labels() -> None:
    students = pd.read_csv(NORMALIZED_DIR / "students.csv")
    certs = pd.read_csv(NORMALIZED_DIR / "certifications.csv")
    projects = pd.read_csv(NORMALIZED_DIR / "projects.csv")
    internships = pd.read_csv(NORMALIZED_DIR / "internships.csv")
    papers = pd.read_csv(NORMALIZED_DIR / "research_papers.csv")
    skills = pd.read_csv(NORMALIZED_DIR / "skills.csv")
    companies = pd.read_csv(NORMALIZED_DIR / "companies.csv")

    features = build_student_features(students, certs, projects, internships, papers, skills)
    features.drop(columns=["skill_list"]).to_csv(NORMALIZED_DIR / "student_features.csv", index=False)
    pairs = build_pair_features(features, companies)
    pairs.to_csv(NORMALIZED_DIR / "pair_features.csv", index=False)

    labels = generate_training_labels(pairs, companies)
    labels.to_csv(NORMALIZED_DIR / "training_labels.csv", index=False)
    ranking = generate_ranking_labels(pairs, labels, companies)
    ranking.to_csv(NORMALIZED_DIR / "ranking_labels.csv", index=False)


def generate_training_labels(pairs: pd.DataFrame, companies: pd.DataFrame) -> pd.DataFrame:
    merged = pairs.merge(
        companies[["company_id", "min_cgpa", "min_10th", "min_12th", "max_active_backlogs", "min_internship_months", "min_projects", "requires_research_paper"]],
        on="company_id",
        how="left",
    )
    merged["hard_cgpa"] = (merged["cgpa_normalized"] * 10 >= merged["min_cgpa"]).astype(int)
    merged["hard_10th"] = (merged["10th_normalized"] * 100 >= merged["min_10th"]).astype(int)
    merged["hard_12th"] = (merged["12th_normalized"] * 100 >= merged["min_12th"]).astype(int)
    merged["hard_backlogs"] = (merged["active_backlogs"] <= merged["max_active_backlogs"]).astype(int)
    merged["hard_dept"] = merged["dept_match"]
    merged["hard_pass"] = (merged["hard_cgpa"] & merged["hard_10th"] & merged["hard_12th"] & merged["hard_backlogs"] & merged["hard_dept"]).astype(int)
    merged["soft_score"] = (
        merged["required_skills_match_ratio"] * 0.25
        + merged["preferred_skills_match_ratio"] * 0.10
        + (merged["total_internship_months"] / 6.0).clip(upper=1.0) * 0.15
        + (merged["max_internship_tier"] / 5.0).clip(upper=1.0) * 0.05
        + (merged["num_projects"] / 4.0).clip(upper=1.0) * 0.10
        + merged["meets_project_complexity"] * 0.10
        + merged["meets_cert_tier"] * 0.10
        + (merged["num_papers"] / 2.0).clip(upper=1.0) * 0.05
        + (merged["num_advanced_skills"] / 3.0).clip(upper=1.0) * 0.05
        + (merged["num_verified_skills"] / 4.0).clip(upper=1.0) * 0.05
    ).clip(0, 1)
    noise = pd.Series([RNG.gauss(0, 0.03) for _ in range(len(merged))])
    merged["noisy_soft"] = (merged["soft_score"] + noise).clip(0, 1)
    merged["eligible"] = ((merged["hard_pass"] == 1) & (merged["noisy_soft"] >= 0.35)).astype(int)
    merged["criteria_score"] = (merged["hard_pass"] * merged["soft_score"]).round(4)
    return merged[["student_id", "company_id", "eligible", "criteria_score", "hard_pass", "soft_score"]]


def generate_ranking_labels(pairs: pd.DataFrame, labels: pd.DataFrame, companies: pd.DataFrame) -> pd.DataFrame:
    df = pairs.merge(labels[["student_id", "company_id", "eligible", "hard_pass"]], on=["student_id", "company_id"], how="left")
    comp_complexity = {"None": 0, "Basic": 1, "Intermediate": 2, "Advanced": 3}
    companies = companies.copy()
    companies["company_complexity_min_encoded"] = companies["project_complexity_min"].map(comp_complexity).fillna(0)
    df = df.merge(companies[["company_id", "company_complexity_min_encoded"]], on="company_id", how="left")
    df["fit_score"] = df.apply(compute_fit_score, axis=1)
    df.loc[df["hard_pass"] == 0, "fit_score"] = 0.0
    company_order = {cid: idx for idx, cid in enumerate(sorted(df["company_id"].unique()))}
    df["group_id"] = df["company_id"].map(company_order)
    df["rank_within_group"] = df.groupby("company_id")["fit_score"].rank(ascending=False, method="min").astype(int)
    df["relevance_grade"] = 0
    eligible = df["hard_pass"] == 1
    q75, q50, q25 = df.loc[eligible, "fit_score"].quantile([0.75, 0.50, 0.25])
    df.loc[eligible & (df["fit_score"] >= q75), "relevance_grade"] = 3
    df.loc[eligible & (df["fit_score"] >= q50) & (df["fit_score"] < q75), "relevance_grade"] = 2
    df.loc[eligible & (df["fit_score"] >= q25) & (df["fit_score"] < q50), "relevance_grade"] = 1
    return df[["student_id", "company_id", "group_id", "fit_score", "relevance_grade", "rank_within_group", "eligible", "hard_pass"]].sort_values(["company_id", "rank_within_group"])


def compute_fit_score(row: pd.Series) -> float:
    project_req = float(row.get("company_complexity_min_encoded", 0) or 0)
    project_score = min(float(row["max_project_complexity"]) / project_req, 1.0) if project_req else min(float(row["max_project_complexity"]) / 3.0, 1.0)
    cert_score = min(float(row.get("meets_cert_tier", 0)) * 0.7 + min(float(row.get("num_global_premium_certs", 0)) / 2.0, 0.5), 1.0)
    score = (
        row["required_skills_match_ratio"] * 0.25
        + row["preferred_skills_match_ratio"] * 0.10
        + min(row["total_internship_months"] / 6.0, 1.0) * 0.15
        + min(row["max_internship_tier"] / 5.0, 1.0) * 0.05
        + min(row["num_projects"] / 4.0, 1.0) * 0.10
        + project_score * 0.10
        + cert_score * 0.10
        + min(row["num_papers"] / 2.0, 1.0) * 0.05
        + min(row["num_advanced_skills"] / 3.0, 1.0) * 0.05
        + min(row["num_verified_skills"] / 4.0, 1.0) * 0.05
    )
    return round(float(max(0.0, min(score, 1.0))), 4)


def main(zip_path: Path = DEFAULT_ZIP) -> None:
    extract_zip(zip_path)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    root = RAW_DIR
    truth = iter_ground_truth(root)
    samplers = build_samplers(truth)

    students: List[Dict[str, Any]] = []
    parsed_records: List[Dict[str, Any]] = []
    for pdf_path, sid, truth_id, fmt in iter_pdfs(root):
        parsed, confidence = parse_resume(pdf_path)
        truth_payload = truth.get(truth_id) or randomized_truth(sid, parsed, samplers, fmt)
        truth_payload = {**truth_payload, "student_id": sid}
        parsed_records.append({
            "student_id": sid,
            "format_folder": fmt,
            "pdf_path": str(pdf_path.relative_to(root)),
            "parsed": parsed,
            "confidence": confidence,
            "synthetic_ground_truth": bool(truth_payload.get("synthetic_ground_truth", False)),
        })
        students.append(record_from_truth(sid, truth_payload, parsed, confidence))

    metrics = parser_metrics(students, parsed_records)
    child_rows = build_child_rows(students)
    save_csvs(students, child_rows)
    build_features_and_labels()

    (PARSED_DIR / "parsed_records.json").write_text(json.dumps(parsed_records, indent=2), encoding="utf-8")
    (PARSED_DIR / "parser_robustness_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({
        "students": len(students),
        "normalized_dir": str(NORMALIZED_DIR),
        "parser_metrics": metrics,
    }, indent=2))


if __name__ == "__main__":
    main()
