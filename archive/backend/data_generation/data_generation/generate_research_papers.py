"""
Generate research_papers.csv linked to students.
Distribution:
  80% → 0 papers
  15% → 1 paper (mostly conference/non-indexed)
  4%  → 2 papers
  1%  → 3+ papers (Scopus/IEEE level)
"""

import csv
import random
import os

SEED = 45
random.seed(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

VENUES = ["IEEE", "Springer", "Scopus", "UGC", "Conference", "Preprint", "Other"]
TIERS = ["Q1", "Q2", "Q3", "Conference", "Non-indexed"]
DOMAINS = ["AI_ML", "Cloud", "Cybersecurity", "Data", "Web", "Programming", "Management", "IoT", "Embedded"]

PAPER_TITLES_BY_DOMAIN = {
    "AI_ML": [
        "Deep Learning Approaches for Medical Image Analysis",
        "Transformer-Based Models for Text Classification",
        "Federated Learning for Privacy-Preserving AI",
        "Reinforcement Learning in Autonomous Systems",
        "Explainable AI for Healthcare Diagnostics",
        "Generative Adversarial Networks for Data Augmentation",
        "Neural Architecture Search: A Survey",
        "Attention Mechanisms in Computer Vision",
        "Transfer Learning for Low-Resource Languages",
        "Bias Detection and Mitigation in ML Models",
    ],
    "Data": [
        "Big Data Analytics in Smart Cities",
        "Real-time Stream Processing with Apache Kafka",
        "Predictive Analytics for Customer Retention",
        "Data Warehouse Optimization Techniques",
        "Graph Analytics for Social Network Analysis",
        "Anomaly Detection in Time Series Data",
        "ETL Pipeline Optimization Strategies",
    ],
    "Cloud": [
        "Serverless Computing Performance Analysis",
        "Multi-Cloud Deployment Strategies",
        "Container Orchestration Best Practices",
        "Edge Computing for IoT Applications",
        "Cloud Security Framework Design",
    ],
    "Cybersecurity": [
        "Intrusion Detection using Machine Learning",
        "Blockchain for Secure Data Sharing",
        "Zero Trust Architecture Implementation",
        "Malware Detection using Deep Learning",
        "Vulnerability Assessment Automation",
    ],
    "Web": [
        "Progressive Web Application Performance",
        "Microservices Architecture Patterns",
        "Web Accessibility Standards Compliance",
        "Single Page Application Optimization",
    ],
    "IoT": [
        "IoT Sensor Network Optimization",
        "Smart Agriculture Monitoring Systems",
        "Wearable Health Device Data Analysis",
        "Industrial IoT Predictive Maintenance",
    ],
    "Embedded": [
        "FPGA-Based Signal Processing",
        "Real-time Operating System Scheduling",
        "Low-Power Embedded System Design",
    ],
    "Programming": [
        "Code Quality Metrics Analysis",
        "Compiler Optimization Techniques",
        "Software Testing Automation Framework",
    ],
    "Management": [
        "Agile Methodology in Software Development",
        "Digital Transformation Strategies",
        "Project Risk Assessment Framework",
    ],
}


def get_num_papers():
    """80% → 0, 15% → 1, 4% → 2, 1% → 3+"""
    r = random.random()
    if r < 0.80:
        return 0
    elif r < 0.95:
        return 1
    elif r < 0.99:
        return 2
    else:
        return random.randint(3, 4)


def pick_venue_and_tier(paper_index):
    """First papers tend to be lower tier, subsequent papers can be higher."""
    if paper_index == 0:
        venue = random.choices(VENUES, weights=[0.08, 0.07, 0.05, 0.10, 0.35, 0.20, 0.15])[0]
        tier = random.choices(TIERS, weights=[0.03, 0.07, 0.10, 0.40, 0.40])[0]
    else:
        venue = random.choices(VENUES, weights=[0.20, 0.15, 0.15, 0.10, 0.20, 0.10, 0.10])[0]
        tier = random.choices(TIERS, weights=[0.10, 0.15, 0.20, 0.30, 0.25])[0]

    # Consistency: Q1/Q2 should be from IEEE/Springer/Scopus
    if tier in ("Q1", "Q2") and venue not in ("IEEE", "Springer", "Scopus"):
        venue = random.choice(["IEEE", "Springer", "Scopus"])

    return venue, tier


def generate_research_papers(student_ids):
    """Generate research_papers.csv."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    papers = []
    paper_counter = 0

    for sid in student_ids:
        num_papers = get_num_papers()
        used_titles = set()

        for idx in range(num_papers):
            paper_counter += 1
            paper_id = f"RP{paper_counter:04d}"
            domain = random.choice(DOMAINS)

            titles = PAPER_TITLES_BY_DOMAIN.get(domain, PAPER_TITLES_BY_DOMAIN["AI_ML"])
            available = [t for t in titles if t not in used_titles]
            if not available:
                available = titles
            title = random.choice(available)
            used_titles.add(title)

            venue, tier = pick_venue_and_tier(idx)
            year = random.choices([2022, 2023, 2024, 2025], weights=[0.15, 0.25, 0.35, 0.25])[0]

            is_first_author = random.random() < 0.6
            co_authors = random.randint(1, 5)

            papers.append({
                "student_id": sid,
                "paper_id": paper_id,
                "title": title,
                "publication_venue": venue,
                "tier": tier,
                "domain": domain,
                "year_published": year,
                "is_first_author": is_first_author,
                "co_authors_count": co_authors,
            })

    filepath = os.path.join(OUTPUT_DIR, "research_papers.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "student_id", "paper_id", "title", "publication_venue",
            "tier", "domain", "year_published", "is_first_author",
            "co_authors_count"
        ])
        writer.writeheader()
        writer.writerows(papers)

    print(f"✅ Generated {len(papers)} research papers → {filepath}")
    return papers


if __name__ == "__main__":
    ids = [f"S{i:04d}" for i in range(1, 801)]
    generate_research_papers(ids)
