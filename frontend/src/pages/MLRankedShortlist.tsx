import { useEffect, useMemo, useState } from 'react';
import {
  IconBolt,
  IconBuilding,
  IconChartDots,
  IconFileExport,
  IconListCheck,
  IconTargetArrow,
  IconTrophy,
} from '@tabler/icons-react';
import { getCompanies, getRankedShortlist, Company, RankedShortlist } from '../services/api';
import { recordActivity } from '../services/activityLog';

const rankerMetric = 'NDCG@10 CV = 0.985';

export default function MLRankedShortlist() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState('');
  const [shortlist, setShortlist] = useState<RankedShortlist | null>(null);
  const [mlLoading, setMlLoading] = useState(false);

  useEffect(() => {
    getCompanies({}).then((res) => setCompanies(res.data.companies)).catch(() => null);
  }, []);

  const activeCompany = useMemo(
    () => companies.find((company) => company.company_id === selectedCompany) || null,
    [companies, selectedCompany],
  );

  const topThree = shortlist?.shortlist.slice(0, 3) || [];
  const remaining = shortlist?.shortlist.slice(3) || [];

  const runRanking = async () => {
    if (!selectedCompany) return;
    setMlLoading(true);
    try {
      const res = await getRankedShortlist(selectedCompany, 20);
      setShortlist(res.data);
      recordActivity({
        kind: 'ranking',
        tone: 'success',
        title: 'ML shortlist generated',
        detail: `${res.data.company_name} ranked ${res.data.total_students} students; top ${res.data.top_k} shown`,
        actor: 'Ranking Pipeline',
        status: 'Generated',
      });
    } catch {
      alert('Ranker not loaded or company not found.');
    } finally {
      setMlLoading(false);
    }
  };

  return (
    <div className="container animate-fade">
      <header className="workspace-header">
        <div>
          <p className="dashboard-kicker">Ranking cockpit</p>
          <h1>ML Ranked Shortlist</h1>
          <p>XGBoost learning-to-rank scores candidates by placement fitness.</p>
        </div>
        <div className="workspace-header-actions">
          <span>{rankerMetric}</span>
          <span>GroupKFold · 50 companies</span>
        </div>
      </header>

      <section className="ranking-layout">
        <aside className="bento-card ranking-control">
          <span className="bento-eyebrow"><IconBuilding size={15} /> Company Target</span>
          <select className="input ranking-select" value={selectedCompany} onChange={(e) => setSelectedCompany(e.target.value)}>
            <option value="">Choose company</option>
            {companies.map((company) => (
              <option key={company.company_id} value={company.company_id}>
                {company.company_name} ({company.tier})
              </option>
            ))}
          </select>

          {activeCompany ? (
            <div className="company-brief">
              <h2>{activeCompany.company_name}</h2>
              <span className="badge badge-info">{activeCompany.tier}</span>
              <div className="brief-grid">
                <div><span>Role</span><strong>{activeCompany.role_offered}</strong></div>
                <div><span>Package</span><strong>{activeCompany.package_lpa.toFixed(1)} LPA</strong></div>
                <div><span>Min CGPA</span><strong>{activeCompany.min_cgpa.toFixed(1)}</strong></div>
                <div><span>Backlogs</span><strong>{activeCompany.max_active_backlogs}</strong></div>
              </div>
              <div className="criteria-chip-cloud">
                {activeCompany.allowed_departments.split(',').map((dept) => <span key={dept}>{dept}</span>)}
              </div>
              <div className="criteria-chip-cloud muted">
                {activeCompany.required_skills.split(',').filter(Boolean).map((skill) => <span key={skill}>{skill}</span>)}
              </div>
            </div>
          ) : (
            <div className="empty-panel">Select a company to inspect criteria.</div>
          )}

          <button className="btn btn-primary btn-lg ranking-run" onClick={runRanking} disabled={mlLoading || !selectedCompany}>
            <IconBolt size={18} />
            {mlLoading ? 'Running ranker...' : 'Generate Shortlist'}
          </button>
        </aside>

        <main className="ranking-main">
          {!shortlist ? (
            <div className="bento-card ranking-empty">
              <IconTargetArrow size={42} />
              <h2>No shortlist generated</h2>
              <p>Select a company to score all 800 students and build a ranked placement shortlist.</p>
            </div>
          ) : (
            <>
              <section className="bento-card ranking-summary">
                <div className="bento-card-topline">
                  <div>
                    <span className="bento-eyebrow"><IconChartDots size={15} /> Generated Shortlist</span>
                    <h2>{shortlist.company_name}</h2>
                  </div>
                  <div className="workspace-header-actions">
                    <span>{shortlist.total_students} scored</span>
                    <span>Top {shortlist.top_k}</span>
                  </div>
                </div>
                <button className="btn btn-ghost btn-sm"><IconFileExport size={16} /> Export</button>
              </section>

              <section className="podium-grid">
                {topThree.map((student, index) => (
                  <article className={`podium-card rank-${index + 1}`} key={student.student_id}>
                    <div className="podium-rank"><IconTrophy size={17} /> #{student.rank}</div>
                    <h3>{student.full_name}</h3>
                    <p>{student.student_id} · {student.department}</p>
                    <div className="podium-metrics">
                      <span>CGPA <b>{student.cgpa.toFixed(2)}</b></span>
                      <span>Score <b>{student.rank_score.toFixed(3)}</b></span>
                    </div>
                    <span className={`badge ${student.dept_eligible ? 'badge-success' : 'badge-danger'}`}>
                      {student.dept_eligible ? 'Dept eligible' : 'Dept blocked'}
                    </span>
                  </article>
                ))}
              </section>

              <section className="bento-card">
                <div className="bento-card-topline">
                  <span className="bento-eyebrow"><IconListCheck size={15} /> Candidate Board</span>
                  <span className="bento-pill">rank score descending</span>
                </div>
                <div className="candidate-list">
                  {remaining.map((student) => (
                    <div className="candidate-row" key={student.student_id}>
                      <strong>#{student.rank}</strong>
                      <div>
                        <b>{student.full_name}</b>
                        <span>{student.student_id} · {student.department} · CGPA {student.cgpa.toFixed(2)}</span>
                      </div>
                      <div className="score-track">
                        <span style={{ width: `${Math.min(100, Math.max(8, student.rank_score * 18))}%` }} />
                      </div>
                      <em>{student.rank_score.toFixed(3)}</em>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}
        </main>
      </section>
    </div>
  );
}
