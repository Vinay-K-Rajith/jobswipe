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
  ranker_loaded: boolean;
  skill_rec_loaded: boolean;
  bias_report_available: boolean;
}

// ── ML Types ────────────────────────────────────────────────
export interface RankedStudent {
  rank: number;
  student_id: string;
  full_name: string;
  department: string;
  cgpa: number;
  rank_score: number;
  dept_eligible: boolean;
}

export interface RankedShortlist {
  company_id: string;
  company_name: string;
  tier: string;
  total_students: number;
  top_k: number;
  shortlist: RankedStudent[];
}

export interface SkillRecommendation {
  skill: string;
  predicted_gain: number;
}

export interface SkillGapResult {
  student_id: string;
  full_name: string;
  department: string;
  current_skill_count: number;
  recommendations: SkillRecommendation[];
  model: string;
}

export interface BiasCompany {
  company_id: string;
  company_name: string;
  tier: string;
  pool_pass_rate: number;
  gender_disparity: number;
  gender_p_value: number;
  gender_flagged: boolean;
  gender_pass_rates: Record<string, number>;
  dept_disparity: number;
  top_bias_criterion: string;
}

export interface BiasReport {
  summary: {
    n_companies: number;
    n_flagged: number;
    flag_rate: number;
    threshold: number;
    significance: number;
    student_pool_size: number;
    gender_pool_dist: Record<string, number>;
  };
  flagged_companies: Array<{
    company_id: string;
    company_name: string;
    tier: string;
    disparity: number;
    p_value: number;
    pass_rates: Record<string, number>;
    top_bias_criterion: string;
  }>;
  all_companies: BiasCompany[];
}

export interface BiasSimulationPoint {
  threshold: number;
  total_eligible: number;
  female_eligible: number;
  male_eligible: number;
  non_binary_eligible: number;
  gender_disparity: number;
  p_value: number;
  pass_rates: Record<string, number>;
}

export interface BiasSimulationResult {
  company_id: string;
  company_name: string;
  criterion: string;
  current_threshold: number;
  current_disparity: number;
  current_pool_size: number;
  sweep: BiasSimulationPoint[];
  recommended_threshold: number | null;
  recommended_result: BiasSimulationPoint | null;
}

export interface BiasRecommendationPayload {
  company_id: string;
  criterion: string;
  current_threshold?: string | number | null;
  recommended_threshold?: string | number | null;
  current_disparity?: number | null;
  projected_disparity?: number | null;
  current_pool_size?: number | null;
  projected_pool_size?: number | null;
  status?: 'proposed' | 'accepted' | 'rejected' | 'implemented';
  recommendation_type?: 'threshold' | 'substitution';
  simulation_payload?: Record<string, any> | null;
}

export interface SavedBiasRecommendation {
  id: number;
  company_id: string;
  criterion: string;
  current_threshold?: string | number | null;
  recommended_threshold?: string | number | null;
  current_disparity?: number | null;
  projected_disparity?: number | null;
  current_pool_size?: number | null;
  projected_pool_size?: number | null;
  status: 'proposed' | 'accepted' | 'rejected' | 'implemented';
  recommendation_type: 'threshold' | 'substitution';
  simulation_payload?: Record<string, any> | null;
  created_at: string;
  persistence_mode: 'supabase' | 'local';
}

export interface BiasRecommendationListResponse {
  company_id?: string | null;
  recommendations: SavedBiasRecommendation[];
  persistence_mode: 'supabase' | 'local';
}

export interface BiasDriver {
  criterion: string;
  baseline_disparity: number;
  disparity_without_criterion: number;
  disparity_reduction: number;
  pool_size_without_criterion: number;
}

export interface CounterfactualCandidate {
  candidate_id: string;
  description: string;
  confidence: 'high' | 'medium' | 'low';
  composite_score: number;
  current_rule: {
    criterion: string;
    threshold: string | number;
    gender_disparity: number;
    pool_size: number;
  };
  alternative_rule: {
    criterion: string;
    threshold: string | number;
    label: string;
    gender_disparity: number;
    pool_size: number;
    p_value: number;
    performance_preservation_score: number;
    pool_similarity: number;
  };
  spec: {
    remove_criterion: string;
    substitution: {
      kind: string;
      value: string | number;
    };
  };
}

export interface CounterfactualRulesResult {
  company_id: string;
  company_name: string;
  drivers: BiasDriver[];
  top_driver: string;
  current_metrics: {
    pool_size: number;
    gender_disparity: number;
    p_value: number;
  };
  candidates: CounterfactualCandidate[];
}

export interface SubstitutionPreviewResult {
  company_id: string;
  newly_eligible_count: number;
  dropped_count: number;
  grouped: Array<{
    department: string;
    gender: string;
    count: number;
  }>;
  students: Array<{
    student_id: string;
    full_name: string;
    department: string;
    gender: string;
    cgpa: number;
  }>;
}

export interface FairnessVariantStudent {
  student_id: string;
  full_name: string;
  department: string;
  cgpa: number;
  score: number;
}

export interface FairnessVariant {
  key: 'baseline' | 'champion' | 'tightened';
  label: string;
  available: boolean;
  detail?: string;
  artifact_path?: string;
  accuracy?: number;
  f1?: number;
  delta_dp?: number;
  delta_eo?: number;
  shortlist_overlap?: number;
  shortlist?: FairnessVariantStudent[];
}

export interface MLFairnessComparison {
  company_id: string;
  reference_shortlist: string[];
  variants: FairnessVariant[];
}

export interface RetrainConstrainedResponse {
  company_id: string;
  epsilon: number;
  accuracy: number;
  f1: number;
  delta_dp: number;
  delta_eo: number;
  trained_at: string;
  triggered_by: string;
  training_time_seconds: number;
  artifact_path: string;
}

export interface FairnessHistoryPoint {
  id?: number;
  company_id: string;
  epsilon: number;
  accuracy: number;
  f1: number;
  delta_dp: number;
  delta_eo: number;
  trained_at: string;
  triggered_by: string;
}

export interface FairnessHistoryResponse {
  company_id: string;
  history: FairnessHistoryPoint[];
}

export interface SkillDeficit {
  skill: string;
  students_with_skill: number;
  missing_students: number;
  missing_share: number;
  coverage_share: number;
  company_demand: number;
  severity: string;
}

export interface SkillDeficitReport {
  total_students: number;
  deficits: SkillDeficit[];
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

export const getSkillDeficits = (limit = 8) =>
  api.get<SkillDeficitReport>('/api/skill-deficits', { params: { limit } });

// ── ML API Methods ──────────────────────────────────────────
export const getRankedShortlist = (companyId: string, topK = 20) =>
  api.get<RankedShortlist>(`/api/ml/ranked-shortlist/${companyId}`, { params: { top_k: topK } });

export const getSkillGap = (studentId: string, topK = 5) =>
  api.get<SkillGapResult>(`/api/ml/skill-gap/${studentId}`, { params: { top_k: topK } });

export const getBiasReport = (flaggedOnly = false) =>
  api.get<BiasReport>('/api/ml/bias-report', { params: { flagged_only: flaggedOnly } });

export const simulateBiasFix = (companyId: string, criterion: string) =>
  api.post<BiasSimulationResult>('/api/bias/simulate-fix', {
    company_id: companyId,
    criterion,
  });

export const saveBiasRecommendation = (payload: BiasRecommendationPayload) =>
  api.post<SavedBiasRecommendation>('/api/bias/recommendations', payload);

export const getBiasRecommendations = (companyId?: string) =>
  api.get<BiasRecommendationListResponse>('/api/bias/recommendations', { params: { company_id: companyId } });

export const getCounterfactualRules = (companyId: string) =>
  api.post<CounterfactualRulesResult>('/api/bias/counterfactual-rules', {
    company_id: companyId,
  });

export const previewSubstitution = (companyId: string, spec: CounterfactualCandidate['spec']) =>
  api.post<SubstitutionPreviewResult>('/api/bias/preview-substitution', {
    company_id: companyId,
    remove_criterion: spec.remove_criterion,
    substitution: spec.substitution,
  });

export const getMLFairnessComparison = (companyId: string) =>
  api.get<MLFairnessComparison>('/api/bias/ml-fairness-comparison', { params: { company_id: companyId } });

export const retrainConstrainedModel = (companyId: string, epsilon: number, triggeredBy = 'admin-dashboard') =>
  api.post<RetrainConstrainedResponse>('/api/bias/retrain-constrained', {
    company_id: companyId,
    epsilon,
    triggered_by: triggeredBy,
  });

export const getModelFairnessHistory = (companyId: string) =>
  api.get<FairnessHistoryResponse>(`/api/bias/model-fairness-history/${companyId}`);

export default api;
