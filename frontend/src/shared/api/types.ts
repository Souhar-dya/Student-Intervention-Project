export type RiskCategory = "Low Risk" | "Medium Risk" | "High Risk";
export type PlanFollowed = "Fully followed" | "Partially followed" | "Not followed" | "Unknown";
export type ProgressTrend = "Improved" | "No clear change" | "Worsened" | "No new evidence";
export type FailureTrend = "Decreased" | "No change" | "Increased" | "Unknown";
export type FollowUpDecision = "Close ticket" | "Monitor" | "Escalate";

export interface AuthSession {
  token: string;
  token_type: "bearer" | string;
  username: string;
}

export interface StudentProfile {
  student_id?: string;
  parent_email?: string;
  school: string;
  age: number;
  attendance: number;
  failures: number;
  absences: number;
  study_time: number;
  previous_grade_average: number;
}

export interface FeatureContribution {
  feature: string;
  contribution: number;
}

export interface FactorInsight {
  feature: string;
  association: "success" | "failure" | string;
  strength: number;
  passed_average: number;
  at_risk_average: number;
  explanation: string;
}

export interface FactorInsightResponse {
  prompt: string;
  source_path: string;
  row_count: number;
  summary: string;
  answer: string;
  generated_by: "llm" | "deterministic" | string;
  factors: FactorInsight[];
}

export interface SearchFilters {
  school?: string;
  min_attendance?: number;
  max_attendance?: number;
  min_failures?: number;
  max_failures?: number;
}

export interface RetrievedCase {
  case_id: string;
  student_id: string;
  score: number;
  school: string;
  failures: number;
  absences: number;
  final_grade: number;
  case_text: string;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: RetrievedCase[];
}

export interface PredictionResponse {
  student_id?: string;
  risk_score: number;
  risk_category: RiskCategory;
  model_name: string;
  top_contributors: FeatureContribution[];
}

export interface RecommendationResponse {
  student_id?: string;
  risk_category: RiskCategory;
  recommendation: string;
  reasoning: string;
  evidence_case_ids: string[];
}

export interface FeedbackResponse {
  feedback_id: string;
  stored: boolean;
  message: string;
}

export interface JudgeScores {
  relevance: number;
  groundedness: number;
  consistency: number;
  usefulness: number;
  overall: number;
}

export interface EvaluationResponse {
  scores: JudgeScores;
  notes: string;
}

export interface ParentEmailResponse {
  eligible: boolean;
  sent: boolean;
  delivery_status: "sent" | "simulated" | "skipped" | string;
  recipient: string;
  subject: string;
  message: string;
}

export interface FollowUpAssessmentRequest {
  student: StudentProfile;
  current_risk_category: RiskCategory;
  current_risk_score: number;
  recommendation: string;
  advisor_note: string;
  weeks_since_plan: number;
  plan_followed: PlanFollowed;
  attendance_trend: ProgressTrend;
  marks_trend: ProgressTrend;
  failures_trend: FailureTrend;
}

export interface FollowUpAssessmentResponse {
  decision: FollowUpDecision;
  recommended_status: "Closed" | "Monitoring" | "Escalated" | string;
  escalation_target: string;
  rationale: string;
  next_steps: string;
  confidence: number;
  generated_by: "llm" | "deterministic" | string;
}

export interface FollowUpCaseEvent {
  event_id: string;
  event_type: string;
  title: string;
  note?: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface FollowUpCaseCreateRequest {
  student: StudentProfile;
  prediction: PredictionResponse;
  recommendation: string;
  recommendation_summary: string;
  evidence_case_ids: string[];
}

export interface FollowUpCaseUpdateRequest {
  note?: string;
  status?: string;
  escalation_target?: string;
  last_event?: string;
  plan_followed?: PlanFollowed;
  attendance_trend?: ProgressTrend;
  marks_trend?: ProgressTrend;
  failures_trend?: FailureTrend;
}

export interface FollowUpCaseResponse {
  case_id: string;
  student_id: string;
  student: StudentProfile;
  risk_category: RiskCategory;
  risk_score: number;
  model_name: string;
  recommendation: string;
  recommendation_summary: string;
  evidence_case_ids: string[];
  note: string;
  status: string;
  escalation_target: string;
  last_event: string;
  plan_followed: PlanFollowed;
  attendance_trend: ProgressTrend;
  marks_trend: ProgressTrend;
  failures_trend: FailureTrend;
  follow_up_decision?: string | null;
  follow_up_rationale?: string | null;
  follow_up_next_steps?: string | null;
  follow_up_confidence?: number | null;
  follow_up_generated_by?: string | null;
  follow_up_assessed_at?: string | null;
  closed_at?: string | null;
  created_at: string;
  updated_at: string;
  events: FollowUpCaseEvent[];
}

export interface InitializeStorageResponse {
  initialized: boolean;
  message: string;
}

export interface IngestionResult {
  source_path: string;
  imported: number;
  skipped: number;
  persisted: boolean;
}

export interface EmbeddingPipelineResult {
  embedded: number;
  uploaded: number;
  collection: string;
  warnings: string[];
}

export interface ModelMetric {
  model_name: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number | null;
}

export interface TrainingResult {
  source_path: string;
  best_model: string;
  artifact_path: string;
  metrics: ModelMetric[];
}
