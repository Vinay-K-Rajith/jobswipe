import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

export default function RecruiterNavbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const active = (path: string) => location.pathname === path ? 'active' : '';

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/recruiter/browse" className="navbar-brand">JobSwipe Recruiter</Link>
        <div className="navbar-links">
          <Link to="/recruiter/browse" className={active('/recruiter/browse')}>Browse</Link>
          <Link to="/recruiter/interested" className={active('/recruiter/interested')}>Interested</Link>
          <Link to="/recruiter/matches" className={active('/recruiter/matches')}>Matches</Link>
          <Link to="/recruiter/post" className={active('/recruiter/post')}>Post Role</Link>
          <Link to="/recruiter/profile" className={active('/recruiter/profile')}>Profile</Link>
        </div>
        <div className="navbar-actions">
          <button className="btn-signup" onClick={() => { logout(); navigate('/login'); }} type="button">Logout</button>
        </div>
      </div>
    </nav>
  );
}
