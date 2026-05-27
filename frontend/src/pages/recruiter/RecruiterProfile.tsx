import { ChangeEvent, useEffect, useState } from 'react';
import {
  IconBriefcase2,
  IconBuilding,
  IconChartBar,
  IconLink,
  IconMail,
  IconMapPin,
  IconTargetArrow,
  IconUsers,
} from '@tabler/icons-react';
import {
  RecruiterProfileSummary,
  getRecruiterProfile,
  updateRecruiterProfile,
} from '../../services/swipeApi';

type RecruiterProfileDraft = {
  name: string;
  email: string;
  company_name: string;
  company_domain: string;
  designation: string;
  phone_number: string;
  industry: string;
  company_size: string;
  headquarters: string;
  hiring_type: string;
  preferred_departments: string;
  preferred_graduation_years: string;
  min_cgpa: string;
  max_active_backlogs: string;
  work_mode: string;
  about_company: string;
  hiring_pitch: string;
  website_url: string;
  careers_url: string;
  linkedin_url: string;
};

function valueText(value?: string | number | null) {
  if (value === undefined || value === null || value === '') return 'Not added';
  return String(value);
}

function listText(values: Array<string | number>) {
  return values.length ? values.join(', ') : 'Not added';
}

function buildDraft(profile: RecruiterProfileSummary): RecruiterProfileDraft {
  return {
    name: profile.identity.name || '',
    email: profile.identity.email || '',
    company_name: profile.identity.company_name || '',
    company_domain: profile.identity.company_domain || '',
    designation: profile.identity.designation || '',
    phone_number: profile.identity.phone_number || '',
    industry: profile.company.industry || '',
    company_size: profile.company.company_size || '',
    headquarters: profile.company.headquarters || '',
    hiring_type: profile.hiring_preferences.hiring_type || '',
    preferred_departments: profile.hiring_preferences.preferred_departments.join(', '),
    preferred_graduation_years: profile.hiring_preferences.preferred_graduation_years.join(', '),
    min_cgpa: profile.hiring_preferences.min_cgpa !== undefined && profile.hiring_preferences.min_cgpa !== null ? String(profile.hiring_preferences.min_cgpa) : '',
    max_active_backlogs: profile.hiring_preferences.max_active_backlogs !== undefined && profile.hiring_preferences.max_active_backlogs !== null ? String(profile.hiring_preferences.max_active_backlogs) : '',
    work_mode: profile.hiring_preferences.work_mode || '',
    about_company: profile.company.about_company || '',
    hiring_pitch: profile.company.hiring_pitch || '',
    website_url: profile.links.website_url || '',
    careers_url: profile.links.careers_url || '',
    linkedin_url: profile.links.linkedin_url || '',
  };
}

function textList(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function numberList(value: string) {
  return textList(value)
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item));
}

function Field({
  label,
  value,
  editing,
  onChange,
  type = 'text',
  readOnly = false,
}: {
  label: string;
  value?: string | number | null;
  editing: boolean;
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void;
  type?: string;
  readOnly?: boolean;
}) {
  if (!editing || readOnly) {
    return (
      <div className="profile-info-item">
        <span>{label}</span>
        <strong>{valueText(value)}</strong>
      </div>
    );
  }

  return (
    <label className="profile-edit-field">
      <span>{label}</span>
      <input className="input" type={type} value={value || ''} onChange={onChange} />
    </label>
  );
}

function TextAreaField({
  label,
  value,
  editing,
  onChange,
}: {
  label: string;
  value?: string | null;
  editing: boolean;
  onChange?: (event: ChangeEvent<HTMLTextAreaElement>) => void;
}) {
  if (!editing) {
    return (
      <div className="profile-info-item">
        <span>{label}</span>
        <strong>{valueText(value)}</strong>
      </div>
    );
  }

  return (
    <label className="profile-edit-field profile-edit-field-wide">
      <span>{label}</span>
      <textarea className="input profile-textarea" value={value || ''} onChange={onChange} />
    </label>
  );
}

function ActivityCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="profile-activity-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function RecruiterProfile() {
  const [profile, setProfile] = useState<RecruiterProfileSummary | null>(null);
  const [draft, setDraft] = useState<RecruiterProfileDraft | null>(null);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function loadProfile() {
    const response = await getRecruiterProfile();
    setProfile(response.data);
    setDraft(buildDraft(response.data));
  }

  useEffect(() => {
    loadProfile()
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load company profile.'))
      .finally(() => setLoading(false));
  }, []);

  function setDraftField<K extends keyof RecruiterProfileDraft>(key: K, value: RecruiterProfileDraft[K]) {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  }

  async function saveProfile() {
    if (!draft) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await updateRecruiterProfile({
        name: draft.name || null,
        company_name: draft.company_name || null,
        company_domain: draft.company_domain || null,
        designation: draft.designation || null,
        phone_number: draft.phone_number || null,
        industry: draft.industry || null,
        company_size: draft.company_size || null,
        headquarters: draft.headquarters || null,
        hiring_type: draft.hiring_type || null,
        preferred_departments: textList(draft.preferred_departments),
        preferred_graduation_years: numberList(draft.preferred_graduation_years),
        min_cgpa: draft.min_cgpa ? Number(draft.min_cgpa) : null,
        max_active_backlogs: draft.max_active_backlogs ? Number(draft.max_active_backlogs) : null,
        work_mode: draft.work_mode || null,
        about_company: draft.about_company || null,
        hiring_pitch: draft.hiring_pitch || null,
        website_url: draft.website_url || null,
        careers_url: draft.careers_url || null,
        linkedin_url: draft.linkedin_url || null,
      });
      await loadProfile();
      setEditing(false);
      setMessage('Company profile updated.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not save company profile.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="loading"><div className="spinner" /> Loading company profile...</div>;

  return (
    <main className="portal-page recruiter-profile-page">
      <header className="portal-header">
        <span>Recruiter Portal</span>
        <h1>Company profile</h1>
      </header>

      {message && <div className="portal-note">{message}</div>}
      {error && <div className="bias-inline-error">{error}</div>}

      {!profile || !draft ? (
        <div className="portal-empty"><h2>Profile unavailable</h2><p>Try signing in again.</p></div>
      ) : (
        <>
          <div className="profile-toolbar">
            {editing ? (
              <>
                <button className="btn btn-ghost" type="button" onClick={() => { setDraft(buildDraft(profile)); setEditing(false); }}>Cancel</button>
                <button className="btn-signup" type="button" onClick={() => void saveProfile()} disabled={saving}>{saving ? 'Saving...' : 'Save changes'}</button>
              </>
            ) : (
              <button className="btn-signup" type="button" onClick={() => setEditing(true)}>Edit profile</button>
            )}
          </div>

          <section className="student-profile-bento recruiter-profile-bento">
            <article className="bento-card profile-identity-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconBuilding size={15} /> Company identity</span>
                <span className="bento-pill">{draft.industry || 'Recruiter'}</span>
              </div>
              <div className="profile-avatar">{draft.company_name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase() || 'CO'}</div>
              <h2>{draft.company_name || 'Company'}</h2>
              <div className="profile-info-grid">
                <Field label="Company name" value={draft.company_name} editing={editing} onChange={(event) => setDraftField('company_name', event.target.value)} />
                <Field label="Company domain" value={draft.company_domain} editing={editing} onChange={(event) => setDraftField('company_domain', event.target.value)} />
                <Field label="Recruiter name" value={draft.name} editing={editing} onChange={(event) => setDraftField('name', event.target.value)} />
                <Field label="Work email" value={draft.email} editing={editing} readOnly />
                <Field label="Designation" value={draft.designation} editing={editing} onChange={(event) => setDraftField('designation', event.target.value)} />
                <Field label="Phone number" value={draft.phone_number} editing={editing} onChange={(event) => setDraftField('phone_number', event.target.value)} />
              </div>
            </article>

            <article className="bento-card profile-activity-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconChartBar size={15} /> Hiring activity</span>
                <span className="bento-pill">Live summary</span>
              </div>
              <div className="profile-activity-grid">
                <ActivityCard label="Posted roles" value={profile.activity.posted_roles} />
                <ActivityCard label="Active roles" value={profile.activity.active_roles} />
                <ActivityCard label="Student interest" value={profile.activity.students_interested} />
                <ActivityCard label="Liked students" value={profile.activity.liked_students} />
                <ActivityCard label="Matches" value={profile.activity.matches} />
                <ActivityCard label="Passed students" value={profile.activity.passed_students} />
              </div>
            </article>

            <article className="bento-card profile-education-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconBriefcase2 size={15} /> Company details</span>
                <span className="bento-pill">{valueText(draft.company_size)}</span>
              </div>
              <div className="profile-info-grid">
                <Field label="Industry" value={draft.industry} editing={editing} onChange={(event) => setDraftField('industry', event.target.value)} />
                <Field label="Company size" value={draft.company_size} editing={editing} onChange={(event) => setDraftField('company_size', event.target.value)} />
                <Field label="Headquarters" value={draft.headquarters} editing={editing} onChange={(event) => setDraftField('headquarters', event.target.value)} />
                <TextAreaField label="About company" value={draft.about_company} editing={editing} onChange={(event) => setDraftField('about_company', event.target.value)} />
                <TextAreaField label="Hiring pitch" value={draft.hiring_pitch} editing={editing} onChange={(event) => setDraftField('hiring_pitch', event.target.value)} />
              </div>
            </article>

            <article className="bento-card profile-preferences-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconTargetArrow size={15} /> Hiring preferences</span>
                <span className="bento-pill">{valueText(draft.hiring_type)}</span>
              </div>
              <div className="profile-info-grid">
                <Field label="Hiring type" value={draft.hiring_type} editing={editing} onChange={(event) => setDraftField('hiring_type', event.target.value)} />
                <Field label="Work mode" value={draft.work_mode} editing={editing} onChange={(event) => setDraftField('work_mode', event.target.value)} />
                <Field label="Preferred departments" value={editing ? draft.preferred_departments : listText(profile.hiring_preferences.preferred_departments)} editing={editing} onChange={(event) => setDraftField('preferred_departments', event.target.value)} />
                <Field label="Graduation years" value={editing ? draft.preferred_graduation_years : listText(profile.hiring_preferences.preferred_graduation_years)} editing={editing} onChange={(event) => setDraftField('preferred_graduation_years', event.target.value)} />
                <Field label="Minimum CGPA" value={draft.min_cgpa} editing={editing} onChange={(event) => setDraftField('min_cgpa', event.target.value)} type="number" />
                <Field label="Max active backlogs" value={draft.max_active_backlogs} editing={editing} onChange={(event) => setDraftField('max_active_backlogs', event.target.value)} type="number" />
              </div>
            </article>

            <article className="bento-card profile-links-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconLink size={15} /> Links</span>
              </div>
              <div className="profile-link-list">
                <Field label="Website" value={draft.website_url} editing={editing} onChange={(event) => setDraftField('website_url', event.target.value)} />
                <Field label="Careers page" value={draft.careers_url} editing={editing} onChange={(event) => setDraftField('careers_url', event.target.value)} />
                <Field label="LinkedIn" value={draft.linkedin_url} editing={editing} onChange={(event) => setDraftField('linkedin_url', event.target.value)} />
              </div>
            </article>

            <article className="bento-card profile-skills-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconUsers size={15} /> Public card preview</span>
                <span className="bento-pill"><IconMapPin size={13} /> {draft.headquarters || 'Location'}</span>
              </div>
              <div className="criteria-matrix profile-criteria-list">
                <div className="criteria-cell pass">
                  <b><IconBriefcase2 size={15} /> Company</b>
                  <span>{draft.company_name || 'Not added'}</span>
                </div>
                <div className="criteria-cell">
                  <b><IconTargetArrow size={15} /> Hiring</b>
                  <span>{draft.hiring_type || 'Not added'}</span>
                </div>
                <div className="criteria-cell">
                  <b><IconMail size={15} /> Contact</b>
                  <span>{draft.email || 'Not added'}</span>
                </div>
              </div>
            </article>
          </section>
        </>
      )}
    </main>
  );
}
