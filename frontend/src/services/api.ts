import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// --- Types ---
export interface Student {
  student_id: string;
  full_name: string;
  department: string;
  '10th_marks': number;
  '10th_board': string;
  '12th_marks': number;
  '12th_board': string;
  cgpa: number;
  backlogs_history: number;
  active_backlogs: number;
  year_of_study: number;
  features?: Record<string, number>;
  skill_list?: string[];
}

export interface Company {
  company_id: string;
  company_name: string;
  industry: string;
  tier: string;
  min_cgpa: number;
  min_10th: number;
  min_12th: number;
  max_active_backlogs: number;
  allowed_departments: string;
  required_skills: string;
  preferred_skills: string;
  min_internship_months: number;
  internship_tier_preference: string;
  min_projects: number;
  project_complexity_min: string;
  requires_research_paper: boolean;
  cert_tier_required: string;
  role_offered: string;
  package_lpa: number;
  bond_years: number;
}

export interface ScorecardItem {
  passed: boolean;
  message: string;
  is_hard: boolean;
}

export interface EligibilityResult {
  student_id: string;
  company_id: string;
  criteria_eligible: boolean;
  ml_result?: { eligible: boolean; score: number; message: string };
  scorecard: Record<string, ScorecardItem>;
  explanation: string;
  improvement_plan?: {
    company_name: string;
    total_suggestions: number;
    hard_blockers: number;
    soft_improvements: number;
    suggestions: Array<{
      priority: number;
      category: string;
      type: string;
      title: string;
      description: string;
      actions: string[];
      timeline: string;
      difficulty: string;
    }>;
  };
}

export interface BatchResult {
  student_id: string;
  full_name: string;
  department: string;
  cgpa: number;
  eligible: boolean;
  score: number;
  hard_pass: boolean;
  hard_failures: string[];
}

export interface BatchResponse {
  company_id: string;
  company_name: string;
  total_checked: number;
  eligible_count: number;
  ineligible_count: number;
  results: BatchResult[];
}

export interface ModelMetrics {
  model_loaded: boolean;
  metrics: {
    accuracy: number;
    precision: number;
    recall: number;
    f1: number;
  };
  fairness?: Record<string, any>;
}

export interface Stats {
  total_students: number;
  total_companies: number;
  departments: Record<string, number>;
  avg_cgpa: number;
  cgpa_distribution: Record<string, number>;
  company_tiers: Record<string, number>;
  model_loaded: boolean;
}

// --- API Methods ---
export const getStudents = (params?: { department?: string; min_cgpa?: number; limit?: number; offset?: number }) =>
  api.get<{ total: number; students: Student[] }>('/api/students', { params });

export const getStudent = (id: string) =>
  api.get<Student>(`/api/students/${id}`);

export const getCompanies = (params?: { tier?: string; industry?: string }) =>
  api.get<{ total: number; companies: Company[] }>('/api/companies', { params });

export const getCompany = (id: string) =>
  api.get<Company>(`/api/companies/${id}`);

export const checkEligibility = (studentId: string, companyId: string) =>
  api.post<EligibilityResult>('/api/eligibility/check', {
    student_id: studentId,
    company_id: companyId,
  });

export const batchCheckEligibility = (companyId: string, studentIds?: string[]) =>
  api.post<BatchResponse>('/api/eligibility/batch', {
    company_id: companyId,
    student_ids: studentIds,
  });

export const getModelMetrics = () =>
  api.get<ModelMetrics>('/api/model/metrics');

export const getStats = () =>
  api.get<Stats>('/api/stats');

export default api;
