import { useMemo, useState } from 'react';
import { IconAlertTriangle, IconCheck, IconFileCheck } from '@tabler/icons-react';
import type { ResumeUploadResponse } from '../../services/api';
import { updateStudentProfile, updateStudentProfileSkills } from '../../services/swipeApi';

// The parser assigns a High / Medium / Low confidence badge per field
// (paper §IV-C). Medium and Low are flagged for the student to review and
// correct before relying on them.
const LEVEL_LABEL: Record<string, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  not_found: 'Not found',
};

function badgeClass(level: string): string {
  if (level === 'high') return 'rp-badge high';
  if (level === 'medium') return 'rp-badge medium';
  if (level === 'low') return 'rp-badge low';
  return 'rp-badge missing';
}

function needsReview(level: string): boolean {
  return level === 'medium' || level === 'low';
}

interface Props {
  studentId: string;
  data: ResumeUploadResponse;
  onClose: () => void;
}

export default function ResumeConfidenceReview({ studentId, data, onClose }: Props) {
  const { confidence, parsed } = data;

  const parsedSkills = useMemo(
    () =>
      Array.isArray(parsed?.skills)
        ? parsed.skills
            .map((s: any) => (typeof s === 'string' ? s : s?.skill_name || s?.name || ''))
            .filter(Boolean)
        : [],
    [parsed],
  );
  const parsedCerts = useMemo(
    () =>
      Array.isArray(parsed?.certifications)
        ? parsed.certifications
            .map((c: any) => (typeof c === 'string' ? c : c?.cert_name || c?.name || c?.title || ''))
            .filter(Boolean)
        : [],
    [parsed],
  );

  const [cgpa, setCgpa] = useState<string>(parsed?.cgpa ? String(parsed.cgpa) : '');
  const [skills, setSkills] = useState<string>(parsedSkills.join(', '));
  const [savingCgpa, setSavingCgpa] = useState(false);
  const [savingSkills, setSavingSkills] = useState(false);
  const [savedCgpa, setSavedCgpa] = useState(false);
  const [savedSkills, setSavedSkills] = useState(false);
  const [error, setError] = useState('');

  async function saveCgpa() {
    setSavingCgpa(true);
    setError('');
    setSavedCgpa(false);
    try {
      await updateStudentProfile(studentId, { cgpa: cgpa ? Number(cgpa) : null });
      setSavedCgpa(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not save CGPA.');
    } finally {
      setSavingCgpa(false);
    }
  }

  async function saveSkills() {
    setSavingSkills(true);
    setError('');
    setSavedSkills(false);
    try {
      const list = skills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
        .map((name) => ({ name, proficiency: 'Not set' }));
      await updateStudentProfileSkills(studentId, { skills: list });
      setSavedSkills(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not save skills.');
    } finally {
      setSavingSkills(false);
    }
  }

  return (
    <section className="rp-panel">
      <header className="rp-head">
        <div>
          <span className="bento-eyebrow">
            <IconFileCheck size={15} /> Parsed field confidence
          </span>
          <h3>Review parsed fields</h3>
          <p>
            Fields the parser was unsure about are flagged below. Correct anything that looks wrong —
            your edits save straight to your profile.
          </p>
        </div>
        <button type="button" className="rp-dismiss" onClick={onClose}>
          Done
        </button>
      </header>

      {error && <div className="bias-inline-error">{error}</div>}

      {/* CGPA — correctable via PUT /profile */}
      <div className={`rp-row ${needsReview(confidence.cgpa) ? 'flagged' : ''}`}>
        <div className="rp-label">
          <span className="rp-field">CGPA</span>
          <span className={badgeClass(confidence.cgpa)}>{LEVEL_LABEL[confidence.cgpa] ?? confidence.cgpa}</span>
          {needsReview(confidence.cgpa) && (
            <span className="rp-flag">
              <IconAlertTriangle size={13} /> Needs review
            </span>
          )}
        </div>
        <div className="rp-edit">
          <input
            className="input"
            type="number"
            step="0.01"
            min="0"
            max="10"
            value={cgpa}
            onChange={(e) => {
              setCgpa(e.target.value);
              setSavedCgpa(false);
            }}
            placeholder="e.g. 8.4"
          />
          <button type="button" className="iv-btn" disabled={savingCgpa} onClick={() => void saveCgpa()}>
            {savingCgpa ? 'Saving…' : 'Save'}
          </button>
          {savedCgpa && (
            <span className="rp-ok">
              <IconCheck size={14} /> Saved
            </span>
          )}
        </div>
      </div>

      {/* Skills — correctable via PUT /profile/{id}/skills */}
      <div className={`rp-row ${needsReview(confidence.skills) ? 'flagged' : ''}`}>
        <div className="rp-label">
          <span className="rp-field">Skills</span>
          <span className={badgeClass(confidence.skills)}>{LEVEL_LABEL[confidence.skills] ?? confidence.skills}</span>
          {needsReview(confidence.skills) && (
            <span className="rp-flag">
              <IconAlertTriangle size={13} /> Needs review
            </span>
          )}
        </div>
        <div className="rp-edit">
          <input
            className="input"
            value={skills}
            onChange={(e) => {
              setSkills(e.target.value);
              setSavedSkills(false);
            }}
            placeholder="Comma-separated, e.g. Python, React, SQL"
          />
          <button type="button" className="iv-btn" disabled={savingSkills} onClick={() => void saveSkills()}>
            {savingSkills ? 'Saving…' : 'Save'}
          </button>
          {savedSkills && (
            <span className="rp-ok">
              <IconCheck size={14} /> Saved
            </span>
          )}
        </div>
      </div>

      {/* Certifications — badge + parsed values (managed on the Profile page) */}
      <div className="rp-row">
        <div className="rp-label">
          <span className="rp-field">Certifications</span>
          <span className={badgeClass(confidence.certifications)}>
            {LEVEL_LABEL[confidence.certifications] ?? confidence.certifications}
          </span>
        </div>
        <div className="rp-readonly">
          <span>{parsedCerts.length ? parsedCerts.join(', ') : 'None detected'}</span>
          <span className="rp-hint">Add or edit certifications on your Profile page.</span>
        </div>
      </div>

      {Array.isArray(confidence.fields_missing) && confidence.fields_missing.length > 0 && (
        <p className="rp-missing">Not found in your resume: {confidence.fields_missing.join(', ')}</p>
      )}
    </section>
  );
}
