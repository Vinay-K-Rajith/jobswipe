"""
FastAPI Main Application for Bias-Free AI Placement System.
Provides REST endpoints for eligibility checking, company management,
and improvement plans.
"""

import os
import sys
import json
import pandas as pd
import math
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

def clean_nan(obj):
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


# Add backend root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.preprocessing.feature_engineering import (
    load_all_data, build_student_features, compute_skill_match
)
from src.explainability.criteria_checker import check_criteria
from src.explainability.explanation_generator import generate_explanation, generate_detailed_report
from src.explainability.improvement_planner import generate_improvement_plan
from app.services.bias_reduction import (
    counterfactual_rules,
    fairness_comparison,
    get_fairness_history,
    load_bias_recommendations,
    preview_substitution,
    retrain_constrained_model,
    save_bias_recommendation,
    simulate_fix,
)

# Try to load classifier model (may not be trained yet)
try:
    from src.model.inference import load_model, run_inference, build_inference_features
    model, scaler, feature_cols = load_model()
    MODEL_LOADED = True
except Exception as e:
    print(f"Warning: Classifier model not loaded: {e}")
    MODEL_LOADED = False
    model, scaler, feature_cols = None, None, None

# Try to load Option 1 — XGBoost Ranker
try:
    import pickle, json as _json
    _mdir = os.path.join(os.path.dirname(__file__), '..', 'models')
    with open(os.path.join(_mdir, 'ranker.pkl'), 'rb') as f:           ranker = pickle.load(f)
    with open(os.path.join(_mdir, 'ranker_scaler.pkl'), 'rb') as f:   ranker_scaler = pickle.load(f)
    with open(os.path.join(_mdir, 'ranker_feature_columns.json')) as f: ranker_feat_cols = _json.load(f)
    RANKER_LOADED = True
    print("Option 1 ranker loaded")
except Exception as e:
    print(f"Warning: Ranker not loaded: {e}")
    RANKER_LOADED = False
    ranker = ranker_scaler = ranker_feat_cols = None

# Try to load Option 2 — Skill Recommender
try:
    with open(os.path.join(_mdir, 'skill_recommender.pkl'), 'rb') as f:               skill_rec_model = pickle.load(f)
    with open(os.path.join(_mdir, 'skill_recommender_scaler.pkl'), 'rb') as f:        skill_rec_scaler = pickle.load(f)
    with open(os.path.join(_mdir, 'skill_recommender_label_encoder.pkl'), 'rb') as f: skill_rec_le = pickle.load(f)
    with open(os.path.join(_mdir, 'skill_recommender_features.json')) as f:           skill_rec_feat_cols = _json.load(f)
    SKILL_REC_LOADED = True
    print("Option 2 skill recommender loaded")
except Exception as e:
    print(f"Warning: Skill recommender not loaded: {e}")
    SKILL_REC_LOADED = False
    skill_rec_model = skill_rec_scaler = skill_rec_le = skill_rec_feat_cols = None

# Option 3 — Bias report is read from JSON on demand (no model object needed)
_bias_report_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'criteria_bias_report.json')
BIAS_REPORT_AVAILABLE = os.path.exists(_bias_report_path)
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

app = FastAPI(
    title="Bias-Free AI Placement System",
    description="Criteria-driven, transparent placement eligibility assessment",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Load data at startup ----------
students_df = None
companies_df = None
student_features_df = None
skills_df = None


def load_data():
    global students_df, companies_df, student_features_df, skills_df
    try:
        students_raw, certs, projects, internships, papers, skills, companies = load_all_data()
        students_df = students_raw
        companies_df = companies
        skills_df = skills
        student_features_df = build_student_features(
            students_raw, certs, projects, internships, papers, skills
        )
        print(f"Loaded {len(students_df)} students, {len(companies_df)} companies")
    except Exception as e:
        print(f"Error loading data: {e}")


load_data()


def compute_department_match_ratio(department: str) -> float:
    """Share of companies whose department restrictions include this department."""
    if companies_df is None or companies_df.empty:
        return 0.0

    matches = 0
    for value in companies_df["allowed_departments"].fillna("").tolist():
        allowed = {d.strip() for d in str(value).split(",") if d.strip()}
        if department in allowed:
            matches += 1

    return matches / len(companies_df)


# ---------- Pydantic Models ----------
class EligibilityRequest(BaseModel):
    student_id: str
    company_id: str


class BatchEligibilityRequest(BaseModel):
    company_id: str
    student_ids: Optional[List[str]] = None  # None = check all students


class CompanyCreate(BaseModel):
    company_name: str
    industry: str = "Tech"
    tier: str = "Tier2"
    min_cgpa: float = 6.0
    min_10th: float = 60.0
    min_12th: float = 60.0
    max_active_backlogs: int = 0
    allowed_departments: str = "CSE,IT,AIML,AIDS"
    required_skills: str = "Python"
    preferred_skills: str = ""
    min_internship_months: float = 0
    internship_tier_preference: str = "Any"
    min_projects: int = 0
    project_complexity_min: str = "Basic"
    requires_research_paper: bool = False
    cert_tier_required: str = "None"
    role_offered: str = "SDE"
    package_lpa: float = 5.0
    bond_years: int = 0


class BiasSimulationRequest(BaseModel):
    company_id: str
    criterion: str


class BiasRecommendationRequest(BaseModel):
    company_id: str
    criterion: str
    current_threshold: Optional[Any] = None
    recommended_threshold: Optional[Any] = None
    current_disparity: Optional[float] = None
    projected_disparity: Optional[float] = None
    current_pool_size: Optional[int] = None
    projected_pool_size: Optional[int] = None
    status: str = "proposed"
    recommendation_type: str = "threshold"
    simulation_payload: Optional[Dict[str, Any]] = None


class CounterfactualRulesRequest(BaseModel):
    company_id: str


class SubstitutionSpecRequest(BaseModel):
    remove_criterion: str
    substitution: Dict[str, Any]


class BiasSubstitutionPreviewRequest(BaseModel):
    company_id: str
    remove_criterion: str
    substitution: Dict[str, Any]


class ConstrainedRetrainRequest(BaseModel):
    company_id: str
    epsilon: float
    triggered_by: str = "admin-dashboard"


# ---------- API Endpoints ----------

@app.get("/")
async def root():
    return {
        "name": "Bias-Free AI Placement System",
        "version": "1.0.0",
        "model_loaded": MODEL_LOADED,
        "students_count": len(students_df) if students_df is not None else 0,
        "companies_count": len(companies_df) if companies_df is not None else 0,
    }


@app.get("/api/students")
async def get_students(
    department: Optional[str] = None,
    min_cgpa: Optional[float] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
):
    """Get students with optional filtering."""
    if students_df is None:
        raise HTTPException(500, "Data not loaded")

    df = students_df.copy()
    if department:
        df = df[df["department"] == department]
    if min_cgpa:
        df = df[df["cgpa"] >= min_cgpa]

    total = len(df)
    df = df.iloc[offset:offset + limit]

    # Don't expose gender in API responses (bias prevention)
    columns_to_return = [c for c in df.columns if c not in ["gender"]]
    records = df[columns_to_return].to_dict(orient="records")

    return {"total": total, "students": clean_nan(records)}


@app.get("/api/students/{student_id}")
async def get_student(student_id: str):
    """Get a single student's full profile."""
    if students_df is None:
        raise HTTPException(500, "Data not loaded")

    student = students_df[students_df["student_id"] == student_id]
    if student.empty:
        raise HTTPException(404, f"Student {student_id} not found")

    record = student.iloc[0].to_dict()

    # Add aggregated features if available
    if student_features_df is not None:
        features = student_features_df[student_features_df["student_id"] == student_id]
        if not features.empty:
            feat_dict = features.iloc[0].to_dict()
            # Remove skill_list (not JSON serializable directly)
            skill_list = feat_dict.pop("skill_list", [])
            record["features"] = feat_dict
            record["skill_list"] = skill_list

    return clean_nan(record)


@app.get("/api/companies")
async def get_companies(
    tier: Optional[str] = None,
    industry: Optional[str] = None,
):
    """Get all companies with optional filtering."""
    if companies_df is None:
        raise HTTPException(500, "Data not loaded")

    df = companies_df.copy()
    if tier:
        df = df[df["tier"] == tier]
    if industry:
        df = df[df["industry"] == industry]

    return {"total": len(df), "companies": clean_nan(df.to_dict(orient="records"))}


@app.get("/api/companies/{company_id}")
async def get_company(company_id: str):
    """Get a single company's requirements."""
    if companies_df is None:
        raise HTTPException(500, "Data not loaded")

    company = companies_df[companies_df["company_id"] == company_id]
    if company.empty:
        raise HTTPException(404, f"Company {company_id} not found")

    return clean_nan(company.iloc[0].to_dict())


@app.post("/api/eligibility/check")
async def check_eligibility(request: EligibilityRequest):
    """Check eligibility of a student for a company."""
    if students_df is None or companies_df is None:
        raise HTTPException(500, "Data not loaded")

    student_feat = student_features_df[
        student_features_df["student_id"] == request.student_id
    ]
    if student_feat.empty:
        raise HTTPException(404, f"Student {request.student_id} not found")

    company = companies_df[companies_df["company_id"] == request.company_id]
    if company.empty:
        raise HTTPException(404, f"Company {request.company_id} not found")

    student_data = student_feat.iloc[0].to_dict()
    company_data = company.iloc[0].to_dict()
    student_skills = student_data.get("skill_list", [])

    # Also get raw student data for criteria checker
    raw_student = students_df[students_df["student_id"] == request.student_id].iloc[0].to_dict()
    student_data.update(raw_student)

    # Run criteria check
    scorecard = check_criteria(student_data, company_data, student_skills)
    explanation = generate_explanation(scorecard, company_data.get("company_name", ""))

    # Run ML model if available
    ml_result = None
    if MODEL_LOADED:
        try:
            result = run_inference(student_data, company_data, model, scaler, feature_cols)
            ml_result = {
                "eligible": result["eligible"],
                "score": result["score"],
                "message": result["message"],
            }
        except Exception as e:
            ml_result = {"error": str(e)}

    # Generate improvement plan if not eligible
    improvement = None
    summary = scorecard.get("_summary", {})
    if not summary.get("eligible", False):
        improvement = generate_improvement_plan(
            scorecard, company_data.get("company_name", ""), company_data
        )

    # Build response (serialize scorecard)
    safe_scorecard = {}
    for key, val in scorecard.items():
        if key == "_summary":
            safe_scorecard[key] = val
        else:
            safe_scorecard[key] = {
                "passed": val.get("passed"),
                "message": val.get("message", ""),
                "is_hard": val.get("is_hard", False),
            }

    return {
        "student_id": request.student_id,
        "company_id": request.company_id,
        "criteria_eligible": summary.get("eligible", False),
        "ml_result": ml_result,
        "scorecard": safe_scorecard,
        "explanation": explanation,
        "improvement_plan": improvement,
    }


@app.post("/api/eligibility/batch")
async def batch_check_eligibility(request: BatchEligibilityRequest):
    """Check eligibility of multiple students for a company."""
    if students_df is None or companies_df is None:
        raise HTTPException(500, "Data not loaded")

    company = companies_df[companies_df["company_id"] == request.company_id]
    if company.empty:
        raise HTTPException(404, f"Company {request.company_id} not found")

    company_data = company.iloc[0].to_dict()

    if request.student_ids:
        student_ids = request.student_ids
    else:
        student_ids = students_df["student_id"].tolist()

    results = []
    for sid in student_ids:
        student_feat = student_features_df[student_features_df["student_id"] == sid]
        if student_feat.empty:
            continue

        student_data = student_feat.iloc[0].to_dict()
        raw_student = students_df[students_df["student_id"] == sid].iloc[0].to_dict()
        student_data.update(raw_student)

        student_skills = student_data.get("skill_list", [])
        scorecard = check_criteria(student_data, company_data, student_skills)
        summary = scorecard.get("_summary", {})

        score = 0.0
        if MODEL_LOADED:
            try:
                result = run_inference(student_data, company_data, model, scaler, feature_cols)
                score = result["score"]
            except:
                pass

        results.append({
            "student_id": sid,
            "full_name": raw_student.get("full_name", ""),
            "department": raw_student.get("department", ""),
            "cgpa": raw_student.get("cgpa", 0),
            "eligible": summary.get("eligible", False),
            "score": round(score, 4),
            "hard_pass": summary.get("hard_pass", False),
            "hard_failures": summary.get("hard_failures", []),
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    eligible_count = sum(1 for r in results if r["eligible"])

    return {
        "company_id": request.company_id,
        "company_name": company_data.get("company_name", ""),
        "total_checked": len(results),
        "eligible_count": eligible_count,
        "ineligible_count": len(results) - eligible_count,
        "results": results,
    }


@app.get("/api/model/metrics")
async def get_model_metrics():
    """Get model training metrics."""
    metrics_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'metrics.json')
    if not os.path.exists(metrics_path):
        raise HTTPException(404, "Model metrics not found (model not trained yet)")

    with open(metrics_path) as f:
        metrics = json.load(f)

    fairness_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'fairness_report.json')
    fairness = None
    if os.path.exists(fairness_path):
        with open(fairness_path) as f:
            fairness = json.load(f)

    return {
        "model_loaded": MODEL_LOADED,
        "metrics": metrics,
        "fairness": fairness,
    }


@app.get("/api/stats")
async def get_stats():
    """Get system statistics."""
    if students_df is None:
        raise HTTPException(500, "Data not loaded")

    stats = {
        "total_students": len(students_df),
        "total_companies": len(companies_df) if companies_df is not None else 0,
        "departments": students_df["department"].value_counts().to_dict(),
        "avg_cgpa": round(float(students_df["cgpa"].mean()), 2),
        "cgpa_distribution": {
            "below_6": int((students_df["cgpa"] < 6).sum()),
            "6_to_7.5": int(((students_df["cgpa"] >= 6) & (students_df["cgpa"] < 7.5)).sum()),
            "7.5_to_8.5": int(((students_df["cgpa"] >= 7.5) & (students_df["cgpa"] < 8.5)).sum()),
            "8.5_to_9.5": int(((students_df["cgpa"] >= 8.5) & (students_df["cgpa"] < 9.5)).sum()),
            "above_9.5": int((students_df["cgpa"] >= 9.5).sum()),
        },
        "company_tiers": companies_df["tier"].value_counts().to_dict() if companies_df is not None else {},
        "model_loaded": MODEL_LOADED,
        "ranker_loaded": RANKER_LOADED,
        "skill_rec_loaded": SKILL_REC_LOADED,
        "bias_report_available": BIAS_REPORT_AVAILABLE,
    }
    return stats


@app.get("/api/skill-deficits")
async def get_skill_deficits(limit: int = Query(default=8, le=25)):
    """Get cohort-level missing-skill aggregates for company-required skills."""
    if students_df is None or companies_df is None or skills_df is None:
        raise HTTPException(500, "Data not loaded")

    total_students = len(students_df)
    required_skill_counts = {}
    for value in companies_df["required_skills"].fillna("").tolist():
        for skill in str(value).split(","):
            normalized = skill.strip()
            if normalized:
                key = normalized.lower()
                required_skill_counts[key] = {
                    "skill": normalized,
                    "company_demand": required_skill_counts.get(key, {}).get("company_demand", 0) + 1,
                }

    student_skill_counts = (
        skills_df.assign(skill_key=skills_df["skill_name"].astype(str).str.strip().str.lower())
        .drop_duplicates(["student_id", "skill_key"])
        .groupby("skill_key")["student_id"]
        .nunique()
        .to_dict()
    )

    deficits = []
    for skill_key, demand_info in required_skill_counts.items():
        students_with_skill = int(student_skill_counts.get(skill_key, 0))
        missing_students = max(total_students - students_with_skill, 0)
        missing_share = missing_students / total_students if total_students else 0
        coverage_share = students_with_skill / total_students if total_students else 0

        if missing_share >= 0.85:
            severity = "Critical"
        elif missing_share >= 0.7:
            severity = "High"
        elif missing_share >= 0.5:
            severity = "Moderate"
        else:
            severity = "Low"

        deficits.append({
            "skill": demand_info["skill"],
            "students_with_skill": students_with_skill,
            "missing_students": missing_students,
            "missing_share": round(missing_share, 4),
            "coverage_share": round(coverage_share, 4),
            "company_demand": int(demand_info["company_demand"]),
            "severity": severity,
        })

    deficits.sort(
        key=lambda item: (
            item["missing_share"] * item["company_demand"],
            item["company_demand"],
            item["missing_students"],
        ),
        reverse=True,
    )

    return {
        "total_students": total_students,
        "deficits": deficits[:limit],
    }


# ═══════════════════════════════════════════════════════════
# OPTION 1 — ML Ranked Shortlist
# GET /api/ml/ranked-shortlist/{company_id}?top_k=20
# ═══════════════════════════════════════════════════════════
@app.get("/api/ml/ranked-shortlist/{company_id}")
async def get_ranked_shortlist(company_id: str, top_k: int = Query(default=20, le=800)):
    """Return ML-ranked shortlist of students for a company (Option 1)."""
    if not RANKER_LOADED:
        raise HTTPException(503, "Ranker model not loaded. Run: python -m src.model.run_ranking")
    if student_features_df is None or companies_df is None:
        raise HTTPException(500, "Data not loaded")

    company = companies_df[companies_df["company_id"] == company_id]
    if company.empty:
        raise HTTPException(404, f"Company {company_id} not found")
    company_data = company.iloc[0].to_dict()

    # Build feature rows for all students vs this company
    import numpy as np
    from src.preprocessing.feature_engineering import compute_skill_match, COMPANY_COMPLEXITY_MAP, COMPANY_CERT_TIER_MAP

    allowed_depts = [d.strip() for d in str(company_data.get("allowed_departments", "")).split(",")]
    company_min_complexity = COMPANY_COMPLEXITY_MAP.get(company_data.get("project_complexity_min", "None"), 0)
    company_cert_req = COMPANY_CERT_TIER_MAP.get(str(company_data.get("cert_tier_required", "None")), 0)

    rows = []
    for _, sf in student_features_df.iterrows():
        dept_match = 1 if sf["department"] in allowed_depts else 0
        req_ratio, pref_ratio = compute_skill_match(
            sf.get("skill_list", []),
            company_data.get("required_skills", ""),
            company_data.get("preferred_skills", ""),
        )
        meets_complexity = 1 if sf.get("max_project_complexity", 0) >= company_min_complexity else 0
        meets_cert = 1 if sf.get("max_cert_tier", 0) >= company_cert_req else 0

        rows.append({
            "student_id": sf["student_id"],
            "cgpa_normalized": sf.get("cgpa_normalized", 0),
            "10th_normalized": sf.get("10th_normalized", 0),
            "12th_normalized": sf.get("12th_normalized", 0),
            "active_backlogs": sf.get("active_backlogs", 0),
            "dept_match": dept_match,
            "required_skills_match_ratio": round(req_ratio, 3),
            "preferred_skills_match_ratio": round(pref_ratio, 3),
            "total_internship_months": sf.get("total_internship_months", 0),
            "max_internship_tier": sf.get("max_internship_tier", 0),
            "num_projects": sf.get("num_projects", 0),
            "max_project_complexity": sf.get("max_project_complexity", 0),
            "meets_project_complexity": meets_complexity,
            "num_global_premium_certs": sf.get("num_global_premium", 0),
            "num_global_standard_certs": sf.get("num_global_standard", 0),
            "num_national_certs": sf.get("num_national", 0),
            "meets_cert_tier": meets_cert,
            "num_papers": sf.get("num_papers", 0),
            "max_paper_tier": sf.get("max_paper_tier", 0),
            "num_advanced_skills": sf.get("num_advanced_skills", 0),
            "num_verified_skills": sf.get("num_verified_skills", 0),
        })

    feat_df = pd.DataFrame(rows)
    student_ids = feat_df["student_id"].tolist()
    X = feat_df[ranker_feat_cols].fillna(0)
    scores = ranker.predict(ranker_scaler.transform(X))

    # Attach names from students_df
    name_map = dict(zip(students_df["student_id"], students_df["full_name"]))
    dept_map = dict(zip(students_df["student_id"], students_df["department"]))
    cgpa_map = dict(zip(students_df["student_id"], students_df["cgpa"]))

    results = sorted([
        {
            "rank": 0,
            "student_id": sid,
            "full_name": name_map.get(sid, sid),
            "department": dept_map.get(sid, ""),
            "cgpa": round(float(cgpa_map.get(sid, 0)), 2),
            "rank_score": round(float(s), 4),
            "dept_eligible": bool(feat_df.loc[feat_df["student_id"] == sid, "dept_match"].values[0]),
        }
        for sid, s in zip(student_ids, scores)
    ], key=lambda x: x["rank_score"], reverse=True)

    for i, r in enumerate(results, 1):
        r["rank"] = i

    return clean_nan({
        "company_id": company_id,
        "company_name": company_data.get("company_name", ""),
        "tier": company_data.get("tier", ""),
        "total_students": len(results),
        "top_k": top_k,
        "shortlist": results[:top_k],
    })


# ═══════════════════════════════════════════════════════════
# OPTION 2 — ML Skill Gap Recommendations
# GET /api/ml/skill-gap/{student_id}?top_k=5
# ═══════════════════════════════════════════════════════════
@app.get("/api/ml/skill-gap/{student_id}")
async def get_skill_gap(student_id: str, top_k: int = Query(default=5, le=20)):
    """Return ML-predicted top skill recommendations for a student (Option 2)."""
    if not SKILL_REC_LOADED:
        raise HTTPException(503, "Skill recommender not loaded. Run: python -m src.model.run_skill_gap")
    if student_features_df is None:
        raise HTTPException(500, "Data not loaded")

    sf = student_features_df[student_features_df["student_id"] == student_id]
    if sf.empty:
        raise HTTPException(404, f"Student {student_id} not found")
    student_row = sf.iloc[0]
    dept_match_ratio = compute_department_match_ratio(student_row.get("department", ""))

    # Score every skill using surrogate model
    rec_rows = []
    for skill in skill_rec_le.classes_:
        skill_enc = int(skill_rec_le.transform([skill])[0])
        feats = {"skill_encoded": skill_enc}
        for col in skill_rec_feat_cols:
            if col != "skill_encoded":
                if col == "dept_match_ratio":
                    feats[col] = dept_match_ratio
                else:
                    feats[col] = float(student_row.get(col, 0) or 0)
        import numpy as np
        X = pd.DataFrame([feats])[skill_rec_feat_cols].fillna(0)
        gain = float(skill_rec_model.predict(skill_rec_scaler.transform(X.values))[0])
        rec_rows.append({"skill": skill, "predicted_gain": round(gain, 4)})

    rec_rows.sort(key=lambda x: x["predicted_gain"], reverse=True)

    # Exclude skills student already has
    current_skills = {s.lower() for s in (student_row.get("skill_list") or [])}
    filtered = [r for r in rec_rows if r["skill"].lower() not in current_skills]

    metrics_path = os.path.join(_mdir, "skill_recommender_metrics.json")
    model_label = "GradientBoosting surrogate"
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            skill_metrics = json.load(f)
        rho = skill_metrics.get("test_spearman_rho")
        r2 = skill_metrics.get("test_r2")
        if rho is not None and r2 is not None:
            model_label = f"GradientBoosting surrogate (R2={r2}, Spearman rho={rho})"

    student_raw = students_df[students_df["student_id"] == student_id].iloc[0]
    return clean_nan({
        "student_id": student_id,
        "full_name": student_raw.get("full_name", ""),
        "department": student_raw.get("department", ""),
        "current_skill_count": len(current_skills),
        "recommendations": filtered[:top_k],
        "model": model_label,
    })


# ═══════════════════════════════════════════════════════════
# OPTION 3 — Criteria Bias Report
# GET /api/ml/bias-report
# ═══════════════════════════════════════════════════════════
@app.get("/api/ml/bias-report")
async def get_bias_report(flagged_only: bool = False):
    """Return upstream criteria bias detection results (Option 3)."""
    if not BIAS_REPORT_AVAILABLE:
        raise HTTPException(503, "Bias report not available. Run: python -m src.model.run_bias_detection")

    with open(_bias_report_path) as f:
        report = json.load(f)

    if flagged_only:
        return clean_nan({
            "summary": report["summary"],
            "flagged_companies": report["flagged_companies"],
        })

    # Return summary + flat company list (without full nested analysis for API speed)
    companies_flat = []
    for c in report.get("all_companies", []):
        ga = c.get("gender_analysis", {})
        da = c.get("dept_analysis", {})
        cd = c.get("criteria_diagnosis", {})
        companies_flat.append({
            "company_id": c["company_id"],
            "company_name": c["company_name"],
            "tier": c["tier"],
            "pool_pass_rate": c["pool_pass_rate"],
            "gender_disparity": ga.get("disparity", 0),
            "gender_p_value": ga.get("p_value", 1),
            "gender_flagged": ga.get("flagged", False),
            "gender_pass_rates": ga.get("pass_rates", {}),
            "dept_disparity": da.get("disparity", 0),
            "top_bias_criterion": max(
                cd, key=lambda k: cd[k].get("disparity", 0), default="none"
            ) if cd else "none",
        })

    return clean_nan({
        "summary": report["summary"],
        "flagged_companies": report["flagged_companies"],
        "all_companies": companies_flat,
    })


@app.post("/api/bias/simulate-fix")
async def post_bias_simulation(request: BiasSimulationRequest):
    if students_df is None or companies_df is None or student_features_df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    try:
        return simulate_fix(
            request.company_id,
            request.criterion,
            students_df,
            companies_df,
            student_features_df,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bias simulation failed: {exc}")


@app.post("/api/bias/recommendations")
async def post_bias_recommendation(request: BiasRecommendationRequest):
    try:
        return save_bias_recommendation(request.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save recommendation: {exc}")


@app.get("/api/bias/recommendations")
async def get_bias_recommendations(company_id: Optional[str] = None):
    try:
        return load_bias_recommendations(company_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load recommendations: {exc}")


@app.post("/api/bias/counterfactual-rules")
async def post_counterfactual_rules(request: CounterfactualRulesRequest):
    if students_df is None or companies_df is None or student_features_df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    try:
        return counterfactual_rules(
            request.company_id,
            students_df,
            companies_df,
            student_features_df,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Counterfactual analysis failed: {exc}")


@app.post("/api/bias/preview-substitution")
async def post_preview_substitution(request: BiasSubstitutionPreviewRequest):
    if students_df is None or companies_df is None or student_features_df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    try:
        return preview_substitution(
            request.company_id,
            {
                "remove_criterion": request.remove_criterion,
                "substitution": request.substitution,
            },
            students_df,
            companies_df,
            student_features_df,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Substitution preview failed: {exc}")


@app.get("/api/bias/ml-fairness-comparison")
async def get_ml_fairness_comparison(company_id: str):
    if students_df is None or companies_df is None or student_features_df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    try:
        return fairness_comparison(
            company_id,
            students_df,
            companies_df,
            student_features_df,
            ranker=ranker if RANKER_LOADED else None,
            ranker_scaler=ranker_scaler if RANKER_LOADED else None,
            ranker_feat_cols=ranker_feat_cols if RANKER_LOADED else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ML fairness comparison failed: {exc}")


@app.post("/api/bias/retrain-constrained")
async def post_retrain_constrained(request: ConstrainedRetrainRequest):
    if students_df is None or companies_df is None or student_features_df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    try:
        return retrain_constrained_model(
            request.company_id,
            request.epsilon,
            students_df,
            companies_df,
            student_features_df,
            request.triggered_by,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Constrained retraining failed: {exc}")


@app.get("/api/bias/model-fairness-history/{company_id}")
async def get_model_fairness_history(company_id: str):
    try:
        return get_fairness_history(company_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load fairness history: {exc}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
