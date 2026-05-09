CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE students ADD COLUMN IF NOT EXISTS register_number TEXT UNIQUE;
ALTER TABLE students ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS email TEXT UNIQUE;
ALTER TABLE students ADD COLUMN IF NOT EXISTS password_hash TEXT;

UPDATE students
SET name = COALESCE(name, full_name),
    register_number = COALESCE(register_number, student_id)
WHERE TRUE;

CREATE TABLE IF NOT EXISTS recruiters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    company_name TEXT NOT NULL,
    company_domain TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE recruiters ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow read recruiters" ON recruiters;
CREATE POLICY "Allow read recruiters" ON recruiters FOR SELECT USING (true);
