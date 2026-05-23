import { FormEvent, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { ROLE_DOMAINS, homeForRole, roleFromEmail } from '../config/roles';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [isSignup, setIsSignup] = useState(false);
  const [form, setForm] = useState({
    email: '',
    password: '',
    name: '',
    register_number: '',
    company_name: '',
    company_domain: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const inferredRole = useMemo(() => roleFromEmail(form.email), [form.email]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const role = roleFromEmail(form.email);
      if (isSignup) {
        if (role === 'student') {
          await api.post('/auth/student/signup', {
            name: form.name,
            register_number: form.register_number,
            email: form.email,
            password: form.password,
          });
        } else if (role === 'recruiter') {
          await api.post('/auth/recruiter/signup', {
            name: form.name,
            company_name: form.company_name,
            company_domain: form.company_domain,
            email: form.email,
            password: form.password,
          });
        } else {
          throw new Error('Admin accounts are issued by the placement team. Please sign in instead.');
        }
      }

      const endpoint = role === 'admin' ? '/auth/admin/login' : `/auth/${role}/login`;
      const response = await api.post(endpoint, { email: form.email, password: form.password });
      const data = response.data;
      const userId = data.student_id || data.recruiter_id || data.admin_id || data.user_id;
      const name = data.name || data.company_name || 'JobSwipe user';
      setAuth(role, userId, name, form.email, data.access_token);
      navigate(homeForRole(role), { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Authentication failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <span className="dashboard-kicker">JobSwipe AI</span>
        <h1>{isSignup ? 'Create your account' : 'Welcome back'}</h1>
        <p>Use your email domain to enter the right portal automatically.</p>
        <form onSubmit={submit} className="login-form">
          <label>Email<input className="input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
          <label>Password<input className="input" type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          {isSignup && inferredRole !== 'admin' && (
            <>
              <label>Name<input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
              {inferredRole === 'student' ? (
                <label>Register number<input className="input" required pattern="RA\d{13}" placeholder="RA2311047010209" value={form.register_number} onChange={(e) => setForm({ ...form, register_number: e.target.value })} /></label>
              ) : (
                <>
                  <label>Company name<input className="input" required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} /></label>
                  <label>Company domain / website<input className="input" required value={form.company_domain} onChange={(e) => setForm({ ...form, company_domain: e.target.value })} /></label>
                </>
              )}
            </>
          )}
          <div className="role-preview">
            <strong>{inferredRole}</strong>
            <span>Student: studentname@{ROLE_DOMAINS.student} · Company: companyname@companyname.com · Admin: admin@{ROLE_DOMAINS.admin} · Password: Test123</span>
          </div>
          {error && <div className="bias-inline-error">{error}</div>}
          <button className="btn btn-primary btn-lg" type="submit" disabled={loading}>
            {loading ? 'Please wait...' : isSignup ? 'Sign up and continue' : 'Sign in'}
          </button>
        </form>
        <button className="login-toggle" type="button" onClick={() => setIsSignup((value) => !value)}>
          {isSignup ? 'Already have an account? Sign in' : 'New here? Sign up'}
        </button>
      </section>
    </main>
  );
}
