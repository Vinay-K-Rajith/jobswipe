import { useEffect, useState } from 'react';
import { StudentCardData, getRecruiterInterested } from '../../services/swipeApi';

export default function RecruiterInterested() {
  const [students, setStudents] = useState<StudentCardData[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    getRecruiterInterested()
      .then((response) => setStudents(response.data.students))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load pending student interest.'));
  }, []);

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Recruiter Portal</span>
        <h1>Pending student responses</h1>
        <p>Students you liked who have not responded yet.</p>
      </header>
      {error && <div className="bias-inline-error">{error}</div>}
      <section className="portal-list">
        {students.length === 0 ? (
          <div className="portal-empty"><h2>No pending likes</h2><p>Students you like from Browse will appear here until they respond.</p></div>
        ) : students.map((student) => (
          <article className="portal-row" key={`${student.student_id}-${student.job_id || ''}`}>
            <div>
              <strong>{student.full_name}</strong>
              <span>{student.department} / GPA {student.cgpa.toFixed(2)}</span>
            </div>
            <span className="badge badge-warning">Pending</span>
          </article>
        ))}
      </section>
    </main>
  );
}
