import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { IconSparkles } from '@tabler/icons-react';
import { TranscriptTurn, getTranscript } from '../../services/interviewApi';

const INTERVIEWER = { name: 'Jordan Lee', initials: 'JL' };

export default function InterviewTranscript() {
  const { sessionId = '' } = useParams();
  const navigate = useNavigate();
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTranscript(sessionId)
      .then((r) => setTurns(r.data.turns))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load the conversation.'))
      .finally(() => setLoading(false));
  }, [sessionId]);

  return (
    <main className="portal-page">
      <div className="iv-wrap">
        <header className="iv-hero">
          <span className="iv-hero__eyebrow"><IconSparkles size={14} /> Mock Interview</span>
          <h1 className="iv-hero__title">Conversation</h1>
          <p className="iv-hero__sub">The full transcript of this mock interview.</p>
        </header>

        {error && <div className="bias-inline-error">{error}</div>}
        {loading && <div className="iv-card"><div className="iv-typing"><span /><span /><span /></div></div>}

        {!loading && turns.length === 0 && !error && (
          <div className="iv-card iv-empty"><h2>No conversation</h2><p>This session has no recorded messages.</p></div>
        )}

        {turns.length > 0 && (
          <div className="iv-thread">
            {turns.map((t, i) => (
              <div key={i} className={`iv-row ${t.speaker === 'interviewer' ? 'iv-row--ai' : 'iv-row--me'}`}>
                <div className={`iv-avatar ${t.speaker === 'interviewer' ? '' : 'iv-avatar--me'}`}>
                  {t.speaker === 'interviewer' ? INTERVIEWER.initials : 'You'}
                </div>
                <div>
                  <div className="iv-who" style={{ textAlign: t.speaker === 'interviewer' ? 'left' : 'right' }}>
                    {t.speaker === 'interviewer' ? INTERVIEWER.name : 'You'}
                  </div>
                  <div className="iv-bubble">{t.content}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div>
          <button className="iv-btn iv-btn--ghost" type="button" onClick={() => navigate('/student/interview')}>
            Back to Interview Prep
          </button>
        </div>
      </div>
    </main>
  );
}
