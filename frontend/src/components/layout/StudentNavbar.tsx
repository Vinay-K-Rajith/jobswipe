import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

interface StudentNavbarProps {
  interestedCount?: number;
}

export default function StudentNavbar({ interestedCount = 0 }: StudentNavbarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const active = (path: string) => location.pathname === path ? 'active' : '';

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/student/browse" className="navbar-brand">JobSwipe Student</Link>
        <div className="navbar-links">
          <Link to="/student/browse" className={active('/student/browse')}>Browse</Link>
          <Link to="/student/interested" className={active('/student/interested')}>
            Interested {interestedCount > 0 && <span className="nav-badge">{interestedCount}</span>}
          </Link>
          <Link to="/student/matches" className={active('/student/matches')}>Matches</Link>
          <Link to="/student/rejections" className={active('/student/rejections')}>Rejection Insights</Link>
          <Link to="/student/profile" className={active('/student/profile')}>Profile</Link>
        </div>
        <div className="navbar-actions">
          <button className="btn-signup" onClick={() => { logout(); navigate('/login'); }} type="button">Logout</button>
        </div>
      </div>
    </nav>
  );
}
