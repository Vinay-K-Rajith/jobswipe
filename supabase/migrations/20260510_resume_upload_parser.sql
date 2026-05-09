alter table public.students
    add column if not exists resume_url text,
    add column if not exists resume_parse_confidence jsonb default '{}'::jsonb;
