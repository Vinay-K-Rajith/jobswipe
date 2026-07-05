import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { IconArrowRight, IconBulb, IconChartBar, IconSparkles } from '@tabler/icons-react';
import { Feedback, getFeedback, rateSession } from '../../services/interviewApi';

function prettyCompetency(s?: string) {
  if (!s) return '';
  const t = s.replace(/_/g, ' ').trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export default function InterviewFeedback() {
  const { sessionId = '' } = useParams();
  const navigate = useNavigate();
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(0);
  const [rated, setRated] = useState<string | null>(null);

  useEffect(() => {
    getFeedback(sessionId)
      .then((r) => setFeedback(r.data))
      .catch((err) => setError(err?.response?.data?.detail || 'Feedback is not available.'))
      .finally(() => setLoading(false));
  }, [sessionId]);

  const handleRate = (rating: 'better' | 'same' | 'harder') => {
    setRated(rating);
    rateSession(sessionId, rating).catch(() => {});
  };

  if (loading) return <main className="portal-page"><div className="iv-wrap"><div className="iv-card"><div className="iv-typing"><span /><span /><span /></div></div></div></main>;
  if (error || !feedback) return <main className="portal-page"><div className="iv-wrap"><div className="bias-inline-error">{error || 'No feedback.'}</div></div></main>;

  const pq = feedback.per_question_feedback;
  const fillerNums = pq.map((q) => q.filler_word_count).filter((n): n is number => typeof n === 'number');
  const wordNums = pq.map((q) => q.answer_word_count).filter((n): n is number => typeof n === 'number');
  const totalFiller = fillerNums.reduce((a, b) => a + b, 0);
  const avgWords = wordNums.length ? Math.round(wordNums.reduce((a, b) => a + b, 0) / wordNums.length) : 0;
  const heroText = feedback.headline_takeaway || feedback.overall_summary;
  const summaryText = feedback.headline_takeaway ? feedback.overall_summary : '';

  return (
    <main className="portal-page">
      <div className="iv-wrap">
        <header className="iv-hero">
          <span className="iv-hero__eyebrow"><IconSparkles size={14} /> Mock Interview</span>
          <h1 className="iv-hero__title">Your feedback</h1>
          <p className="iv-hero__sub">Specific, transcript-grounded notes from your mock interview.</p>
        </header>

        <section className="iv-bento">
          <article className="iv-tile iv-tile--hero iv-tile--accent">
            <span className="iv-tile__label"><IconBulb size={15} /> Headline takeaway</span>
            <p className="iv-tile__headline">{heroText}</p>
            {summaryText && <p className="iv-tile__summary">{summaryText}</p>}
          </article>

          <article className="iv-tile iv-tile--side">
            <span className="iv-tile__label"><IconChartBar size={15} /> At a glance</span>
            <div className="iv-statlist">
              <div className="iv-statline"><b>{pq.length}</b><span>Questions</span></div>
              <div className="iv-statline"><b>{totalFiller}</b><span>Filler words</span></div>
              <div className="iv-statline"><b>{avgWords}</b><span>Avg words / answer</span></div>
            </div>
          </article>

          <article className="iv-tile iv-tile--side">
            <span className="iv-tile__label"><IconArrowRight size={15} /> Next session</span>
            <p className="iv-tile__body">{feedback.next_session_suggestion || 'Run another session to keep building on this.'}</p>
          </article>
        </section>

        <div>
          <div className="iv-section-title">Question by question</div>
          {feedback.per_question_feedback.length === 0 ? (
            <div className="iv-card iv-empty"><p>No per-question feedback available.</p></div>
          ) : (
            <div className="iv-acc">
              {feedback.per_question_feedback.map((q, i) => (
                <div className="iv-acc__item" key={i}>
                  <button type="button" className="iv-acc__head" onClick={() => setExpanded(expanded === i ? null : i)}>
                    <b>
                      <span style={{ color: 'var(--text-muted)', fontWeight: 500, marginRight: 10 }}>{String(i + 1).padStart(2, '0')}</span>
                      {prettyCompetency(q.competency) || `Question ${i + 1}`}
                    </b>
                    <span className="iv-acc__chev">{expanded === i ? '−' : '+'}</span>
                  </button>
                  {expanded === i && (
                    <div className="iv-acc__body">
                      <p className="iv-q">{q.question}</p>
                      {q.what_happened && <div className="iv-block"><span>What happened</span><p>{q.what_happened}</p></div>}
                      {q.what_worked && <div className="iv-block iv-block--good"><span>What worked</span><p>{q.what_worked}</p></div>}
                      {q.what_was_missing && <div className="iv-block iv-block--bad"><span>What was missing</span><p>{q.what_was_missing}</p></div>}
                      {q.reconstructed_answer && <div className="iv-block iv-block--fix"><span>A stronger version of your answer</span><p>{q.reconstructed_answer}</p></div>}
                      {(typeof q.filler_word_count === 'number' || typeof q.answer_word_count === 'number') && (
                        <div className="iv-metrics">
                          {typeof q.filler_word_count === 'number' && <span className="iv-metric">Filler words: {q.filler_word_count}</span>}
                          {typeof q.answer_word_count === 'number' && <span className="iv-metric">{q.answer_word_count} words</span>}
                          {q.answer_too_long && <span className="iv-metric" style={{ color: '#fbbf24' }}>Too long</span>}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {feedback.recurring_patterns.length > 0 && (
          <div>
            <div className="iv-section-title">Patterns across this session</div>
            <div className="iv-card">
              <ul className="iv-list">{feedback.recurring_patterns.map((p, i) => <li key={i}>{p}</li>)}</ul>
            </div>
          </div>
        )}

        <div className="iv-card iv-stack">
          <strong style={{ color: '#fff' }}>How did that feel?</strong>
          <div className="iv-rate">
            {(['better', 'same', 'harder'] as const).map((r) => (
              <button key={r} type="button" className={rated === r ? 'active' : ''} onClick={() => handleRate(r)}>
                {r === 'better' ? 'Better' : r === 'same' ? 'About the same' : 'Harder than expected'}
              </button>
            ))}
          </div>
          <div>
            <button className="iv-btn" type="button" onClick={() => navigate('/student/interview')}>Start another session</button>
          </div>
        </div>
      </div>
    </main>
  );
}
