CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recruiter_id UUID REFERENCES recruiters(id),
    role_title TEXT NOT NULL,
    industry TEXT,
    location TEXT,
    remote_policy TEXT CHECK (remote_policy IN ('on-site', 'hybrid', 'remote')),
    required_skills TEXT[],
    preferred_skills TEXT[],
    interview_timeline TEXT,
    mentorship TEXT,
    highlight_line TEXT,
    min_cgpa FLOAT DEFAULT 0,
    allowed_departments TEXT[],
    grad_years_eligible INTEGER[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS recruiter_id UUID REFERENCES recruiters(id);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS role_title TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS remote_policy TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS interview_timeline TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS mentorship TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS highlight_line TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS allowed_departments TEXT[];
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS grad_years_eligible INTEGER[];
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS student_interest (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id TEXT NOT NULL,
    job_id UUID REFERENCES jobs(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(student_id, job_id)
);

CREATE TABLE IF NOT EXISTS recruiter_interest (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recruiter_id UUID REFERENCES recruiters(id),
    student_id TEXT NOT NULL,
    job_id UUID REFERENCES jobs(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(recruiter_id, student_id, job_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id TEXT NOT NULL,
    recruiter_id UUID REFERENCES recruiters(id),
    job_id UUID REFERENCES jobs(id),
    matched_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(student_id, job_id)
);

CREATE TABLE IF NOT EXISTS student_pass (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id TEXT NOT NULL,
    job_id UUID REFERENCES jobs(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(student_id, job_id)
);

CREATE TABLE IF NOT EXISTS recruiter_pass (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recruiter_id UUID REFERENCES recruiters(id),
    student_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(recruiter_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_recruiter ON jobs(recruiter_id);
CREATE INDEX IF NOT EXISTS idx_student_interest_student ON student_interest(student_id);
CREATE INDEX IF NOT EXISTS idx_recruiter_interest_recruiter ON recruiter_interest(recruiter_id);
CREATE INDEX IF NOT EXISTS idx_matches_student ON matches(student_id);
CREATE INDEX IF NOT EXISTS idx_matches_recruiter ON matches(recruiter_id);

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_interest ENABLE ROW LEVEL SECURITY;
ALTER TABLE recruiter_interest ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_pass ENABLE ROW LEVEL SECURITY;
ALTER TABLE recruiter_pass ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow read jobs" ON jobs;
DROP POLICY IF EXISTS "Allow read student interest" ON student_interest;
DROP POLICY IF EXISTS "Allow read recruiter interest" ON recruiter_interest;
DROP POLICY IF EXISTS "Allow read matches" ON matches;
DROP POLICY IF EXISTS "Allow read student pass" ON student_pass;
DROP POLICY IF EXISTS "Allow read recruiter pass" ON recruiter_pass;

CREATE POLICY "Allow read jobs" ON jobs FOR SELECT USING (true);
CREATE POLICY "Allow read student interest" ON student_interest FOR SELECT USING (true);
CREATE POLICY "Allow read recruiter interest" ON recruiter_interest FOR SELECT USING (true);
CREATE POLICY "Allow read matches" ON matches FOR SELECT USING (true);
CREATE POLICY "Allow read student pass" ON student_pass FOR SELECT USING (true);
CREATE POLICY "Allow read recruiter pass" ON recruiter_pass FOR SELECT USING (true);
