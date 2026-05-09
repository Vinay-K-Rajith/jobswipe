import { FormEvent, useState } from 'react';
import { createRecruiterJob } from '../../services/swipeApi';

const DEPARTMENTS = ['CSE', 'IT', 'AIML', 'AIDS', 'ECE', 'EEE', 'MECH'];
const YEARS = [2025, 2026, 2027];

function splitTags(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

export default function RecruiterPostJob() {
  const [form, setForm] = useState({
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
  });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  function toggleArray<T>(values: T[], value: T) {
    return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    setError('');
    try {
      await createRecruiterJob({
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
      });
      setMessage('Role posted successfully.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not post this role.');
    }
  }

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Recruiter Portal</span>
        <h1>Post a role</h1>
        <p>Create a listing that appears in qualified student feeds.</p>
      </header>
      {message && <div className="portal-note">{message}</div>}
      {error && <div className="bias-inline-error">{error}</div>}
      <form className="portal-form-card job-form" onSubmit={submit}>
        <label>Role title<input className="input" required value={form.role_title} onChange={(e) => setForm({ ...form, role_title: e.target.value })} /></label>
        <label>Industry / domain<input className="input" required value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} /></label>
        <label>Location<input className="input" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></label>
        <label>Remote policy
          <select className="input" value={form.remote_policy} onChange={(e) => setForm({ ...form, remote_policy: e.target.value })}>
            <option value="on-site">On-site</option>
            <option value="hybrid">Hybrid</option>
            <option value="remote">Remote</option>
          </select>
        </label>
        <label>Required skills<input className="input" placeholder="Python, SQL, React" value={form.required_skills} onChange={(e) => setForm({ ...form, required_skills: e.target.value })} /></label>
        <label>Preferred skills<input className="input" placeholder="AWS, Docker" value={form.preferred_skills} onChange={(e) => setForm({ ...form, preferred_skills: e.target.value })} /></label>
        <label>Interview timeline<textarea className="input" value={form.interview_timeline} onChange={(e) => setForm({ ...form, interview_timeline: e.target.value })} /></label>
        <label>Mentorship structure<textarea className="input" value={form.mentorship} onChange={(e) => setForm({ ...form, mentorship: e.target.value })} /></label>
        <label>Highlight line<textarea className="input" required value={form.highlight_line} onChange={(e) => setForm({ ...form, highlight_line: e.target.value })} /></label>
        <label>Min CGPA<input className="input" type="number" step="0.1" value={form.min_cgpa} onChange={(e) => setForm({ ...form, min_cgpa: e.target.value })} /></label>
        <div className="form-group">
          <strong>Allowed departments</strong>
          <div className="choice-row">
            {DEPARTMENTS.map((dept) => (
              <button type="button" className={form.allowed_departments.includes(dept) ? 'selected' : ''} key={dept} onClick={() => setForm({ ...form, allowed_departments: toggleArray(form.allowed_departments, dept) })}>{dept}</button>
            ))}
          </div>
        </div>
        <div className="form-group">
          <strong>Graduation years</strong>
          <div className="choice-row">
            {YEARS.map((year) => (
              <button type="button" className={form.grad_years_eligible.includes(year) ? 'selected' : ''} key={year} onClick={() => setForm({ ...form, grad_years_eligible: toggleArray(form.grad_years_eligible, year) })}>{year}</button>
            ))}
          </div>
        </div>
        <button className="btn btn-primary" type="submit">Post role</button>
      </form>
    </main>
  );
}
