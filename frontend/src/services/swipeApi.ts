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

export interface RejectionInsightWeakness {
  label: string;
  severity: 'high' | 'medium' | 'low' | string;
  detail: string;
}

export interface RejectionInsightSkill {
  skill: string;
  source: 'required' | 'preferred' | string;
  reason: string;
}

export interface RejectionImprovementAction {
  priority: number;
  category: string;
  type: string;
  title: string;
  description: string;
  actions: string[];
  timeline: string;
  difficulty: string;
}

export interface StudentRejectionInsight {
  id: string;
  student_id: string;
  recruiter_id?: string;
  job_id: string;
  created_at: string;
  company_name: string;
  role_title: string;
  reason_code: string;
  reason_label: string;
  reason_note?: string;
  headline: string;
  match_snapshot: {
    overall_score?: number;
    breakdown?: Record<string, number>;
    rank_position?: number;
    pool_size?: number;
  };
  competitive_weaknesses: RejectionInsightWeakness[];
  peer_comparison: Record<string, number>;
  criteria_snapshot: {
    required_skill_match_ratio?: number;
    preferred_skill_match_ratio?: number;
    missing_required_skills?: string[];
    hard_failures?: string[];
    soft_weaknesses?: string[];
  };
  skill_gap_focus: RejectionInsightSkill[];
  improvement_plan: RejectionImprovementAction[];
}

export interface StudentProfileSummary {
  basic_info: {
    name: string;
    personal_email?: string | null;
    college_email?: string | null;
    phone_number?: string | null;
    college_roll_number?: string | null;
    student_id: string;
    department?: string | null;
    current_year?: number | null;
    graduation_year?: number | null;
  };
  education: {
    class_10_marks?: number | null;
    class_10_board?: string | null;
    class_12_marks?: number | null;
    class_12_board?: string | null;
    college_name?: string | null;
    degree?: string | null;
    cgpa?: number | null;
    active_backlogs?: number | null;
    backlog_history?: number | null;
  };
  skills: Array<{
    name: string;
    proficiency: string;
    verified: boolean;
    category: string;
  }>;
  preferences: {
    looking_for?: string | null;
    preferred_roles: string[];
    preferred_locations: string[];
    remote_preference?: string | null;
    open_to_relocation: boolean;
  };
  resume_links: {
    resume_url?: string | null;
    linkedin_url?: string | null;
    github_url?: string | null;
    portfolio_url?: string | null;
    coding_profile_url?: string | null;
  };
  activity: {
    liked_companies: number;
    passed_roles: number;
    companies_interested: number;
    pending_decisions: number;
    matches: number;
    growth_insights: number;
  };
}

export interface StudentProfileUpdatePayload {
  full_name?: string | null;
  personal_email?: string | null;
  college_email?: string | null;
  phone_number?: string | null;
  register_number?: string | null;
  department?: string | null;
  branch?: string | null;
  college_name?: string | null;
  degree?: string | null;
  class_10_marks?: number | null;
  class_10_board?: string | null;
  class_12_marks?: number | null;
  class_12_board?: string | null;
  cgpa?: number | null;
  active_backlogs?: number | null;
  backlog_history?: number | null;
  year_of_study?: number | null;
  batch_year?: number | null;
  looking_for?: string | null;
  preferred_roles?: string[];
  preferred_locations?: string[];
  remote_preference?: string | null;
  open_to_relocation?: boolean;
  portfolio_url?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  coding_profile_url?: string | null;
}

export interface StudentProfileSkillsPayload {
  skills: Array<{
    name: string;
    proficiency: string;
  }>;
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

export const getStudentRejectionInsights = () =>
  api.get<{ insights: StudentRejectionInsight[] }>('/student/rejection-insights');

export const getStudentProfile = () =>
  api.get<StudentProfileSummary>('/student/profile');

export const updateStudentProfile = (studentId: string, payload: StudentProfileUpdatePayload) =>
  api.patch<{ message: string }>(`/profile/${studentId}`, payload);

export const updateStudentProfileSkills = (studentId: string, payload: StudentProfileSkillsPayload) =>
  api.put<{ message: string; count: number }>(`/profile/${studentId}/skills`, payload);

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

export const recruiterSwipeLeft = (studentId: string, jobId: string, reasonCode = 'selected_stronger_match', reasonNote?: string) =>
  api.post<{ passed: boolean }>('/recruiter/swipe/left', {
    student_id: studentId,
    job_id: jobId,
    reason_code: reasonCode,
    reason_note: reasonNote,
  });

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
