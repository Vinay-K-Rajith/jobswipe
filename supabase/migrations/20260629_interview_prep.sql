-- AI Interview Prep (text-mode v1)
-- Sessions, turns, and post-session feedback for the mock-interview feature.

create table if not exists public.interview_sessions (
    id uuid primary key default gen_random_uuid(),
    student_id text not null,
    target_role text not null,
    target_domain text,
    seniority text not null default 'mid',
    interview_stage text not null default 'first_round',
    structured_profile jsonb not null default '{}'::jsonb,
    competency_plan jsonb not null default '{}'::jsonb,
    question_sequence jsonb not null default '[]'::jsonb,
    -- in-session state (no Redis; the session row is the source of truth)
    phase text not null default 'pre_session',
        -- 'pre_session' | 'active' | 'completed'
    current_index integer not null default 0,
    follow_up_used boolean not null default false,
    status text not null default 'pre_session',
        -- mirrors phase for clarity: 'pre_session' | 'active' | 'completed'
    self_rating text,  -- 'better' | 'same' | 'harder'
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz default now()
);

create index if not exists idx_interview_sessions_student
    on public.interview_sessions(student_id, created_at desc);

create table if not exists public.interview_turns (
    id uuid primary key default gen_random_uuid(),
    session_id uuid references public.interview_sessions(id) on delete cascade,
    turn_index integer not null,
    speaker text not null,        -- 'interviewer' | 'candidate'
    content text not null,
    question_ref text,            -- competency this turn belongs to
    created_at timestamptz default now()
);

create index if not exists idx_interview_turns_session
    on public.interview_turns(session_id, turn_index);

create table if not exists public.interview_feedback (
    id uuid primary key default gen_random_uuid(),
    session_id uuid references public.interview_sessions(id) on delete cascade unique,
    overall_summary text not null default '',
    headline_takeaway text not null default '',
    per_question_feedback jsonb not null default '[]'::jsonb,
    recurring_patterns jsonb not null default '[]'::jsonb,
    next_session_suggestion text not null default '',
    created_at timestamptz default now()
);

-- Backend uses the service key (bypasses RLS); permissive policies match the
-- rest of the schema. Tighten with real RLS if the anon key is ever used.
alter table public.interview_sessions enable row level security;
alter table public.interview_turns enable row level security;
alter table public.interview_feedback enable row level security;

drop policy if exists "Allow all interview_sessions" on public.interview_sessions;
create policy "Allow all interview_sessions" on public.interview_sessions
    for all using (true) with check (true);

drop policy if exists "Allow all interview_turns" on public.interview_turns;
create policy "Allow all interview_turns" on public.interview_turns
    for all using (true) with check (true);

drop policy if exists "Allow all interview_feedback" on public.interview_feedback;
create policy "Allow all interview_feedback" on public.interview_feedback
    for all using (true) with check (true);
