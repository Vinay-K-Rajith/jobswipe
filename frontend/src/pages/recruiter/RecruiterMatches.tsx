import { useEffect, useState } from 'react';
import { MatchItem, getRecruiterMatches } from '../../services/swipeApi';

export default function RecruiterMatches() {
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [error, setError] = useState('');
  const [chatMessage, setChatMessage] = useState('');

  useEffect(() => {
    getRecruiterMatches()
      .then((response) => setMatches(response.data.matches))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load matches.'));
  }, []);

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Recruiter Portal</span>
        <h1>Mutual matches</h1>
        <p>Students who liked your role after you liked them, or vice versa.</p>
      </header>
      {error && <div className="bias-inline-error">{error}</div>}
      {chatMessage && <div className="portal-note">{chatMessage}</div>}
      <section className="portal-list">
        {matches.length === 0 ? (
          <div className="portal-empty"><h2>No matches yet</h2><p>Keep browsing students to create your first match.</p></div>
        ) : matches.map((match) => (
          <article className="portal-row" key={match.id}>
            <div>
              <strong>{match.student_name || 'Student'}</strong>
              <span>
                {match.role_title || 'Role'} / {match.department || 'Department'} / Matched {new Date(match.matched_at).toLocaleDateString()}
              </span>
            </div>
            <button className="btn btn-ghost" type="button" onClick={() => setChatMessage('Chat is coming soon for mutual matches.')}>Chat</button>
          </article>
        ))}
      </section>
    </main>
  );
}
