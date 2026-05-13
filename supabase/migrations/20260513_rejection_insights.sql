alter table public.recruiter_pass
    add column if not exists job_id uuid references public.jobs(id) on delete cascade,
    add column if not exists reason_code text not null default 'selected_stronger_match',
    add column if not exists reason_note text,
    add column if not exists insight_payload jsonb not null default '{}'::jsonb;

alter table public.recruiter_pass
    drop constraint if exists recruiter_pass_recruiter_id_student_id_key;

create unique index if not exists idx_recruiter_pass_unique_job
    on public.recruiter_pass(recruiter_id, student_id, job_id);

create index if not exists idx_recruiter_pass_student_job
    on public.recruiter_pass(student_id, job_id, created_at desc);

drop policy if exists "Allow write recruiter pass" on public.recruiter_pass;
create policy "Allow write recruiter pass" on public.recruiter_pass
    for all using (true) with check (true);
