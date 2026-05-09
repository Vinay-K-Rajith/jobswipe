import { IconExternalLink, IconSchool, IconSparkles, IconTrophy, IconX } from '@tabler/icons-react';
import { StudentCardData } from '../../services/swipeApi';

const DEPT_COLOURS: Record<string, string> = {
  CSE: '#38bdf8',
  CS: '#38bdf8',
  IT: '#8b5cf6',
  AIDS: '#14b8a6',
  AIML: '#06b6d4',
  DS: '#22c55e',
  ECE: '#f97316',
  EEE: '#f59e0b',
  MECH: '#94a3b8',
};

function deptColour(department: string) {
  return DEPT_COLOURS[department.toUpperCase()] || '#64748b';
}

function chips(values: string[], limit = 6) {
  return values.filter(Boolean).slice(0, limit).map((skill) => <span className="swipe-chip" key={skill}>{skill}</span>);
}

function percent(value: number | undefined) {
  return `${Math.round((value || 0) * 100)}%`;
}

interface StudentCardProps {
  student: StudentCardData;
  expanded: boolean;
  onToggle: () => void;
}

export default function StudentCard({ student, expanded, onToggle }: StudentCardProps) {
  return (
    <article className={`swipe-card student ${expanded ? 'expanded' : ''}`} onClick={onToggle}>
      {!expanded ? (
        <>
          <div className="student-card-art" style={{ background: deptColour(student.department) }}>
            <span className="card-tag">{student.department}</span>
            <span className="phi-badge">Phi {student.phi_score.toFixed(2)}</span>
            <div className="card-art-mark">
              <IconSchool size={38} />
              <strong>{student.full_name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</strong>
            </div>
            <div className="card-art-meta">
              <span><IconTrophy size={14} /> GPA {student.cgpa.toFixed(2)}</span>
              <span><IconSparkles size={14} /> {student.graduation_year}</span>
            </div>
          </div>
          <div className="swipe-card-body student-body">
            <h2>{student.full_name}</h2>
            {student.email && <span className="student-email">{student.email}</span>}
            <p>{student.degree} / {student.university} / {student.graduation_year}</p>
            <em>{student.highlight_line || 'Best project: Built a production-minded analytics project with clean documentation.'}</em>
            {student.preference_summary && <div className="detail-line strong-line">{student.preference_summary}</div>}
            <div className="match-score-strip">
              <span>Match</span>
              <strong>{percent(student.phi_score)}</strong>
            </div>
            <div className="student-strip">
              <span className="gpa-chip">GPA {student.cgpa.toFixed(2)}</span>
              {chips(student.skills, 3)}
            </div>
          </div>
        </>
      ) : (
        <div className="swipe-detail" onClick={(event) => event.stopPropagation()}>
          <button type="button" className="detail-close" onClick={onToggle} aria-label="Close details">
            <IconX size={18} />
          </button>
          <span className="card-tag">{student.department}</span>
          <h2>{student.full_name}</h2>
          {student.email && <span className="student-email">{student.email}</span>}
          <p>{student.degree} / Graduation {student.graduation_year}</p>
          {student.preference_summary && (
            <div className="detail-section">
              <strong>Preferences</strong>
              <span>{student.preference_summary}</span>
            </div>
          )}
          {!!student.match_breakdown && (
            <div className="detail-section">
              <strong>TalentForge match</strong>
              <div className="match-breakdown-grid">
                <span>Skills <b>{percent(student.match_breakdown.skills)}</b></span>
                <span>Role <b>{percent(student.match_breakdown.role)}</b></span>
                <span>Category <b>{percent(student.match_breakdown.category)}</b></span>
                <span>Overall <b>{percent(student.match_breakdown.overall)}</b></span>
              </div>
            </div>
          )}
          <div className="detail-section">
            <strong>Top projects</strong>
            {student.top_projects.slice(0, 2).map((project) => (
              <span key={project.title}><b>{project.title}</b>: {project.description}</span>
            ))}
          </div>
          <div className="detail-grid">
            <div>
              <strong>Coursework</strong>
              <div className="chip-row">{chips(student.coursework, 4)}</div>
            </div>
            <div>
              <strong>Certifications</strong>
              {student.certifications.slice(0, 3).map((cert) => (
                <span className="detail-line" key={cert.name}>{cert.name} / {cert.issuer}</span>
              ))}
            </div>
          </div>
          <div className="detail-grid">
            <div><strong>GPA</strong><span>{student.cgpa.toFixed(2)}</span></div>
            <div><strong>Availability</strong><span>{student.availability}</span></div>
            <div><strong>Work authorization</strong><span>{student.work_authorization}</span></div>
          </div>
          {!!student.profile_tags?.length && (
            <div className="detail-section">
              <strong>Profile tags</strong>
              <div className="chip-row">{chips(student.profile_tags, 6)}</div>
            </div>
          )}
          {student.portfolio_url && (
            <a href={student.portfolio_url} target="_blank" rel="noreferrer" className="detail-link">
              <IconExternalLink size={16} /> Portfolio
            </a>
          )}
        </div>
      )}
    </article>
  );
}
