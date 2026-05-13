import { IconBuildingSkyscraper, IconExternalLink, IconMapPin, IconRocket, IconWallet, IconX } from '@tabler/icons-react';
import { JobCardData } from '../../services/swipeApi';

const INDUSTRY_COLOURS: Record<string, string> = {
  fintech: '#14b8a6',
  finance: '#14b8a6',
  healthtech: '#22c55e',
  healthcare: '#22c55e',
  edtech: '#38bdf8',
  ecommerce: '#f97316',
  'e-commerce': '#f97316',
  analytics: '#06b6d4',
  consulting: '#f59e0b',
  ai: '#8b5cf6',
};

function colourForIndustry(industry: string) {
  return INDUSTRY_COLOURS[industry.toLowerCase()] || '#64748b';
}

function chips(values: string[]) {
  return values.filter(Boolean).slice(0, 6).map((skill) => <span className="swipe-chip" key={skill}>{skill}</span>);
}

function isRepeatedHighlight(job: JobCardData) {
  const highlight = (job.highlight_line || '').toLowerCase();
  const repeatedValues = [job.salary, job.job_type, job.company_size, job.candidate_level]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase());

  return repeatedValues.length >= 2 && repeatedValues.filter((value) => highlight.includes(value)).length >= 2;
}

interface CompanyCardProps {
  job: JobCardData;
  expanded: boolean;
  onToggle: () => void;
}

export default function CompanyCard({ job, expanded, onToggle }: CompanyCardProps) {
  const metaLine = [job.salary, job.job_type, job.company_size, job.candidate_level].filter(Boolean).join(' / ');
  const highlightLine = !isRepeatedHighlight(job)
    ? job.highlight_line
    : '';

  return (
    <article className={`swipe-card company ${expanded ? 'expanded' : ''}`} onClick={onToggle}>
      {!expanded ? (
        <>
          <div className="company-card-art" style={{ background: colourForIndustry(job.industry) }}>
            <span className="card-tag">{job.industry || 'Role'}</span>
            <div className="card-art-mark">
              <IconBuildingSkyscraper size={38} />
              <strong>{job.company_name.slice(0, 2).toUpperCase()}</strong>
            </div>
            <div className="card-art-meta">
              <span><IconMapPin size={14} /> {job.location || 'Location TBA'}</span>
              <span><IconRocket size={14} /> {job.remote_policy || 'Hybrid'}</span>
            </div>
          </div>
          <div className="swipe-card-body">
            <h2>{job.company_name}</h2>
            <p>{job.role_title}</p>
            {highlightLine && <em>{highlightLine}</em>}
            {metaLine && (
              <div className="card-metric-strip">
                {job.salary && <span><IconWallet size={14} /> {job.salary}</span>}
                {job.job_type && <span>{job.job_type}</span>}
                {job.company_size && <span>{job.company_size}</span>}
                {job.candidate_level && <span>{job.candidate_level}</span>}
              </div>
            )}
            <div className="chip-row">{chips(job.required_skills.slice(0, 3))}</div>
          </div>
        </>
      ) : (
        <div className="swipe-detail" onClick={(event) => event.stopPropagation()}>
          <button type="button" className="detail-close" onClick={onToggle} aria-label="Close details">
            <IconX size={18} />
          </button>
          <span className="card-tag">{job.industry || 'Role'}</span>
          <h2>{job.company_name}</h2>
          <h3>{job.role_title}</h3>
          <p>{job.location || 'Location TBA'} / {job.remote_policy || 'hybrid'}</p>
          <div className="detail-grid">
            <div><strong>Compensation</strong><span>{job.salary || 'Not specified'}</span></div>
            <div><strong>Type</strong><span>{job.job_type || 'Role'}</span></div>
            <div><strong>Company</strong><span>{job.company_size || 'Not specified'}</span></div>
            <div><strong>Candidate level</strong><span>{job.candidate_level || 'All candidates'}</span></div>
          </div>
          <div className="detail-section">
            <strong>Interview timeline</strong>
            <span>{job.interview_timeline || 'OA to technical rounds to offer, about 3 weeks.'}</span>
          </div>
          <div className="detail-section">
            <strong>Mentorship</strong>
            <span>{job.mentorship || 'Each intern is paired with an engineering mentor and weekly project reviews.'}</span>
          </div>
          <div className="detail-grid">
            <div>
              <strong>Required</strong>
              <div className="chip-row">{chips(job.required_skills)}</div>
            </div>
            <div>
              <strong>Preferred</strong>
              <div className="chip-row">{chips(job.preferred_skills)}</div>
            </div>
          </div>
          {job.careers_url && (
            <a href={job.careers_url} target="_blank" rel="noreferrer" className="detail-link">
              <IconExternalLink size={16} /> Careers page
            </a>
          )}
        </div>
      )}
    </article>
  );
}
