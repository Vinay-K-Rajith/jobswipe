import { useState } from 'react';
import { useAuthStore } from '../../store/authStore';
import { previewResume, downloadResume } from '../../services/resumeBuilderApi';

function errorMessage(err: any) {
  return err?.response?.data?.detail || 'Something went wrong.';
}

export default function ResumeBuilder() {
  const studentId = useAuthStore((state) => state.userId);
  const [resumeText, setResumeText] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [editInstruction, setEditInstruction] = useState('');
  const [error, setError] = useState<string | null>(null);

  const generateResume = async () => {
    if (!studentId) {
      setError('Student session not found.');
      return;
    }

    setError(null);
    setIsGenerating(true);
    try {
      const response = await previewResume(studentId, 'default');
      setResumeText(response.data.resume_text);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsGenerating(false);
    }
  };

  const applyEdit = async () => {
    if (!studentId) {
      setError('Student session not found.');
      return;
    }

    setError(null);
    setIsEditing(true);
    try {
      const response = await previewResume(studentId, 'default', resumeText, editInstruction);
      setResumeText(response.data.resume_text);
      setEditInstruction('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsEditing(false);
    }
  };

  const downloadPdf = async () => {
    if (!studentId) {
      setError('Student session not found.');
      return;
    }

    setError(null);
    setIsDownloading(true);
    try {
      await downloadResume(studentId, resumeText);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <main className="portal-page">
      <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <section className="portal-list" style={{ flex: '1 1 280px' }}>
          <header className="portal-header">
            <span>Student Portal</span>
            <h1>AI Resume Builder</h1>
            <p>Create a clean resume from your student profile, then refine it with focused edits.</p>
          </header>

          <button className="btn" type="button" onClick={generateResume} disabled={isGenerating}>
            {isGenerating && <span className="spinner" />}
            {isGenerating ? 'Generating...' : 'Generate Resume'}
          </button>

          <hr />

          <label htmlFor="resume-edit-instruction" style={{ display: 'block', fontWeight: 700 }}>
            Edit instruction
          </label>
          <textarea
            id="resume-edit-instruction"
            rows={3}
            value={editInstruction}
            onChange={(event) => setEditInstruction(event.target.value)}
            placeholder="e.g. make the summary shorter, reword the Python project"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              minHeight: '96px',
              marginTop: '8px',
              padding: '12px 14px',
              borderRadius: '8px',
              border: '1px solid rgba(148, 163, 184, 0.35)',
              background: 'rgba(15, 23, 42, 0.92)',
              color: '#f8fafc',
              fontSize: '14px',
              lineHeight: '1.5',
              resize: 'vertical',
              outline: 'none',
            }}
          />

          <button className="btn btn-ghost" type="button" onClick={applyEdit} disabled={!resumeText || isEditing}>
            {isEditing && <span className="spinner" />}
            {isEditing ? 'Applying...' : 'Apply Edit'}
          </button>

          <button className="btn" type="button" onClick={downloadPdf} disabled={!resumeText || isDownloading}>
            {isDownloading && <span className="spinner" />}
            {isDownloading ? 'Downloading...' : 'Download PDF'}
          </button>

          {error !== null && <div className="bias-inline-error">{error}</div>}
        </section>

        <section style={{ flex: '2 1 420px' }}>
          {resumeText === '' ? (
            <div className="portal-empty">
              <p>Your resume will appear here after generation.</p>
            </div>
          ) : (
            <pre
              style={{
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
                fontSize: '13px',
                lineHeight: '1.6',
                color: '#111827',
                background: '#f9f9f9',
                padding: '16px',
                borderRadius: '8px',
                overflowX: 'auto',
              }}
            >
              {resumeText}
            </pre>
          )}
        </section>
      </div>
    </main>
  );
}
