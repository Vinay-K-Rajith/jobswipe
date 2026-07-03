"""
Generate internships.csv linked to students.
Distribution:
  35% → 0 internships
  45% → 1 internship
  15% → 2 internships
  5%  → 3+
"""

import csv
import random
import os

SEED = 44
random.seed(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

COMPANY_NAMES_BY_TIER = {
    "Tier1": [
        "Google", "Microsoft", "Amazon", "Apple", "Meta", "Netflix",
        "Goldman Sachs", "JP Morgan", "Adobe", "Salesforce", "Uber",
        "Oracle", "IBM", "SAP", "Deloitte", "McKinsey",
    ],
    "Tier2": [
        "Infosys", "TCS", "Wipro", "HCL", "Cognizant", "Tech Mahindra",
        "Capgemini", "Accenture", "L&T Infotech", "Mindtree", "Mphasis",
        "Zoho", "Freshworks", "Razorpay", "PhonePe", "Swiggy", "Flipkart",
        "Zomato", "Ola", "Byju's",
    ],
    "Tier3": [
        "SmallTech Solutions", "DataWare Inc", "WebCraft Studios",
        "CloudNine Tech", "PixelPerfect", "CodeBase Solutions",
        "AlphaSoft", "ByteWorks", "NetGenius", "Innov8 Labs",
        "SoftStack", "AppForge", "DigiCraft", "TechVista", "CodeWave",
    ],
    "Startup": [
        "HealthAI Startup", "EduTech Innovations", "FinLit App",
        "AgriBot Startup", "CleanEnergy Tech", "SocialImpact AI",
        "RetailSense", "TravelMate AI", "FoodChain Tech", "CyberShield",
        "SmartBuild", "GreenPath", "MedConnect", "LearnLoop", "PayEase",
    ],
    "NGO": [
        "Digital Literacy Foundation", "Code for India",
        "Tech4Good Foundation", "Rural Innovation Hub",
        "Open Source for Education", "Women in Tech Foundation",
    ],
}

ROLES = ["SDE", "Data Analyst", "ML Intern", "Web Dev", "Management", "Other"]
DOMAINS = ["AI_ML", "Web", "Data", "IoT", "Embedded", "Finance", "Other"]
MODES = ["Remote", "Hybrid", "Onsite"]
YEARS = [2022, 2023, 2024, 2025]


def get_num_internships():
    """35% → 0, 45% → 1, 15% → 2, 5% → 3+"""
    r = random.random()
    if r < 0.35:
        return 0
    elif r < 0.80:
        return 1
    elif r < 0.95:
        return 2
    else:
        return random.randint(3, 4)


def pick_company_tier():
    """Realistic distribution of internship tiers."""
    return random.choices(
        ["Tier1", "Tier2", "Tier3", "Startup", "NGO"],
        weights=[0.10, 0.30, 0.25, 0.25, 0.10]
    )[0]


def generate_internships(student_ids):
    """Generate internships.csv."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    internships = []
    intern_counter = 0

    for sid in student_ids:
        num_intern = get_num_internships()

        for _ in range(num_intern):
            intern_counter += 1
            internship_id = f"I{intern_counter:04d}"
            tier = pick_company_tier()
            company_name = random.choice(COMPANY_NAMES_BY_TIER[tier])
            role = random.choice(ROLES)
            domain = random.choice(DOMAINS)

            # Duration varies by tier
            if tier == "Tier1":
                duration = random.choice([2.0, 3.0, 6.0])
            elif tier in ("Tier2", "Tier3"):
                duration = random.choice([1.0, 2.0, 3.0, 6.0])
            elif tier == "Startup":
                duration = random.choice([1.0, 1.5, 2.0, 3.0])
            else:
                duration = random.choice([1.0, 2.0])

            # Stipend more likely at higher tiers
            if tier == "Tier1":
                stipend = random.random() < 0.95
            elif tier == "Tier2":
                stipend = random.random() < 0.80
            elif tier == "Tier3":
                stipend = random.random() < 0.60
            elif tier == "Startup":
                stipend = random.random() < 0.40
            else:
                stipend = random.random() < 0.15

            mode = random.choices(MODES, weights=[0.35, 0.30, 0.35])[0]
            year = random.choice(YEARS)

            internships.append({
                "student_id": sid,
                "internship_id": internship_id,
                "company_name": company_name,
                "company_tier": tier,
                "role": role,
                "domain": domain,
                "duration_months": duration,
                "stipend": stipend,
                "mode": mode,
                "year": year,
            })

    filepath = os.path.join(OUTPUT_DIR, "internships.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "student_id", "internship_id", "company_name", "company_tier",
            "role", "domain", "duration_months", "stipend", "mode", "year"
        ])
        writer.writeheader()
        writer.writerows(internships)

    print(f"✅ Generated {len(internships)} internships → {filepath}")
    return internships


if __name__ == "__main__":
    ids = [f"S{i:04d}" for i in range(1, 801)]
    generate_internships(ids)
