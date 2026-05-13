import { useEffect, useState } from 'react';
import CardCarousel from '../../components/swipe/CardCarousel';
import StudentCard from '../../components/swipe/StudentCard';
import {
  BrowseTrack,
  StudentCardData,
  getRecruiterFeed,
  getRecruiterJobs,
  recruiterSwipeLeft,
  recruiterSwipeRight,
  JobCardData,
} from '../../services/swipeApi';

function inferTrack(job: JobCardData): BrowseTrack {
  const combined = [
    job.job_type,
    job.role_title,
    job.highlight_line,
    job.salary,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  if (combined.includes('intern') || combined.includes('/month') || combined.includes('per month')) {
    return 'internship';
  }
  return 'full-time';
}

export default function RecruiterBrowse() {
  const [students, setStudents] = useState<StudentCardData[]>([]);
  const [jobs, setJobs] = useState<JobCardData[]>([]);
  const [track, setTrack] = useState<BrowseTrack>('internship');
  const [jobId, setJobId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  async function loadFeed(selectedJobId: string, selectedTrack: BrowseTrack) {
    if (!selectedJobId) {
      setStudents([]);
      return;
    }
    const response = await getRecruiterFeed(selectedJobId, selectedTrack);
    setStudents(response.data.students);
  }

  const visibleJobs = jobs.filter((job) => {
    return (job.is_active ?? true) && inferTrack(job) === track;
  });

  useEffect(() => {
    getRecruiterJobs()
      .then((response) => {
        setJobs(response.data.jobs);
      })
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load your job postings.'));
  }, []);

  useEffect(() => {
    const nextJobId = visibleJobs[0]?.id || '';
    setJobId((current) => (visibleJobs.some((job) => job.id === current) ? current : nextJobId));
  }, [track, jobs.length]);

  useEffect(() => {
    if (!jobId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    loadFeed(jobId, track)
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load student cards.'))
      .finally(() => setLoading(false));
  }, [jobId, track]);

  async function removeStudent(student: StudentCardData, liked: boolean) {
    if (!jobId) return;
    if (liked) await recruiterSwipeRight(student.student_id, jobId);
    else await recruiterSwipeLeft(student.student_id);
    const remaining = students.filter((item) => item.student_id !== student.student_id);
    setStudents(remaining);
    if (!remaining.length) {
      try {
        await loadFeed(jobId, track);
      } catch {
        // Keep the empty state if the refresh fails.
      }
    }
  }

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Recruiter Portal</span>
        <h1>Browse students</h1>
        <p>Review candidates for one active role at a time.</p>
      </header>
      <div className="tier-tabs browse-track-tabs">
        <button type="button" className={track === 'internship' ? 'active' : ''} onClick={() => setTrack('internship')}>Internship seekers</button>
        <button type="button" className={track === 'full-time' ? 'active' : ''} onClick={() => setTrack('full-time')}>Full-time seekers</button>
      </div>
      {error && <div className="bias-inline-error">{error}</div>}
      <div className="portal-toolbar">
        <select className="input" value={jobId} onChange={(event) => setJobId(event.target.value)}>
          <option value="">Select a posted role</option>
          {visibleJobs.map((job) => <option key={job.id} value={job.id}>{job.role_title}</option>)}
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
          emptyTitle={jobId ? `No more ${track === 'internship' ? 'internship-seeking' : 'full-time-seeking'} students right now` : 'Post a role first'}
          emptyText={jobId ? `You have reached the end of this ${track === 'internship' ? 'internship' : 'full-time'} student feed.` : 'Create a job posting before browsing candidates.'}
        />
      )}
    </main>
  );
}
