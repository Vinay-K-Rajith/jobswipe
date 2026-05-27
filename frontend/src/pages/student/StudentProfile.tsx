import { ChangeEvent, useEffect, useState } from 'react';
import {
  IconAward,
  IconBook2,
  IconBriefcase2,
  IconId,
  IconLink,
  IconMail,
  IconMapPin,
  IconSchool,
  IconSparkles,
  IconTargetArrow,
} from '@tabler/icons-react';
import {
  StudentProfileSummary,
  getStudentProfile,
  updateStudentProfile,
  updateStudentProfileSkills,
} from '../../services/swipeApi';

type ProfileDraft = {
  full_name: string;
  personal_email: string;
  college_email: string;
  phone_number: string;
  register_number: string;
  department: string;
  current_year: string;
  graduation_year: string;
  class_10_marks: string;
  class_10_board: string;
  class_12_marks: string;
  class_12_board: string;
  college_name: string;
  degree: string;
  cgpa: string;
  active_backlogs: string;
  backlog_history: string;
  looking_for: string;
  preferred_roles: string;
  preferred_locations: string;
  remote_preference: string;
  open_to_relocation: boolean;
  portfolio_url: string;
  linkedin_url: string;
  github_url: string;
  coding_profile_url: string;
  skills: Array<{
    name: string;
    proficiency: string;
    verified: boolean;
  }>;
};

function valueText(value?: string | number | null) {
  if (value === undefined || value === null || value === '') return 'Not added';
  return String(value);
}

function listText(values: string[]) {
  return values.length ? values.join(', ') : 'Not added';
}

function buildDraft(profile: StudentProfileSummary): ProfileDraft {
  return {
    full_name: profile.basic_info.name || '',
    personal_email: profile.basic_info.personal_email || '',
    college_email: profile.basic_info.college_email || '',
    phone_number: profile.basic_info.phone_number || '',
    register_number: profile.basic_info.college_roll_number || '',
    department: profile.basic_info.department || '',
    current_year: profile.basic_info.current_year ? String(profile.basic_info.current_year) : '',
    graduation_year: profile.basic_info.graduation_year ? String(profile.basic_info.graduation_year) : '',
    class_10_marks: profile.education.class_10_marks ? String(profile.education.class_10_marks) : '',
    class_10_board: profile.education.class_10_board || '',
    class_12_marks: profile.education.class_12_marks ? String(profile.education.class_12_marks) : '',
    class_12_board: profile.education.class_12_board || '',
    college_name: profile.education.college_name || '',
    degree: profile.education.degree || '',
    cgpa: profile.education.cgpa ? String(profile.education.cgpa) : '',
    active_backlogs: profile.education.active_backlogs !== undefined && profile.education.active_backlogs !== null ? String(profile.education.active_backlogs) : '',
    backlog_history: profile.education.backlog_history !== undefined && profile.education.backlog_history !== null ? String(profile.education.backlog_history) : '',
    looking_for: profile.preferences.looking_for || '',
    preferred_roles: profile.preferences.preferred_roles.join(', '),
    preferred_locations: profile.preferences.preferred_locations.join(', '),
    remote_preference: profile.preferences.remote_preference || '',
    open_to_relocation: profile.preferences.open_to_relocation,
    portfolio_url: profile.resume_links.portfolio_url || '',
    linkedin_url: profile.resume_links.linkedin_url || '',
    github_url: profile.resume_links.github_url || '',
    coding_profile_url: profile.resume_links.coding_profile_url || '',
    skills: profile.skills.map((skill) => ({
      name: skill.name,
      proficiency: skill.proficiency,
      verified: skill.verified,
    })),
  };
}

function Field({
  label,
  value,
  editing,
  onChange,
  type = 'text',
}: {
  label: string;
  value?: string | number | null;
  editing: boolean;
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void;
  type?: string;
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
    <label className="profile-edit-field">
      <span>{label}</span>
      <input className="input" type={type} value={value || ''} onChange={onChange} />
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

export default function StudentProfile() {
  const [profile, setProfile] = useState<StudentProfileSummary | null>(null);
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');

  async function loadProfile() {
    const response = await getStudentProfile();
    setProfile(response.data);
    setDraft(buildDraft(response.data));
  }

  useEffect(() => {
    loadProfile()
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load your profile.'))
      .finally(() => setLoading(false));
  }, []);

  function setDraftField<K extends keyof ProfileDraft>(key: K, value: ProfileDraft[K]) {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  }

  function updateSkill(index: number, key: 'name' | 'proficiency', value: string) {
    setDraft((current) => {
      if (!current) return current;
      const nextSkills = [...current.skills];
      nextSkills[index] = { ...nextSkills[index], [key]: value };
      return { ...current, skills: nextSkills };
    });
  }

  function addSkill() {
    setDraft((current) => current ? {
      ...current,
      skills: [...current.skills, { name: '', proficiency: 'Intermediate', verified: false }],
    } : current);
  }

  function removeSkill(index: number) {
    setDraft((current) => current ? {
      ...current,
      skills: current.skills.filter((_, currentIndex) => currentIndex !== index),
    } : current);
  }

  async function saveProfile() {
    if (!profile || !draft) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await updateStudentProfile(profile.basic_info.student_id, {
        full_name: draft.full_name,
        personal_email: draft.personal_email || null,
        college_email: draft.college_email || null,
        phone_number: draft.phone_number || null,
        register_number: draft.register_number || null,
        department: draft.department || null,
        class_10_marks: draft.class_10_marks ? Number(draft.class_10_marks) : null,
        class_10_board: draft.class_10_board || null,
        class_12_marks: draft.class_12_marks ? Number(draft.class_12_marks) : null,
        class_12_board: draft.class_12_board || null,
        college_name: draft.college_name || null,
        degree: draft.degree || null,
        cgpa: draft.cgpa ? Number(draft.cgpa) : null,
        active_backlogs: draft.active_backlogs ? Number(draft.active_backlogs) : null,
        backlog_history: draft.backlog_history ? Number(draft.backlog_history) : null,
        year_of_study: draft.current_year ? Number(draft.current_year) : null,
        batch_year: draft.graduation_year ? Number(draft.graduation_year) : null,
        looking_for: draft.looking_for || null,
        preferred_roles: draft.preferred_roles.split(',').map((item) => item.trim()).filter(Boolean),
        preferred_locations: draft.preferred_locations.split(',').map((item) => item.trim()).filter(Boolean),
        remote_preference: draft.remote_preference || null,
        open_to_relocation: draft.open_to_relocation,
        portfolio_url: draft.portfolio_url || null,
        linkedin_url: draft.linkedin_url || null,
        github_url: draft.github_url || null,
        coding_profile_url: draft.coding_profile_url || null,
      });

      await updateStudentProfileSkills(profile.basic_info.student_id, {
        skills: draft.skills
          .map((skill) => ({
            name: skill.name.trim(),
            proficiency: skill.proficiency.trim() || 'Not set',
          }))
          .filter((skill) => skill.name),
      });

      await loadProfile();
      setEditing(false);
      setMessage('Profile updated.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not save your profile.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="loading"><div className="spinner" /> Loading profile...</div>;

  return (
    <main className="portal-page student-profile-page">
      <header className="portal-header">
        <span>Student Portal</span>
        <h1>Profile</h1>
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

          <section className="student-profile-bento">
            <article className="bento-card profile-identity-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconId size={15} /> Basic info</span>
                <span className="bento-pill">{draft.department || 'Student'}</span>
              </div>
              <div className="profile-avatar">{draft.full_name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</div>
              <h2>{draft.full_name || 'Student'}</h2>
              <div className="profile-info-grid">
                <Field label="Name" value={draft.full_name} editing={editing} onChange={(event) => setDraftField('full_name', event.target.value)} />
                <Field label="Personal email" value={draft.personal_email} editing={editing} onChange={(event) => setDraftField('personal_email', event.target.value)} />
                <Field label="College email" value={draft.college_email} editing={editing} onChange={(event) => setDraftField('college_email', event.target.value)} />
                <Field label="Phone number" value={draft.phone_number} editing={editing} onChange={(event) => setDraftField('phone_number', event.target.value)} />
                <Field label="Roll number" value={draft.register_number} editing={editing} onChange={(event) => setDraftField('register_number', event.target.value)} />
                <Field label="Department" value={draft.department} editing={editing} onChange={(event) => setDraftField('department', event.target.value)} />
                <Field label="Current year" value={draft.current_year} editing={editing} onChange={(event) => setDraftField('current_year', event.target.value)} type="number" />
                <Field label="Graduation year" value={draft.graduation_year} editing={editing} onChange={(event) => setDraftField('graduation_year', event.target.value)} type="number" />
              </div>
            </article>

            <article className="bento-card profile-activity-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconMail size={15} /> Activity</span>
                <span className="bento-pill">Swipe summary</span>
              </div>
              <div className="profile-activity-grid">
                <ActivityCard label="Liked companies" value={profile.activity.liked_companies} />
                <ActivityCard label="Passed roles" value={profile.activity.passed_roles} />
                <ActivityCard label="Companies interested" value={profile.activity.companies_interested} />
                <ActivityCard label="Pending decisions" value={profile.activity.pending_decisions} />
                <ActivityCard label="Matches" value={profile.activity.matches} />
                <ActivityCard label="Growth insights" value={profile.activity.growth_insights} />
              </div>
            </article>

            <article className="bento-card profile-education-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconSchool size={15} /> Education</span>
                <span className="bento-pill">CGPA {valueText(draft.cgpa)}</span>
              </div>
              <div className="profile-info-grid">
                <Field label="Class 10" value={draft.class_10_marks} editing={editing} onChange={(event) => setDraftField('class_10_marks', event.target.value)} type="number" />
                <Field label="Class 10 board" value={draft.class_10_board} editing={editing} onChange={(event) => setDraftField('class_10_board', event.target.value)} />
                <Field label="Class 12" value={draft.class_12_marks} editing={editing} onChange={(event) => setDraftField('class_12_marks', event.target.value)} type="number" />
                <Field label="Class 12 board" value={draft.class_12_board} editing={editing} onChange={(event) => setDraftField('class_12_board', event.target.value)} />
                <Field label="College" value={draft.college_name} editing={editing} onChange={(event) => setDraftField('college_name', event.target.value)} />
                <Field label="Degree" value={draft.degree} editing={editing} onChange={(event) => setDraftField('degree', event.target.value)} />
                <Field label="CGPA" value={draft.cgpa} editing={editing} onChange={(event) => setDraftField('cgpa', event.target.value)} type="number" />
                <Field label="Active backlogs" value={draft.active_backlogs} editing={editing} onChange={(event) => setDraftField('active_backlogs', event.target.value)} type="number" />
                <Field label="Backlog history" value={draft.backlog_history} editing={editing} onChange={(event) => setDraftField('backlog_history', event.target.value)} type="number" />
              </div>
            </article>

            <article className="bento-card profile-skills-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconSparkles size={15} /> Skills</span>
                <span className="bento-pill">{draft.skills.length} skills</span>
              </div>
              <div className="profile-skill-list">
                {draft.skills.length === 0 ? (
                  <p className="muted-text">No skills added yet.</p>
                ) : draft.skills.map((skill, index) => (
                  <div className="profile-skill-row" key={`${skill.name}-${index}`}>
                    {editing ? (
                      <div className="profile-skill-edit-grid">
                        <input className="input" value={skill.name} onChange={(event) => updateSkill(index, 'name', event.target.value)} placeholder="Skill name" />
                        <input className="input" value={skill.proficiency} onChange={(event) => updateSkill(index, 'proficiency', event.target.value)} placeholder="Proficiency" />
                      </div>
                    ) : (
                      <div>
                        <strong>{skill.name}</strong>
                        <span>Technical / {skill.proficiency}</span>
                      </div>
                    )}
                    {editing ? (
                      <button className="btn btn-ghost profile-skill-remove" type="button" onClick={() => removeSkill(index)}>Remove</button>
                    ) : (
                      skill.verified && <span className="badge badge-success">Verified</span>
                    )}
                  </div>
                ))}
                {editing && <button className="btn btn-ghost profile-add-skill" type="button" onClick={addSkill}>Add skill</button>}
              </div>
            </article>

            <article className="bento-card profile-preferences-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconTargetArrow size={15} /> Preferences</span>
                <span className="bento-pill">{valueText(draft.looking_for)}</span>
              </div>
              {editing ? (
                <div className="profile-info-grid">
                  <Field label="Looking for" value={draft.looking_for} editing={editing} onChange={(event) => setDraftField('looking_for', event.target.value)} />
                  <Field label="Preferred roles" value={draft.preferred_roles} editing={editing} onChange={(event) => setDraftField('preferred_roles', event.target.value)} />
                  <Field label="Preferred locations" value={draft.preferred_locations} editing={editing} onChange={(event) => setDraftField('preferred_locations', event.target.value)} />
                  <Field label="Work mode" value={draft.remote_preference} editing={editing} onChange={(event) => setDraftField('remote_preference', event.target.value)} />
                  <label className="profile-toggle-field">
                    <span>Open to relocation</span>
                    <input type="checkbox" checked={draft.open_to_relocation} onChange={(event) => setDraftField('open_to_relocation', event.target.checked)} />
                  </label>
                </div>
              ) : (
                <div className="criteria-matrix profile-criteria-list">
                  <div className="criteria-cell pass">
                    <b><IconBriefcase2 size={15} /> Preferred roles</b>
                    <span>{listText(profile.preferences.preferred_roles)}</span>
                  </div>
                  <div className="criteria-cell">
                    <b><IconMapPin size={15} /> Locations</b>
                    <span>{listText(profile.preferences.preferred_locations)}</span>
                  </div>
                  <div className="criteria-cell">
                    <b><IconBook2 size={15} /> Work mode</b>
                    <span>{valueText(profile.preferences.remote_preference)}</span>
                  </div>
                  <div className="criteria-cell">
                    <b><IconAward size={15} /> Relocation</b>
                    <span>{profile.preferences.open_to_relocation ? 'Open to relocation' : 'Not open to relocation'}</span>
                  </div>
                </div>
              )}
            </article>

            <article className="bento-card profile-links-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconLink size={15} /> Resume & links</span>
              </div>
              <div className="profile-link-list">
                <div className="profile-info-item">
                  <span>Resume</span>
                  <strong>{profile.resume_links.resume_url ? 'Uploaded' : 'Not added'}</strong>
                </div>
                <Field label="LinkedIn" value={draft.linkedin_url} editing={editing} onChange={(event) => setDraftField('linkedin_url', event.target.value)} />
                <Field label="GitHub" value={draft.github_url} editing={editing} onChange={(event) => setDraftField('github_url', event.target.value)} />
                <Field label="Portfolio" value={draft.portfolio_url} editing={editing} onChange={(event) => setDraftField('portfolio_url', event.target.value)} />
                <Field label="Coding profile" value={draft.coding_profile_url} editing={editing} onChange={(event) => setDraftField('coding_profile_url', event.target.value)} />
              </div>
            </article>
          </section>
        </>
      )}
    </main>
  );
}
