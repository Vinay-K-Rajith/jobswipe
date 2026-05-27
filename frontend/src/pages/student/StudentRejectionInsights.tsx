import { useEffect, useState } from 'react';
import {
  IconAlertCircle,
  IconArrowUpRight,
  IconBriefcase2,
  IconChartBar,
  IconSparkles,
  IconTargetArrow,
} from '@tabler/icons-react';
import { StudentRejectionInsight, getStudentRejectionInsights } from '../../services/swipeApi';

function formatPercent(value?: number) {
  if (value === undefined || value === null || Number.isNaN(value)) return '--';
  return `${Math.round(value * 100)}%`;
}

function severityTone(value: string) {
  if (value === 'high') return 'danger';
  if (value === 'medium') return 'warning';
  return 'neutral';
}

export default function StudentRejectionInsights() {
  const [insights, setInsights] = useState<StudentRejectionInsight[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStudentRejectionInsights()
      .then((response) => setInsights(response.data.insights))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load growth insights.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading"><div className="spinner" /> Loading growth insights...</div>;

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Student Portal</span>
        <h1>Growth insights</h1>
      </header>
      {error && <div className="bias-inline-error">{error}</div>}
      <section className="portal-list rejection-insight-list">
        {insights.length === 0 ? (
          <div className="portal-empty">
            <h2>No growth insights yet</h2>
            <p>When a recruiter shares feedback on a recommended profile, it will appear here.</p>
          </div>
        ) : insights.map((insight) => (
          <article className="bento-card rejection-insight-card" key={insight.id}>
            <div className="bento-card-topline">
              <span className="bento-eyebrow"><IconBriefcase2 size={15} /> {insight.company_name}</span>
              <span className="bento-pill">{new Date(insight.created_at).toLocaleDateString()}</span>
            </div>
            <h2>{insight.role_title}</h2>
            <p className="feed-replay-lead">{insight.headline}</p>

            <div className="rejection-meta-grid">
              <div className="criteria-cell pass">
                <b><IconChartBar size={15} /> Match snapshot</b>
                <span>
                  Score {insight.match_snapshot.overall_score?.toFixed(3) ?? '--'}
                  {typeof insight.match_snapshot.rank_position === 'number' && typeof insight.match_snapshot.pool_size === 'number'
                    ? ` / ranked #${insight.match_snapshot.rank_position} of ${insight.match_snapshot.pool_size}`
                    : ''}
                </span>
              </div>
              <div className={`criteria-cell ${severityTone(insight.competitive_weaknesses[0]?.severity || 'neutral')}`}>
                <b><IconAlertCircle size={15} /> Recruiter feedback</b>
                <span>{insight.reason_label}{insight.reason_note ? `: ${insight.reason_note}` : ''}</span>
              </div>
            </div>

            {!!insight.competitive_weaknesses.length && (
              <div className="criteria-matrix">
                {insight.competitive_weaknesses.map((weakness) => (
                  <div className={`criteria-cell ${severityTone(weakness.severity)}`} key={`${insight.id}-${weakness.label}`}>
                    <b>{weakness.label}</b>
                    <span>{weakness.detail}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="rejection-detail-grid">
              <article className="action-card">
                <b><IconTargetArrow size={15} /> Peer comparison</b>
                <p>
                  Top candidates averaged CGPA {insight.peer_comparison.top_band_avg_cgpa ?? '--'} vs your {insight.peer_comparison.student_cgpa ?? '--'}.
                  Internship months: {insight.peer_comparison.top_band_avg_internship_months ?? '--'} vs {insight.peer_comparison.student_internship_months ?? '--'}.
                </p>
                <span>
                  Required skills match {formatPercent(insight.criteria_snapshot.required_skill_match_ratio)} / Preferred skills match {formatPercent(insight.criteria_snapshot.preferred_skill_match_ratio)}
                </span>
              </article>

              <article className="action-card">
                <b><IconSparkles size={15} /> Skill gap focus</b>
                {insight.skill_gap_focus.length === 0 ? (
                  <p>No missing skill callouts were captured for this role.</p>
                ) : (
                  insight.skill_gap_focus.map((item) => (
                    <p key={`${insight.id}-${item.skill}`}>
                      <strong>{item.skill}</strong> {item.reason}
                    </p>
                  ))
                )}
              </article>
            </div>

            {!!insight.improvement_plan.length && (
              <div className="action-stack">
                {insight.improvement_plan.map((step) => (
                  <div className="action-card" key={`${insight.id}-${step.priority}-${step.title}`}>
                    <b><IconArrowUpRight size={15} /> {step.title}</b>
                    <p>{step.description}</p>
                    <span>{step.timeline} / {step.difficulty}</span>
                  </div>
                ))}
              </div>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}
