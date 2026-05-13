import { useEffect, useState } from 'react';
import { IconFileCheck, IconUpload } from '@tabler/icons-react';
import CardCarousel from '../../components/swipe/CardCarousel';
import CompanyCard from '../../components/swipe/CompanyCard';
import { uploadStudentResume } from '../../services/api';
import { BrowseTrack, JobCardData, getStudentFeed, studentSwipeLeft, studentSwipeRight } from '../../services/swipeApi';
import { useAuthStore } from '../../store/authStore';

export default function StudentBrowse() {
  const studentId = useAuthStore((state) => state.userId);
  const [jobs, setJobs] = useState<JobCardData[]>([]);
  const [track, setTrack] = useState<BrowseTrack>('internship');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  async function loadFeed() {
    const response = await getStudentFeed(track);
    setJobs(response.data.jobs);
  }

  useEffect(() => {
    setLoading(true);
    loadFeed()
      .catch((err) => setError(err?.response?.data?.detail || 'Could not load your company feed.'))
      .finally(() => setLoading(false));
  }, [track]);

  async function removeJob(job: JobCardData, liked: boolean) {
    if (liked) await studentSwipeRight(job.id);
    else await studentSwipeLeft(job.id);
    const remaining = jobs.filter((item) => item.id !== job.id);
    setJobs(remaining);
    if (!remaining.length) {
      try {
        await loadFeed();
      } catch {
        // Keep the empty state if the refresh fails.
      }
    }
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
      loadFeed().catch(() => undefined);
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
      <div className="tier-tabs browse-track-tabs">
        <button type="button" className={track === 'internship' ? 'active' : ''} onClick={() => setTrack('internship')}>Internships</button>
        <button type="button" className={track === 'full-time' ? 'active' : ''} onClick={() => setTrack('full-time')}>Full-time</button>
      </div>
      <section className="resume-upload-panel student-browse-resume-panel">
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
        <section className={`resume-upload-status student-browse-resume-status ${uploadMessage.type}`}>
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
        emptyTitle={`No more ${track === 'internship' ? 'internships' : 'full-time roles'} right now`}
        emptyText={`You have reached the end of your current ${track === 'internship' ? 'internship' : 'full-time'} feed.`}
      />
    </main>
  );
}
