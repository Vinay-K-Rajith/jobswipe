"""
Master script to generate ALL datasets for the Bias-Free AI Placement System.
Run this single file to produce all 7 CSVs in backend/data/.

Usage:
    cd backend
    python -m src.data_generation.generate_all
"""

import os
import sys
import csv

# Add parent dirs to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.data_generation.generate_students import generate_students
from src.data_generation.generate_certifications import generate_certifications
from src.data_generation.generate_projects import generate_projects
from src.data_generation.generate_internships import generate_internships
from src.data_generation.generate_research_papers import generate_research_papers
from src.data_generation.generate_skills import generate_skills
from src.data_generation.generate_companies import generate_companies


def main():
    print("=" * 60)
    print("  Bias-Free AI Placement System — Dataset Generator")
    print("=" * 60)
    print()

    # Step 1: Generate students
    print("📋 STEP 1/7: Generating students...")
    students = generate_students()
    student_ids = [s["student_id"] for s in students]
    student_depts = {s["student_id"]: s["department"] for s in students}
    print()

    # Step 2: Generate certifications
    print("📜 STEP 2/7: Generating certifications...")
    certs = generate_certifications(student_ids)
    print()

    # Step 3: Generate projects
    print("🔧 STEP 3/7: Generating projects...")
    projects = generate_projects(student_ids)
    print()

    # Step 4: Generate internships
    print("💼 STEP 4/7: Generating internships...")
    internships = generate_internships(student_ids)
    print()

    # Step 5: Generate research papers
    print("📄 STEP 5/7: Generating research papers...")
    papers = generate_research_papers(student_ids)
    print()

    # Step 6: Generate skills (dept-aware)
    print("🛠️  STEP 6/7: Generating skills...")
    skills = generate_skills(student_ids, student_depts)
    print()

    # Step 7: Generate companies
    print("🏢 STEP 7/7: Generating companies...")
    companies = generate_companies()
    print()

    # Summary
    print("=" * 60)
    print("  ✅ ALL DATASETS GENERATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"  Students:          {len(students)}")
    print(f"  Certifications:    {len(certs)}")
    print(f"  Projects:          {len(projects)}")
    print(f"  Internships:       {len(internships)}")
    print(f"  Research Papers:   {len(papers)}")
    print(f"  Skills:            {len(skills)}")
    print(f"  Companies:         {len(companies)}")
    print(f"  Output directory:  {os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data'))}")
    print("=" * 60)


if __name__ == "__main__":
    main()
