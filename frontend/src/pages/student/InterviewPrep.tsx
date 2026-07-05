import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { IconFileCheck, IconUpload, IconSparkles, IconClock, IconMessageDots } from '@tabler/icons-react';
import { uploadStudentResume } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import {
  CreateSessionPayload,
  SessionSummary,
  createSession,
  listSessions,
} from '../../services/interviewApi';

const SENIORITY = ['entry', 'mid', 'senior', 'lead'];
const STAGES = [
  { value: 'first_round', label: 'First Round' },
  { value: 'final_round', label: 'Final Round' },
  { value: 'hiring_manager', label: 'Hiring Manager' },
];

const STATUS_META: Record<string, { cls: string; label: string }> = {
  completed: { cls: 'iv-status--done', label: 'Completed' },
  active: { cls: 'iv-status--active', label: 'In progress' },
  pre_session: { cls: 'iv-status--idle', label: 'Not started' },
};

export default function InterviewPrep() {
  const navigate = useNavigate();
  const studentId = useAuthStore((state) => state.userId);
  const [form, setForm] = useState<CreateSessionPayload>({
    target_role: '',
    seniority: 'mid',
    target_domain: '',
    interview_stage: 'first_round',
  });
  const [creating, setCreating] = useState(false);
  const [plan, setPlan] = useState<SessionSummary | null>(null);
  const [error, setError] = useState('');
  const [past, setPast] = useState<SessionSummary[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadPast = () => {
    listSessions().then((r) => setPast(r.data.sessions)).catch(() => {});
  };
  useEffect(loadPast, []);

  async function handleResumeUpload(file?: File) {
    if (!file) return;
    if (!studentId) {
      setUploadMessage({ type: 'error', text: 'Your student session is missing. Please log in again.' });
      return;
    }
    if (file.type && file.type !== 'application/pdf') {
      setUploadMessage({ type: 'error', text: 'Please choose a PDF resume.' });
      return;
    }
    setUploading(true);
    setUploadMessage(null);
    try {
      await uploadStudentResume(studentId, file);
      setUploadMessage({ type: 'success', text: 'Resume parsed — your interview will be tailored to it.' });
    } catch (err: any) {
      setUploadMessage({ type: 'error', text: err?.response?.data?.detail || 'Resume upload failed.' });
    } finally {
      setUploading(false);
    }
  }

  const handleCreate = async () => {
    if (!form.target_role.trim()) {
      setError('Enter a target role to continue.');
      return;
    }
    setError('');
    setCreating(true);
    try {
      const res = await createSession(form);
      setPlan(res.data);
      loadPast();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not create the session.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="portal-page">
      <div className="iv-wrap">
        <header className="iv-hero">
          <span className="iv-hero__eyebrow"><IconSparkles size={14} /> Student Portal</span>
          <h1 className="iv-hero__title">AI Interview Prep</h1>
          <p className="iv-hero__sub">
            Sit a realistic behavioral mock interview with an AI interviewer, then get specific,
            transcript-grounded feedback you can actually act on.
          </p>
        </header>

        {error && <div className="bias-inline-error">{error}</div>}

        {!plan ? (
          <section className="iv-card iv-card--glow iv-stack">
            <div className="iv-field">
              <span>Target role</span>
              <input
                className="input"
                value={form.target_role}
                onChange={(e) => setForm({ ...form, target_role: e.target.value })}
                placeholder="e.g. Software Engineer, Product Manager, Data Analyst"
              />
            </div>

            <div className="iv-grid-3">
              <label className="iv-field">
                <span>Seniority</span>
                <select className="input" value={form.seniority} onChange={(e) => setForm({ ...form, seniority: e.target.value })}>
                  {SENIORITY.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <label className="iv-field">
                <span>Interview stage</span>
                <select className="input" value={form.interview_stage} onChange={(e) => setForm({ ...form, interview_stage: e.target.value })}>
                  {STAGES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </label>
              <label className="iv-field">
                <span>Domain (optional)</span>
                <input
                  className="input"
                  value={form.target_domain || ''}
                  onChange={(e) => setForm({ ...form, target_domain: e.target.value })}
                  placeholder="fintech, healthtech…"
                />
              </label>
            </div>

            <section className="resume-upload-panel">
              <div>
                <span className="bento-eyebrow"><IconFileCheck size={15} /> Resume profile</span>
                <p>Upload your latest PDF resume to tailor the questions to your experience. Optional — leave blank to use your saved profile.</p>
              </div>
              <label className={`resume-upload-button ${uploading ? 'disabled' : ''}`}>
                <IconUpload size={16} />
                <span>{uploading ? 'Parsing…' : 'Upload resume'}</span>
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  disabled={uploading}
                  onChange={(event) => {
                    handleResumeUpload(event.target.files?.[0]);
                    event.currentTarget.value = '';
                  }}
                />
              </label>
            </section>
            {uploadMessage && (
              <section className={`resume-upload-status ${uploadMessage.type}`}>
                <IconFileCheck size={17} />
                <span>{uploadMessage.text}</span>
              </section>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="iv-btn" type="button" onClick={handleCreate} disabled={creating || uploading}>
                {creating ? 'Preparing…' : 'Prepare interview'}
              </button>
            </div>
          </section>
        ) : (
          <section className="iv-card iv-card--accent iv-stack">
            <span className="iv-hero__eyebrow"><IconSparkles size={14} /> Your briefing</span>
            <h2 style={{ margin: 0, fontSize: 22, color: '#fff' }}>Here's what we'll focus on</h2>

            <div className="iv-meta">
              <div className="iv-stat"><b>{plan.total_questions}</b><span>Questions</span></div>
              <div className="iv-stat"><b>~{plan.estimated_minutes}m</b><span>Duration</span></div>
              <div className="iv-stat" style={{ textTransform: 'capitalize' }}><b style={{ fontSize: 15 }}>{plan.seniority}</b><span>{plan.target_role}</span></div>
            </div>

            {plan.strengths.length > 0 && (
              <div>
                <div className="iv-section-title">Strengths we'll probe</div>
                <div className="iv-chips">{plan.strengths.map((c) => <span key={c} className="iv-chip iv-chip--strength">{c}</span>)}</div>
              </div>
            )}
            {plan.risks.length > 0 && (
              <div>
                <div className="iv-section-title">Areas to grow</div>
                <div className="iv-chips">{plan.risks.map((c) => <span key={c} className="iv-chip iv-chip--risk">{c}</span>)}</div>
              </div>
            )}
            {plan.blind_spots.length > 0 && (
              <div className="iv-callout">
                <span className="iv-callout__icon">⚠</span>
                <div>
                  <b>Blind spots</b>
                  <p>Not strongly represented in your profile — think of an example before you start: {plan.blind_spots.join(', ')}.</p>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 10 }}>
              <button className="iv-btn" type="button" onClick={() => navigate(`/student/interview/${plan.id}`)}>Start interview</button>
              <button className="iv-btn iv-btn--ghost" type="button" onClick={() => setPlan(null)}>Back</button>
            </div>
          </section>
        )}

        <div>
          <div className="iv-section-title">Past sessions</div>
          {past.length === 0 ? (
            <div className="iv-card iv-empty">
              <h2>No sessions yet</h2>
              <p>Run your first mock interview above to start tracking your progress.</p>
            </div>
          ) : (
            <div className="iv-sessions">
              {past.map((s) => {
                const meta = STATUS_META[s.status] || STATUS_META.pre_session;
                return (
                  <article className="iv-session" key={s.id}>
                    <div className="iv-session__main">
                      <span className="iv-session__title">{s.target_role}</span>
                      <span className="iv-session__meta">
                        <span style={{ textTransform: 'capitalize' }}>{s.seniority}</span>
                        <span>·</span>
                        {new Date(s.created_at).toLocaleDateString()}
                        <span className={`iv-status ${meta.cls}`}>{meta.label}</span>
                      </span>
                    </div>
                    <div className="iv-session__actions">
                      {s.status === 'completed' ? (
                        <>
                          <button className="iv-btn iv-btn--ghost iv-btn--sm" type="button" onClick={() => navigate(`/student/interview/${s.id}/transcript`)}>
                            <IconMessageDots size={15} /> Chat
                          </button>
                          <button className="iv-btn iv-btn--sm" type="button" onClick={() => navigate(`/student/interview/${s.id}/feedback`)}>
                            Feedback
                          </button>
                        </>
                      ) : (
                        <button className="iv-btn iv-btn--ghost iv-btn--sm" type="button" onClick={() => navigate(`/student/interview/${s.id}`)}>
                          <IconClock size={15} /> {s.status === 'active' ? 'Resume' : 'Start'}
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
