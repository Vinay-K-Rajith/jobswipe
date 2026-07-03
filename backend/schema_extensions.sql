-- Schema extensions: run this in Supabase SQL Editor AFTER setup.sql
-- Adds missing tables and extra columns not covered by the base schema.

-- ── students: extra columns ──────────────────────────────────────────────────
ALTER TABLE students
    ADD COLUMN IF NOT EXISTS id TEXT,
    ADD COLUMN IF NOT EXISTS register_number TEXT,
    ADD COLUMN IF NOT EXISTS name TEXT,
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS password_hash TEXT,
    ADD COLUMN IF NOT EXISTS batch_year INTEGER,
    ADD COLUMN IF NOT EXISTS resume_url TEXT,
    ADD COLUMN IF NOT EXISTS resume_parse_confidence JSONB DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS idx_students_email ON students(email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_students_register ON students(register_number) WHERE register_number IS NOT NULL;

-- ── recruiters ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recruiters (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    company_name TEXT,
    company_domain TEXT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_recruiters_email ON recruiters(email);

-- ── jobs ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    recruiter_id UUID REFERENCES recruiters(id) ON DELETE SET NULL,
    company_name TEXT,
    role TEXT,
    role_title TEXT,
    industry TEXT,
    location TEXT DEFAULT 'Chennai',
    remote_policy TEXT DEFAULT 'hybrid',
    required_skills JSONB DEFAULT '[]'::jsonb,
    preferred_skills JSONB DEFAULT '[]'::jsonb,
    interview_timeline TEXT,
    mentorship TEXT,
    highlight_line TEXT,
    job_description TEXT,
    careers_url TEXT,
    ctc TEXT,
    package_lpa FLOAT,
    job_type TEXT,
    selection_rounds JSONB DEFAULT '[]'::jsonb,
    phi_score FLOAT,
    is_active BOOLEAN DEFAULT TRUE,
    allowed_departments JSONB DEFAULT '[]'::jsonb,
    allowed_branches JSONB DEFAULT '[]'::jsonb,
    grad_years_eligible JSONB DEFAULT '[]'::jsonb,
    min_cgpa FLOAT DEFAULT 0,
    min_10th FLOAT DEFAULT 0,
    min_12th FLOAT DEFAULT 0,
    max_active_backlogs INTEGER DEFAULT 999,
    min_internship_months FLOAT DEFAULT 0,
    min_projects INTEGER DEFAULT 0,
    requires_research_paper BOOLEAN DEFAULT FALSE,
    cert_tier_required TEXT DEFAULT 'None',
    bond_years INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_recruiter ON jobs(recruiter_id);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active);

-- ── student_interest ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS student_interest (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id TEXT NOT NULL,
    job_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_student_interest_sid ON student_interest(student_id);
CREATE INDEX IF NOT EXISTS idx_student_interest_jid ON student_interest(job_id);

-- ── student_pass ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS student_pass (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id TEXT NOT NULL,
    job_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_student_pass_sid ON student_pass(student_id);

-- ── recruiter_interest ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recruiter_interest (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    recruiter_id UUID REFERENCES recruiters(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL,
    job_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, job_id, recruiter_id)
);

CREATE INDEX IF NOT EXISTS idx_recruiter_interest_sid ON recruiter_interest(student_id);
CREATE INDEX IF NOT EXISTS idx_recruiter_interest_rid ON recruiter_interest(recruiter_id);

-- ── recruiter_pass ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recruiter_pass (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    recruiter_id UUID REFERENCES recruiters(id) ON DELETE SET NULL,
    student_id TEXT NOT NULL,
    job_id UUID NOT NULL,
    reason_code TEXT DEFAULT 'selected_stronger_match',
    reason_note TEXT,
    insight_payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, job_id, recruiter_id)
);

CREATE INDEX IF NOT EXISTS idx_recruiter_pass_sid ON recruiter_pass(student_id);
CREATE INDEX IF NOT EXISTS idx_recruiter_pass_created ON recruiter_pass(created_at DESC);

-- ── matches ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS matches (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id TEXT NOT NULL,
    recruiter_id UUID REFERENCES recruiters(id) ON DELETE SET NULL,
    job_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_sid ON matches(student_id);
CREATE INDEX IF NOT EXISTS idx_matches_jid ON matches(job_id);

-- ── applications ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS applications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id TEXT NOT NULL,
    job_id UUID NOT NULL,
    current_status TEXT DEFAULT 'Applied',
    round_results JSONB DEFAULT '{}'::jsonb,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_applications_sid ON applications(student_id);
CREATE INDEX IF NOT EXISTS idx_applications_jid ON applications(job_id);

-- ── skills_graph ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS skills_graph (
    id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,
    avg_learning_weeks INTEGER DEFAULT 3,
    difficulty_level TEXT DEFAULT 'Intermediate',
    prerequisites JSONB DEFAULT '[]'::jsonb
);

-- ── learning_resources ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS learning_resources (
    id SERIAL PRIMARY KEY,
    skill_name TEXT NOT NULL,
    title TEXT,
    url TEXT,
    resource_type TEXT,
    estimated_hours INTEGER
);

CREATE INDEX IF NOT EXISTS idx_learning_resources_skill ON learning_resources(skill_name);
