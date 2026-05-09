export type UserRole = 'admin' | 'student' | 'recruiter';

export const ROLE_DOMAINS = {
  student: (import.meta.env.VITE_STUDENT_EMAIL_DOMAIN || 'srmist.edu.in').toLowerCase(),
  admin: (import.meta.env.VITE_ADMIN_EMAIL_DOMAIN || 'placement.srmist.edu.in').toLowerCase(),
};

export function emailDomain(email: string) {
  return email.trim().toLowerCase().split('@')[1] || '';
}

export function roleFromEmail(email: string): UserRole {
  const domain = emailDomain(email);
  if (domain === ROLE_DOMAINS.admin) return 'admin';
  if (domain === ROLE_DOMAINS.student) return 'student';
  return 'recruiter';
}

export function homeForRole(role: UserRole | null) {
  if (role === 'admin') return '/dashboard';
  if (role === 'student') return '/student/browse';
  if (role === 'recruiter') return '/recruiter/browse';
  return '/login';
}
