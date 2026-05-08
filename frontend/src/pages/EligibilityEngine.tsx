import { useEffect, useMemo, useState } from 'react';
import {
  IconChecklist,
  IconCircleCheck,
  IconCircleX,
  IconLoader2,
  IconSparkles,
  IconUserScan,
} from '@tabler/icons-react';
import {
  getCompanies,
  getStudents,
  checkEligibility,
  batchCheckEligibility,
  getSkillGap,
  Company,
  Student,
  BatchResult,
  EligibilityResult,
  SkillGapResult,
} from '../services/api';

export default function EligibilityEngine() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedCompany, setSelectedCompany] = useState('');
  const [selectedStudent, setSelectedStudent] = useState('');
  const [mode, setMode] = useState<'single' | 'batch'>('single');
  const [checking, setChecking] = useState(false);
  const [singleResult, setSingleResult] = useState<EligibilityResult | null>(null);
  const [batchResults, setBatchResults] = useState<{
    company_name: string;
    total: number;
    eligible: number;
    results: BatchResult[];
  } | null>(null);
  const [skillGap, setSkillGap] = useState<SkillGapResult | null>(null);

  useEffect(() => {
    getCompanies({}).then((res) => setCompanies(res.data.companies));
    getStudents({ limit: 100 }).then((res) => setStudents(res.data.students));
  }, []);

  const company = useMemo(
    () => companies.find((item) => item.company_id === selectedCompany) || null,
    [companies, selectedCompany],
  );
  const student = useMemo(
    () => students.find((item) => item.student_id === selectedStudent) || null,
    [students, selectedStudent],
  );
  const scorecardItems = Object.entries(singleResult?.scorecard || {}).filter(([key]) => key !== '_summary');
  const hardFailures = scorecardItems.filter(([, value]) => !value.passed && value.is_hard).length;
  const softWarnings = scorecardItems.filter(([, value]) => !value.passed && !value.is_hard).length;
  const rulePass = Boolean(singleResult?.criteria_eligible);
  const mlPass = singleResult?.ml_result?.eligible ?? null;
  const finalEligible = singleResult ? (mlPass === null ? rulePass : rulePass && mlPass) : false;

  const runCheck = async () => {
    if (!selectedCompany) return;

    setChecking(true);
    setSingleResult(null);
    setBatchResults(null);
    setSkillGap(null);

    try {
      if (mode === 'single' && selectedStudent) {
        const [eligRes, skillRes] = await Promise.all([
          checkEligibility(selectedStudent, selectedCompany),
          getSkillGap(selectedStudent, 5).catch(() => null),
        ]);
        setSingleResult(eligRes.data);
        if (skillRes) setSkillGap(skillRes.data);
      } else if (mode === 'batch') {
        const res = await batchCheckEligibility(selectedCompany);
        setBatchResults({
          company_name: res.data.company_name,
          total: res.data.total_checked,
          eligible: res.data.eligible_count,
          results: res.data.results,
        });
      }
    } catch (err) {
      console.error(err);
      alert('Assessment failed. Ensure both Student and Company exist in DB.');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="container animate-fade">
      <header className="workspace-header">
        <div>
          <p className="dashboard-kicker">Decision simulator</p>
          <h1>Assessment Engine</h1>
          <p>Run rule checks, ML scoring, blocker diagnosis, and skill recommendations.</p>
        </div>
        <div className="workspace-header-actions">
          <span>{companies.length} companies</span>
          <span>{students.length} sampled students</span>
        </div>
      </header>

      <section className="eligibility-layout">
        <aside className="bento-card eligibility-control">
          <span className="bento-eyebrow"><IconUserScan size={15} /> Assessment Setup</span>
          <div className="segmented-control">
            <button className={mode === 'single' ? 'active' : ''} onClick={() => setMode('single')}>Single</button>
            <button className={mode === 'batch' ? 'active' : ''} onClick={() => setMode('batch')}>Batch</button>
          </div>

          <label>Company role</label>
          <select className="input" value={selectedCompany} onChange={(e) => setSelectedCompany(e.target.value)}>
            <option value="">Choose company</option>
            {companies.map((item) => (
              <option key={item.company_id} value={item.company_id}>
                {item.company_name} - {item.role_offered}
              </option>
            ))}
          </select>

          {mode === 'single' && (
            <>
              <label>Student profile</label>
              <select className="input" value={selectedStudent} onChange={(e) => setSelectedStudent(e.target.value)}>
                <option value="">Choose student</option>
                {students.map((item) => (
                  <option key={item.student_id} value={item.student_id}>
                    {item.full_name} ({item.department}) - CGPA {item.cgpa}
                  </option>
                ))}
              </select>
            </>
          )}

          {company && (
            <div className="company-brief compact">
              <h2>{company.company_name}</h2>
              <div className="brief-grid">
                <div><span>Min CGPA</span><strong>{company.min_cgpa.toFixed(1)}</strong></div>
                <div><span>Package</span><strong>{company.package_lpa.toFixed(1)} LPA</strong></div>
              </div>
              <div className="criteria-chip-cloud muted">
                {company.required_skills.split(',').filter(Boolean).slice(0, 5).map((skill) => <span key={skill}>{skill}</span>)}
              </div>
            </div>
          )}

          {student && (
            <div className="student-mini-card">
              <strong>{student.full_name}</strong>
              <span>{student.student_id} · {student.department}</span>
              <b>CGPA {student.cgpa.toFixed(2)}</b>
            </div>
          )}

          <button
            className="btn btn-primary btn-lg ranking-run"
            onClick={runCheck}
            disabled={checking || !selectedCompany || (mode === 'single' && !selectedStudent)}
          >
            {checking ? <IconLoader2 size={18} /> : <IconChecklist size={18} />}
            {checking ? 'Running assessment...' : mode === 'single' ? 'Run Assessment' : 'Run Batch Pipeline'}
          </button>
        </aside>

        <main className="eligibility-main">
          {checking && (
            <div className="bento-card ranking-empty">
              <div className="spinner"></div>
              <h2>Executing assessment</h2>
              <p>Applying hard criteria, ML scoring, and recommendation analysis.</p>
            </div>
          )}

          {!checking && !singleResult && !batchResults && (
            <div className="bento-card ranking-empty">
              <IconChecklist size={42} />
              <h2>Ready to assess</h2>
              <p>Choose a company and run a single-student diagnosis or full batch cohort scan.</p>
            </div>
          )}

          {!checking && singleResult && (
            <>
              <section className={`bento-card verdict-card ${finalEligible ? 'pass' : 'fail'}`}>
                <div>
                  <span className="bento-eyebrow">{finalEligible ? <IconCircleCheck size={15} /> : <IconCircleX size={15} />} Final Verdict</span>
                  <h2>{finalEligible ? 'Eligible candidate' : 'Not eligible yet'}</h2>
                  <p>{singleResult.ml_result?.message || singleResult.explanation || 'Criteria checks completed.'}</p>
                </div>
                <div className="verdict-metrics">
                  <div><span>Rule engine</span><strong>{rulePass ? 'Passed' : 'Failed'}</strong></div>
                  <div><span>ML score</span><strong>{singleResult.ml_result ? singleResult.ml_result.score.toFixed(3) : 'N/A'}</strong></div>
                  <div><span>Hard blockers</span><strong>{hardFailures}</strong></div>
                  <div><span>Soft warnings</span><strong>{softWarnings}</strong></div>
                </div>
              </section>

              <section className="eligibility-result-grid">
                <article className="bento-card">
                  <span className="bento-eyebrow"><IconChecklist size={15} /> Criteria Matrix</span>
                  <div className="criteria-matrix">
                    {scorecardItems.map(([key, value]) => (
                      <div className={`criteria-cell ${value.passed ? 'pass' : value.is_hard ? 'fail' : 'warn'}`} key={key}>
                        <b>{value.passed ? 'Pass' : value.is_hard ? 'Blocker' : 'Warning'}</b>
                        <span>{value.message}</span>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="bento-card">
                  <span className="bento-eyebrow"><IconSparkles size={15} /> Improvement Plan</span>
                  {singleResult.improvement_plan?.suggestions?.length ? (
                    <div className="action-stack">
                      {singleResult.improvement_plan.suggestions.slice(0, 4).map((suggestion) => (
                        <div className="action-card" key={`${suggestion.priority}-${suggestion.title}`}>
                          <b>{suggestion.priority}. {suggestion.title}</b>
                          <p>{suggestion.description}</p>
                          <span>{suggestion.timeline} · {suggestion.difficulty}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-panel">No remediation needed from the rule engine.</div>
                  )}
                </article>
              </section>

              {skillGap && (
                <section className="bento-card">
                  <div className="bento-card-topline">
                    <span className="bento-eyebrow"><IconSparkles size={15} /> Skill Gap AI</span>
                    <span className="bento-pill">{skillGap.model}</span>
                  </div>
                  <div className="skill-rec-grid">
                    {skillGap.recommendations.slice(0, 5).map((rec, index) => (
                      <div className="skill-rec-card" key={rec.skill}>
                        <strong>#{index + 1}</strong>
                        <h3>{rec.skill}</h3>
                        <span>+{(rec.predicted_gain * 100).toFixed(2)}% predicted gain</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}

          {!checking && batchResults && (
            <>
              <section className="audit-grid">
                <article className="bento-card">
                  <span className="bento-eyebrow">Processed</span>
                  <div className="large-metric">{batchResults.total}</div>
                </article>
                <article className="bento-card">
                  <span className="bento-eyebrow">Eligible</span>
                  <div className="large-metric success">{batchResults.eligible}</div>
                </article>
                <article className="bento-card">
                  <span className="bento-eyebrow">Eligibility Rate</span>
                  <div className="large-metric">{((batchResults.eligible / batchResults.total) * 100).toFixed(1)}%</div>
                </article>
              </section>

              <section className="bento-card">
                <div className="bento-card-topline">
                  <span className="bento-eyebrow">Batch Candidates · {batchResults.company_name}</span>
                  <span className="bento-pill">top 50 shown</span>
                </div>
                <div className="table-container workspace-table">
                  <table>
                    <thead>
                      <tr><th>Rank</th><th>Student</th><th>Dept</th><th>Status</th><th>Score</th></tr>
                    </thead>
                    <tbody>
                      {batchResults.results.slice(0, 50).map((result, index) => (
                        <tr key={result.student_id}>
                          <td>#{index + 1}</td>
                          <td><strong>{result.full_name}</strong><br /><span className="muted-text">{result.student_id} · CGPA {result.cgpa.toFixed(2)}</span></td>
                          <td><span className="badge badge-info">{result.department}</span></td>
                          <td><span className={`badge ${result.eligible ? 'badge-success' : result.hard_pass ? 'badge-warning' : 'badge-danger'}`}>{result.eligible ? 'Eligible' : result.hard_pass ? 'Low skill match' : 'Hard fail'}</span></td>
                          <td>{result.score.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </main>
      </section>
    </div>
  );
}
