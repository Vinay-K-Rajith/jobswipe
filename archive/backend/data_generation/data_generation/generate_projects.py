"""
Generate projects.csv linked to students.
Average ~2 projects per student → ~1600 total.
"""

import csv
import random
import os

SEED = 43
random.seed(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

DOMAINS = ["AI_ML", "Web", "Data", "IoT", "Embedded", "Finance", "Other"]

TECH_STACKS_BY_DOMAIN = {
    "AI_ML": [
        ["Python", "TensorFlow", "Flask"],
        ["Python", "PyTorch", "FastAPI"],
        ["Python", "Scikit-learn", "Pandas"],
        ["Python", "Keras", "Streamlit"],
        ["Python", "OpenCV", "NumPy"],
        ["Python", "Hugging Face", "Transformers"],
        ["Python", "NLTK", "SpaCy"],
        ["Python", "TensorFlow", "Docker"],
    ],
    "Web": [
        ["React", "Node.js", "MongoDB"],
        ["React", "Express", "PostgreSQL"],
        ["Angular", "Spring Boot", "MySQL"],
        ["Vue.js", "Django", "SQLite"],
        ["Next.js", "Prisma", "PostgreSQL"],
        ["HTML", "CSS", "JavaScript"],
        ["React", "Firebase", "Tailwind"],
        ["Django", "Bootstrap", "PostgreSQL"],
    ],
    "Data": [
        ["Python", "Pandas", "Matplotlib"],
        ["Python", "SQL", "Tableau"],
        ["Python", "PySpark", "Hadoop"],
        ["R", "ggplot2", "dplyr"],
        ["Python", "Power BI", "Excel"],
        ["Python", "Pandas", "Seaborn"],
        ["SQL", "Python", "Airflow"],
        ["Python", "Databricks", "Spark"],
    ],
    "IoT": [
        ["Arduino", "C++", "Sensors"],
        ["Raspberry Pi", "Python", "MQTT"],
        ["ESP32", "MicroPython", "ThingSpeak"],
        ["Arduino", "Python", "Firebase"],
        ["NodeMCU", "C", "Blynk"],
    ],
    "Embedded": [
        ["C", "ARM", "RTOS"],
        ["C++", "STM32", "FreeRTOS"],
        ["Verilog", "FPGA", "ModelSim"],
        ["C", "PIC", "Assembly"],
        ["C", "Arduino", "PCB Design"],
    ],
    "Finance": [
        ["Python", "Pandas", "yfinance"],
        ["Python", "NumPy", "Matplotlib"],
        ["Excel", "VBA", "SQL"],
        ["Python", "Dash", "Plotly"],
        ["R", "Shiny", "quantmod"],
    ],
    "Other": [
        ["Python", "Flask", "SQLite"],
        ["Java", "Spring", "MySQL"],
        ["C#", ".NET", "SQL Server"],
        ["PHP", "Laravel", "MySQL"],
        ["Kotlin", "Android Studio", "Firebase"],
    ],
}

PROJECT_TITLES_BY_DOMAIN = {
    "AI_ML": [
        "Sentiment Analysis on Product Reviews",
        "Image Classification using CNN",
        "Chatbot using NLP and Transformers",
        "Object Detection with YOLO",
        "Fake News Detection System",
        "Speech Emotion Recognition",
        "Medical Image Segmentation",
        "Recommendation Engine for E-commerce",
        "Autonomous Lane Detection",
        "Sign Language Recognition System",
        "Text Summarization using BERT",
        "Predictive Maintenance using ML",
        "Customer Churn Prediction",
        "AI-Powered Resume Screener",
        "Handwritten Digit Recognition",
    ],
    "Web": [
        "E-Commerce Platform",
        "Social Media Dashboard",
        "Online Learning Management System",
        "Hospital Management System",
        "Real-time Chat Application",
        "Portfolio Website with CMS",
        "Food Delivery App",
        "Event Management Platform",
        "Job Portal with Matching",
        "Blog Platform with Auth",
        "Library Management System",
        "Expense Tracker App",
        "Booking System for Hotels",
        "Student Information System",
        "Online Voting System",
    ],
    "Data": [
        "COVID-19 Data Analysis Dashboard",
        "Sales Forecasting Model",
        "Customer Segmentation Analysis",
        "Stock Market Trend Analysis",
        "Crime Data Visualization",
        "Weather Pattern Analysis",
        "Social Media Analytics",
        "Employee Attrition Analysis",
        "Retail Demand Forecasting",
        "Healthcare Cost Analysis",
        "Education Data Mining",
        "Supply Chain Analytics",
    ],
    "IoT": [
        "Smart Home Automation System",
        "Air Quality Monitoring System",
        "Smart Agriculture System",
        "Wearable Health Monitor",
        "Smart Parking System",
        "Water Quality Sensor Network",
        "Industrial IoT Dashboard",
        "Smart Energy Meter",
    ],
    "Embedded": [
        "Traffic Light Controller",
        "RFID-based Attendance System",
        "Line Following Robot",
        "Drone Flight Controller",
        "Digital Lock System",
        "Pulse Oximeter Design",
        "Motor Speed Controller",
    ],
    "Finance": [
        "Personal Finance Manager",
        "Stock Portfolio Tracker",
        "Loan Default Prediction",
        "Cryptocurrency Price Predictor",
        "Budget Planning Tool",
        "Credit Risk Assessment",
        "Invoice Management System",
    ],
    "Other": [
        "Attendance Management System",
        "Inventory Management System",
        "Travel Planner Application",
        "Fitness Tracking App",
        "Music Player Application",
        "File Encryption Tool",
        "QR Code Generator",
        "Password Manager",
    ],
}

COMPLEXITY_WEIGHTS = {
    "Basic": 0.40,
    "Intermediate": 0.40,
    "Advanced": 0.20,
}


def get_num_projects():
    """Avg ~2 per student."""
    return random.choices([0, 1, 2, 3, 4], weights=[0.05, 0.25, 0.35, 0.25, 0.10])[0]


def generate_projects(student_ids):
    """Generate projects.csv."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    projects = []
    proj_counter = 0

    for sid in student_ids:
        num_proj = get_num_projects()
        used_titles = set()

        for _ in range(num_proj):
            proj_counter += 1
            project_id = f"P{proj_counter:04d}"
            domain = random.choice(DOMAINS)

            titles = PROJECT_TITLES_BY_DOMAIN[domain]
            available_titles = [t for t in titles if t not in used_titles]
            if not available_titles:
                available_titles = titles
            title = random.choice(available_titles)
            used_titles.add(title)

            tech_stack = random.choice(TECH_STACKS_BY_DOMAIN[domain])
            complexity = random.choices(
                list(COMPLEXITY_WEIGHTS.keys()),
                weights=list(COMPLEXITY_WEIGHTS.values())
            )[0]

            team_size = random.choices([1, 2, 3, 4], weights=[0.20, 0.35, 0.30, 0.15])[0]
            team_size_str = str(team_size) if team_size < 4 else "4+"

            # Advanced projects more likely to be deployed/on GitHub
            if complexity == "Advanced":
                has_deployment = random.random() < 0.6
                has_github = random.random() < 0.8
                duration_weeks = random.randint(8, 20)
            elif complexity == "Intermediate":
                has_deployment = random.random() < 0.3
                has_github = random.random() < 0.6
                duration_weeks = random.randint(4, 12)
            else:
                has_deployment = random.random() < 0.1
                has_github = random.random() < 0.3
                duration_weeks = random.randint(2, 6)

            year = random.choices([2022, 2023, 2024, 2025], weights=[0.15, 0.25, 0.35, 0.25])[0]

            projects.append({
                "student_id": sid,
                "project_id": project_id,
                "project_title": title,
                "domain": domain,
                "tech_stack": ",".join(tech_stack),
                "complexity": complexity,
                "team_size": team_size_str,
                "has_deployment": has_deployment,
                "has_github": has_github,
                "duration_weeks": duration_weeks,
                "year": year,
            })

    filepath = os.path.join(OUTPUT_DIR, "projects.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "student_id", "project_id", "project_title", "domain",
            "tech_stack", "complexity", "team_size", "has_deployment",
            "has_github", "duration_weeks", "year"
        ])
        writer.writeheader()
        writer.writerows(projects)

    print(f"✅ Generated {len(projects)} projects → {filepath}")
    return projects


if __name__ == "__main__":
    ids = [f"S{i:04d}" for i in range(1, 801)]
    generate_projects(ids)
