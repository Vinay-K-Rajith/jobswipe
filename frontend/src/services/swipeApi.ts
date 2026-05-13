import api from './api';

export interface JobCardData {
  id: string;
  recruiter_id?: string;
  company_name: string;
  role_title: string;
  industry: string;
  location: string;
  remote_policy: 'on-site' | 'hybrid' | 'remote' | string;
  required_skills: string[];
  preferred_skills: string[];
  interview_timeline: string;
  mentorship: string;
  highlight_line: string;
  careers_url?: string;
  salary?: string;
  company_size?: string;
  candidate_level?: string;
  job_type?: string;
  phi_score: number;
  min_cgpa?: number;
  allowed_departments?: string[];
  grad_years_eligible?: number[];
  is_active?: boolean;
  created_at?: string;
}

export type BrowseTrack = 'internship' | 'full-time';

export interface StudentCardData {
  student_id: string;
  email?: string;
  full_name: string;
  department: string;
  degree: string;
  university: string;
  graduation_year: number;
  cgpa: number;
  skills: string[];
  top_projects: Array<{ title: string; description: string }>;
  coursework: string[];
  certifications: Array<{ name: string; issuer: string }>;
  availability: string;
  work_authorization: string;
  portfolio_url?: string;
  preference_summary?: string;
  profile_tags?: string[];
  highlight_line: string;
  phi_score: number;
  match_breakdown?: Record<string, number>;
  job_id?: string;
}

export interface MatchItem {
  id: string;
  student_id: string;
  recruiter_id: string;
  job_id: string;
  company_name?: string;
  role_title?: string;
  student_name?: string;
  department?: string;
  cgpa?: number;
  matched_at: string;
}

export interface RecruiterJobInput {
  role_title: string;
  industry: string;
  location: string;
  remote_policy: string;
  required_skills: string[];
  preferred_skills: string[];
  interview_timeline: string;
  mentorship: string;
  highlight_line: string;
  min_cgpa: number;
  allowed_departments: string[];
  grad_years_eligible: number[];
}

export interface RecruiterJobUpdateInput extends RecruiterJobInput {
  is_active: boolean;
}

export const getStudentFeed = (jobType?: BrowseTrack, limit = 20, offset = 0) =>
  api.get<{ jobs: JobCardData[] }>('/student/feed', { params: { job_type: jobType, limit, offset } });

export const getStudentInterested = () =>
  api.get<{ jobs: JobCardData[] }>('/student/interested');

export const getStudentMatches = () =>
  api.get<{ matches: MatchItem[] }>('/student/matches');

export const studentSwipeRight = (jobId: string) =>
  api.post<{ matched: boolean }>('/student/swipe/right', { job_id: jobId });

export const studentSwipeLeft = (jobId: string) =>
  api.post<{ passed: boolean }>('/student/swipe/left', { job_id: jobId });

export const getRecruiterFeed = (jobId?: string, preferenceType?: BrowseTrack, limit = 20, offset = 0) =>
  api.get<{ students: StudentCardData[] }>('/recruiter/feed', { params: { job_id: jobId, preference_type: preferenceType, limit, offset } });

export const getRecruiterInterested = () =>
  api.get<{ students: StudentCardData[] }>('/recruiter/interested');

export const getRecruiterMatches = () =>
  api.get<{ matches: MatchItem[] }>('/recruiter/matches');

export const recruiterSwipeRight = (studentId: string, jobId: string) =>
  api.post<{ matched: boolean }>('/recruiter/swipe/right', { student_id: studentId, job_id: jobId });

export const recruiterSwipeLeft = (studentId: string) =>
  api.post<{ passed: boolean }>('/recruiter/swipe/left', { student_id: studentId });

export const createRecruiterJob = (payload: RecruiterJobInput) =>
  api.post<JobCardData>('/recruiter/jobs', payload);

export const getRecruiterJobs = () =>
  api.get<{ jobs: JobCardData[] }>('/recruiter/jobs');

export const updateRecruiterJob = (jobId: string, payload: RecruiterJobUpdateInput) =>
  api.put<JobCardData>(`/recruiter/jobs/${jobId}`, payload);

export const setRecruiterJobStatus = (jobId: string, isActive: boolean) =>
  api.post<JobCardData>(`/recruiter/jobs/${jobId}/status`, { is_active: isActive });

export const deleteRecruiterJob = (jobId: string) =>
  api.post<{ deleted: boolean; job_id: string }>(`/recruiter/jobs/${jobId}/delete`);
