import { useEffect, useState } from 'react';
import CardCarousel from '../../components/swipe/CardCarousel';
import CompanyCard from '../../components/swipe/CompanyCard';
import { JobCardData, getStudentFeed, studentSwipeLeft, studentSwipeRight } from '../../services/swipeApi';

export default function StudentBrowse() {
  const [jobs, setJobs] = useState<JobCardData[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStudentFeed()
      .then((response) => setJobs(response.data.jobs))
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load your company feed.'))
      .finally(() => setLoading(false));
  }, []);

  async function removeJob(job: JobCardData, liked: boolean) {
    if (liked) await studentSwipeRight(job.id);
    else await studentSwipeLeft(job.id);
    setJobs((current) => current.filter((item) => item.id !== job.id));
  }

  if (loading) return <div className="loading"><div className="spinner" /> Loading company cards...</div>;

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Student Portal</span>
        <h1>Browse roles</h1>
        <p>Swipe through roles selected for your profile and criteria fit.</p>
      </header>
      {error && <div className="bias-inline-error">{error}</div>}
      <CardCarousel
        items={jobs}
        getKey={(job) => job.id}
        renderCard={(job, expanded, toggle) => <CompanyCard job={job} expanded={expanded} onToggle={toggle} />}
        onPass={(job) => removeJob(job, false)}
        onLike={(job) => removeJob(job, true)}
        emptyTitle="No more roles right now"
        emptyText="You have reached the end of your current feed."
      />
    </main>
  );
}
