import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  IconAlertTriangle,
  IconBuildingSkyscraper,
  IconChartBar,
  IconFilterExclamation,
  IconScale,
  IconShieldCheck,
} from '@tabler/icons-react';
import { getBiasReport, BiasCompany, BiasReport } from '../services/api';

export default function BiasDetection() {
  const [biasReport, setBiasReport] = useState<BiasReport | null>(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');

  useEffect(() => {
    getBiasReport(false).then((r) => {
      setBiasReport(r.data);
      setSelectedCompanyId(r.data.flagged_companies[0]?.company_id || r.data.all_companies?.[0]?.company_id || '');
    }).catch(() => {});
  }, []);

  const sortedCompanies = useMemo(
    () => [...(biasReport?.all_companies || [])].sort((a, b) => b.gender_disparity - a.gender_disparity),
    [biasReport],
  );

  const selectedCompany = useMemo(
    () => sortedCompanies.find((company) => company.company_id === selectedCompanyId) || sortedCompanies[0],
    [selectedCompanyId, sortedCompanies],
  );

  const selectedFlag = biasReport?.flagged_companies.find((company) => company.company_id === selectedCompany?.company_id);
  const passRates = Object.entries(selectedCompany?.gender_pass_rates || selectedFlag?.pass_rates || {}).map(([group, rate]) => ({
    group,
    rate: Math.round((rate as number) * 1000) / 10,
  }));

  return (
    <div className="container animate-fade">
      <header className="workspace-header">
        <div>
          <p className="dashboard-kicker">Fairness audit</p>
          <h1>Bias Detection</h1>
          <p>Criteria-level disparate impact analysis for placement rules.</p>
        </div>
        {biasReport && (
          <div className="workspace-header-actions">
            <span>{biasReport.summary.student_pool_size} student pool</span>
            <span>p &lt; {biasReport.summary.significance}</span>
          </div>
        )}
      </header>

      {!biasReport ? (
        <div className="loading"><div className="spinner"></div> Loading bias report...</div>
      ) : (
        <>
          <section className="audit-grid">
            <article className="audit-hero bento-card">
              <div className="bento-card-topline">
                <div>
                  <span className="bento-eyebrow"><IconScale size={15} /> Audit Summary</span>
                  <h2>{(biasReport.summary.flag_rate * 100).toFixed(1)}% gender flag rate</h2>
                </div>
                <span className="bento-pill">{biasReport.summary.n_companies} companies</span>
              </div>
              <p className="audit-finding">
                Low gender flag rate suggests disparity is primarily structural, driven by department restrictions and hard academic criteria rather than direct gender-discriminatory hard rules.
              </p>
              <div className="audit-stat-row">
                <div>
                  <strong>{biasReport.summary.n_flagged}</strong>
                  <span>flagged companies</span>
                </div>
                <div>
                  <strong>{(biasReport.summary.threshold * 100).toFixed(0)}%</strong>
                  <span>gap threshold</span>
                </div>
                <div>
                  <strong>Fisher</strong>
                  <span>significance test</span>
                </div>
              </div>
            </article>

            <article className="bento-card">
              <span className="bento-eyebrow"><IconFilterExclamation size={15} /> Risk Mix</span>
              <div className="risk-meter">
                <span style={{ width: `${Math.max(4, biasReport.summary.flag_rate * 100)}%` }} />
              </div>
              <div className="risk-meter-labels">
                <span>Clean: {biasReport.summary.n_companies - biasReport.summary.n_flagged}</span>
                <span>Flagged: {biasReport.summary.n_flagged}</span>
              </div>
            </article>

            <article className="bento-card">
              <span className="bento-eyebrow"><IconBuildingSkyscraper size={15} /> Gender Pool</span>
              <div className="pool-list">
                {Object.entries(biasReport.summary.gender_pool_dist).map(([gender, share]) => (
                  <div key={gender}>
                    <span>{gender}</span>
                    <strong>{((share as number) * 100).toFixed(1)}%</strong>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="audit-workspace">
            <aside className="bento-card audit-watchlist">
              <span className="bento-eyebrow"><IconAlertTriangle size={15} /> Flagged Watchlist</span>
              <div className="watchlist-stack">
                {biasReport.flagged_companies.map((company) => (
                  <button
                    className={`watchlist-item ${selectedCompanyId === company.company_id ? 'active' : ''}`}
                    key={company.company_id}
                    onClick={() => setSelectedCompanyId(company.company_id)}
                  >
                    <span>
                      <strong>{company.company_name}</strong>
                      <small>{company.tier} · Driver: {company.top_bias_criterion}</small>
                    </span>
                    <b>{(company.disparity * 100).toFixed(1)}%</b>
                  </button>
                ))}
              </div>
            </aside>

            <main className="bento-card audit-detail">
              <div className="bento-card-topline">
                <div>
                  <span className="bento-eyebrow"><IconChartBar size={15} /> Selected Company</span>
                  <h2>{selectedCompany?.company_name || 'No company selected'}</h2>
                </div>
                {selectedCompany && (
                  <span className={`bento-pill ${selectedCompany.gender_flagged ? 'danger' : 'success'}`}>
                    {selectedCompany.gender_flagged ? 'Flagged' : 'Clean'}
                  </span>
                )}
              </div>

              {selectedCompany && (
                <>
                  <div className="audit-detail-metrics">
                    <div>
                      <span>Pool pass rate</span>
                      <strong>{(selectedCompany.pool_pass_rate * 100).toFixed(1)}%</strong>
                    </div>
                    <div>
                      <span>Gender disparity</span>
                      <strong>{(selectedCompany.gender_disparity * 100).toFixed(1)}%</strong>
                    </div>
                    <div>
                      <span>p-value</span>
                      <strong>{selectedCompany.gender_p_value.toFixed(4)}</strong>
                    </div>
                    <div>
                      <span>Top driver</span>
                      <strong>{selectedCompany.top_bias_criterion}</strong>
                    </div>
                  </div>

                  <div className="audit-chart-shell">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={passRates} margin={{ top: 10, right: 16, bottom: 0, left: -12 }}>
                        <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                        <XAxis dataKey="group" axisLine={false} tickLine={false} tick={{ fill: '#a1a1aa', fontSize: 12 }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#a1a1aa', fontSize: 12 }} />
                        <Tooltip contentStyle={{ background: '#050505', border: '1px solid rgba(255,255,255,0.16)', borderRadius: 8 }} />
                        <Bar dataKey="rate" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </>
              )}
            </main>
          </section>

          <section className="bento-card audit-table-card">
            <div className="bento-card-topline">
              <span className="bento-eyebrow"><IconShieldCheck size={15} /> Full Company Ranking</span>
              <span className="bento-pill">sorted by disparity</span>
            </div>
            <div className="table-container workspace-table">
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Tier</th>
                    <th>Pool Pass</th>
                    <th>Disparity</th>
                    <th>p-value</th>
                    <th>Driver</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedCompanies.map((company: BiasCompany) => (
                    <tr key={company.company_id}>
                      <td><strong>{company.company_name}</strong></td>
                      <td><span className="badge badge-info">{company.tier}</span></td>
                      <td>{(company.pool_pass_rate * 100).toFixed(1)}%</td>
                      <td>{(company.gender_disparity * 100).toFixed(1)}%</td>
                      <td>{company.gender_p_value.toFixed(4)}</td>
                      <td>{company.top_bias_criterion}</td>
                      <td>
                        <span className={`badge ${company.gender_flagged ? 'badge-warning' : 'badge-success'}`}>
                          {company.gender_flagged ? 'Review' : 'Clean'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
