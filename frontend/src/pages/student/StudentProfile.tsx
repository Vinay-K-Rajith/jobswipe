import { useAuthStore } from '../../store/authStore';

export default function StudentProfile() {
  const { userName, userEmail, userId } = useAuthStore();

  return (
    <main className="portal-page">
      <header className="portal-header">
        <span>Student Portal</span>
        <h1>Profile</h1>
        <p>Keep your student profile current so recommendations stay accurate.</p>
      </header>
      <section className="portal-form-card">
        <label>Name<input className="input" value={userName || ''} readOnly /></label>
        <label>Email<input className="input" value={userEmail || ''} readOnly /></label>
        <label>Student ID<input className="input" value={userId || ''} readOnly /></label>
        <p className="muted-text">Profile editing hooks into the existing student data model next; this view is ready for editable fields.</p>
      </section>
    </main>
  );
}
