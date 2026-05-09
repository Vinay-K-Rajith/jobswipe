-- Supabase Schema for Bias-Free AI Placement System
-- Run this in Supabase SQL Editor

-- Students table
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    gender TEXT,
    department TEXT NOT NULL,
    "10th_marks" FLOAT,
    "10th_board" TEXT,
    "12th_marks" FLOAT,
    "12th_board" TEXT,
    cgpa FLOAT,
    backlogs_history INTEGER DEFAULT 0,
    active_backlogs INTEGER DEFAULT 0,
    year_of_study INTEGER
);

-- Certifications table
CREATE TABLE IF NOT EXISTS certifications (
    cert_id TEXT PRIMARY KEY,
    student_id TEXT REFERENCES students(student_id),
    cert_name TEXT NOT NULL,
    issuing_body TEXT,
    tier TEXT,
    domain TEXT,
    year_obtained INTEGER
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    student_id TEXT REFERENCES students(student_id),
    project_title TEXT,
    domain TEXT,
    tech_stack TEXT,
    complexity TEXT,
    team_size TEXT,
    has_deployment BOOLEAN DEFAULT FALSE,
    has_github BOOLEAN DEFAULT FALSE,
    duration_weeks INTEGER,
    year INTEGER
);

-- Internships table
CREATE TABLE IF NOT EXISTS internships (
    internship_id TEXT PRIMARY KEY,
    student_id TEXT REFERENCES students(student_id),
    company_name TEXT,
    company_tier TEXT,
    role TEXT,
    domain TEXT,
    duration_months FLOAT,
    stipend BOOLEAN DEFAULT FALSE,
    mode TEXT,
    year INTEGER
);

-- Research Papers table
CREATE TABLE IF NOT EXISTS research_papers (
    paper_id TEXT PRIMARY KEY,
    student_id TEXT REFERENCES students(student_id),
    title TEXT,
    publication_venue TEXT,
    tier TEXT,
    domain TEXT,
    year_published INTEGER,
    is_first_author BOOLEAN DEFAULT FALSE,
    co_authors_count INTEGER DEFAULT 0
);

-- Skills table
CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    student_id TEXT REFERENCES students(student_id),
    skill_name TEXT NOT NULL,
    proficiency TEXT,
    verified BOOLEAN DEFAULT FALSE
);

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    industry TEXT,
    tier TEXT,
    min_cgpa FLOAT,
    min_10th FLOAT,
    min_12th FLOAT,
    max_active_backlogs INTEGER DEFAULT 0,
    allowed_departments TEXT,
    required_skills TEXT,
    preferred_skills TEXT,
    min_internship_months FLOAT DEFAULT 0,
    internship_tier_preference TEXT DEFAULT 'Any',
    min_projects INTEGER DEFAULT 0,
    project_complexity_min TEXT DEFAULT 'Basic',
    requires_research_paper BOOLEAN DEFAULT FALSE,
    cert_tier_required TEXT DEFAULT 'None',
    role_offered TEXT,
    package_lpa FLOAT,
    bond_years INTEGER DEFAULT 0
);

-- Eligibility Results (model output)
CREATE TABLE IF NOT EXISTS eligibility_results (
    id SERIAL PRIMARY KEY,
    student_id TEXT REFERENCES students(student_id),
    company_id TEXT REFERENCES companies(company_id),
    eligible BOOLEAN NOT NULL,
    score FLOAT,
    criteria_breakdown JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, company_id)
);

-- Improvement Plans
CREATE TABLE IF NOT EXISTS improvement_plans (
    id SERIAL PRIMARY KEY,
    student_id TEXT REFERENCES students(student_id),
    company_id TEXT REFERENCES companies(company_id),
    suggestions JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, company_id)
);

-- Bias reduction recommendations persisted from the admin workflow
CREATE TABLE IF NOT EXISTS bias_recommendations (
    id BIGINT PRIMARY KEY,
    company_id TEXT REFERENCES companies(company_id),
    criterion TEXT NOT NULL,
    current_threshold JSONB,
    recommended_threshold JSONB,
    current_disparity FLOAT,
    projected_disparity FLOAT,
    current_pool_size INTEGER,
    projected_pool_size INTEGER,
    status TEXT DEFAULT 'proposed',
    recommendation_type TEXT DEFAULT 'threshold',
    simulation_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Level 3 fairness retraining audit trail
CREATE TABLE IF NOT EXISTS model_fairness_history (
    id BIGINT PRIMARY KEY,
    company_id TEXT REFERENCES companies(company_id),
    epsilon FLOAT NOT NULL,
    accuracy FLOAT,
    f1 FLOAT,
    delta_dp FLOAT,
    delta_eo FLOAT,
    trained_at TIMESTAMPTZ DEFAULT NOW(),
    triggered_by TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_certs_student ON certifications(student_id);
CREATE INDEX IF NOT EXISTS idx_projects_student ON projects(student_id);
CREATE INDEX IF NOT EXISTS idx_internships_student ON internships(student_id);
CREATE INDEX IF NOT EXISTS idx_papers_student ON research_papers(student_id);
CREATE INDEX IF NOT EXISTS idx_skills_student ON skills(student_id);
CREATE INDEX IF NOT EXISTS idx_eligibility_student ON eligibility_results(student_id);
CREATE INDEX IF NOT EXISTS idx_eligibility_company ON eligibility_results(company_id);
CREATE INDEX IF NOT EXISTS idx_improvement_student ON improvement_plans(student_id);
CREATE INDEX IF NOT EXISTS idx_bias_recommendations_company ON bias_recommendations(company_id);
CREATE INDEX IF NOT EXISTS idx_fairness_history_company ON model_fairness_history(company_id);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE eligibility_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE bias_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_fairness_history ENABLE ROW LEVEL SECURITY;

-- Allow read access for anon users
CREATE POLICY IF NOT EXISTS "Allow read students" ON students FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read companies" ON companies FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read eligibility" ON eligibility_results FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read improvements" ON improvement_plans FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read certifications" ON certifications FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read projects" ON projects FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read internships" ON internships FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read papers" ON research_papers FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read skills" ON skills FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read bias recommendations" ON bias_recommendations FOR SELECT USING (true);
CREATE POLICY IF NOT EXISTS "Allow read fairness history" ON model_fairness_history FOR SELECT USING (true);
