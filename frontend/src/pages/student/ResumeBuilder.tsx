import { useState, useEffect } from 'react';
import { useAuthStore } from '../../store/authStore';
import { previewResume, downloadResume, compileResume, scoreResume } from '../../services/resumeBuilderApi';

function errorMessage(err: unknown) {
  const e = err as { response?: { data?: { detail?: string } } };
  return e?.response?.data?.detail ?? 'Something went wrong.';
}

export default function ResumeBuilder() {
  const studentId = useAuthStore((state) => state.userId);
  const [resumeText, setResumeText] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [editInstruction, setEditInstruction] = useState('');
  const [error, setError] = useState<string | null>(null);

  // LaTeX Preview States
  const [templateId, setTemplateId] = useState('classic');
  const [activeTab, setActiveTab] = useState<'pdf' | 'source' | 'score'>('pdf');
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [lastCompiledText, setLastCompiledText] = useState('');
  const [isCompiling, setIsCompiling] = useState(false);
  const [compileErrorLog, setCompileErrorLog] = useState<string | null>(null);
  const [score, setScore] = useState<any>(null);

  const compilePdf = async (textToCompile: string, previewScore?: any) => {
    if (!studentId || !textToCompile) return;
    setIsCompiling(true);
    setCompileErrorLog(null);
    setError(null);
    try {
      const data = await compileResume(studentId, textToCompile);
      
      if (pdfUrl) {
        window.URL.revokeObjectURL(pdfUrl);
      }
      
      const blob = new Blob([data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      setPdfUrl(url);
      setLastCompiledText(textToCompile);
      
      if (previewScore) {
        setScore(previewScore);
      } else {
        const scoreRes = await scoreResume(studentId, textToCompile);
        setScore(scoreRes.data);
      }
    } catch (err: any) {
      console.error(err);
      try {
        const errorText = await err.response.data.text();
        const parsedError = JSON.parse(errorText);
        const detail = parsedError.detail;
        if (typeof detail === 'object' && detail.log) {
          setError(detail.message || 'LaTeX compilation failed.');
          setCompileErrorLog(detail.log);
        } else {
          setError(detail || 'Failed to compile LaTeX.');
        }
      } catch {
        setError('LaTeX compilation failed. Please check document syntax.');
      }
      setActiveTab('pdf');
    } finally {
      setIsCompiling(false);
    }
  };

  useEffect(() => {
    return () => {
      if (pdfUrl) {
        window.URL.revokeObjectURL(pdfUrl);
      }
    };
  }, [pdfUrl]);

  const generateResume = async () => {
    if (!studentId) { setError('Student session not found.'); return; }
    setError(null);
    setIsGenerating(true);
    try {
      const res = await previewResume(studentId, templateId);
      setResumeText(res.data.resume_text);
      await compilePdf(res.data.resume_text, res.data.score);
      setActiveTab('pdf');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsGenerating(false);
    }
  };

  const applyEdit = async () => {
    if (!studentId) { setError('Student session not found.'); return; }
    setError(null);
    setIsEditing(true);
    try {
      const res = await previewResume(studentId, templateId, resumeText, editInstruction);
      setResumeText(res.data.resume_text);
      await compilePdf(res.data.resume_text, res.data.score);
      setEditInstruction('');
      setActiveTab('pdf');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsEditing(false);
    }
  };

  const downloadPdf = async () => {
    if (!studentId) { setError('Student session not found.'); return; }
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
      <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'stretch', minHeight: 'calc(100vh - 120px)' }}>

        {/* Sidebar controls */}
        <section className="portal-list" style={{ flex: '0 0 280px', display: 'flex', flexDirection: 'column' }}>
          <header className="portal-header">
            <span>Student Portal</span>
            <h1>Resume Builder</h1>
          </header>

          <label htmlFor="resume-template" style={{ display: 'block', fontWeight: 700, fontSize: '13px', marginBottom: '8px', color: '#94a3b8' }}>
            Choose Template Style
          </label>
          <select
            id="resume-template"
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              marginBottom: '12px',
              padding: '10px 12px',
              borderRadius: '8px',
              border: '1px solid rgba(148,163,184,0.15)',
              background: 'rgba(15,23,42,0.6)',
              color: '#f8fafc',
              fontSize: '13px',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value="classic">Classic (Chronological)</option>
            <option value="technical">Technical (Skills-First)</option>
            <option value="research">Research (Academics/Pubs)</option>
            <option value="minimal">Minimal (ATS-Parsed)</option>
          </select>

          <button className="btn" type="button" onClick={generateResume} disabled={isGenerating || isCompiling}>
            {isGenerating && <span className="spinner" />}
            {isGenerating ? 'Generating…' : 'Generate Resume'}
          </button>

          <hr style={{ border: 'none', borderTop: '1px solid rgba(148,163,184,0.1)', margin: '16px 0' }} />

          <label htmlFor="resume-edit-instruction" style={{ display: 'block', fontWeight: 700, fontSize: '13px', color: '#94a3b8' }}>
            Refine with AI Instructions
          </label>
          <textarea
            id="resume-edit-instruction"
            rows={3}
            value={editInstruction}
            onChange={(e) => setEditInstruction(e.target.value)}
            placeholder="e.g. shorten the summary, emphasise the ML project"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              marginTop: '8px',
              padding: '10px 12px',
              borderRadius: '8px',
              border: '1px solid rgba(148,163,184,0.15)',
              background: 'rgba(15,23,42,0.6)',
              color: '#f8fafc',
              fontSize: '13px',
              lineHeight: '1.5',
              resize: 'vertical',
              outline: 'none',
            }}
          />

          <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
            <button
              type="button"
              onClick={() => setEditInstruction('Make it a 1-page resume')}
              style={{ padding: '4px 10px', fontSize: '11px', background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '12px', cursor: 'pointer' }}
            >
              1-Page
            </button>
            <button
              type="button"
              onClick={() => setEditInstruction('Change to Harvard format')}
              style={{ padding: '4px 10px', fontSize: '11px', background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '12px', cursor: 'pointer' }}
            >
              Harvard
            </button>
            <button
              type="button"
              onClick={() => setEditInstruction('Make it more concise')}
              style={{ padding: '4px 10px', fontSize: '11px', background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '12px', cursor: 'pointer' }}
            >
              Concise
            </button>
          </div>

          <button
            className="btn btn-ghost"
            type="button"
            onClick={applyEdit}
            disabled={!resumeText || isEditing || isCompiling || !editInstruction.trim()}
          >
            {isEditing && <span className="spinner" />}
            {isEditing ? 'Applying…' : 'Apply Edit'}
          </button>

          <button className="btn" type="button" onClick={downloadPdf} disabled={!resumeText || isDownloading || isCompiling} style={{ marginTop: '8px' }}>
            {isDownloading && <span className="spinner" />}
            {isDownloading ? 'Downloading…' : 'Download PDF'}
          </button>

          {error !== null && <div className="bias-inline-error" style={{ marginTop: '12px' }}>{error}</div>}

          {resumeText && (
            <p style={{ marginTop: 'auto', paddingTop: '16px', fontSize: '11px', color: '#94a3b8', lineHeight: '1.5' }}>
              The resume is written in standard LaTeX. You can manually customize the source layout in the editor tab.
            </p>
          )}
        </section>

        {/* Dashboard Preview panel */}
        <section style={{ flex: '1 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          {resumeText === '' ? (
            <div className="portal-empty" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a', borderRadius: '12px', border: '1px solid rgba(148,163,184,0.1)' }}>
              <p>Your resume preview will appear here after generation.</p>
            </div>
          ) : (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
              background: '#1e293b',
              borderRadius: '12px',
              border: '1px solid rgba(148,163,184,0.1)',
              overflow: 'hidden',
              boxShadow: '0 4px 20px rgba(0,0,0,0.15)'
            }}>
              {/* Tab Headers */}
              <div style={{
                display: 'flex',
                background: '#0f172a',
                borderBottom: '1px solid rgba(148,163,184,0.1)',
                padding: '0 16px'
              }}>
                <button 
                  onClick={() => setActiveTab('pdf')} 
                  style={{
                    padding: '14px 20px',
                    background: 'none',
                    border: 'none',
                    color: activeTab === 'pdf' ? '#6366f1' : '#94a3b8',
                    fontWeight: 600,
                    fontSize: '14px',
                    cursor: 'pointer',
                    borderBottom: activeTab === 'pdf' ? '2px solid #6366f1' : '2px solid transparent',
                    transition: 'all 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <span>📄</span> PDF Preview
                </button>
                
                <button 
                  onClick={() => setActiveTab('source')} 
                  style={{
                    padding: '14px 20px',
                    background: 'none',
                    border: 'none',
                    color: activeTab === 'source' ? '#6366f1' : '#94a3b8',
                    fontWeight: 600,
                    fontSize: '14px',
                    cursor: 'pointer',
                    borderBottom: activeTab === 'source' ? '2px solid #6366f1' : '2px solid transparent',
                    transition: 'all 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <span>💻</span> LaTeX Source
                  {resumeText && resumeText !== lastCompiledText && (
                    <span style={{
                      width: '6px',
                      height: '6px',
                      background: '#f59e0b',
                      borderRadius: '50%',
                      display: 'inline-block',
                      marginLeft: '6px'
                    }} />
                  )}
                </button>
                
                <button 
                  onClick={() => setActiveTab('score')} 
                  style={{
                    padding: '14px 20px',
                    background: 'none',
                    border: 'none',
                    color: activeTab === 'score' ? '#6366f1' : '#94a3b8',
                    fontWeight: 600,
                    fontSize: '14px',
                    cursor: 'pointer',
                    borderBottom: activeTab === 'score' ? '2px solid #6366f1' : '2px solid transparent',
                    transition: 'all 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                  disabled={!score}
                >
                  <span>📊</span> ATS Score {score ? `(${score.overall}%)` : ''}
                </button>
              </div>

              {/* Tab Content */}
              <div style={{ flex: 1, overflow: 'auto', background: '#0f172a', position: 'relative', minHeight: '500px' }}>
                {activeTab === 'pdf' && (
                  <div style={{ width: '100%', height: '100%', position: 'relative', display: 'flex', flexDirection: 'column' }}>
                    {isCompiling && (
                      <div style={{
                        position: 'absolute',
                        inset: 0,
                        background: 'rgba(15,23,42,0.85)',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 10,
                        gap: '12px'
                      }}>
                        <div className="spinner" style={{ width: '32px', height: '32px' }} />
                        <span style={{ color: '#f8fafc', fontSize: '14px', fontWeight: 500 }}>Compiling LaTeX to PDF...</span>
                      </div>
                    )}
                    
                    {compileErrorLog ? (
                      <div style={{ padding: '24px', height: '100%', boxSizing: 'border-box', display: 'flex', flexDirection: 'column' }}>
                        <div style={{
                          background: '#f87171',
                          color: '#7f1d1d',
                          padding: '12px 16px',
                          borderRadius: '6px',
                          fontWeight: 600,
                          marginBottom: '16px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px'
                        }}>
                          <span>❌</span> LaTeX Compilation Failed!
                        </div>
                        <pre style={{
                          flex: 1,
                          background: '#020617',
                          color: '#ef4444',
                          padding: '16px',
                          borderRadius: '8px',
                          overflow: 'auto',
                          fontFamily: 'monospace',
                          fontSize: '12px',
                          lineHeight: '1.5',
                          border: '1px solid rgba(239,68,68,0.2)'
                        }}>
                          {compileErrorLog}
                        </pre>
                      </div>
                    ) : pdfUrl ? (
                      <iframe 
                        src={`${pdfUrl}#toolbar=0&navpanes=0&scrollbar=0`}
                        style={{ width: '100%', height: '100%', border: 'none', background: '#0f172a', flex: 1 }}
                        title="PDF Resume Preview"
                      />
                    ) : (
                      <div className="portal-empty" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <p style={{ color: '#94a3b8' }}>Generate a resume or compile to view PDF.</p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'source' && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '500px', padding: '16px', boxSizing: 'border-box' }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '10px'
                    }}>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                        {resumeText !== lastCompiledText ? '⚠️ Uncompiled changes detected' : '✓ Up to date'}
                      </span>
                      <button 
                        className="btn btn-ghost" 
                        style={{ padding: '6px 12px', fontSize: '12px', height: 'auto', margin: 0 }}
                        onClick={() => compilePdf(resumeText)}
                        disabled={isCompiling || !resumeText}
                      >
                        {isCompiling ? 'Compiling...' : '⚡ Compile & Preview'}
                      </button>
                    </div>
                    <textarea
                      value={resumeText}
                      onChange={(e) => setResumeText(e.target.value)}
                      style={{
                        flex: 1,
                        fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                        fontSize: '13px',
                        background: '#020617',
                        color: '#e2e8f0',
                        border: '1px solid rgba(148,163,184,0.15)',
                        borderRadius: '6px',
                        padding: '16px',
                        resize: 'none',
                        outline: 'none',
                        lineHeight: '1.5',
                        minHeight: '400px'
                      }}
                      placeholder="% LaTeX code goes here..."
                    />
                  </div>
                )}

                {activeTab === 'score' && score && (
                  <div style={{ padding: '24px', color: '#f8fafc', overflow: 'auto', height: '100%', boxSizing: 'border-box' }}>
                    {/* Overall Score Banner */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '24px',
                      background: 'rgba(15,23,42,0.6)',
                      padding: '20px',
                      borderRadius: '8px',
                      border: '1px solid rgba(148,163,184,0.1)',
                      marginBottom: '24px'
                    }}>
                      <div style={{
                        width: '80px',
                        height: '80px',
                        borderRadius: '50%',
                        background: score.overall >= 80 ? '#059669' : score.overall >= 50 ? '#d97706' : '#dc2626',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '28px',
                        fontWeight: 'bold',
                        boxShadow: '0 0 16px rgba(99,102,241,0.2)'
                      }}>
                        {score.overall}%
                      </div>
                      <div>
                        <h3 style={{ fontSize: '18px', fontWeight: 'bold', margin: '0 0 4px' }}>Overall ATS Score</h3>
                        <p style={{ fontSize: '13px', color: '#94a3b8', margin: 0 }}>
                          Word Count: <strong>{score.word_count} words</strong>
                        </p>
                      </div>
                    </div>

                    {/* Dimensions Breakdown */}
                    <h4 style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6366f1', marginBottom: '16px' }}>
                      Score Dimensions
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                      {Object.entries(score.dimensions).map(([key, dim]: [string, any]) => {
                        const barColor = dim.score >= 85 ? '#10b981' : dim.score >= 50 ? '#f59e0b' : '#ef4444';
                        return (
                          <div key={key} style={{
                            background: 'rgba(15,23,42,0.4)',
                            padding: '16px',
                            borderRadius: '8px',
                            border: '1px solid rgba(148,163,184,0.05)'
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '14px' }}>
                              <span style={{ fontWeight: 600 }}>{dim.label}</span>
                              <span style={{ fontWeight: 'bold', color: barColor }}>{dim.score}%</span>
                            </div>
                            
                            {/* Progress Bar */}
                            <div style={{ width: '100%', height: '6px', background: 'rgba(148,163,184,0.1)', borderRadius: '3px', marginBottom: '10px' }}>
                              <div style={{ width: `${dim.score}%`, height: '100%', background: barColor, borderRadius: '3px', transition: 'width 0.4s ease-out' }} />
                            </div>

                            {/* Tip */}
                            <p style={{ fontSize: '12px', color: '#94a3b8', margin: '0 0 8px', lineHeight: '1.4' }}>
                              {dim.tip}
                            </p>

                            {/* Keywords list for keywords dimension */}
                            {key === 'keywords' && (dim.matched?.length > 0 || dim.missing?.length > 0) && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '10px' }}>
                                {dim.matched.map((k: string) => (
                                  <span key={k} style={{ fontSize: '11px', background: 'rgba(16,185,129,0.15)', color: '#34d399', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(16,185,129,0.3)' }}>
                                    ✓ {k}
                                  </span>
                                ))}
                                {dim.missing.map((k: string) => (
                                  <span key={k} style={{ fontSize: '11px', background: 'rgba(239,68,68,0.15)', color: '#f87171', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(239,68,68,0.3)' }}>
                                    ✗ {k}
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Sections lists for sections dimension */}
                            {key === 'sections' && (dim.found?.length > 0 || dim.missing?.length > 0) && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '10px' }}>
                                {dim.found.map((s: string) => (
                                  <span key={s} style={{ fontSize: '11px', background: 'rgba(16,185,129,0.15)', color: '#34d399', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(16,185,129,0.3)' }}>
                                    ✓ {s}
                                  </span>
                                ))}
                                {dim.missing.map((s: string) => (
                                  <span key={s} style={{ fontSize: '11px', background: 'rgba(239,68,68,0.15)', color: '#f87171', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(239,68,68,0.3)' }}>
                                    ✗ {s}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>

      </div>
    </main>
  );
}
