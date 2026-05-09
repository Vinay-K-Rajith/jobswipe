"""
Inference Pipeline: Full eligibility assessment for new students/companies.
Combines Layer 1 (rule-based criteria) + Layer 2 (ML scoring).
"""

import pandas as pd
import numpy as np
import pickle
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')


def load_model():
    """Load trained model and scaler."""
    with open(os.path.join(MODEL_DIR, "model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "feature_columns.json"), "r") as f:
        feature_cols = json.load(f)
    return model, scaler, feature_cols


def build_inference_features(student_features, company_data):
    """
    Build feature vector for a single student–company pair.
    student_features: dict with all student aggregate features
    company_data: dict with company requirements
    """
    from src.preprocessing.feature_engineering import compute_skill_match, COMPANY_COMPLEXITY_MAP, COMPANY_CERT_TIER_MAP

    student_skills = student_features.get("skill_list", [])

    allowed_depts = [d.strip() for d in str(company_data.get("allowed_departments", "")).split(",")]
    dept_match = 1 if student_features.get("department", "") in allowed_depts else 0

    req_ratio, pref_ratio = compute_skill_match(
        student_skills,
        company_data.get("required_skills", ""),
        company_data.get("preferred_skills", "")
    )

    company_min_complexity = COMPANY_COMPLEXITY_MAP.get(
        company_data.get("project_complexity_min", "None"), 0
    )
    meets_complexity = 1 if student_features.get("max_project_complexity", 0) >= company_min_complexity else 0

    company_cert_req = COMPANY_CERT_TIER_MAP.get(
        str(company_data.get("cert_tier_required", "None")), 0
    )
    meets_cert = 1 if student_features.get("max_cert_tier", 0) >= company_cert_req else 0

    features = {
        "cgpa_normalized": student_features.get("cgpa_normalized", 0),
        "10th_normalized": student_features.get("10th_normalized", 0),
        "12th_normalized": student_features.get("12th_normalized", 0),
        "active_backlogs": student_features.get("active_backlogs", 0),
        "dept_match": dept_match,
        "required_skills_match_ratio": round(req_ratio, 3),
        "preferred_skills_match_ratio": round(pref_ratio, 3),
        "total_internship_months": student_features.get("total_internship_months", 0),
        "max_internship_tier": student_features.get("max_internship_tier", 0),
        "num_projects": student_features.get("num_projects", 0),
        "max_project_complexity": student_features.get("max_project_complexity", 0),
        "meets_project_complexity": meets_complexity,
        "num_global_premium_certs": student_features.get("num_global_premium", 0),
        "num_global_standard_certs": student_features.get("num_global_standard", 0),
        "num_national_certs": student_features.get("num_national", 0),
        "meets_cert_tier": meets_cert,
        "num_papers": student_features.get("num_papers", 0),
        "max_paper_tier": student_features.get("max_paper_tier", 0),
        "num_advanced_skills": student_features.get("num_advanced_skills", 0),
        "num_verified_skills": student_features.get("num_verified_skills", 0),
    }
    return features


def run_inference(student_features, company_data, model=None, scaler=None, feature_cols=None, pdf_path=None):
    """
    Full inference for one student–company pair.
    Returns eligibility result with explanation.
    """
    from src.explainability.criteria_checker import check_criteria

    if pdf_path:
        from src.preprocessing.resume_parser import parse_resume

        parsed_resume, confidence = parse_resume(pdf_path)
        if confidence["overall"] == "low" or confidence["cgpa"] == "low":
            return {
                "status": "VERIFICATION_REQUIRED",
                "reason": "parsing_uncertainty",
                "format_detected": confidence["format_type"],
                "fields_to_verify": confidence["fields_missing"],
                "message": "Parser confidence is low. Student should confirm extracted data.",
                "parsed_resume": parsed_resume,
                "confidence": confidence,
            }
        student_features = {**student_features, **parsed_resume}

    if model is None:
        model, scaler, feature_cols = load_model()

    # Layer 1: Rule-based criteria check
    scorecard = check_criteria(
        student_features, company_data,
        student_skills=student_features.get("skill_list", [])
    )
    summary = scorecard["_summary"]

    # If hard disqualifiers fail → immediately ineligible
    if not summary["hard_pass"]:
        return {
            "eligible": False,
            "reason": "hard_disqualifier",
            "score": 0.0,
            "scorecard": scorecard,
            "hard_failures": summary["hard_failures"],
            "message": "Ineligible: Hard criteria not met",
        }

    # Layer 2: ML model scoring
    pair_features = build_inference_features(student_features, company_data)
    feature_vector = pd.DataFrame([pair_features])[feature_cols]
    feature_scaled = scaler.transform(feature_vector.fillna(0))

    probability = float(model.predict_proba(feature_scaled)[0][1])
    prediction = probability >= 0.5

    return {
        "eligible": bool(prediction),
        "reason": "model_prediction",
        "score": round(probability, 4),
        "scorecard": scorecard,
        "hard_failures": [],
        "soft_weaknesses": summary["soft_weaknesses"],
        "message": f"{'Eligible' if prediction else 'Ineligible'}: Model score {probability:.2f}",
    }


def batch_inference(student_features_list, company_data):
    """Run inference for multiple students against one company."""
    model, scaler, feature_cols = load_model()

    results = []
    for sf in student_features_list:
        result = run_inference(sf, company_data, model, scaler, feature_cols)
        result["student_id"] = sf.get("student_id", "unknown")
        results.append(result)

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


if __name__ == "__main__":
    # Demo inference
    print("Loading model...")
    model, scaler, feature_cols = load_model()
    print(f"Model loaded. Features: {len(feature_cols)}")

    # Example student
    student = {
        "student_id": "S0001",
        "department": "CSE",
        "cgpa": 8.1,
        "cgpa_normalized": 0.81,
        "10th_marks": 85,
        "10th_normalized": 0.85,
        "12th_marks": 82,
        "12th_normalized": 0.82,
        "active_backlogs": 0,
        "total_internship_months": 3,
        "max_internship_tier": 4,
        "num_projects": 3,
        "max_project_complexity": 2,
        "num_global_premium": 1,
        "num_global_standard": 1,
        "num_national": 1,
        "max_cert_tier": 4,
        "num_papers": 0,
        "max_paper_tier": 0,
        "num_advanced_skills": 2,
        "num_verified_skills": 3,
        "skill_list": ["Python", "SQL", "React", "TensorFlow"],
    }

    company = {
        "min_cgpa": 7.5, "min_10th": 60, "min_12th": 60,
        "max_active_backlogs": 0,
        "allowed_departments": "CSE,IT,AIML,AIDS",
        "required_skills": "Python,SQL",
        "preferred_skills": "TensorFlow,AWS",
        "min_internship_months": 2, "min_projects": 2,
        "project_complexity_min": "Intermediate",
        "requires_research_paper": False,
        "cert_tier_required": "National",
    }

    result = run_inference(student, company, model, scaler, feature_cols)
    print(f"\nResult: {'✅ ELIGIBLE' if result['eligible'] else '❌ INELIGIBLE'}")
    print(f"Score: {result['score']}")
    print(f"Message: {result['message']}")
