import { useEffect, useState } from 'react';
import CompanyCard from '../../components/swipe/CompanyCard';
import ActionButtons from '../../components/swipe/ActionButtons';
import { JobCardData, getStudentInterested, studentSwipeLeft, studentSwipeRight } from '../../services/swipeApi';

export default function StudentInterested() {
  const [jobs, setJobs] = useState<JobCardData[]>([]);
  const [selected, setSelected] = useState<JobCardData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStudentInterested()
      .then((response) => setJobs(response.data.jobs))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load companies interested in you.'))
      .finally(() => setLoading(false));
  }, []);

  async function decide(job: JobCardData, liked: boolean) {
    if (liked) await studentSwipeRight(job.id);
    else await studentSwipeLeft(job.id);
    setJobs((current) => current.filter((item) => item.id !== job.id));
    setSelected(null);
  }

  if (loading) return <div className="loading"><div className="spinner" /> Loading interested companies...</div>;

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Student Portal</span>
        <h1>Interested in you</h1>
        <p>Companies that already liked your profile. Decide to create a match or pass.</p>
      </header>
      {error && <div className="bias-inline-error">{error}</div>}
      <section className="portal-list">
        {jobs.length === 0 ? (
          <div className="portal-empty"><h2>No pending interest</h2><p>New recruiter likes will appear here.</p></div>
        ) : jobs.map((job) => (
          <article className="portal-row" key={job.id}>
            <div className="avatar-circle">{job.company_name.slice(0, 2).toUpperCase()}</div>
            <div>
              <strong>{job.company_name}</strong>
              <span>{job.role_title}</span>
            </div>
            <button className="btn btn-primary" type="button" onClick={() => setSelected(job)}>Decide</button>
          </article>
        ))}
      </section>
      {selected && (
        <section className="decision-panel">
          <CompanyCard job={selected} expanded onToggle={() => setSelected(null)} />
          <ActionButtons onPass={() => void decide(selected, false)} onLike={() => void decide(selected, true)} />
        </section>
      )}
    </main>
  );
}
