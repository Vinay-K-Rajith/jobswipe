import api from './api';

export interface SessionSummary {
  id: string;
  target_role: string;
  target_domain?: string | null;
  seniority: string;
  interview_stage: string;
  status: 'pre_session' | 'active' | 'completed';
  phase: string;
  self_rating?: string | null;
  created_at: string;
  completed_at?: string | null;
  strengths: string[];
  risks: string[];
  blind_spots: string[];
  total_questions: number;
  estimated_minutes: number;
  current_question?: string | null;
  current_competency?: string | null;
}

export interface CreateSessionPayload {
  target_role: string;
  seniority?: string;
  target_domain?: string;
  interview_stage?: string;
  resume_text?: string;
}

export interface StartResponse {
  session: SessionSummary;
  first_question: string | null;
  question_number: number;
  total_questions: number;
}

export interface AnswerResponse {
  interviewer_turn: string | null;
  is_follow_up?: boolean;
  competency?: string | null;
  question_number?: number;
  total_questions?: number;
  done: boolean;
}

export interface PerQuestionFeedback {
  question: string;
  competency: string;
  what_happened: string;
  what_worked: string;
  what_was_missing: string;
  reconstructed_answer: string;
  filler_word_count?: number;
  answer_word_count?: number;
  answer_too_long?: boolean;
}

export interface Feedback {
  session_id: string;
  overall_summary: string;
  headline_takeaway: string;
  per_question_feedback: PerQuestionFeedback[];
  recurring_patterns: string[];
  next_session_suggestion: string;
}

export const createSession = (payload: CreateSessionPayload) =>
  api.post<SessionSummary>('/interview/sessions', payload);

export const listSessions = () =>
  api.get<{ sessions: SessionSummary[] }>('/interview/sessions');

export const getSession = (id: string) =>
  api.get<SessionSummary>(`/interview/sessions/${id}`);

export const startInterview = (id: string) =>
  api.post<StartResponse>(`/interview/sessions/${id}/start`);

export const submitAnswer = (id: string, text: string) =>
  api.post<AnswerResponse>(`/interview/sessions/${id}/answer`, { text });

export const completeSession = (id: string) =>
  api.post<Feedback>(`/interview/sessions/${id}/complete`);

export const getFeedback = (id: string) =>
  api.get<Feedback>(`/interview/feedback/${id}`);

export interface TranscriptTurn {
  speaker: 'interviewer' | 'candidate';
  content: string;
  turn_index: number;
}

export const getTranscript = (id: string) =>
  api.get<{ turns: TranscriptTurn[] }>(`/interview/sessions/${id}/transcript`);

export const rateSession = (id: string, self_rating: 'better' | 'same' | 'harder') =>
  api.post<{ success: boolean }>(`/interview/sessions/${id}/rating`, { self_rating });

export const transcribeAudio = (blob: Blob) => {
  const form = new FormData();
  form.append('file', blob, 'answer.webm');
  return api.post<{ text: string }>('/interview/transcribe', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
