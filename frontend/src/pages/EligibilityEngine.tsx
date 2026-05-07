import { useEffect, useState } from 'react';
import { 
  getCompanies, getStudents, checkEligibility, batchCheckEligibility,
  Company, Student, BatchResult, EligibilityResult 
} from '../services/api';

export default function EligibilityEngine() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string>('');
  const [selectedStudent, setSelectedStudent] = useState<string>('');
  const [mode, setMode] = useState<'single' | 'batch'>('single');
  
  const [checking, setChecking] = useState(false);
  const [singleResult, setSingleResult] = useState<EligibilityResult | null>(null);
  const [batchResults, setBatchResults] = useState<{
    company_name: string;
    total: number;
    eligible: number;
    results: BatchResult[];
  } | null>(null);

  useEffect(() => {
    getCompanies({}).then(res => setCompanies(res.data.companies));
    // Fetch a subset for single testing
    getStudents({ limit: 100 }).then(res => setStudents(res.data.students));
  }, []);

  const runCheck = async () => {
    if (!selectedCompany) return;
    
    setChecking(true);
    setSingleResult(null);
    setBatchResults(null);

    try {
      if (mode === 'single' && selectedStudent) {
        const res = await checkEligibility(selectedStudent, selectedCompany);
        setSingleResult(res.data);
      } else if (mode === 'batch') {
        const res = await batchCheckEligibility(selectedCompany);
        setBatchResults({
          company_name: res.data.company_name,
          total: res.data.total_checked,
          eligible: res.data.eligible_count,
          results: res.data.results
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
      <header className="page-header">
        <h1>Assessment Engine</h1>
        <p>Run Rule-Based Filtering + AI Scoring</p>
      </header>

      <div className="glass-card animate-slide delay-100" style={{ marginBottom: '24px' }}>
        <div className="grid grid-2">
           <div>
             <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>Select Company Role</label>
             <select 
                className="input" 
                value={selectedCompany} 
                onChange={e => setSelectedCompany(e.target.value)}
             >
                <option value="">-- Choose Company --</option>
                {companies.map(c => (
                  <option key={c.company_id} value={c.company_id}>
                    {c.company_name} - {c.role_offered} (Min CGPA: {c.min_cgpa})
                  </option>
                ))}
             </select>
           </div>
           
           <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                 <label style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Assessment Target (Test Pool)</label>
                 <div style={{ display: 'flex', gap: '8px' }}>
                    <button 
                       className={`btn btn-sm ${mode === 'single' ? 'btn-primary' : 'btn-ghost'}`}
                       onClick={() => setMode('single')} style={{ padding: '2px 8px' }}
                    >Single</button>
                    <button 
                       className={`btn btn-sm ${mode === 'batch' ? 'btn-primary' : 'btn-ghost'}`}
                       onClick={() => setMode('batch')} style={{ padding: '2px 8px' }}
                    >Batch Pool</button>
                 </div>
              </div>
              
              {mode === 'single' ? (
                <select 
                  className="input" 
                  value={selectedStudent} 
                  onChange={e => setSelectedStudent(e.target.value)}
                >
                  <option value="">-- Choose Student --</option>
                  {students.map(s => (
                    <option key={s.student_id} value={s.student_id}>
                      {s.full_name} ({s.department}) - CGPA: {s.cgpa}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="input" style={{ opacity: 0.7, padding: '10px 16px', background: 'var(--bg-secondary)' }}>
                  All 800+ candidate profiles in database
                </div>
              )}
           </div>
        </div>
        
        <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
           <button 
              className="btn btn-primary btn-lg" 
              onClick={runCheck} 
              disabled={checking || !selectedCompany || (mode === 'single' && !selectedStudent)}
           >
              {checking ? 'Running Assessment Engine...' : mode === 'single' ? 'Run ML Pipeline' : 'Run Batch Pipeline'}
           </button>
        </div>
      </div>

      {checking && (
         <div className="loading" style={{ height: '300px' }}>
           <div className="spinner" style={{ width: '40px', height: '40px', borderWidth: '4px' }}></div>
           <span style={{ fontSize: '18px', marginLeft: '16px' }}>Executing ML Rules & Bias Checks...</span>
         </div>
      )}

      {/* SINGLE RESULT VIEW */}
      {!checking && singleResult && (
         <div className="animate-slide">
            <div className="glass-card" style={{ marginBottom: '24px', borderColor: singleResult.criteria_eligible ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                            {(() => {
                                 const rulePass = singleResult.criteria_eligible;
                                 const mlPass = singleResult.ml_result ? singleResult.ml_result.eligible : null;
                                 const finalEligible = mlPass === null ? rulePass : (rulePass && mlPass);
                                 return (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                       <h2 style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '24px' }} className={finalEligible ? 'animate-pulse-glow' : ''}>
                                          {finalEligible ? '✅ ELIGIBLE' : '❌ INELIGIBLE'}
                                       </h2>
                                       <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                          <span className={`badge ${rulePass ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '12px' }}>{rulePass ? 'Rules: PASSED' : 'Rules: FAILED'}</span>
                                          <span className={`badge ${mlPass === null ? 'badge-ghost' : (mlPass ? 'badge-success' : 'badge-warning')}`} style={{ fontSize: '12px' }}>{mlPass === null ? 'ML: N/A' : (mlPass ? 'ML: Recommended' : 'ML: Not Recommended')}</span>
                                          <span className="badge badge-info" style={{ fontSize: '12px' }}>AI Model Score: {singleResult.ml_result ? singleResult.ml_result.score.toFixed(3) : 'N/A'}</span>
                                       </div>
                                    </div>
                                 );
                            })()}
                        </div>
                
                <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>
                   {singleResult.ml_result?.message || 'Criteria checks failed.'}
                </p>

                <div className="grid grid-2">
                   <div>
                      <h4 style={{ marginBottom: '12px', color: 'var(--text-accent)' }}>Criteria Scorecard (Explainable AI)</h4>
                      
                      {Object.entries(singleResult.scorecard)
                        .filter(([k]) => k !== '_summary')
                        .map(([key, val]) => (
                           <div key={key} className={`scorecard-item ${val.passed ? 'pass' : (val.is_hard ? 'fail' : 'warn')}`}>
                              <span className="icon">{val.passed ? '✅' : (val.is_hard ? '❌' : '⚠️')}</span>
                              <span>{val.message}</span>
                              {val.is_hard && <span className="badge badge-danger" style={{ marginLeft: 'auto', transform: 'scale(0.8)' }}>Hard</span>}
                           </div>
                      ))}
                   </div>
                   
                   <div>
                      {singleResult.improvement_plan && (
                         <>
                            <h4 style={{ marginBottom: '12px', color: 'var(--accent-warning)' }}>Improvement Action Plan</h4>
                            {singleResult.improvement_plan.suggestions.map((sug, i) => (
                               <div key={i} className={`improvement-card ${sug.type === 'hard_requirement' ? 'hard' : ''}`}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                     <h4>{sug.priority}. {sug.title}</h4>
                                     <span className="badge" style={{ background: 'var(--bg-secondary)' }}>{sug.category}</span>
                                  </div>
                                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{sug.description}</p>
                                  <ul className="actions">
                                     {sug.actions.map((act, j) => <li key={j}>{act}</li>)}
                                  </ul>
                                  <div className="meta">
                                     <span>🕒 {sug.timeline}</span>
                                     <span>⚡ {sug.difficulty}</span>
                                  </div>
                               </div>
                            ))}
                         </>
                      )}
                      
                      {singleResult.criteria_eligible && (
                         <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(16, 185, 129, 0.05)', borderRadius: '12px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                            <div style={{ textAlign: 'center' }}>
                               <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎉</div>
                               <h3 style={{ color: 'var(--accent-success)' }}>Outstanding Candidate!</h3>
                               <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>Passed all hard disqualifiers and scored favorably on ML evaluation.</p>
                            </div>
                         </div>
                      )}
                   </div>
                </div>
            </div>
         </div>
      )}

      {/* BATCH VIEW */}
      {!checking && batchResults && (
         <div className="animate-slide">
             <div className="grid grid-3" style={{ marginBottom: '24px' }}>
                <div className="stat-card animate-slide delay-100">
                  <div className="stat-label">Total Processed Pool</div>
                  <div className="stat-value">{batchResults.total}</div>
                </div>
                <div className="stat-card animate-slide delay-200" style={{ borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                  <div className="stat-label">Eligible Candidates</div>
                  <div className="stat-value" style={{ color: 'var(--accent-success)' }}>{batchResults.eligible}</div>
                </div>
                <div className="stat-card animate-slide delay-300">
                  <div className="stat-label">Eligibility Rate</div>
                  <div className="stat-value">
                     {((batchResults.eligible / batchResults.total) * 100).toFixed(1)}%
                  </div>
                </div>
             </div>

             <div className="glass-card animate-slide delay-400">
                <h3 style={{ marginBottom: '16px', color: 'var(--text-accent)' }}>
                   Ranked Candidates List | {batchResults.company_name}
                </h3>
                <div className="table-container">
                   <table>
                      <thead>
                         <tr>
                            <th>Rank</th>
                            <th>Student ID & Name</th>
                            <th>Dept</th>
                            <th>Status (Explainable)</th>
                            <th>Model Score</th>
                         </tr>
                      </thead>
                      <tbody>
                         {batchResults.results.slice(0, 50).map((r, idx) => (
                           <tr key={r.student_id} style={{ background: idx < batchResults.eligible ? 'rgba(16, 185, 129, 0.05)' : 'transparent' }}>
                              <td style={{ fontWeight: 800, color: idx < 3 ? 'var(--accent-warning)' : 'var(--text-muted)' }}>
                                 #{idx + 1}
                              </td>
                              <td>
                                 <div style={{ fontWeight: 600 }}>{r.full_name}</div>
                                 <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{r.student_id} | CGPA: {r.cgpa.toFixed(2)}</div>
                              </td>
                              <td><span className="badge badge-info">{r.department}</span></td>
                              <td>
                                 {r.eligible ? (
                                    <span className="badge badge-success">Eligible</span>
                                 ) : !r.hard_pass ? (
                                    <span className="badge badge-danger">Failed Hard Checks</span>
                                 ) : (
                                    <span className="badge badge-warning">Low Skills Match</span>
                                 )}
                                 
                                 {r.hard_failures?.length > 0 && (
                                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                                       Ex: {r.hard_failures[0].replace('_check', '')}
                                    </div>
                                 )}
                              </td>
                              <td>
                                 <div style={{ fontWeight: 600, color: r.eligible ? 'var(--accent-success)' : 'var(--text-primary)' }}>
                                    {r.score.toFixed(4)}
                                 </div>
                              </td>
                           </tr>
                         ))}
                      </tbody>
                   </table>
                   {batchResults.total > 50 && (
                      <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px', background: 'var(--bg-tertiary)' }}>
                         Showing top 50 matches. Remaining are hidden.
                      </div>
                   )}
                </div>
             </div>
         </div>
      )}
    </div>
  );
}
