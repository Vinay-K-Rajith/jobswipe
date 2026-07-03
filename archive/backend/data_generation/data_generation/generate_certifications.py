"""
Generate certifications.csv linked to students.
Distribution:
  30% students → 0 certs
  40% → 1-2 certs (mostly Local/National)
  25% → 3-4 certs (mix)
  5%  → 5+ certs (high achievers)
"""

import csv
import random
import os

SEED = 42
random.seed(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

# --- Certification catalog ---
CERTS_BY_TIER = {
    "Global_Premium": [
        ("AWS Solutions Architect", "AWS", "Cloud"),
        ("AWS Cloud Practitioner", "AWS", "Cloud"),
        ("Azure AI Fundamentals", "Microsoft", "AI_ML"),
        ("Azure Data Scientist Associate", "Microsoft", "AI_ML"),
        ("Azure Administrator", "Microsoft", "Cloud"),
        ("Google Cloud Professional Data Engineer", "Google", "Cloud"),
        ("Google Cloud Associate Cloud Engineer", "Google", "Cloud"),
        ("Oracle Cloud Infrastructure Architect", "Oracle", "Cloud"),
        ("TensorFlow Developer Certificate", "Google", "AI_ML"),
        ("Google Professional Machine Learning Engineer", "Google", "AI_ML"),
        ("AWS Machine Learning Specialty", "AWS", "AI_ML"),
        ("Certified Kubernetes Administrator", "CNCF", "Cloud"),
    ],
    "Global_Standard": [
        ("Google Data Analytics", "Google", "Data"),
        ("Google IT Support", "Google", "Programming"),
        ("IBM Data Science", "IBM", "Data"),
        ("Meta Front-End Developer", "Meta", "Web"),
        ("Meta Back-End Developer", "Meta", "Web"),
        ("Cisco CCNA", "Cisco", "Cybersecurity"),
        ("CompTIA Security+", "CompTIA", "Cybersecurity"),
        ("Oracle Java SE Programmer", "Oracle", "Programming"),
        ("Salesforce Administrator", "Salesforce", "Management"),
        ("HubSpot Inbound Marketing", "HubSpot", "Management"),
        ("GitHub Foundations", "GitHub", "Programming"),
        ("HashiCorp Terraform Associate", "HashiCorp", "Cloud"),
    ],
    "National": [
        ("NPTEL Programming in Java", "NPTEL", "Programming"),
        ("NPTEL Data Science", "NPTEL", "Data"),
        ("NPTEL Machine Learning", "NPTEL", "AI_ML"),
        ("NPTEL Python", "NPTEL", "Programming"),
        ("NPTEL Deep Learning", "NPTEL", "AI_ML"),
        ("NPTEL Cloud Computing", "NPTEL", "Cloud"),
        ("NPTEL Cybersecurity", "NPTEL", "Cybersecurity"),
        ("NPTEL Database Management", "NPTEL", "Data"),
        ("SWAYAM AI Fundamentals", "SWAYAM", "AI_ML"),
        ("SWAYAM Web Development", "SWAYAM", "Web"),
        ("SWAYAM IoT", "SWAYAM", "Programming"),
        ("SWAYAM Management Principles", "SWAYAM", "Management"),
    ],
    "Local": [
        ("College Workshop on Python", "College", "Programming"),
        ("College Workshop on Web Dev", "College", "Web"),
        ("College Workshop on AI", "College", "AI_ML"),
        ("College Workshop on Data Analytics", "College", "Data"),
        ("Udemy Complete Python Bootcamp", "Udemy", "Programming"),
        ("Udemy Machine Learning A-Z", "Udemy", "AI_ML"),
        ("Udemy React Complete Guide", "Udemy", "Web"),
        ("Udemy SQL Bootcamp", "Udemy", "Data"),
        ("Coursera Python for Everybody", "Coursera", "Programming"),
        ("Coursera Machine Learning Specialization", "Coursera", "AI_ML"),
        ("Coursera Web Development", "Coursera", "Web"),
        ("Coursera Financial Markets", "Coursera", "Management"),
    ],
}

YEARS = [2022, 2023, 2024, 2025]


def get_num_certs():
    """
    30% → 0, 40% → 1-2, 25% → 3-4, 5% → 5+
    """
    r = random.random()
    if r < 0.30:
        return 0
    elif r < 0.70:
        return random.randint(1, 2)
    elif r < 0.95:
        return random.randint(3, 4)
    else:
        return random.randint(5, 7)


def pick_cert_tier(num_certs_so_far, total_certs):
    """
    Low cert count students tend toward Local/National.
    High cert count students have a mix including Global.
    """
    if total_certs <= 2:
        return random.choices(
            ["Global_Premium", "Global_Standard", "National", "Local"],
            weights=[0.05, 0.10, 0.35, 0.50]
        )[0]
    else:
        return random.choices(
            ["Global_Premium", "Global_Standard", "National", "Local"],
            weights=[0.15, 0.25, 0.30, 0.30]
        )[0]


def generate_certifications(student_ids):
    """Generate certifications.csv."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    certifications = []
    cert_counter = 0

    for sid in student_ids:
        num_certs = get_num_certs()
        used_certs = set()

        for _ in range(num_certs):
            cert_counter += 1
            cert_id = f"C{cert_counter:04d}"
            tier = pick_cert_tier(len(used_certs), num_certs)
            available = [c for c in CERTS_BY_TIER[tier] if c[0] not in used_certs]
            if not available:
                # Try another tier
                for fallback_tier in ["Local", "National", "Global_Standard", "Global_Premium"]:
                    available = [c for c in CERTS_BY_TIER[fallback_tier] if c[0] not in used_certs]
                    if available:
                        tier = fallback_tier
                        break
            if not available:
                continue

            cert_name, issuing_body, domain = random.choice(available)
            used_certs.add(cert_name)
            year = random.choice(YEARS)

            certifications.append({
                "student_id": sid,
                "cert_id": cert_id,
                "cert_name": cert_name,
                "issuing_body": issuing_body,
                "tier": tier,
                "domain": domain,
                "year_obtained": year,
            })

    filepath = os.path.join(OUTPUT_DIR, "certifications.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "student_id", "cert_id", "cert_name", "issuing_body",
            "tier", "domain", "year_obtained"
        ])
        writer.writeheader()
        writer.writerows(certifications)

    print(f"✅ Generated {len(certifications)} certifications → {filepath}")
    return certifications


if __name__ == "__main__":
    # Quick test with dummy IDs
    ids = [f"S{i:04d}" for i in range(1, 801)]
    generate_certifications(ids)
