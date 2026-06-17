import type {
  AuthSession,
  EmbeddingPipelineResult,
  EvaluationResponse,
  FactorInsightResponse,
  FeedbackResponse,
  FollowUpAssessmentRequest,
  FollowUpAssessmentResponse,
  FollowUpCaseCreateRequest,
  FollowUpCaseResponse,
  FollowUpCaseUpdateRequest,
  IngestionResult,
  InitializeStorageResponse,
  ParentEmailResponse,
  PredictionResponse,
  RecommendationResponse,
  SearchFilters,
  SearchResponse,
  StudentProfile,
  TrainingResult,
} from "./types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const ATTENDANCE_WINDOW = 15;
const authTokenKey = "student-success-auth-token";
const authUserKey = "student-success-auth-user";

function setCookie(name: string, value: string, days: number): void {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${encodeURIComponent(name)}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[1]) : null;
}

function removeCookie(name: string): void {
  document.cookie = `${encodeURIComponent(name)}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax`;
}

export function getStoredAuthSession(): Pick<AuthSession, "token" | "username"> | null {
  const token = getCookie(authTokenKey);
  const username = getCookie(authUserKey);
  if (!token || !username) {
    return null;
  }
  return { token, username };
}

export function storeAuthSession(session: AuthSession): void {
  setCookie(authTokenKey, session.token, 7);
  setCookie(authUserKey, session.username, 7);
}

export function clearAuthSession(): void {
  removeCookie(authTokenKey);
  removeCookie(authUserKey);
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const token = getCookie(authTokenKey);
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (response.status === 401) {
    clearAuthSession();
    window.dispatchEvent(new Event("auth-expired"));
    throw new Error("Session expired");
  }

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<AuthSession> {
  return request<AuthSession>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function recommendIntervention(
  student: StudentProfile,
  query: string,
): Promise<RecommendationResponse> {
  return request<RecommendationResponse>("/recommend", {
    method: "POST",
    body: JSON.stringify({
      prediction: { student },
      search: {
        query,
        top_k: 5,
        filters: buildSimilarCaseFilters(student),
      },
    }),
  });
}

export function buildSimilarCaseFilters(student: StudentProfile): SearchFilters {
  return {
    school: student.school,
    min_attendance: Math.max(0, student.attendance - ATTENDANCE_WINDOW),
    max_attendance: Math.min(100, student.attendance + ATTENDANCE_WINDOW),
    min_failures: Math.max(0, student.failures - 1),
    max_failures: Math.min(4, student.failures + 1),
  };
}

export async function searchCases(
  query: string,
  filters: SearchFilters,
  topK = 5,
): Promise<SearchResponse> {
  return request<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK, filters }),
  });
}

export async function predictRisk(student: StudentProfile): Promise<PredictionResponse> {
  return request<PredictionResponse>("/predict", {
    method: "POST",
    body: JSON.stringify({ student }),
  });
}

export async function evaluateRecommendation(
  query: string,
  recommendation: string,
  evidenceCaseIds: string[],
): Promise<EvaluationResponse> {
  return request<EvaluationResponse>("/evaluate", {
    method: "POST",
    body: JSON.stringify({
      query,
      recommendation,
      evidence_case_ids: evidenceCaseIds,
    }),
  });
}

export async function submitFeedback(
  query: string,
  recommendation: string,
  rating: "useful" | "not_useful",
): Promise<FeedbackResponse> {
  return request<FeedbackResponse>("/feedback", {
    method: "POST",
    body: JSON.stringify({ query, recommendation, rating }),
  });
}

export async function sendParentEmail(
  student: StudentProfile,
  prediction: PredictionResponse,
  recommendation: string,
  parentEmail: string,
  subject: string,
  body: string,
): Promise<ParentEmailResponse> {
  return request<ParentEmailResponse>("/parent-email/send", {
    method: "POST",
    body: JSON.stringify({
      student,
      prediction,
      recommendation,
      parent_email: parentEmail,
      subject,
      body,
    }),
  });
}

export async function assessFollowUp(
  assessment: FollowUpAssessmentRequest,
): Promise<FollowUpAssessmentResponse> {
  return request<FollowUpAssessmentResponse>("/follow-up/assess", {
    method: "POST",
    body: JSON.stringify(assessment),
  });
}

export async function listFollowUpCases(): Promise<FollowUpCaseResponse[]> {
  return request<FollowUpCaseResponse[]>("/follow-up/cases", {
    method: "GET",
  });
}

export async function saveFollowUpCase(
  draft: FollowUpCaseCreateRequest,
): Promise<FollowUpCaseResponse> {
  return request<FollowUpCaseResponse>("/follow-up/cases", {
    method: "POST",
    body: JSON.stringify(draft),
  });
}

export async function updateFollowUpCase(
  caseId: string,
  changes: FollowUpCaseUpdateRequest,
  recordEvent = true,
): Promise<FollowUpCaseResponse> {
  const params = recordEvent ? "" : "?record_event=false";
  return request<FollowUpCaseResponse>(`/follow-up/cases/${encodeURIComponent(caseId)}${params}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export async function assessSavedFollowUpCase(caseId: string, directDecision?: string): Promise<FollowUpCaseResponse> {
  const params = directDecision ? `?direct_decision=${encodeURIComponent(directDecision)}` : "";
  return request<FollowUpCaseResponse>(`/follow-up/cases/${encodeURIComponent(caseId)}/assess${params}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function summarizeFactors(prompt: string, path?: string): Promise<FactorInsightResponse> {
  return request<FactorInsightResponse>("/insights/factors", {
    method: "POST",
    body: JSON.stringify({ prompt, path }),
  });
}

export async function initializeStorage(): Promise<InitializeStorageResponse> {
  return request<InitializeStorageResponse>("/admin/storage/init", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function ingestDataset(path: string): Promise<IngestionResult> {
  return request<IngestionResult>("/admin/ingest", {
    method: "POST",
    body: JSON.stringify({ path, persist: true }),
  });
}

export async function buildEmbeddings(limit = 1000): Promise<EmbeddingPipelineResult> {
  return request<EmbeddingPipelineResult>("/admin/embeddings/build", {
    method: "POST",
    body: JSON.stringify({ limit }),
  });
}

export async function trainModels(path: string): Promise<TrainingResult> {
  return request<TrainingResult>("/admin/models/train", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}
