import { create } from 'zustand';

type UserRole = 'admin' | 'student' | 'recruiter' | null;

interface AuthState {
  userRole: UserRole;
  userId: string | null;
  userName: string | null;
  userEmail: string | null;
  accessToken: string | null;
  studentId: string | null;
  setAuth: (role: AuthState['userRole'], userId: string, userName: string, userEmail: string, token: string) => void;
  setRole: (role: UserRole) => void;
  setStudentId: (id: string | null) => void;
  logout: () => void;
}

function readStorage(key: string) {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(key);
}

export const useAuthStore = create<AuthState>((set) => ({
  userRole: readStorage('jobswipe_role') as UserRole,
  userId: readStorage('jobswipe_user_id'),
  userName: readStorage('jobswipe_user_name'),
  userEmail: readStorage('jobswipe_user_email'),
  accessToken: readStorage('jobswipe_token'),
  studentId: readStorage('jobswipe_role') === 'student' ? readStorage('jobswipe_user_id') : null,
  setAuth: (role, userId, userName, userEmail, token) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('jobswipe_role', role || '');
      window.localStorage.setItem('jobswipe_user_id', userId);
      window.localStorage.setItem('jobswipe_user_name', userName);
      window.localStorage.setItem('jobswipe_user_email', userEmail);
      window.localStorage.setItem('jobswipe_token', token);
    }
    set({
      userRole: role,
      userId,
      userName,
      userEmail,
      accessToken: token,
      studentId: role === 'student' ? userId : null,
    });
  },
  setRole: (role) => {
    if (typeof window !== 'undefined') {
      if (role) window.localStorage.setItem('jobswipe_role', role);
      else window.localStorage.removeItem('jobswipe_role');
    }
    set({ userRole: role });
  },
  setStudentId: (id) => set({ studentId: id, userId: id }),
  logout: () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('jobswipe_role');
      window.localStorage.removeItem('jobswipe_user_id');
      window.localStorage.removeItem('jobswipe_user_name');
      window.localStorage.removeItem('jobswipe_user_email');
      window.localStorage.removeItem('jobswipe_token');
    }
    set({ userRole: null, userId: null, userName: null, userEmail: null, accessToken: null, studentId: null });
  },
}));
