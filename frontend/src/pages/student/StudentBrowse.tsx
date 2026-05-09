import { useEffect, useState } from 'react';
import { IconFileCheck, IconUpload } from '@tabler/icons-react';
import CardCarousel from '../../components/swipe/CardCarousel';
import CompanyCard from '../../components/swipe/CompanyCard';
import { uploadStudentResume } from '../../services/api';
import { JobCardData, getStudentFeed, studentSwipeLeft, studentSwipeRight } from '../../services/swipeApi';
import { useAuthStore } from '../../store/authStore';

export default function StudentBrowse() {
  const studentId = useAuthStore((state) => state.userId);
  const [jobs, setJobs] = useState<JobCardData[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

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

  async function handleResumeUpload(file?: File) {
    if (!file) return;
    if (!studentId) {
      setUploadMessage({ type: 'error', text: 'Your student session is missing. Please log in again.' });
      return;
    }
    if (file.type && file.type !== 'application/pdf') {
      setUploadMessage({ type: 'error', text: 'Please choose a PDF resume.' });
      return;
    }

    setUploading(true);
    setUploadMessage(null);
    try {
      await uploadStudentResume(studentId, file);
      setUploadMessage({
        type: 'success',
        text: `Resume parsed and profile updated. CGPA, skills, projects, certifications, internships, and research details were synced where found.`,
      });
      getStudentFeed()
        .then((response) => setJobs(response.data.jobs))
        .catch(() => undefined);
    } catch (err: any) {
      setUploadMessage({
        type: 'error',
        text: err?.response?.data?.detail || 'Resume upload failed.',
      });
    } finally {
      setUploading(false);
    }
  }

  if (loading) return <div className="loading"><div className="spinner" /> Loading company cards...</div>;

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Student Portal</span>
        <h1>Browse roles</h1>
        <p>Swipe through roles selected for your profile and criteria fit.</p>
      </header>
      <section className="resume-upload-panel">
        <div>
          <span className="bento-eyebrow"><IconFileCheck size={15} /> Resume profile</span>
          <p>Upload your latest PDF resume to refresh your skills, projects, certifications, internships, and research profile.</p>
        </div>
        <label className={`resume-upload-button ${uploading ? 'disabled' : ''}`}>
          <IconUpload size={16} />
          <span>{uploading ? 'Parsing...' : 'Upload resume'}</span>
          <input
            type="file"
            accept="application/pdf,.pdf"
            disabled={uploading}
            onChange={(event) => {
              handleResumeUpload(event.target.files?.[0]);
              event.currentTarget.value = '';
            }}
          />
        </label>
      </section>
      {uploadMessage && (
        <section className={`resume-upload-status ${uploadMessage.type}`}>
          <IconFileCheck size={17} />
          <span>{uploadMessage.text}</span>
        </section>
      )}
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
