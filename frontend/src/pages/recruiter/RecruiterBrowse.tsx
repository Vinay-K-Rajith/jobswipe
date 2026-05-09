import { useEffect, useState } from 'react';
import CardCarousel from '../../components/swipe/CardCarousel';
import StudentCard from '../../components/swipe/StudentCard';
import {
  StudentCardData,
  getRecruiterFeed,
  getRecruiterJobs,
  recruiterSwipeLeft,
  recruiterSwipeRight,
  JobCardData,
} from '../../services/swipeApi';

export default function RecruiterBrowse() {
  const [students, setStudents] = useState<StudentCardData[]>([]);
  const [jobs, setJobs] = useState<JobCardData[]>([]);
  const [jobId, setJobId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRecruiterJobs()
      .then((response) => {
        setJobs(response.data.jobs);
        setJobId(response.data.jobs[0]?.id || '');
      })
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load your job postings.'));
  }, []);

  useEffect(() => {
    if (!jobId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getRecruiterFeed(jobId)
      .then((response) => setStudents(response.data.students))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load student cards.'))
      .finally(() => setLoading(false));
  }, [jobId]);

  async function removeStudent(student: StudentCardData, liked: boolean) {
    if (!jobId) return;
    if (liked) await recruiterSwipeRight(student.student_id, jobId);
    else await recruiterSwipeLeft(student.student_id);
    setStudents((current) => current.filter((item) => item.student_id !== student.student_id));
  }

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Recruiter Portal</span>
        <h1>Browse students</h1>
        <p>Review candidates for one active role at a time.</p>
      </header>
      {error && <div className="bias-inline-error">{error}</div>}
      <div className="portal-toolbar">
        <select className="input" value={jobId} onChange={(event) => setJobId(event.target.value)}>
          <option value="">Select a posted role</option>
          {jobs.map((job) => <option key={job.id} value={job.id}>{job.role_title}</option>)}
        </select>
      </div>
      {loading ? (
        <div className="loading"><div className="spinner" /> Loading student cards...</div>
      ) : (
        <CardCarousel
          items={students}
          getKey={(student) => student.student_id}
          renderCard={(student, expanded, toggle) => <StudentCard student={student} expanded={expanded} onToggle={toggle} />}
          onPass={(student) => removeStudent(student, false)}
          onLike={(student) => removeStudent(student, true)}
          emptyTitle={jobId ? 'No more students right now' : 'Post a role first'}
          emptyText={jobId ? 'You have reached the end of this role feed.' : 'Create a job posting before browsing candidates.'}
        />
      )}
    </main>
  );
}
