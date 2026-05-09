"""
Improvement Planner: Generate actionable improvement suggestions for ineligible students.
For each gap identified in the criteria check, produces specific, achievable recommendations.
"""

FEASIBILITY_BY_YEAR = {
    ("cgpa_improvement", 1): 0.9,
    ("cgpa_improvement", 2): 0.7,
    ("cgpa_improvement", 3): 0.4,
    ("cgpa_improvement", 4): 0.0,
    ("skill_addition", 1): 1.0,
    ("skill_addition", 2): 1.0,
    ("skill_addition", 3): 1.0,
    ("skill_addition", 4): 1.0,
    ("internship", 1): 0.9,
    ("internship", 2): 0.9,
    ("internship", 3): 0.7,
    ("internship", 4): 0.2,
    ("certification", 1): 1.0,
    ("certification", 2): 1.0,
    ("certification", 3): 1.0,
    ("certification", 4): 0.8,
    ("project_complexity", 1): 1.0,
    ("project_complexity", 2): 1.0,
    ("project_complexity", 3): 0.8,
    ("project_complexity", 4): 0.3,
    ("10th_marks", "any"): 0.0,
    ("12th_marks", "any"): 0.0,
    ("backlogs", "any"): 0.6,
    ("department_change", "any"): 0.0,
}

DIFFICULTY_INDEX = {
    "cgpa_improvement": 3,
    "skill_addition": 1,
    "internship": 2,
    "certification": 1,
    "project_complexity": 2,
    "backlogs": 2,
}


def _feasibility_label(weight):
    if weight == 0.0:
        return "Not feasible"
    if weight < 0.4:
        return "Hard"
    if weight < 0.8:
        return "Achievable"
    return "Easy"


def _suggestion_type_from_key(gap_key):
    return {
        "cgpa_check": "cgpa_improvement",
        "10th_check": "10th_marks",
        "12th_check": "12th_marks",
        "backlog_check": "backlogs",
        "department_check": "department_change",
        "required_skills_score": "skill_addition",
        "internship_score": "internship",
        "project_score": "project_complexity",
        "cert_score": "certification",
        "research_score": "project_complexity",
    }.get(gap_key, "skill_addition")


def _annotate_suggestion(suggestion, suggestion_type, opportunity_count, year_of_study):
    fw = FEASIBILITY_BY_YEAR.get(
        (suggestion_type, year_of_study),
        FEASIBILITY_BY_YEAR.get((suggestion_type, "any"), 0.5),
    )
    difficulty = DIFFICULTY_INDEX.get(suggestion_type, 2)
    suggestion["suggestion_type"] = suggestion_type
    suggestion["feasibility_weight"] = fw
    suggestion["feasibility_label"] = _feasibility_label(fw)
    suggestion["adjusted_score"] = opportunity_count * fw * (1.0 + (1.0 / difficulty))
    return suggestion


def generate_improvement_plan(scorecard, company_name="the company", company_data=None, year_of_study=3):
    """
    Generate a personalized improvement plan based on criteria gaps.
    Returns structured suggestions with priority levels.
    """
    summary = scorecard.get("_summary", {})
    suggestions = []
    priority = 1

    # Hard failures first (most critical)
    for failure_key in summary.get("hard_failures", []):
        item = scorecard.get(failure_key, {})

        if failure_key == "cgpa_check":
            gap = item["required_value"] - item["student_value"]
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Academic",
                "type": "hard_requirement",
                "title": "Improve CGPA",
                "description": f"Improve CGPA from {item['student_value']} to at least {item['required_value']} (gap: {gap:.2f})",
                "actions": [
                    "Focus on scoring well in remaining semester exams",
                    "Retake courses where you scored poorly (if allowed)",
                    "Form study groups for challenging subjects",
                    "Attend extra tutorials and office hours",
                ],
                "timeline": "1-2 semesters",
                "difficulty": "High" if gap > 1.0 else "Medium",
            }, _suggestion_type_from_key(failure_key), 1, year_of_study))
            priority += 1

        elif failure_key == "10th_check":
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Academic",
                "type": "hard_requirement",
                "title": "10th Marks Below Threshold",
                "description": f"10th marks ({item['student_value']}) below minimum ({item['required_value']})",
                "actions": [
                    "This is a historical score and cannot be changed",
                    "Focus on meeting all OTHER criteria exceptionally well",
                    "Look for companies with lower 10th mark requirements",
                    "Build a strong portfolio to compensate",
                ],
                "timeline": "N/A",
                "difficulty": "Cannot be changed",
            }, _suggestion_type_from_key(failure_key), 1, year_of_study))
            priority += 1

        elif failure_key == "12th_check":
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Academic",
                "type": "hard_requirement",
                "title": "12th Marks Below Threshold",
                "description": f"12th marks ({item['student_value']}) below minimum ({item['required_value']})",
                "actions": [
                    "This is a historical score and cannot be changed",
                    "Focus on meeting all OTHER criteria exceptionally well",
                    "Look for companies with lower 12th mark requirements",
                    "Build strong skills and certifications to compensate",
                ],
                "timeline": "N/A",
                "difficulty": "Cannot be changed",
            }, _suggestion_type_from_key(failure_key), 1, year_of_study))
            priority += 1

        elif failure_key == "backlog_check":
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Academic",
                "type": "hard_requirement",
                "title": "Clear Active Backlogs",
                "description": f"Clear {item['student_value']} active backlog(s) (max allowed: {item['required_value']})",
                "actions": [
                    "Prioritize clearing backlogs in the next exam cycle",
                    "Seek tutoring help for backlog subjects",
                    "Allocate dedicated study time each day for backlog subjects",
                    "Contact professors for guidance on exam preparation",
                ],
                "timeline": "Next exam cycle",
                "difficulty": "Medium",
            }, _suggestion_type_from_key(failure_key), 1, year_of_study))
            priority += 1

        elif failure_key == "department_check":
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Eligibility",
                "type": "hard_requirement",
                "title": "Department Not Eligible",
                "description": f"Department {item['student_value']} not in allowed list ({item['required_value']})",
                "actions": [
                    f"This company only hires from: {item['required_value']}",
                    "Focus on companies that accept your department",
                    "Build cross-domain skills that are in demand",
                    "Consider roles that value diverse backgrounds",
                ],
                "timeline": "N/A",
                "difficulty": "Cannot be changed",
            }, _suggestion_type_from_key(failure_key), 1, year_of_study))
            priority += 1

    # Soft weaknesses (improvable)
    for weakness_key in summary.get("soft_weaknesses", []):
        item = scorecard.get(weakness_key, {})

        if weakness_key == "required_skills_score":
            missing = item.get("missing", [])
            if missing:
                suggestions.append(_annotate_suggestion({
                    "priority": priority,
                    "category": "Skills",
                    "type": "soft_improvement",
                    "title": "Learn Missing Required Skills",
                    "description": f"Missing required skills: {', '.join(missing)}",
                    "actions": [
                        f"Learn {skill} through online courses (Coursera/Udemy/NPTEL)"
                        for skill in missing[:3]
                    ] + [
                        "Build projects using these skills to demonstrate proficiency",
                        "Get certified in these technologies",
                    ],
                    "timeline": "1-3 months per skill",
                    "difficulty": "Medium",
                }, _suggestion_type_from_key(weakness_key), len(missing), year_of_study))
                priority += 1

        elif weakness_key == "internship_score":
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Experience",
                "type": "soft_improvement",
                "title": "Gain Internship Experience",
                "description": f"Internship experience ({item.get('student_value', 0)} months) below requirement ({item.get('required_value', 0)} months)",
                "actions": [
                    "Apply for internships on LinkedIn, Internshala, AngelList",
                    "Reach out to startups for short-term internship opportunities",
                    "Participate in open-source projects (counts as practical experience)",
                    "Consider virtual internships if onsite isn't available",
                    "Build a portfolio project equivalent to internship work",
                ],
                "timeline": "1-3 months",
                "difficulty": "Medium",
            }, _suggestion_type_from_key(weakness_key), 1, year_of_study))
            priority += 1

        elif weakness_key == "project_score":
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Projects",
                "type": "soft_improvement",
                "title": "Build More Projects",
                "description": f"Projects ({item.get('student_value', 0)}) below requirement ({item.get('required_value', 0)})",
                "actions": [
                    "Build at least one intermediate/advanced project in your domain",
                    "Deploy your project (Heroku, Vercel, AWS) — deployed projects stand out",
                    "Push code to GitHub with proper documentation (README, comments)",
                    "Contribute to open-source projects",
                    "Participate in hackathons to build projects quickly",
                ],
                "timeline": "2-6 weeks per project",
                "difficulty": "Low-Medium",
            }, _suggestion_type_from_key(weakness_key), 1, year_of_study))
            priority += 1

        elif weakness_key == "cert_score":
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Certifications",
                "type": "soft_improvement",
                "title": "Obtain Higher-Tier Certifications",
                "description": f"Certification tier insufficient for requirement",
                "actions": [
                    "Get AWS/Azure/GCP cloud certifications (Global Premium tier)",
                    "Complete NPTEL courses with certification (National tier)",
                    "Google/IBM professional certificates on Coursera (Global Standard)",
                    "Start with free certifications and progress to paid ones",
                ],
                "timeline": "1-2 months per certification",
                "difficulty": "Medium",
            }, _suggestion_type_from_key(weakness_key), 1, year_of_study))
            priority += 1

        elif weakness_key == "research_score":
            suggestions.append(_annotate_suggestion({
                "priority": priority,
                "category": "Research",
                "type": "soft_improvement",
                "title": "Publish a Research Paper",
                "description": "Company requires at least one research publication",
                "actions": [
                    "Approach professors for research collaboration opportunities",
                    "Start with a conference paper (easier than journal)",
                    "Look into IEEE/Springer conferences in your domain",
                    "Write a survey paper as a starting point",
                    "Consider preprint servers (arXiv) for quick publication",
                ],
                "timeline": "3-6 months",
                "difficulty": "High",
            }, _suggestion_type_from_key(weakness_key), 1, year_of_study))
            priority += 1

    active_suggestions = sorted(
        [item for item in suggestions if item["feasibility_weight"] > 0.0],
        key=lambda item: item["adjusted_score"],
        reverse=True,
    )
    long_term_suggestions = [item for item in suggestions if item["feasibility_weight"] == 0.0]

    return {
        "company_name": company_name,
        "total_suggestions": len(suggestions),
        "hard_blockers": len(summary.get("hard_failures", [])),
        "soft_improvements": len(summary.get("soft_weaknesses", [])),
        "year_of_study": year_of_study,
        "suggestions": active_suggestions,
        "long_term_suggestions": long_term_suggestions,
        "long_term_note": "These changes are not feasible in your current year but matter for future students.",
    }


def format_improvement_plan(plan):
    """Format improvement plan as readable text."""
    lines = []
    lines.append(f"\n📝 Improvement Plan for {plan['company_name']}")
    lines.append("=" * 50)
    lines.append(f"Total areas to improve: {plan['total_suggestions']}")
    lines.append(f"Hard blockers: {plan['hard_blockers']}")
    lines.append(f"Soft improvements: {plan['soft_improvements']}")

    for suggestion in plan["suggestions"]:
        priority_icon = "🔴" if suggestion["type"] == "hard_requirement" else "🟡"
        lines.append(f"\n{priority_icon} Priority {suggestion['priority']}: {suggestion['title']}")
        lines.append(f"   Category: {suggestion['category']}")
        lines.append(f"   {suggestion['description']}")
        lines.append(f"   Timeline: {suggestion['timeline']} | Difficulty: {suggestion['difficulty']}")
        lines.append("   Actions:")
        for action in suggestion["actions"]:
            lines.append(f"     • {action}")

    return "\n".join(lines)


if __name__ == "__main__":
    from src.explainability.criteria_checker import check_criteria

    student = {
        "cgpa": 6.2, "10th_marks": 72, "12th_marks": 68,
        "active_backlogs": 1, "department": "ECE",
        "total_internship_months": 0, "num_projects": 1,
        "max_project_complexity": 1, "num_papers": 0, "max_cert_tier": 1,
    }
    company = {
        "min_cgpa": 7.0, "min_10th": 60, "min_12th": 60,
        "max_active_backlogs": 0,
        "allowed_departments": "CSE,IT,AIML",
        "required_skills": "Python,Java,SQL",
        "preferred_skills": "React,AWS",
        "min_internship_months": 2, "min_projects": 2,
        "project_complexity_min": "Intermediate",
        "requires_research_paper": False, "cert_tier_required": "National",
    }
    skills = ["Python", "C"]

    scorecard = check_criteria(student, company, skills)
    plan = generate_improvement_plan(scorecard, "Google India", company)
    print(format_improvement_plan(plan))
