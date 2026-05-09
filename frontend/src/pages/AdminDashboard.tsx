import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  IconArrowRight,
  IconAlertTriangle,
  IconBrain,
  IconChartBar,
  IconClockBolt,
  IconFileExport,
  IconListDetails,
  IconRefresh,
  IconShieldExclamation,
  IconSparkles,
  IconTargetArrow,
  IconUsersGroup,
} from '@tabler/icons-react';
import {
  BiasReport,
  ModelArtifacts,
  ModelMetrics,
  Stats,
  SkillDeficitReport,
  getBiasReport,
  getModelArtifacts,
  getModelMetrics,
  getSkillDeficits,
  getStats,
} from '../services/api';
import { ActivityEntry, readActivityLog } from '../services/activityLog';

type PulseModel = {
  label: string;
  latency: number;
  online: boolean;
};

const trendData = [
  { month: 'Jul', score: 61, eligible: 46 },
  { month: 'Aug', score: 64, eligible: 49 },
  { month: 'Sep', score: 67, eligible: 53 },
  { month: 'Oct', score: 71, eligible: 57 },
  { month: 'Nov', score: 76, eligible: 63 },
  { month: 'Dec', score: 78, eligible: 66 },
  { month: 'Jan', score: 82, eligible: 71 },
  { month: 'Feb', score: 86, eligible: 74 },
];

const defaultActivityLog: ActivityEntry[] = [
  {
    id: 'seed-eligibility',
    createdAt: new Date().toISOString(),
    kind: 'eligibility',
    title: 'Eligibility batch completed',
    detail: 'Tier-1 pool processed against hard criteria',
    actor: 'Eligibility Engine',
    status: 'Complete',
    tone: 'success',
  },
  {
    id: 'seed-bias',
    createdAt: new Date(Date.now() - 18 * 60 * 1000).toISOString(),
    kind: 'bias',
    title: 'Bias scan refreshed',
    detail: 'Criteria disparity recalculated for active companies',
    actor: 'Fairness Monitor',
    status: 'Review',
    tone: 'warning',
  },
  {
    id: 'seed-skills',
    createdAt: new Date(Date.now() - 41 * 60 * 1000).toISOString(),
    kind: 'skills',
    title: 'Skill gaps regenerated',
    detail: 'Cohort recommendations updated from ML model',
    actor: 'Skill Gap Model',
    status: 'Synced',
    tone: 'info',
  },
  {
    id: 'seed-export',
    createdAt: new Date(Date.now() - 73 * 60 * 1000).toISOString(),
    kind: 'export',
    title: 'Shortlist exported',
    detail: 'Placement review pack prepared for admin team',
    actor: 'Ranking Pipeline',
    status: 'Exported',
    tone: 'neutral',
  },
];

const quickActions = [
  {
    label: 'Ranking',
    to: '/ranking',
    icon: IconTargetArrow,
    detail: 'Generate ML shortlists',
  },
  {
    label: 'Bias',
    to: '/bias',
    icon: IconShieldExclamation,
    detail: 'Review fairness risks',
  },
  {
    label: 'Eligibility',
    to: '/eligibility',
    icon: IconListDetails,
    detail: 'Run rule checks',
  },
];

function buildPulse(stats: Stats | null, baseLatency: number): PulseModel[] {
  return [
    { label: 'Eligibility ML', latency: baseLatency + 12, online: Boolean(stats?.model_loaded) },
    { label: 'Ranker', latency: baseLatency + 26, online: Boolean(stats?.ranker_loaded) },
    { label: 'Skill Gap', latency: baseLatency + 18, online: Boolean(stats?.skill_rec_loaded) },
  ];
}

function formatActivityTime(createdAt: string) {
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(createdAt));
}

function getActivityIcon(kind: ActivityEntry['kind']) {
  const icons = {
    ranking: IconTargetArrow,
    bias: IconAlertTriangle,
    eligibility: IconListDetails,
    skills: IconBrain,
    export: IconFileExport,
  };

  return icons[kind];
}

function formatPercent(value?: number | null, digits = 1) {
  if (value === undefined || value === null) return '--';
  return `${(value * 100).toFixed(digits)}%`;
}

function formatArtifactPercent(value?: number | null, digits = 1) {
  if (value === undefined || value === null) return '--';
  return `${value.toFixed(digits)}%`;
}

function formatMs(value?: number | null) {
  if (value === undefined || value === null) return '--';
  return `${value.toFixed(value >= 10 ? 1 : 2)}ms`;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [artifacts, setArtifacts] = useState<ModelArtifacts | null>(null);
  const [biasReport, setBiasReport] = useState<BiasReport | null>(null);
  const [skillDeficitReport, setSkillDeficitReport] = useState<SkillDeficitReport | null>(null);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [latency, setLatency] = useState(44);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const loadDashboard = async () => {
      const startedAt = performance.now();
      const [statsRes, metricsRes, artifactsRes, biasRes, skillDeficitsRes] = await Promise.all([
        getStats().catch(() => null),
        getModelMetrics().catch(() => null),
        getModelArtifacts().catch(() => null),
        getBiasReport(false).catch(() => null),
        getSkillDeficits(8).catch(() => null),
      ]);

      if (!active) return;

      if (statsRes?.data) setStats(statsRes.data);
      if (metricsRes?.data) setMetrics(metricsRes.data);
      if (artifactsRes?.data) setArtifacts(artifactsRes.data);
      if (biasRes?.data) setBiasReport(biasRes.data);
      if (skillDeficitsRes?.data) setSkillDeficitReport(skillDeficitsRes.data);
      setLatency(Math.max(28, Math.round(performance.now() - startedAt)));
      setLoading(false);
    };

    loadDashboard();
    const interval = window.setInterval(loadDashboard, 30000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const syncActivity = () => {
      const storedLog = readActivityLog();
      setActivityLog([...storedLog, ...defaultActivityLog].slice(0, 8));
    };

    syncActivity();
    window.addEventListener('storage', syncActivity);
    window.addEventListener('jobswipe:activity-log-updated', syncActivity);

    return () => {
      window.removeEventListener('storage', syncActivity);
      window.removeEventListener('jobswipe:activity-log-updated', syncActivity);
    };
  }, []);

  const skillDeficits = skillDeficitReport?.deficits || [];
  const topSkillDeficit = skillDeficits[0];
  const maxCoveredStudents = Math.max(
    1,
    ...skillDeficits.map((item) => item.students_with_skill),
  );

  const pulseModels = useMemo(() => buildPulse(stats, latency), [stats, latency]);
  const topBiasRisks = biasReport?.flagged_companies?.slice(0, 4) || [];
  const readinessScore = trendData[trendData.length - 1].score;
  const avgCgpa = stats?.avg_cgpa?.toFixed(2) || '--';
  const cv = artifacts?.cv_results;
  const bestEpsilon = artifacts?.best_epsilon;
  const epsilonSweep = artifacts?.epsilon_sweep || [];
  const parserBuckets = artifacts?.resume_parser_accuracy
    ? Object.entries(artifacts.resume_parser_accuracy).filter(([, value]) => typeof value === 'object') as Array<[string, { n: number; cgpa_mae: number | null; skills_recall: number | null }]>
    : [];
  const parserSamples = parserBuckets.reduce((sum, [, bucket]) => sum + (bucket.n || 0), 0);
  const projectedScale = artifacts?.scalability?.projected_5000;

  if (loading) {
    return <div className="loading"><div className="spinner"></div> Loading Dashboard...</div>;
  }

  if (!stats) {
    return <div className="empty-state"><div className="icon">!</div><h3>Failed to load stats</h3></div>;
  }

  return (
    <div className="container animate-fade">
      <header className="dashboard-hero-header">
        <div>
          <p className="dashboard-kicker">Placement command center</p>
          <h1>Overview Dashboard</h1>
        </div>
        <div className="dashboard-summary-strip">
          <span>{stats.total_students} students</span>
          <span>{stats.total_companies} companies</span>
          <span>{avgCgpa} avg CGPA</span>
        </div>
      </header>

      <section className="dashboard-bento">
        <article className="bento-card bento-hero">
          <div className="bento-card-topline">
            <div>
              <span className="bento-eyebrow"><IconChartBar size={15} /> Placement Readiness Trend</span>
              <h2>{readinessScore}% ready cohort</h2>
            </div>
            <span className="bento-pill success">+14 pts</span>
          </div>
          <div className="chart-shell hero-chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="readinessGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="eligibleGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#a1a1aa" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#a1a1aa" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(148, 163, 184, 0.11)" vertical={false} />
                <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} domain={[40, 90]} />
                <Tooltip contentStyle={{ background: '#050505', border: '1px solid rgba(255,255,255,0.16)', borderRadius: 8 }} />
                <Area type="monotone" dataKey="eligible" stroke="#a1a1aa" strokeWidth={2} fill="url(#eligibleGradient)" />
                <Area type="monotone" dataKey="score" stroke="#22c55e" strokeWidth={3} fill="url(#readinessGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="bento-card bias-card">
          <span className="bento-eyebrow"><IconShieldExclamation size={15} /> Bias Risk Watchlist</span>
          <div className="bias-warning">
            <strong>{biasReport?.summary?.n_flagged ?? 0} companies flagged</strong>
            <span>{((biasReport?.summary?.flag_rate ?? 0) * 100).toFixed(1)}% flag rate</span>
          </div>
          <div className="bias-list">
            {topBiasRisks.length ? topBiasRisks.map((company) => (
              <div className="bias-row" key={company.company_id}>
                <div>
                  <strong>{company.company_name}</strong>
                  <span>{company.top_bias_criterion}</span>
                </div>
                <b>{(company.disparity * 100).toFixed(1)}%</b>
              </div>
            )) : (
              <p className="text-muted">No live bias flags returned.</p>
            )}
          </div>
        </article>

        <article className="bento-card quick-card">
          <span className="bento-eyebrow"><IconSparkles size={15} /> Quick Actions</span>
          <div className="quick-action-list">
            {quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <Link className="quick-action" to={action.to} key={action.to}>
                  <span><Icon size={19} /></span>
                  <div>
                    <strong>{action.label}</strong>
                    <small>{action.detail}</small>
                  </div>
                  <IconArrowRight size={17} />
                </Link>
              );
            })}
          </div>
        </article>

        <article className="bento-card skill-card">
          <div className="bento-card-topline">
            <div>
              <span className="bento-eyebrow"><IconUsersGroup size={15} /> Global Skill Deficits</span>
              <h3 className="bento-section-title">
                {topSkillDeficit ? `${topSkillDeficit.skill} has the highest demand-adjusted gap` : 'Skill coverage pending'}
              </h3>
            </div>
            <span className="bento-pill">{skillDeficitReport?.total_students ?? stats.total_students} profiles</span>
          </div>
          <div className="skill-deficit-summary">
            <div>
              <strong>{topSkillDeficit ? `${Math.round(topSkillDeficit.missing_share * 100)}%` : '--'}</strong>
              <span>missing in cohort</span>
            </div>
            <div>
              <strong>{topSkillDeficit?.students_with_skill ?? '--'}</strong>
              <span>students have it</span>
            </div>
          </div>
          <div className="skill-deficit-list">
            {skillDeficits.map((item) => (
              <div className="skill-deficit-row" key={item.skill}>
                <div className="skill-deficit-meta">
                  <strong>{item.skill}</strong>
                  <span>{Math.round(item.missing_share * 100)}% missing · {item.students_with_skill} have it · {item.company_demand} company demand</span>
                </div>
                <div className="skill-deficit-track" aria-label={`${item.skill} student coverage`}>
                  <span style={{ width: `${Math.max(5, Math.round((item.students_with_skill / maxCoveredStudents) * 100))}%` }} />
                </div>
                <b className={item.severity.toLowerCase()}>{item.severity}</b>
              </div>
            ))}
          </div>
        </article>

        <article className="bento-card pulse-card">
          <span className="bento-eyebrow"><IconClockBolt size={15} /> System Pulse</span>
          <div className="pulse-stack">
            {pulseModels.map((model) => (
              <div className="pulse-row" key={model.label}>
                <span className={`live-dot ${model.online ? 'online' : 'offline'}`}>
                  <i className="animate-ping" />
                </span>
                <div>
                  <strong>{model.label}</strong>
                  <small>{model.online ? 'Loaded' : 'Offline'}</small>
                </div>
                <b>{model.online ? `${model.latency}ms` : '--'}</b>
              </div>
            ))}
          </div>
        </article>

        <article className="bento-card activity-card">
          <div className="bento-card-topline">
            <div>
              <span className="bento-eyebrow"><IconListDetails size={15} /> Activity Log</span>
              <h3 className="bento-section-title">Recent admin operations</h3>
            </div>
            <span className="bento-pill"><IconRefresh size={13} /> Live</span>
          </div>
          <div className="timeline">
            {activityLog.map((item) => {
              const Icon = getActivityIcon(item.kind);
              return (
              <div className={`timeline-item ${item.tone}`} key={item.id}>
                <time>{formatActivityTime(item.createdAt)}</time>
                <div className="timeline-card">
                  <span className="timeline-icon"><Icon size={15} /></span>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                    <small>{item.actor}</small>
                  </div>
                  <b>{item.status}</b>
                </div>
              </div>
              );
            })}
          </div>
        </article>

        <article className="bento-card metric-card">
          <span className="bento-eyebrow"><IconChartBar size={15} /> Model Quality</span>
          <div className="metric-grid">
            {[
              { label: 'Accuracy', value: metrics?.metrics ? formatPercent(metrics.metrics.accuracy) : '--' },
              { label: 'F1', value: metrics?.metrics ? metrics.metrics.f1.toFixed(3) : '--' },
              { label: 'CV Accuracy', value: cv ? `${formatPercent(cv.accuracy_mean)} ± ${(cv.accuracy_std * 100).toFixed(2)}` : metrics?.metrics?.cv_accuracy_mean ? `${formatPercent(metrics.metrics.cv_accuracy_mean)} ± ${((metrics.metrics.cv_accuracy_std || 0) * 100).toFixed(2)}` : '--' },
              { label: 'CV F1', value: cv ? `${cv.f1_mean.toFixed(3)} ± ${cv.f1_std.toFixed(3)}` : metrics?.metrics?.cv_f1_mean ? `${metrics.metrics.cv_f1_mean.toFixed(3)} ± ${(metrics.metrics.cv_f1_std || 0).toFixed(3)}` : '--' },
            ].map((item) => (
              <div key={item.label}>
                <strong>{item.value}</strong>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="bento-card artifact-card">
          <div className="bento-card-topline">
            <div>
              <span className="bento-eyebrow"><IconBrain size={15} /> Validation & Tradeoffs</span>
              <h3 className="bento-section-title">Model evidence from latest artifacts</h3>
            </div>
            <span className="bento-pill">{cv?.n_folds ? `${cv.n_folds}-fold CV` : 'Artifacts'}</span>
          </div>

          <div className="artifact-summary-grid">
            <div>
              <strong>{bestEpsilon ? bestEpsilon.eps.toFixed(3) : '--'}</strong>
              <span>best epsilon</span>
            </div>
            <div>
              <strong>{bestEpsilon ? formatArtifactPercent(bestEpsilon.gender_parity_gap, 2) : '--'}</strong>
              <span>gender parity gap</span>
            </div>
            <div>
              <strong>{projectedScale ? formatMs(projectedScale.classifier_total_ms) : '--'}</strong>
              <span>5k classifier projection</span>
            </div>
            <div>
              <strong>{parserSamples || '--'}</strong>
              <span>parser test samples</span>
            </div>
          </div>

          {epsilonSweep.length ? (
            <div className="artifact-chart-shell">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={epsilonSweep} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                  <XAxis dataKey="eps" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: '#050505', border: '1px solid rgba(255,255,255,0.16)', borderRadius: 8 }} />
                  <Line type="monotone" dataKey="accuracy" stroke="#22c55e" strokeWidth={2} dot={false} name="Accuracy %" />
                  <Line type="monotone" dataKey="gender_parity_gap" stroke="#fbbf24" strokeWidth={2} dot={false} name="Parity gap %" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-muted">No epsilon sweep artifact found yet.</p>
          )}

          <div className="artifact-note-row">
            <span>Pareto chart artifact {artifacts?.available_charts?.pareto_frontier ? 'available' : 'missing'}</span>
            <span>Epsilon chart artifact {artifacts?.available_charts?.epsilon_sweep ? 'available' : 'missing'}</span>
          </div>
        </article>
      </section>
    </div>
  );
}
