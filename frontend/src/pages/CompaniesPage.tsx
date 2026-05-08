import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { IconBuildingSkyscraper, IconSearch, IconShieldCheck, IconTargetArrow } from '@tabler/icons-react';
import { getCompanies, Company } from '../services/api';

function strictness(company: Company) {
  let score = 0;
  score += company.min_cgpa >= 8 ? 25 : company.min_cgpa >= 7 ? 15 : 8;
  score += company.max_active_backlogs === 0 ? 18 : 6;
  score += company.min_projects >= 3 ? 18 : company.min_projects >= 1 ? 10 : 4;
  score += company.cert_tier_required !== 'None' ? 14 : 4;
  score += company.requires_research_paper ? 12 : 0;
  score += company.required_skills.split(',').filter(Boolean).length * 3;
  return Math.min(100, score);
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [tier, setTier] = useState('All');

  useEffect(() => {
    getCompanies()
      .then((res) => setCompanies(res.data.companies))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const tiers = ['All', ...Array.from(new Set(companies.map((company) => company.tier)))];
  const filtered = companies.filter((company) => {
    const textMatch =
      company.company_name.toLowerCase().includes(filter.toLowerCase()) ||
      company.industry.toLowerCase().includes(filter.toLowerCase()) ||
      company.role_offered.toLowerCase().includes(filter.toLowerCase());
    const tierMatch = tier === 'All' || company.tier === tier;
    return textMatch && tierMatch;
  });

  const topSkills = useMemo(() => {
    const counts = new Map<string, number>();
    companies.forEach((company) => {
      company.required_skills.split(',').filter(Boolean).forEach((skill) => {
        counts.set(skill, (counts.get(skill) || 0) + 1);
      });
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [companies]);

  return (
    <div className="container animate-fade">
      <header className="workspace-header">
        <div>
          <p className="dashboard-kicker">Company intelligence</p>
          <h1>Companies & Criteria</h1>
          <p>Inspect placement requirements, strictness, skills demand, and available workflows.</p>
        </div>
        <div className="workspace-header-actions">
          <span>{companies.length} partners</span>
          <span>{topSkills.length} top skills tracked</span>
        </div>
      </header>

      <section className="company-toolbar bento-card">
        <div className="search-box">
          <IconSearch size={17} />
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search company, role, industry..." />
        </div>
        <div className="tier-tabs">
          {tiers.map((item) => (
            <button className={tier === item ? 'active' : ''} key={item} onClick={() => setTier(item)}>{item}</button>
          ))}
        </div>
      </section>

      {loading ? (
        <div className="loading"><div className="spinner"></div>Loading companies...</div>
      ) : (
        <>
          <section className="company-skill-strip">
            {topSkills.map(([skill, count]) => (
              <div className="bento-card skill-demand-card" key={skill}>
                <span>{skill}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </section>

          <section className="company-card-grid">
            {filtered.map((company) => {
              const strict = strictness(company);
              return (
                <article className="company-card bento-card" key={company.company_id}>
                  <div className="bento-card-topline">
                    <span className="bento-eyebrow"><IconBuildingSkyscraper size={15} /> {company.industry}</span>
                    <span className="badge badge-info">{company.tier}</span>
                  </div>
                  <h2>{company.company_name}</h2>
                  <p>{company.role_offered} · {company.package_lpa.toFixed(1)} LPA</p>

                  <div className="company-card-metrics">
                    <div><span>CGPA</span><strong>{company.min_cgpa.toFixed(1)}</strong></div>
                    <div><span>Projects</span><strong>{company.min_projects}</strong></div>
                    <div><span>Backlogs</span><strong>{company.max_active_backlogs}</strong></div>
                  </div>

                  <div className="strictness-block">
                    <div><span>Criteria strictness</span><b>{strict}/100</b></div>
                    <div className="score-track"><span style={{ width: `${strict}%` }} /></div>
                  </div>

                  <div className="criteria-chip-cloud">
                    {company.allowed_departments.split(',').map((dept) => <span key={dept}>{dept}</span>)}
                  </div>
                  <div className="criteria-chip-cloud muted">
                    {company.required_skills.split(',').filter(Boolean).slice(0, 5).map((skill) => <span key={skill}>{skill}</span>)}
                  </div>

                  <div className="company-actions">
                    <Link to="/ranking"><IconTargetArrow size={16} /> Shortlist</Link>
                    <Link to="/bias"><IconShieldCheck size={16} /> Audit</Link>
                  </div>
                </article>
              );
            })}
          </section>
        </>
      )}
    </div>
  );
}
