"""
Generate companies.csv — 50 companies with varied requirements.
Distribution: 10 Tier1, 20 Tier2, 20 Tier3
"""

import csv
import random
import os

SEED = 47
random.seed(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

INDUSTRIES = ["Tech", "Finance", "Consulting", "Healthcare", "Manufacturing"]

ALL_DEPARTMENTS = ["CSE", "AIDS", "AIML", "IT", "ECE", "EEE", "MECH", "CIVIL", "MBA", "BCA"]

ALL_SKILLS = [
    "Python", "Java", "C", "C++", "JavaScript", "TypeScript", "SQL",
    "React", "Angular", "Node.js", "Django", "Flask", "Spring Boot",
    "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Git",
    "MongoDB", "PostgreSQL", "MySQL", "Redis",
    "HTML/CSS", "REST APIs", "Linux", "Tableau", "Power BI",
    "Excel", "Communication", "Leadership",
]

COMPANY_TEMPLATES = {
    "Tier1": {
        "names": [
            "Google India", "Microsoft India", "Amazon Development Center",
            "Goldman Sachs", "Adobe Systems", "Oracle India",
            "Salesforce India", "JPMorgan Chase", "Apple India", "Meta Platforms",
        ],
        "min_cgpa_range": (7.5, 8.5),
        "min_10th_range": (70, 85),
        "min_12th_range": (70, 85),
        "max_backlogs": 0,
        "dept_pool_size": (3, 5),
        "required_skills_count": (2, 4),
        "preferred_skills_count": (2, 4),
        "min_intern_months": (2, 6),
        "intern_tier_pref": ["Tier1", "Tier1_or_Tier2"],
        "min_projects": (2, 4),
        "project_complexity": ["Intermediate", "Advanced"],
        "research_paper_prob": 0.30,
        "cert_tier": ["Global_Standard", "Global_Premium"],
        "roles": ["SDE", "Data Analyst", "ML Engineer"],
        "package_range": (12.0, 45.0),
        "bond_range": (0, 0),
    },
    "Tier2": {
        "names": [
            "Infosys", "TCS", "Wipro", "HCL Technologies", "Cognizant",
            "Tech Mahindra", "Capgemini", "Accenture", "L&T Infotech",
            "Mindtree", "Zoho Corporation", "Freshworks", "Razorpay",
            "PhonePe", "Flipkart", "Mphasis", "KPMG India",
            "Deloitte India", "EY India", "PwC India",
        ],
        "min_cgpa_range": (6.5, 7.5),
        "min_10th_range": (60, 75),
        "min_12th_range": (60, 75),
        "max_backlogs": [0, 0, 0, 1],
        "dept_pool_size": (4, 7),
        "required_skills_count": (1, 3),
        "preferred_skills_count": (1, 3),
        "min_intern_months": (0, 3),
        "intern_tier_pref": ["Any", "Tier1_or_Tier2", "Any"],
        "min_projects": (1, 3),
        "project_complexity": ["Basic", "Intermediate", "Intermediate"],
        "research_paper_prob": 0.10,
        "cert_tier": ["None", "Local", "National", "Global_Standard"],
        "roles": ["SDE", "Data Analyst", "ML Engineer", "Consultant"],
        "package_range": (4.5, 14.0),
        "bond_range": (0, 2),
    },
    "Tier3": {
        "names": [
            "DataSolve Analytics", "CloudNine Solutions", "WebCraft Studios",
            "AlphaSoft Technologies", "ByteWorks Systems", "NexGen Software",
            "PixelPerfect Design", "CodeBase Solutions", "TechVista Global",
            "SmartBuild Software", "DigiCraft IT", "SoftStack India",
            "AppForge Technologies", "NetGenius Solutions", "InnovateTech",
            "CyberPulse", "DataDriven Co", "CloudFirst India",
            "UrbanTech Solutions", "GreenCode Systems",
        ],
        "min_cgpa_range": (5.5, 6.5),
        "min_10th_range": (50, 65),
        "min_12th_range": (50, 65),
        "max_backlogs": [0, 1, 1, 2],
        "dept_pool_size": (5, 10),
        "required_skills_count": (1, 2),
        "preferred_skills_count": (0, 2),
        "min_intern_months": (0, 0),
        "intern_tier_pref": ["Any"],
        "min_projects": (0, 2),
        "project_complexity": ["Basic", "Basic", "Intermediate"],
        "research_paper_prob": 0.02,
        "cert_tier": ["None", "None", "Local"],
        "roles": ["SDE", "Data Analyst", "Web Dev", "Consultant"],
        "package_range": (2.5, 6.0),
        "bond_range": (0, 3),
    },
}


def generate_companies():
    """Generate companies.csv."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    companies = []
    company_counter = 0

    for tier, template in COMPANY_TEMPLATES.items():
        for name in template["names"]:
            company_counter += 1
            company_id = f"CO{company_counter:03d}"
            industry = random.choice(INDUSTRIES)

            min_cgpa = round(random.uniform(*template["min_cgpa_range"]), 1)
            min_10th = round(random.uniform(*template["min_10th_range"]), 0)
            min_12th = round(random.uniform(*template["min_12th_range"]), 0)

            if isinstance(template["max_backlogs"], list):
                max_backlogs = random.choice(template["max_backlogs"])
            else:
                max_backlogs = template["max_backlogs"]

            # Departments
            num_depts = random.randint(*template["dept_pool_size"])
            # Always include CSE-related departments for tech companies
            core_depts = ["CSE", "IT", "AIDS", "AIML"]
            if industry == "Finance":
                core_depts = ["CSE", "IT", "MBA", "AIDS"]
            elif industry == "Manufacturing":
                core_depts = ["MECH", "EEE", "ECE", "CSE"]
            elif industry == "Healthcare":
                core_depts = ["CSE", "AIDS", "AIML", "ECE"]

            selected_depts = list(set(random.sample(core_depts, min(len(core_depts), num_depts))))
            remaining = [d for d in ALL_DEPARTMENTS if d not in selected_depts]
            if len(selected_depts) < num_depts and remaining:
                extra = random.sample(remaining, min(num_depts - len(selected_depts), len(remaining)))
                selected_depts.extend(extra)
            allowed_departments = ",".join(sorted(selected_depts))

            # Skills
            num_req = random.randint(*template["required_skills_count"])
            num_pref = random.randint(*template["preferred_skills_count"])
            req_skills = random.sample(ALL_SKILLS[:20], min(num_req, 20))  # Technical skills
            remaining_skills = [s for s in ALL_SKILLS if s not in req_skills]
            pref_skills = random.sample(remaining_skills, min(num_pref, len(remaining_skills)))

            required_skills = ",".join(req_skills)
            preferred_skills = ",".join(pref_skills)

            # Internship
            min_intern = round(random.uniform(*template["min_intern_months"]), 1)
            intern_tier = random.choice(template["intern_tier_pref"])

            # Projects
            min_projects = random.randint(*template["min_projects"])
            proj_complexity = random.choice(template["project_complexity"])

            # Research
            requires_paper = random.random() < template["research_paper_prob"]

            # Certification
            cert_tier = random.choice(template["cert_tier"])

            # Role & Package
            role = random.choice(template["roles"])
            package = round(random.uniform(*template["package_range"]), 1)
            bond = random.randint(*template["bond_range"])

            companies.append({
                "company_id": company_id,
                "company_name": name,
                "industry": industry,
                "tier": tier,
                "min_cgpa": min_cgpa,
                "min_10th": min_10th,
                "min_12th": min_12th,
                "max_active_backlogs": max_backlogs,
                "allowed_departments": allowed_departments,
                "required_skills": required_skills,
                "preferred_skills": preferred_skills,
                "min_internship_months": min_intern,
                "internship_tier_preference": intern_tier,
                "min_projects": min_projects,
                "project_complexity_min": proj_complexity,
                "requires_research_paper": requires_paper,
                "cert_tier_required": cert_tier,
                "role_offered": role,
                "package_lpa": package,
                "bond_years": bond,
            })

    filepath = os.path.join(OUTPUT_DIR, "companies.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "company_id", "company_name", "industry", "tier",
            "min_cgpa", "min_10th", "min_12th", "max_active_backlogs",
            "allowed_departments", "required_skills", "preferred_skills",
            "min_internship_months", "internship_tier_preference",
            "min_projects", "project_complexity_min",
            "requires_research_paper", "cert_tier_required",
            "role_offered", "package_lpa", "bond_years"
        ])
        writer.writeheader()
        writer.writerows(companies)

    print(f"✅ Generated {len(companies)} companies → {filepath}")
    return companies


if __name__ == "__main__":
    generate_companies()
