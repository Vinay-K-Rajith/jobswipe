"""
Generate skills.csv linked to students.
Average ~3-4 skills per student → ~2800 total.
Skill proficiency is correlated with verification (projects/certs).
"""

import csv
import random
import os

SEED = 46
random.seed(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

# Skills pool organized by category
SKILLS_POOL = {
    "Programming": ["Python", "Java", "C", "C++", "JavaScript", "TypeScript",
                     "Go", "Rust", "Kotlin", "Swift", "PHP", "Ruby", "R",
                     "MATLAB", "Scala"],
    "Web": ["React", "Angular", "Vue.js", "Node.js", "Express", "Django",
            "Flask", "Spring Boot", "Next.js", "HTML/CSS", "Tailwind",
            "Bootstrap", "REST APIs", "GraphQL"],
    "Data": ["SQL", "Pandas", "NumPy", "Tableau", "Power BI", "Excel",
             "Apache Spark", "Hadoop", "MongoDB", "PostgreSQL", "MySQL",
             "Redis", "Elasticsearch"],
    "AI_ML": ["TensorFlow", "PyTorch", "Scikit-learn", "Keras", "OpenCV",
              "NLP", "Computer Vision", "Deep Learning", "Hugging Face",
              "MLflow", "NLTK", "SpaCy"],
    "Cloud": ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
              "CI/CD", "Linux", "Git", "GitHub Actions", "Jenkins"],
    "Cybersecurity": ["Network Security", "Ethical Hacking", "Cryptography",
                      "Penetration Testing", "SIEM", "Firewall Management"],
    "Embedded": ["Arduino", "Raspberry Pi", "VHDL", "Verilog", "RTOS",
                 "Embedded C", "PCB Design"],
    "Management": ["MS Office", "Agile", "Scrum", "JIRA", "Leadership",
                   "Communication", "Project Management"],
}

# Department → likely skill categories
DEPT_SKILL_AFFINITY = {
    "CSE": ["Programming", "Web", "Data", "AI_ML", "Cloud"],
    "AIDS": ["Programming", "Data", "AI_ML", "Cloud"],
    "AIML": ["Programming", "AI_ML", "Data", "Cloud"],
    "IT": ["Programming", "Web", "Cloud", "Data"],
    "ECE": ["Programming", "Embedded", "Cloud"],
    "EEE": ["Programming", "Embedded"],
    "MECH": ["Programming", "Embedded", "Management"],
    "CIVIL": ["Programming", "Data", "Management"],
    "MBA": ["Management", "Data"],
    "BCA": ["Programming", "Web", "Data"],
}


def get_num_skills():
    """Avg 3-4 per student."""
    return random.choices([1, 2, 3, 4, 5, 6, 7],
                          weights=[0.05, 0.15, 0.25, 0.25, 0.15, 0.10, 0.05])[0]


def generate_skills(student_ids, student_departments=None):
    """
    Generate skills.csv.
    If student_departments dict provided, skills are dept-correlated.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    skills = []

    for sid in student_ids:
        num_skills = get_num_skills()
        dept = student_departments.get(sid, "CSE") if student_departments else "CSE"
        affinities = DEPT_SKILL_AFFINITY.get(dept, ["Programming", "Web"])

        used_skills = set()
        for _ in range(num_skills):
            # 70% chance from affinity categories, 30% any
            if random.random() < 0.70:
                category = random.choice(affinities)
            else:
                category = random.choice(list(SKILLS_POOL.keys()))

            available = [s for s in SKILLS_POOL[category] if s not in used_skills]
            if not available:
                # Try any category
                for cat in SKILLS_POOL:
                    available = [s for s in SKILLS_POOL[cat] if s not in used_skills]
                    if available:
                        break
            if not available:
                continue

            skill_name = random.choice(available)
            used_skills.add(skill_name)

            proficiency = random.choices(
                ["Beginner", "Intermediate", "Advanced"],
                weights=[0.30, 0.45, 0.25]
            )[0]

            # Advanced proficiency more likely to be verified
            if proficiency == "Advanced":
                verified = random.random() < 0.70
            elif proficiency == "Intermediate":
                verified = random.random() < 0.40
            else:
                verified = random.random() < 0.15

            skills.append({
                "student_id": sid,
                "skill_name": skill_name,
                "proficiency": proficiency,
                "verified": verified,
            })

    filepath = os.path.join(OUTPUT_DIR, "skills.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "student_id", "skill_name", "proficiency", "verified"
        ])
        writer.writeheader()
        writer.writerows(skills)

    print(f"✅ Generated {len(skills)} skills → {filepath}")
    return skills


if __name__ == "__main__":
    ids = [f"S{i:04d}" for i in range(1, 801)]
    generate_skills(ids)
