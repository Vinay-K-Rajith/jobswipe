import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useDynamicNavbarClass } from './useDynamicNavbar';

export default function Navbar() {
  const location = useLocation();
  const { userRole, logout } = useAuthStore();
  const navbarClass = useDynamicNavbarClass();

  const isActive = (path: string) => location.pathname === path ? 'active' : '';

  return (
    <nav className={`navbar ${navbarClass}`}>
      <div className="navbar-inner">
        <div className="navbar-brand-container">
          <Link to="/" className="navbar-brand">
            JobSwipe AI
          </Link>
        </div>
        <div className="navbar-links">
          {userRole === 'admin' ? (
             <>
               <Link to="/" className={isActive('/')}>Overview</Link>
               <Link to="/students" className={isActive('/students')}>Students</Link>
               <Link to="/companies" className={isActive('/companies')}>Companies</Link>
               <Link to="/eligibility" className={isActive('/eligibility')}>Eligibility Engine</Link>
               <Link to="/ranking" className={isActive('/ranking')}>ML Ranked Shortlist</Link>
               <Link to="/bias" className={isActive('/bias')}>Bias Report</Link>
               <Link to="/feed-replay" className={isActive('/feed-replay')}>Feed Replay</Link>
             </>
          ) : (
            <>
               <Link to="/" className={isActive('/')}>My Profile</Link>
               <Link to="/opportunities" className={isActive('/opportunities')}>Opportunities</Link>
               <Link to="/improvement" className={isActive('/improvement')}>Improvement Plan</Link>
            </>
          )}
        </div>
        <div className="navbar-actions">
          <button onClick={logout} className="btn-signup">
             Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
