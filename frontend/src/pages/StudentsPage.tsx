import { useEffect, useMemo, useState } from 'react';
import { IconChevronLeft, IconChevronRight, IconFilter, IconUsersGroup } from '@tabler/icons-react';
import { getStudents, Student } from '../services/api';

const departments = ['CSE', 'IT', 'AIML', 'AIDS', 'ECE', 'EEE', 'MECH'];
const LIMIT = 50;

function readiness(student: Student) {
  let score = 0;
  score += Math.min(35, student.cgpa * 3.5);
  score += student.active_backlogs === 0 ? 20 : 0;
  score += Math.min(20, student['12th_marks'] / 5);
  score += Math.min(15, student['10th_marks'] / 7);
  score += student.year_of_study >= 3 ? 10 : 4;
  return Math.round(Math.min(100, score));
}

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [dept, setDept] = useState('');
  const [offset, setOffset] = useState(0);

  const loadStudents = () => {
    setLoading(true);
    return getStudents({ department: dept || undefined, limit: LIMIT, offset })
      .then((res) => {
        setStudents(res.data.students);
        setTotal(res.data.total);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStudents();
  }, [dept, offset]);

  const pageStats = useMemo(() => {
    const avgCgpa = students.length ? students.reduce((sum, student) => sum + student.cgpa, 0) / students.length : 0;
    const activeBacklogs = students.filter((student) => student.active_backlogs > 0).length;
    const avgReadiness = students.length ? students.reduce((sum, student) => sum + readiness(student), 0) / students.length : 0;
    return { avgCgpa, activeBacklogs, avgReadiness };
  }, [students]);

  return (
    <div className="container animate-fade">
      <header className="workspace-header">
        <div>
          <p className="dashboard-kicker">Cohort explorer</p>
          <h1>Student Directory</h1>
          <p>Anonymized placement profiles with bias-sensitive attributes hidden.</p>
        </div>
        <div className="workspace-header-actions">
          <span>{total} profiles</span>
          <span>showing {offset + 1}-{Math.min(offset + LIMIT, total)}</span>
        </div>
      </header>

      <section className="student-shell">
        <aside className="bento-card student-filter-panel">
          <span className="bento-eyebrow"><IconFilter size={15} /> Filters</span>
          <div className="dept-filter-list">
            <button className={dept === '' ? 'active' : ''} onClick={() => { setDept(''); setOffset(0); }}>All Departments</button>
            {departments.map((item) => (
              <button className={dept === item ? 'active' : ''} key={item} onClick={() => { setDept(item); setOffset(0); }}>{item}</button>
            ))}
          </div>

          <div className="student-page-metrics">
            <div><span>Avg CGPA</span><strong>{pageStats.avgCgpa.toFixed(2)}</strong></div>
            <div><span>Avg readiness</span><strong>{pageStats.avgReadiness.toFixed(0)}%</strong></div>
            <div><span>Active backlog risk</span><strong>{pageStats.activeBacklogs}</strong></div>
          </div>
        </aside>

        <main className="student-main">
          {loading ? (
            <div className="loading"><div className="spinner"></div>Loading students...</div>
          ) : (
            <>
              <section className="bento-card student-cohort-banner">
                <div>
                  <span className="bento-eyebrow"><IconUsersGroup size={15} /> Current Cohort Slice</span>
                  <h2>{dept || 'All departments'}</h2>
                </div>
                <div className="workspace-header-actions">
                  <span>{students.length} loaded</span>
                  <span>{pageStats.activeBacklogs} active backlog cases</span>
                </div>
              </section>

              <section className="student-card-grid">
                {students.map((student) => {
                  const score = readiness(student);
                  const backlogLabel = student.active_backlogs > 0
                    ? `${student.active_backlogs} active backlog${student.active_backlogs > 1 ? 's' : ''}`
                    : 'No active backlogs';

                  return (
                    <article className="student-profile-card bento-card" key={student.student_id}>
                      <h3>{student.full_name}</h3>
                      <div className="student-profile-meta">
                        <p>{student.student_id} · Year {student.year_of_study}</p>
                        <div className="student-tag-row">
                          <span className="student-inline-tag">{student.department}</span>
                          <span className={`student-inline-tag ${student.active_backlogs > 0 ? 'risk' : 'clear'}`}>
                            {backlogLabel}
                          </span>
                        </div>
                      </div>
                      <div className="student-score-ring">
                        <div>
                          <strong>{score}%</strong>
                          <span>readiness</span>
                        </div>
                        <div className="score-track"><span style={{ width: `${score}%` }} /></div>
                      </div>
                      <div className="student-academic-grid">
                        <div><span>CGPA</span><strong>{student.cgpa.toFixed(2)}</strong></div>
                        <div><span>12th</span><strong>{student['12th_marks'].toFixed(1)}%</strong></div>
                        <div><span>10th</span><strong>{student['10th_marks'].toFixed(1)}%</strong></div>
                      </div>
                    </article>
                  );
                })}
              </section>

              <div className="student-pagination bento-card">
                <span>Showing {offset + 1} to {Math.min(offset + LIMIT, total)} of {total}</span>
                <div>
                  <button className="btn btn-ghost btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
                    <IconChevronLeft size={16} /> Previous
                  </button>
                  <button className="btn btn-ghost btn-sm" disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)}>
                    Next <IconChevronRight size={16} />
                  </button>
                </div>
              </div>
            </>
          )}
        </main>
      </section>
    </div>
  );
}
