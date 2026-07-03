"""
Generate students.csv with realistic distributions.
Anti-bias: full_name and gender stored for audit only, never fed to model.
Board type stored but treated equally in scoring.
"""

import csv
import random
import os

SEED = 42
random.seed(SEED)

NUM_STUDENTS = 800

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

# --- Name pools (for audit/display only, never model input) ---
FIRST_NAMES_M = [
    "Arjun", "Rohan", "Vikram", "Siddharth", "Aditya", "Karthik", "Rahul",
    "Pranav", "Nikhil", "Harsh", "Ankit", "Varun", "Aman", "Akash", "Deepak",
    "Ravi", "Suresh", "Manoj", "Naveen", "Gaurav", "Sanjay", "Vivek", "Ajay",
    "Pradeep", "Ramesh", "Rohit", "Mohit", "Sachin", "Tarun", "Pavan",
    "Dev", "Ishaan", "Kabir", "Lakshya", "Yash", "Dhruv", "Arnav", "Reyansh",
    "Aarav", "Vihaan"
]
FIRST_NAMES_F = [
    "Priya", "Sneha", "Anjali", "Divya", "Pooja", "Nisha", "Kavya", "Meera",
    "Riya", "Sakshi", "Tanvi", "Shruti", "Neha", "Swathi", "Lakshmi",
    "Shalini", "Deepika", "Ananya", "Ishita", "Bhavana", "Manisha", "Rekha",
    "Sunita", "Pallavi", "Rashmi", "Namita", "Jyoti", "Aishwarya", "Kritika",
    "Lavanya", "Saanvi", "Myra", "Aanya", "Diya", "Kiara", "Anvi", "Pari",
    "Aadhya", "Siya", "Tara"
]
FIRST_NAMES_NB = [
    "Avery", "Morgan", "Jordan", "Casey", "Riley", "Rowan", "Sage", "Quinn",
    "Arin", "Kiran"
]
LAST_NAMES = [
    "Sharma", "Patel", "Kumar", "Singh", "Reddy", "Gupta", "Nair", "Iyer",
    "Joshi", "Chatterjee", "Verma", "Mishra", "Mehta", "Shah", "Das",
    "Pillai", "Rao", "Menon", "Bhat", "Hegde", "Deshmukh", "Kulkarni",
    "Patil", "Jadhav", "More", "Ghosh", "Mukherjee", "Roy", "Sen", "Bose",
    "Agarwal", "Jain", "Bansal", "Saxena", "Tiwari", "Pandey", "Dubey",
    "Yadav", "Chauhan", "Thakur"
]

# --- Department distribution ---
DEPARTMENTS = [
    ("CSE", 0.20), ("AIDS", 0.15), ("AIML", 0.15), ("IT", 0.12),
    ("ECE", 0.12), ("EEE", 0.08), ("MECH", 0.08), ("CIVIL", 0.05),
    ("MBA", 0.03), ("BCA", 0.02)
]

# --- Board types ---
BOARDS_10TH = ["CBSE", "State", "ICSE", "Matriculation"]
BOARDS_12TH = ["CBSE", "State", "ICSE", "HSC"]

# --- Gender distribution ---
GENDER_DIST = [("M", 0.55), ("F", 0.40), ("Non-binary", 0.05)]


def weighted_choice(choices_with_weights):
    """Pick from list of (value, weight) tuples."""
    values, weights = zip(*choices_with_weights)
    return random.choices(values, weights=weights, k=1)[0]


def generate_cgpa():
    """
    CGPA distribution:
    40% → 6.0–7.5
    35% → 7.5–8.5
    15% → 8.5–9.5
    10% → below 6.0 or above 9.5
    """
    r = random.random()
    if r < 0.40:
        return round(random.uniform(6.0, 7.5), 2)
    elif r < 0.75:
        return round(random.uniform(7.5, 8.5), 2)
    elif r < 0.90:
        return round(random.uniform(8.5, 9.5), 2)
    else:
        # 5% below 6.0, 5% above 9.5
        if random.random() < 0.5:
            return round(random.uniform(4.0, 6.0), 2)
        else:
            return round(random.uniform(9.5, 10.0), 2)


def generate_10th_marks(cgpa):
    """Generate 10th marks correlated with CGPA but with noise."""
    base = cgpa * 10  # rough correlation
    noise = random.gauss(0, 8)
    marks = base + noise
    return round(max(35.0, min(99.5, marks)), 1)


def generate_12th_marks(cgpa, marks_10th):
    """Generate 12th marks correlated with CGPA and 10th."""
    base = (cgpa * 10 + marks_10th) / 2
    noise = random.gauss(0, 7)
    marks = base + noise
    return round(max(35.0, min(99.5, marks)), 1)


def generate_backlogs(cgpa):
    """Higher CGPA → fewer backlogs (correlated, not deterministic)."""
    if cgpa >= 8.5:
        backlog_history = random.choices([0, 1], weights=[0.9, 0.1])[0]
    elif cgpa >= 7.0:
        backlog_history = random.choices([0, 1, 2, 3], weights=[0.6, 0.25, 0.1, 0.05])[0]
    elif cgpa >= 6.0:
        backlog_history = random.choices([0, 1, 2, 3, 4], weights=[0.3, 0.3, 0.2, 0.15, 0.05])[0]
    else:
        backlog_history = random.choices([0, 1, 2, 3, 4, 5], weights=[0.1, 0.2, 0.25, 0.2, 0.15, 0.1])[0]

    # Active backlogs are subset of history
    if backlog_history == 0:
        active = 0
    else:
        active = random.randint(0, min(backlog_history, 2))

    return backlog_history, active


def generate_name(gender):
    """Generate a full name based on gender."""
    if gender == "M":
        first = random.choice(FIRST_NAMES_M)
    elif gender == "F":
        first = random.choice(FIRST_NAMES_F)
    else:
        first = random.choice(FIRST_NAMES_NB)
    last = random.choice(LAST_NAMES)
    return f"{first} {last}"


def generate_students():
    """Generate the students.csv dataset."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    students = []
    for i in range(1, NUM_STUDENTS + 1):
        student_id = f"S{i:04d}"
        gender = weighted_choice(GENDER_DIST)
        full_name = generate_name(gender)
        department = weighted_choice(DEPARTMENTS)

        cgpa = generate_cgpa()
        marks_10th = generate_10th_marks(cgpa)
        board_10th = random.choice(BOARDS_10TH)
        marks_12th = generate_12th_marks(cgpa, marks_10th)
        board_12th = random.choice(BOARDS_12TH)

        backlog_history, active_backlogs = generate_backlogs(cgpa)
        year_of_study = random.choices([2, 3, 4], weights=[0.15, 0.30, 0.55])[0]

        students.append({
            "student_id": student_id,
            "full_name": full_name,
            "gender": gender,
            "department": department,
            "10th_marks": marks_10th,
            "10th_board": board_10th,
            "12th_marks": marks_12th,
            "12th_board": board_12th,
            "cgpa": cgpa,
            "backlogs_history": backlog_history,
            "active_backlogs": active_backlogs,
            "year_of_study": year_of_study,
        })

    filepath = os.path.join(OUTPUT_DIR, "students.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=students[0].keys())
        writer.writeheader()
        writer.writerows(students)

    print(f"✅ Generated {len(students)} students → {filepath}")
    return students


if __name__ == "__main__":
    generate_students()
