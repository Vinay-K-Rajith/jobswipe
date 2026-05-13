import { useEffect, useMemo, useState } from 'react';
import {
  IconArrowUpRight,
  IconBuildingSkyscraper,
  IconFilterExclamation,
  IconHierarchy3,
  IconListSearch,
  IconScale,
  IconUserHeart,
} from '@tabler/icons-react';
import { BiasCompany, BiasReport, JobSwipeFeedReplay, getBiasReport, getJobSwipeFeedReplay } from '../services/api';

function formatPercent(value?: number | null, digits = 1) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function formatRankShift(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }
  return value > 0 ? `+${value}` : `${value}`;
}

function toneClass(value?: number, positiveWhenHigher = true) {
  if (value === undefined) return 'neutral';
  if (value === 0) return 'neutral';
  const positive = positiveWhenHigher ? value > 0 : value < 0;
  return positive ? 'positive' : 'negative';
}

function feedTitle(company?: JobSwipeFeedReplay | null) {
  if (!company) return 'JobSwipe Feed Replay';
  return `${company.company_name} ${company.role_offered ? `- ${company.role_offered}` : ''}`;
}

export default function JobSwipeFeedReplayPage() {
  const [biasReport, setBiasReport] = useState<BiasReport | null>(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState('');
  const [replay, setReplay] = useState<JobSwipeFeedReplay | null>(null);
  const [loading, setLoading] = useState(true);
  const [replayLoading, setReplayLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    getBiasReport(false)
      .then((response) => {
        if (cancelled) return;
        const sorted = [...response.data.all_companies].sort((a, b) => b.dept_disparity - a.dept_disparity);
        setBiasReport({ ...response.data, all_companies: sorted });
        setSelectedCompanyId(sorted[0]?.company_id || '');
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || 'Failed to load company fairness data.');
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedCompanyId) return;
    let cancelled = false;
    setReplayLoading(true);
    setError('');

    getJobSwipeFeedReplay(selectedCompanyId)
      .then((response) => {
        if (cancelled) return;
        setReplay(response.data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || 'Failed to load JobSwipe feed replay.');
      })
      .finally(() => {
        if (!cancelled) setReplayLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedCompanyId]);

  const selectedCompany = useMemo(
    () => biasReport?.all_companies.find((company) => company.company_id === selectedCompanyId) || biasReport?.all_companies[0],
    [biasReport, selectedCompanyId],
  );

  const headlineCards = replay ? [
    {
      label: 'Gender NDCG Gap',
      value: formatPercent(replay.headline_metrics.ndcg_fairness_gap, 2),
      detail: 'Baseline rank quality gap between male and female students.',
      icon: IconScale,
    },
    {
      label: 'Top 20 Female Count',
      value: `${replay.top20.baseline.female_count} to ${replay.top20.champion.female_count}`,
      detail: 'How many women appear in the recruiter feed after fairness intervention.',
      icon: IconUserHeart,
    },
    {
      label: 'Top 20 Non-CSE Count',
      value: `${replay.top20.baseline.non_cse_count} to ${replay.top20.champion.non_cse_count}`,
      detail: 'Non-CSE representation in the same top-20 feed.',
      icon: IconHierarchy3,
    },
    {
      label: 'Department Parity Gap',
      value: formatPercent(replay.headline_metrics.department_parity_disparity, 2),
      detail: `${replay.headline_metrics.highest_department || 'IT'} ${formatPercent(replay.headline_metrics.highest_rate)} vs ${replay.headline_metrics.lowest_department || 'CIVIL'} ${formatPercent(replay.headline_metrics.lowest_rate)}.`,
      icon: IconFilterExclamation,
    },
  ] : [];

  if (loading) {
    return <div className="loading"><div className="spinner" /> Loading feed replay...</div>;
  }

  return (
    <main className="container animate-fade feed-replay-page">
      <header className="feed-replay-hero">
        <div>
          <p className="dashboard-kicker">Admin fairness replay</p>
          <h1>{feedTitle(replay)}</h1>
          <p>
            Replay the same recruiter feed with the baseline `model.pkl` and the fairness-constrained
            `fairlearn_lightgbm_eps_0.01.pkl` model, then inspect who moves into or out of the top 20.
          </p>
        </div>
        <div className="feed-replay-selector portal-form-card">
          <label>
            Company / role
            <select className="input" value={selectedCompanyId} onChange={(event) => setSelectedCompanyId(event.target.value)}>
              {(biasReport?.all_companies || []).map((company: BiasCompany) => (
                <option key={company.company_id} value={company.company_id}>
                  {company.company_name} - dept gap {formatPercent(company.dept_disparity, 1)}
                </option>
              ))}
            </select>
          </label>
          {selectedCompany && (
            <p className="muted-text">
              Focus company: <strong>{selectedCompany.company_name}</strong> with department disparity {formatPercent(selectedCompany.dept_disparity, 1)}.
            </p>
          )}
        </div>
      </header>

      {error && <div className="bias-inline-error">{error}</div>}
      {replayLoading && <div className="loading"><div className="spinner" /> Replaying JobSwipe feed...</div>}

      {replay && (
        <>
          <section className="feed-replay-headline-grid">
            {headlineCards.map((card) => (
              <article className="bento-card feed-replay-stat-card" key={card.label}>
                <div className="bento-card-topline">
                  <span className="bento-eyebrow"><card.icon size={15} /> {card.label}</span>
                </div>
                <strong>{card.value}</strong>
                <p>{card.detail}</p>
              </article>
            ))}
          </section>

          <section className="feed-replay-story-grid">
            <article className="bento-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconBuildingSkyscraper size={15} /> What The Feed Hid Before Fairness</span>
              </div>
              <p className="feed-replay-lead">
                Baseline JobSwipe learned historical department and CGPA correlations strongly enough that lower-represented
                departments were suppressed in the recruiter feed even when their profile fit was otherwise competitive.
              </p>
              <p className="muted-text">
                The saved fairness audit shows gender parity under the 10% threshold at {formatPercent(replay.headline_metrics.gender_parity_disparity, 2)},
                while department parity fails badly at {formatPercent(replay.headline_metrics.department_parity_disparity, 2)}.
              </p>
              <p className="muted-text">
                Highest pass-rate department: <strong>{replay.headline_metrics.highest_department}</strong> at {formatPercent(replay.headline_metrics.highest_rate)}.
                Lowest: <strong>{replay.headline_metrics.lowest_department}</strong> at {formatPercent(replay.headline_metrics.lowest_rate)}.
              </p>
            </article>

            <article className="bento-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconArrowUpRight size={15} /> Fairness-adjusted rank improvement</span>
              </div>
              {!replay.representative_female_shift ? (
                <p className="muted-text">No female student was available for the selected company replay.</p>
              ) : (
                <>
                  <p className="feed-replay-lead">
                    {replay.representative_female_shift.full_name} ({replay.representative_female_shift.department}) moved from
                    baseline rank <strong>#{replay.representative_female_shift.baseline_rank}</strong> to
                    champion rank <strong>#{replay.representative_female_shift.champion_rank}</strong>.
                  </p>
                  <p className={`feed-replay-rank-shift ${toneClass(replay.representative_female_shift.rank_improvement)}`}>
                    Rank improvement {formatRankShift(replay.representative_female_shift.rank_improvement)}
                  </p>
                  <p className="muted-text">
                    This turns the abstract fairness metrics into a concrete feed outcome the admin can see without leaving the dashboard.
                  </p>
                </>
              )}
            </article>
          </section>

          <section className="feed-replay-feed-grid">
            <article className="bento-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconListSearch size={15} /> Baseline Feed</span>
                <span className="bento-pill">{replay.artifacts.baseline}</span>
              </div>
              <p className="muted-text">
                Female in top 20: <strong>{replay.top20.baseline.female_count}</strong> · Non-CSE in top 20: <strong>{replay.top20.baseline.non_cse_count}</strong>
              </p>
              <div className="feed-replay-student-list">
                {replay.top20.baseline.students.map((student) => (
                  <div className="feed-replay-student-row" key={`baseline-${student.student_id}`}>
                    <strong>#{student.rank}</strong>
                    <div>
                      <span>{student.full_name}</span>
                      <small>{student.department} · {student.gender || 'Unknown'} · CGPA {student.cgpa ?? '--'}</small>
                    </div>
                    <span className="feed-replay-score">{student.score?.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </article>

            <article className="bento-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconScale size={15} /> Champion Feed</span>
                <span className="bento-pill">{replay.artifacts.champion}</span>
              </div>
              <p className="muted-text">
                Female in top 20: <strong>{replay.top20.champion.female_count}</strong> · Non-CSE in top 20: <strong>{replay.top20.champion.non_cse_count}</strong>
              </p>
              <div className="feed-replay-student-list">
                {replay.top20.champion.students.map((student) => (
                  <div className="feed-replay-student-row" key={`champion-${student.student_id}`}>
                    <strong>#{student.rank}</strong>
                    <div>
                      <span>{student.full_name}</span>
                      <small>{student.department} · {student.gender || 'Unknown'} · CGPA {student.cgpa ?? '--'}</small>
                    </div>
                    <span className="feed-replay-score">{student.score?.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="feed-replay-summary-grid">
            <article className="bento-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconUserHeart size={15} /> Average rank improvement</span>
              </div>
              <div className="feed-replay-summary-list">
                {replay.rank_change_summary.map((item) => (
                  <div className="feed-replay-summary-row" key={item.label}>
                    <div>
                      <strong>{item.label}</strong>
                      <small>{item.count} students</small>
                    </div>
                    <span className={toneClass(item.avg_rank_improvement)}>{formatRankShift(item.avg_rank_improvement)}</span>
                  </div>
                ))}
              </div>
            </article>

            <article className="bento-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconHierarchy3 size={15} /> Department movement</span>
              </div>
              <div className="feed-replay-summary-list">
                {replay.department_rank_change.slice(0, 8).map((item) => (
                  <div className="feed-replay-summary-row" key={item.department}>
                    <div>
                      <strong>{item.department}</strong>
                      <small>{item.count} students</small>
                    </div>
                    <span className={toneClass(item.avg_rank_improvement)}>{formatRankShift(item.avg_rank_improvement)}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="feed-replay-feed-grid">
            <article className="bento-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconArrowUpRight size={15} /> Biggest upward movers</span>
              </div>
              <div className="feed-replay-student-list compact">
                {replay.top_upward_movers.map((student) => (
                  <div className="feed-replay-student-row" key={`up-${student.student_id}`}>
                    <div>
                      <span>{student.full_name}</span>
                      <small>{student.department} · {student.gender || 'Unknown'}</small>
                    </div>
                    <span className="positive">#{student.baseline_rank} to #{student.champion_rank}</span>
                  </div>
                ))}
              </div>
            </article>

            <article className="bento-card">
              <div className="bento-card-topline">
                <span className="bento-eyebrow"><IconFilterExclamation size={15} /> Biggest downward movers</span>
              </div>
              <div className="feed-replay-student-list compact">
                {replay.top_downward_movers.map((student) => (
                  <div className="feed-replay-student-row" key={`down-${student.student_id}`}>
                    <div>
                      <span>{student.full_name}</span>
                      <small>{student.department} · {student.gender || 'Unknown'}</small>
                    </div>
                    <span className="negative">#{student.baseline_rank} to #{student.champion_rank}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>
        </>
      )}
    </main>
  );
}
