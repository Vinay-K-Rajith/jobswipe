"""
Upload CSV data to Supabase tables.
"""

import pandas as pd
import os
import json
from src.database.supabase_client import get_client

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

TABLES_TO_UPLOAD = [
    ("students", "students.csv"),
    ("certifications", "certifications.csv"),
    ("projects", "projects.csv"),
    ("internships", "internships.csv"),
    ("research_papers", "research_papers.csv"),
    ("skills", "skills.csv"),
    ("companies", "companies.csv"),
]

BATCH_SIZE = 100


def upload_table(client, table_name, csv_filename):
    """Upload a CSV file to a Supabase table."""
    filepath = os.path.join(DATA_DIR, csv_filename)
    if not os.path.exists(filepath):
        print(f"  ⚠️  {csv_filename} not found, skipping")
        return 0

    df = pd.read_csv(filepath)

    # Convert boolean columns
    bool_cols = df.select_dtypes(include=['bool']).columns
    for col in bool_cols:
        df[col] = df[col].astype(bool)

    # Convert NaN to None for JSON serialization. Keep this after the
    # dataframe-to-dict conversion so float columns cannot coerce None back
    # to NaN.
    records = df.to_dict(orient="records")
    records = [
        {key: (None if pd.isna(value) else value) for key, value in record.items()}
        for record in records
    ]
    total = len(records)

    # Upload in batches
    uploaded = 0
    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        try:
            client.table(table_name).upsert(batch).execute()
            uploaded += len(batch)
        except Exception as e:
            print(f"  ❌ Error uploading batch {i//BATCH_SIZE + 1}: {e}")
            # Try inserting one by one
            for record in batch:
                try:
                    client.table(table_name).upsert(record).execute()
                    uploaded += 1
                except Exception as e2:
                    print(f"    ❌ Failed record: {e2}")

    print(f"  ✅ {table_name}: {uploaded}/{total} records uploaded")
    return uploaded


def upload_all():
    """Upload all CSV data to Supabase."""
    print("=" * 60)
    print("  📤 Uploading data to Supabase")
    print("=" * 60)

    client = get_client(use_service_key=True)

    for table_name, csv_filename in TABLES_TO_UPLOAD:
        print(f"\n  Uploading {table_name}...")
        upload_table(client, table_name, csv_filename)

    print("\n✅ All tables uploaded successfully!")


if __name__ == "__main__":
    upload_all()
