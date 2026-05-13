import { FormEvent, useEffect, useState } from 'react';
import {
  JobCardData,
  RecruiterJobInput,
  createRecruiterJob,
  deleteRecruiterJob,
  getRecruiterJobs,
  setRecruiterJobStatus,
  updateRecruiterJob,
} from '../../services/swipeApi';

const DEPARTMENTS = ['CSE', 'IT', 'AIML', 'AIDS', 'ECE', 'EEE', 'MECH'];
const YEARS = [2025, 2026, 2027];

type RolesTab = 'view' | 'post';

type RoleFormState = {
  role_title: string;
  industry: string;
  location: string;
  remote_policy: string;
  required_skills: string;
  preferred_skills: string;
  interview_timeline: string;
  mentorship: string;
  highlight_line: string;
  min_cgpa: string;
  allowed_departments: string[];
  grad_years_eligible: number[];
};

const defaultFormState: RoleFormState = {
  role_title: '',
  industry: '',
  location: '',
  remote_policy: 'hybrid',
  required_skills: '',
  preferred_skills: '',
  interview_timeline: '',
  mentorship: '',
  highlight_line: '',
  min_cgpa: '6',
  allowed_departments: ['CSE', 'IT'],
  grad_years_eligible: [2026],
};

function splitTags(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function joinTags(values?: string[]) {
  return (values || []).join(', ');
}

function buildPayload(form: RoleFormState): RecruiterJobInput {
  return {
    role_title: form.role_title,
    industry: form.industry,
    location: form.location,
    remote_policy: form.remote_policy,
    required_skills: splitTags(form.required_skills),
    preferred_skills: splitTags(form.preferred_skills),
    interview_timeline: form.interview_timeline,
    mentorship: form.mentorship,
    highlight_line: form.highlight_line,
    min_cgpa: Number(form.min_cgpa),
    allowed_departments: form.allowed_departments,
    grad_years_eligible: form.grad_years_eligible,
  };
}

function formFromJob(job: JobCardData): RoleFormState {
  return {
    role_title: job.role_title || '',
    industry: job.industry || '',
    location: job.location || '',
    remote_policy: job.remote_policy || 'hybrid',
    required_skills: joinTags(job.required_skills),
    preferred_skills: joinTags(job.preferred_skills),
    interview_timeline: job.interview_timeline || '',
    mentorship: job.mentorship || '',
    highlight_line: job.highlight_line || '',
    min_cgpa: String(job.min_cgpa ?? 0),
    allowed_departments: job.allowed_departments || ['CSE', 'IT'],
    grad_years_eligible: job.grad_years_eligible || [2026],
  };
}

function toggleArray<T>(values: T[], value: T) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function RoleForm({
  form,
  onChange,
  onSubmit,
  submitLabel,
  busy,
}: {
  form: RoleFormState;
  onChange: (next: RoleFormState) => void;
  onSubmit: (event: FormEvent) => void;
  submitLabel: string;
  busy: boolean;
}) {
  return (
    <form className="portal-form-card job-form" onSubmit={onSubmit}>
      <label>Role title<input className="input" required value={form.role_title} onChange={(e) => onChange({ ...form, role_title: e.target.value })} /></label>
      <label>Industry / domain<input className="input" required value={form.industry} onChange={(e) => onChange({ ...form, industry: e.target.value })} /></label>
      <label>Location<input className="input" value={form.location} onChange={(e) => onChange({ ...form, location: e.target.value })} /></label>
      <label>Remote policy
        <select className="input" value={form.remote_policy} onChange={(e) => onChange({ ...form, remote_policy: e.target.value })}>
          <option value="on-site">On-site</option>
          <option value="hybrid">Hybrid</option>
          <option value="remote">Remote</option>
        </select>
      </label>
      <label>Required skills<input className="input" placeholder="Python, SQL, React" value={form.required_skills} onChange={(e) => onChange({ ...form, required_skills: e.target.value })} /></label>
      <label>Preferred skills<input className="input" placeholder="AWS, Docker" value={form.preferred_skills} onChange={(e) => onChange({ ...form, preferred_skills: e.target.value })} /></label>
      <label>Interview timeline<textarea className="input" value={form.interview_timeline} onChange={(e) => onChange({ ...form, interview_timeline: e.target.value })} /></label>
      <label>Mentorship structure<textarea className="input" value={form.mentorship} onChange={(e) => onChange({ ...form, mentorship: e.target.value })} /></label>
      <label>Highlight line<textarea className="input" required value={form.highlight_line} onChange={(e) => onChange({ ...form, highlight_line: e.target.value })} /></label>
      <label>Min CGPA<input className="input" type="number" step="0.1" value={form.min_cgpa} onChange={(e) => onChange({ ...form, min_cgpa: e.target.value })} /></label>
      <div className="form-group">
        <strong>Allowed departments</strong>
        <div className="choice-row">
          {DEPARTMENTS.map((dept) => (
            <button type="button" className={form.allowed_departments.includes(dept) ? 'selected' : ''} key={dept} onClick={() => onChange({ ...form, allowed_departments: toggleArray(form.allowed_departments, dept) })}>{dept}</button>
          ))}
        </div>
      </div>
      <div className="form-group">
        <strong>Graduation years</strong>
        <div className="choice-row">
          {YEARS.map((year) => (
            <button type="button" className={form.grad_years_eligible.includes(year) ? 'selected' : ''} key={year} onClick={() => onChange({ ...form, grad_years_eligible: toggleArray(form.grad_years_eligible, year) })}>{year}</button>
          ))}
        </div>
      </div>
      <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? 'Saving...' : submitLabel}</button>
    </form>
  );
}

export default function RecruiterPostJob() {
  const [activeTab, setActiveTab] = useState<RolesTab>('view');
  const [jobs, setJobs] = useState<JobCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [postForm, setPostForm] = useState<RoleFormState>(defaultFormState);
  const [posting, setPosting] = useState(false);
  const [editingJobId, setEditingJobId] = useState('');
  const [editForm, setEditForm] = useState<RoleFormState>(defaultFormState);
  const [busyJobId, setBusyJobId] = useState('');

  async function loadJobs() {
    setLoading(true);
    try {
      const response = await getRecruiterJobs();
      const sorted = [...response.data.jobs].sort((a, b) => {
        const aTime = new Date(a.created_at || 0).getTime();
        const bTime = new Date(b.created_at || 0).getTime();
        return bTime - aTime;
      });
      setJobs(sorted);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not load your roles.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadJobs();
  }, []);

  async function submitNewRole(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    setError('');
    setPosting(true);
    try {
      const response = await createRecruiterJob(buildPayload(postForm));
      setJobs((current) => [response.data, ...current]);
      setPostForm(defaultFormState);
      setActiveTab('view');
      setMessage('Role posted successfully.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not post this role.');
    } finally {
      setPosting(false);
    }
  }

  function startEditing(job: JobCardData) {
    setEditingJobId(job.id);
    setEditForm(formFromJob(job));
    setMessage('');
    setError('');
  }

  function cancelEditing() {
    setEditingJobId('');
    setEditForm(defaultFormState);
  }

  async function submitRoleUpdate(event: FormEvent, job: JobCardData) {
    event.preventDefault();
    setMessage('');
    setError('');
    setBusyJobId(job.id);
    try {
      const response = await updateRecruiterJob(job.id, {
        ...buildPayload(editForm),
        is_active: job.is_active ?? true,
      });
      setJobs((current) => current.map((item) => item.id === job.id ? response.data : item));
      cancelEditing();
      setMessage('Role updated successfully.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not update this role.');
    } finally {
      setBusyJobId('');
    }
  }

  async function toggleRoleStatus(job: JobCardData, isActive: boolean) {
    setMessage('');
    setError('');
    setBusyJobId(job.id);
    try {
      const response = await setRecruiterJobStatus(job.id, isActive);
      setJobs((current) => current.map((item) => item.id === job.id ? response.data : item));
      setMessage(isActive ? 'Role reopened successfully.' : 'Role closed successfully.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not change this role status.');
    } finally {
      setBusyJobId('');
    }
  }

  async function removeRole(job: JobCardData) {
    const confirmed = window.confirm(`Delete "${job.role_title}" permanently?`);
    if (!confirmed) return;

    setMessage('');
    setError('');
    setBusyJobId(job.id);
    try {
      await deleteRecruiterJob(job.id);
      setJobs((current) => current.filter((item) => item.id !== job.id));
      if (editingJobId === job.id) {
        cancelEditing();
      }
      setMessage('Role deleted successfully.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not delete this role.');
    } finally {
      setBusyJobId('');
    }
  }

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Recruiter Portal</span>
        <h1>Roles</h1>
        <p>Manage existing roles, close or delete older postings, and publish new ones from one place.</p>
      </header>

      <div className="tier-tabs browse-track-tabs role-tabs">
        <button type="button" className={activeTab === 'view' ? 'active' : ''} onClick={() => setActiveTab('view')}>View Roles</button>
        <button type="button" className={activeTab === 'post' ? 'active' : ''} onClick={() => setActiveTab('post')}>Post Role</button>
      </div>

      {message && <div className="portal-note">{message}</div>}
      {error && <div className="bias-inline-error">{error}</div>}

      {activeTab === 'post' ? (
        <RoleForm
          form={postForm}
          onChange={setPostForm}
          onSubmit={submitNewRole}
          submitLabel="Post role"
          busy={posting}
        />
      ) : loading ? (
        <div className="loading"><div className="spinner" /> Loading roles...</div>
      ) : jobs.length === 0 ? (
        <div className="portal-empty">
          <h2>No roles yet</h2>
          <p>Create your first role from the Post Role tab.</p>
        </div>
      ) : (
        <section className="roles-list">
          {jobs.map((job) => {
            const isEditing = editingJobId === job.id;
            const isBusy = busyJobId === job.id;
            const active = job.is_active ?? true;

            return (
              <article className={`portal-form-card role-card ${active ? '' : 'role-card-closed'}`} key={job.id}>
                <div className="role-card-header">
                  <div>
                    <span className={`role-status-pill ${active ? 'active' : 'closed'}`}>{active ? 'Active' : 'Closed'}</span>
                    <h2>{job.role_title}</h2>
                    <p>{job.industry || 'General'} {job.location ? `| ${job.location}` : ''}</p>
                  </div>
                  {!isEditing && (
                    <div className="role-card-actions">
                      <button type="button" className="btn btn-ghost" disabled={isBusy} onClick={() => startEditing(job)}>Modify</button>
                      <button type="button" className="btn btn-ghost" disabled={isBusy} onClick={() => toggleRoleStatus(job, !active)}>
                        {active ? 'Close role' : 'Reopen role'}
                      </button>
                      <button type="button" className="btn btn-danger" disabled={isBusy} onClick={() => removeRole(job)}>Delete</button>
                    </div>
                  )}
                </div>

                {isEditing ? (
                  <>
                    <RoleForm
                      form={editForm}
                      onChange={setEditForm}
                      onSubmit={(event) => submitRoleUpdate(event, job)}
                      submitLabel="Save changes"
                      busy={isBusy}
                    />
                    <div className="role-editor-footer">
                      <button type="button" className="btn btn-ghost" onClick={cancelEditing}>Cancel</button>
                    </div>
                  </>
                ) : (
                  <div className="role-card-details">
                    <p><strong>Remote policy:</strong> {job.remote_policy || 'Not specified'}</p>
                    <p><strong>Highlight:</strong> {job.highlight_line || 'No highlight added.'}</p>
                    <p><strong>Required skills:</strong> {job.required_skills?.length ? job.required_skills.join(', ') : 'None listed'}</p>
                    <p><strong>Preferred skills:</strong> {job.preferred_skills?.length ? job.preferred_skills.join(', ') : 'None listed'}</p>
                    <p><strong>Departments:</strong> {job.allowed_departments?.length ? job.allowed_departments.join(', ') : 'All departments'}</p>
                    <p><strong>Graduation years:</strong> {job.grad_years_eligible?.length ? job.grad_years_eligible.join(', ') : 'All years'}</p>
                    <p><strong>Minimum CGPA:</strong> {job.min_cgpa ?? 'Not specified'}</p>
                  </div>
                )}
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
