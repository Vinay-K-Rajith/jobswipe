import { useAuthStore } from '../../store/authStore';

export default function RecruiterProfile() {
  const { userName, userEmail, userId } = useAuthStore();

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Recruiter Portal</span>
        <h1>Company profile</h1>
        <p>Manage the recruiter identity attached to your postings.</p>
      </header>
      <section className="portal-form-card">
        <label>Name<input className="input" value={userName || ''} readOnly /></label>
        <label>Email<input className="input" value={userEmail || ''} readOnly /></label>
        <label>Recruiter ID<input className="input" value={userId || ''} readOnly /></label>
        <p className="muted-text">Editable company profile fields can be added here without changing the swipe flow.</p>
      </section>
    </main>
  );
}
