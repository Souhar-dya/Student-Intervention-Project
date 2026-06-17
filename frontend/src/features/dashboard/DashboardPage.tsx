import { useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  LoaderCircle,
  Mail,
  Search,
  Send,
  ShieldAlert,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "../../components/ui/Button";
import {
  assessSavedFollowUpCase,
  buildSimilarCaseFilters,
  evaluateRecommendation,
  listFollowUpCases,
  predictRisk,
  recommendIntervention,
  saveFollowUpCase,
  searchCases,
  sendParentEmail,
  submitFeedback,
  summarizeFactors,
  updateFollowUpCase,
} from "../../shared/api/client";
import type {
  EvaluationResponse,
  FactorInsightResponse,
  FeatureContribution,
  FollowUpCaseEvent,
  FollowUpCaseResponse,
  FollowUpCaseUpdateRequest,
  ParentEmailResponse,
  PlanFollowed,
  PredictionResponse,
  RecommendationResponse,
  RetrievedCase,
  RiskCategory,
  StudentProfile,
} from "../../shared/api/types";

type StepId = "student" | "analysis" | "evaluate" | "follow-up" | "factors";
type ActionId =
  | "evaluate"
  | "factors"
  | "feedback-not-useful"
  | "feedback-useful"
  | "follow-up"
  | "full-analysis"
  | "load-follow-up"
  | "parent-email"
  | "predict"
  | "recommend"
  | "search"
  | "save-follow-up";
type NumericStudentField =
  | "age"
  | "attendance"
  | "failures"
  | "previous_grade_average"
  | "study_time";
type StudentDraft = Omit<StudentProfile, NumericStudentField> & Record<NumericStudentField, number | "">;
type ParentMailDraft = {
  parent_email: string;
  subject: string;
  body: string;
};
const caseStatuses = ["Open", "Monitoring", "Escalated", "Supported", "Closed"] as const;
const escalationTargets = [
  "Class teacher",
  "Academic advisor",
  "Counsellor",
  "Parent / guardian",
  "Attendance team",
] as const;
const planFollowedOptions: PlanFollowed[] = [
  "Fully followed",
  "Partially followed",
  "Not followed",
  "Unknown",
];
const progressTrendOptions: ProgressTrend[] = [
  "Improved",
  "No clear change",
  "Worsened",
  "No new evidence",
];
const failureTrendOptions: FailureTrend[] = ["Decreased", "No change", "Increased", "Unknown"];
type CaseStatus = (typeof caseStatuses)[number];
type EscalationTarget = (typeof escalationTargets)[number];
type StudentCaseRecord = {
  id: string;
  student_id: string;
  school: string;
  parent_email?: string;
  risk_category: RiskCategory;
  risk_score: number;
  model_name: string;
  age: number;
  attendance: number;
  failures: number;
  study_time: number;
  previous_grade_average: number;
  note: string;
  status: CaseStatus;
  escalation_target: EscalationTarget;
  last_event: string;
  plan_followed: PlanFollowed;
  attendance_trend: ProgressTrend;
  marks_trend: ProgressTrend;
  failures_trend: FailureTrend;
  follow_up_decision?: string;
  follow_up_rationale?: string;
  follow_up_next_steps?: string;
  follow_up_confidence?: number;
  follow_up_generated_by?: string;
  follow_up_assessed_at?: string;
  closed_at?: string;
  recommendation_text: string;
  recommendation_summary: string;
  evidence_case_ids: string[];
  events: FollowUpCaseEvent[];
  created_at: string;
  updated_at: string;
};

const defaultStudent: StudentDraft = {
  student_id: "student-demo-001",
  parent_email: "parent@example.edu",
  school: "GP",
  age: 17,
  attendance: 62,
  failures: 2,
  absences: 38,
  study_time: 1,
  previous_grade_average: 8,
};

const steps: Array<{ id: StepId; label: string; caption: string }> = [
  { id: "student", label: "Student", caption: "Case intake" },
  { id: "analysis", label: "Analysis", caption: "Risk and evidence" },
  { id: "evaluate", label: "Evaluate", caption: "Judge and feedback" },
  { id: "follow-up", label: "Follow Up", caption: "Tickets and review" },
  { id: "factors", label: "Factors", caption: "Success signals" },
];

const numericFields: Array<[NumericStudentField, string, number, number]> = [
  ["attendance", "Attendance %", 0, 100],
  ["failures", "Failures", 0, 4],
  ["study_time", "Study time", 1, 4],
  ["previous_grade_average", "Prev. avg", 0, 20],
  ["age", "Age", 15, 22],
];
const riskBoardOrder: RiskCategory[] = ["High Risk", "Medium Risk"];

export function DashboardPage() {
  const [activeStep, setActiveStep] = useState<StepId>("student");
  const [student, setStudent] = useState<StudentDraft>(defaultStudent);
  const [query, setQuery] = useState("How should I support this student?");
  const [factorPrompt, setFactorPrompt] = useState("What factors influence student success or failure the most?");
  const [datasetPath, setDatasetPath] = useState("../data/processed/student-merged.csv");
  const [status, setStatus] = useState("Ready");
  const [cases, setCases] = useState<RetrievedCase[]>([]);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationResponse | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [judged, setJudged] = useState(false);
  const [parentEmailResult, setParentEmailResult] = useState<ParentEmailResponse | null>(null);
  const [factorInsights, setFactorInsights] = useState<FactorInsightResponse | null>(null);
  const [factorMeta, setFactorMeta] = useState<{ prompt: string; updatedAt: string } | null>(null);
  const [pendingFactorPrompt, setPendingFactorPrompt] = useState<string | null>(null);
  const [caseRecords, setCaseRecords] = useState<StudentCaseRecord[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [assessingCaseId, setAssessingCaseId] = useState<string | null>(null);
  const [runningAction, setRunningAction] = useState<ActionId | null>(null);
  const runningActionRef = useRef(runningAction);
  runningActionRef.current = runningAction;

  useEffect(() => {
    setJudged(false);
  }, [recommendation]);

  const stats = useMemo(
    () => [
      { label: "Tracked", value: caseRecords.length.toString().padStart(2, "0") },
      { label: "Risk", value: prediction ? `${Math.round(prediction.risk_score * 100)}%` : "--" },
      {
        label: "Escalated",
        value: caseRecords
          .filter((item) => item.status === "Escalated")
          .length.toString()
          .padStart(2, "0"),
      },
      { label: "Judge", value: evaluation ? evaluation.scores.overall.toFixed(1) : "--" },
    ],
    [caseRecords, evaluation, prediction],
  );

  const selectedCase = useMemo(
    () => caseRecords.find((record) => record.id === selectedCaseId) ?? caseRecords[0] ?? null,
    [caseRecords, selectedCaseId],
  );

  useEffect(() => {
    void loadFollowUpCases();
  }, []);

  function setNumericField(field: NumericStudentField, value: string) {
    setStudent({ ...student, [field]: value === "" ? "" : Number(value) });
  }

  function currentStudentProfile(): StudentProfile | null {
    const normalized = { ...student } as StudentProfile;
    for (const [field, label, min, max] of numericFields) {
      const value = student[field];
      if (value === "" || Number.isNaN(Number(value))) {
        setStatus(`Enter ${label}`);
        return null;
      }
      const numericValue = Number(value);
      if (numericValue < min || numericValue > max) {
        setStatus(`${label} must be between ${min} and ${max}`);
        return null;
      }
      normalized[field] = numericValue;
    }
    normalized.absences = 100 - normalized.attendance;
    return normalized;
  }

  async function loadFollowUpCases() {
    const result = await runExclusive(
      "load-follow-up",
      "Loading follow-up tickets",
      listFollowUpCases,
      "Follow-up tickets failed to load",
    );
    if (result) {
      const records = sortCaseRecords(result.map(caseRecordFromResponse));
      const lowRiskOpen = records.filter((r) => r.risk_category === "Low Risk" && r.status !== "Closed");
      for (const r of lowRiskOpen) {
        try {
          const saved = await updateFollowUpCase(r.id, { status: "Closed" }, false);
          const idx = records.findIndex((x) => x.id === r.id);
          if (idx >= 0) records[idx] = caseRecordFromResponse(saved);
        } catch {
          // ignore individual close failures
        }
      }
      setCaseRecords(records);
      setSelectedCaseId((previous) => previous ?? firstOpenCase(records)?.id ?? records[0]?.id ?? null);
      setStatus(`Loaded ${records.length} follow-up tickets`);
    }
  }

  async function saveCaseFromAnalysis(
    currentStudent: StudentProfile,
    nextPrediction: PredictionResponse,
    nextRecommendation: RecommendationResponse | null,
  ) {
    if (nextPrediction.risk_category === "Low Risk") {
      return null;
    }
    try {
      const saved = await saveFollowUpCase({
        student: currentStudent,
        prediction: nextPrediction,
        recommendation: plainTextForEmail(nextRecommendation?.recommendation) ?? "",
        recommendation_summary: summarizeRecommendation(nextRecommendation?.recommendation),
        evidence_case_ids: nextRecommendation?.evidence_case_ids ?? [],
      });
      const record = caseRecordFromResponse(saved);
      setCaseRecords((previous) => upsertCaseRecord(previous, record));
      setSelectedCaseId(record.id);
      return record;
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Follow-up ticket save failed");
      return null;
    }
  }

  function patchCaseLocally(
    id: string,
    changes: FollowUpCaseUpdateRequest | Partial<StudentCaseRecord>,
  ) {
    const localChanges = { ...(changes as Partial<StudentCaseRecord>) };
    if ("status" in changes && changes.status) {
      localChanges.status = normalizeCaseStatus(changes.status);
    }
    if ("escalation_target" in changes && changes.escalation_target) {
      localChanges.escalation_target = normalizeEscalationTarget(changes.escalation_target);
    }
    setCaseRecords((previous) =>
      previous.map((record) =>
        record.id === id ? { ...record, ...localChanges, updated_at: new Date().toISOString() } : record,
      ),
    );
  }

  async function updateCaseRecord(id: string, changes: FollowUpCaseUpdateRequest) {
    patchCaseLocally(id, changes);
    try {
      const saved = await updateFollowUpCase(id, changes);
      const record = caseRecordFromResponse(saved);
      setCaseRecords((previous) => upsertCaseRecord(previous, record));
      setSelectedCaseId(record.id);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Follow-up ticket update failed");
      void loadFollowUpCases();
    }
  }

  function selectCaseRecord(record: StudentCaseRecord) {
    setSelectedCaseId(record.id);
    setStatus(`${record.student_id} opened in follow-up`);
  }

  async function removeCaseRecord(id: string) {
    try {
      await updateFollowUpCase(id, { status: "Removed" }, false);
    } catch {
      // ignore removal failures
    }
    setCaseRecords((previous) => previous.filter((record) => record.id !== id));
    setSelectedCaseId((previous) => previous === id ? null : previous);
    setStatus("Ticket removed");
  }

  function loadCaseStudentIntoForm(record: StudentCaseRecord) {
    setStudent(studentDraftFromRecord(record));
    setStatus(`${record.student_id} loaded into student intake`);
    setActiveStep("student");
  }

  async function runFollowUpAssessment(record: StudentCaseRecord, directDecision?: string) {
    const note = record.note.trim();
    if (!note && !directDecision) {
      setStatus("Add what happened before assessing follow-up");
      return;
    }

    setAssessingCaseId(record.id);
    const result = await runExclusive(
      "follow-up",
      "Assessing two-week follow-up",
      async () => {
        await updateFollowUpCase(record.id, {
          attendance_trend: record.attendance_trend,
          failures_trend: record.failures_trend,
          marks_trend: record.marks_trend,
          note: record.note,
          plan_followed: record.plan_followed,
        }, false);
        return assessSavedFollowUpCase(record.id, directDecision);
      },
      "Follow-up assessment failed",
    );
    setAssessingCaseId(null);

    if (result) {
      const nextRecord = caseRecordFromResponse(result);
      setCaseRecords((previous) => upsertCaseRecord(previous, nextRecord));
      setSelectedCaseId(nextRecord.id);
      setStatus(`${nextRecord.student_id}: ${nextRecord.follow_up_decision ?? nextRecord.last_event}`);
    }
  }

  async function runExclusive<T>(
    actionId: ActionId,
    label: string,
    action: () => Promise<T>,
    fallbackMessage: string,
  ) {
    if (runningActionRef.current) {
      return null;
    }

    runningActionRef.current = actionId;
    setRunningAction(actionId);
    setStatus(label);
    try {
      return await action();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : fallbackMessage);
      return null;
    } finally {
      runningActionRef.current = null;
      setRunningAction(null);
    }
  }

  async function runSearch() {
    const currentStudent = currentStudentProfile();
    if (!currentStudent) {
      return;
    }
    const result = await runExclusive(
      "search",
      "Searching cases",
      () => searchCases(query, buildSimilarCaseFilters(currentStudent), 5),
      "Search failed",
    );
    if (result) {
      setCases(result.results);
      setStatus(`Retrieved ${result.results.length} cases`);
      setActiveStep("analysis");
    }
  }

  async function runPrediction() {
    const currentStudent = currentStudentProfile();
    if (!currentStudent) {
      return;
    }
    const result = await runExclusive(
      "predict",
      "Predicting risk",
      () => predictRisk(currentStudent),
      "Prediction failed",
    );
    if (result) {
      setPrediction(result);
      setParentEmailResult(null);
      const record = await saveCaseFromAnalysis(currentStudent, result, null);
      if (record) {
        setStatus(`Prediction complete: ${record.risk_category}; follow-up ticket saved`);
        setActiveStep("follow-up");
      } else {
        setStatus(`Prediction complete: ${result.risk_category}; follow-up ticket was not saved`);
        setActiveStep("analysis");
      }
    }
  }

  async function runRecommendation() {
    const currentStudent = currentStudentProfile();
    if (!currentStudent) {
      return;
    }
    const result = await runExclusive(
      "recommend",
      "Generating recommendation",
      () => recommendIntervention(currentStudent, query),
      "Recommendation failed",
    );
    if (result) {
      setRecommendation(result);
      if (prediction) {
        await saveCaseFromAnalysis(currentStudent, prediction, result);
      }
      setParentEmailResult(null);
      setStatus("Recommendation ready");
    }
  }

  async function runFactorInsights() {
    if (runningAction) {
      return;
    }

    const requestedPrompt = factorPrompt.trim();
    setFactorInsights(null);
    setFactorMeta(null);
    setPendingFactorPrompt(requestedPrompt);
    const result = await runExclusive(
      "factors",
      "Analyzing success factors",
      () => summarizeFactors(requestedPrompt, datasetPath),
      "Factor analysis failed",
    );
    setPendingFactorPrompt(null);
    if (result) {
      setFactorInsights(result);
      setFactorMeta({
        prompt: requestedPrompt,
        updatedAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      });
      setFactorPrompt("");
      setStatus("Factor analysis ready");
      setActiveStep("factors");
    }
  }

  async function runFullAnalysis() {
    const currentStudent = currentStudentProfile();
    if (!currentStudent) {
      return;
    }
    const result = await runExclusive(
      "full-analysis",
      "Running complete analysis",
      async () => {
        const searchResult = await searchCases(
          query,
          buildSimilarCaseFilters(currentStudent),
          5,
        );
        const predictionResult = await predictRisk(currentStudent);
        const recommendationResult = await recommendIntervention(currentStudent, query);
        return { predictionResult, recommendationResult, searchResult };
      },
      "Complete analysis failed",
    );
    if (result) {
      setCases(result.searchResult.results);
      setPrediction(result.predictionResult);
      setRecommendation(result.recommendationResult);
      const record = await saveCaseFromAnalysis(
        currentStudent,
        result.predictionResult,
        result.recommendationResult,
      );
      setParentEmailResult(null);
      if (record) {
        setStatus("Complete analysis ready and saved to follow-up");
        setActiveStep("analysis");
      } else {
        setStatus("Complete analysis ready, but follow-up ticket was not saved");
        setActiveStep("analysis");
      }
    }
  }

  async function runEvaluation() {
    if (!recommendation) {
      setStatus("Run a recommendation first");
      return;
    }
    const result = await runExclusive(
      "evaluate",
      "Evaluating recommendation",
      () =>
        evaluateRecommendation(
          query,
          recommendation.recommendation,
          recommendation.evidence_case_ids,
        ),
      "Evaluation failed",
    );
    if (result) {
      setEvaluation(result);
      setJudged(true);
      setStatus("Evaluation complete");
      setActiveStep("evaluate");
    }
  }

  async function recordFeedback(rating: "useful" | "not_useful") {
    if (!recommendation) {
      setStatus("Run a recommendation first");
      return;
    }
    const actionId = rating === "useful" ? "feedback-useful" : "feedback-not-useful";
    const result = await runExclusive(
      actionId,
      "Recording feedback",
      () => submitFeedback(query, recommendation.recommendation, rating),
      "Feedback failed",
    );
    if (result) {
      setStatus("Feedback recorded");
    }
  }

  async function runParentEmail(draft: ParentMailDraft) {
    if (!prediction || !recommendation) {
      setStatus("Run analysis and judge before sending parent email");
      return;
    }
    if (!isParentMailEligible(prediction)) {
      setStatus("Parent email is only available for medium or high risk");
      return;
    }
    const currentStudent = currentStudentProfile();
    if (!currentStudent) {
      return;
    }

    const result = await runExclusive(
      "parent-email",
      "Sending parent email",
      () =>
        sendParentEmail(
          currentStudent,
          prediction,
          recommendation.recommendation,
          draft.parent_email,
          draft.subject,
          draft.body,
        ),
      "Parent email failed",
    );
    if (result) {
      setParentEmailResult(result);
      setStatus(result.message);
    }
  }

  async function runPipelineStep(actionId: ActionId, label: string, action: () => Promise<unknown>) {
    if (runningActionRef.current) {
      return null;
    }

    runningActionRef.current = actionId;
    setRunningAction(actionId);
    setStatus(label);
    try {
      const result = await action();
      setPipelineLog((previous) => [`${label}: done`, ...previous].slice(0, 5));
      setStatus(`${label}: done`);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : `${label} failed`;
      setPipelineLog((previous) => [`${label}: ${message}`, ...previous].slice(0, 5));
      setStatus(message);
      return null;
    } finally {
      runningActionRef.current = null;
      setRunningAction(null);
    }
  }

  return (
    <section id="dashboard" className="newsprint-texture border-b border-ink">
      <div className="mx-auto max-w-screen-xl border-l border-t border-ink">
        <Hero runningAction={runningAction} status={status} stats={stats} onRun={runFullAnalysis} />

        <StepNav activeStep={activeStep} onSelect={setActiveStep} />

        {activeStep === "student" ? (
          <StudentPanel
            query={query}
            runFullAnalysis={runFullAnalysis}
            runFactorInsights={runFactorInsights}
            runningAction={runningAction}
            setNumericField={setNumericField}
            setQuery={setQuery}
            setStudent={setStudent}
            student={student}
          />
        ) : null}

        {activeStep === "factors" ? (
          <FactorsPanel
            datasetPath={datasetPath}
            factorInsights={factorInsights}
            factorMeta={factorMeta}
            factorPrompt={factorPrompt}
            pendingFactorPrompt={pendingFactorPrompt}
            runningAction={runningAction}
            runFactorInsights={runFactorInsights}
            setFactorPrompt={setFactorPrompt}
          />
        ) : null}

        {activeStep === "analysis" ? (
          <AnalysisPanel
            cases={cases}
            judged={judged}
            prediction={prediction}
            recommendation={recommendation}
            runningAction={runningAction}
            runEvaluation={runEvaluation}
          />
        ) : null}

        {activeStep === "follow-up" ? (
          <FollowUpPanel
            assessingCaseId={assessingCaseId}
            caseRecords={caseRecords}
            onAssessFollowUp={runFollowUpAssessment}
            onLoadStudent={loadCaseStudentIntoForm}
            onPatchCase={patchCaseLocally}
            onRemoveCase={removeCaseRecord}
            onSelectCase={selectCaseRecord}
            onUpdateCase={updateCaseRecord}
            runningAction={runningAction}
            selectedCase={selectedCase}
          />
        ) : null}

        {activeStep === "evaluate" ? (
          <EvaluatePanel
            evaluation={evaluation}
            judged={judged}
            parentEmailResult={parentEmailResult}
            prediction={prediction}
            recommendation={recommendation}
            recordFeedback={recordFeedback}
            runningAction={runningAction}
            runParentEmail={runParentEmail}
            runEvaluation={runEvaluation}
            onRetryRecommendation={runRecommendation}
            student={student}
          />
        ) : null}
      </div>
    </section>
  );
}

function Hero({
  runningAction,
  status,
  stats,
  onRun,
}: {
  runningAction: ActionId | null;
  status: string;
  stats: Array<{ label: string; value: string }>;
  onRun: () => void;
}) {
  return (
    <div className="grid grid-cols-12 border-b border-ink">
      <div className="col-span-12 border-r border-ink p-6 lg:col-span-8 lg:p-10">
        <p className="font-mono text-xs uppercase tracking-widest text-red-700">Advisor desk</p>
        <h2 className="mt-4 max-w-4xl font-serif text-5xl font-black leading-[0.9] sm:text-6xl lg:text-7xl">
          Student intervention workflow.
        </h2>
        <p className="mt-6 max-w-2xl text-justify font-body text-lg leading-relaxed">
          Prepare the data once, enter a student case, run analysis, then review evidence,
          recommendations, judge scores, and feedback.
        </p>
        <Button
          className="mt-8"
          disabled={runningAction !== null}
          isLoading={runningAction === "full-analysis"}
          loadingLabel="Running"
          onClick={onRun}
        >
          Run complete analysis
        </Button>
      </div>
      <aside className="col-span-12 border-r border-ink bg-ink p-6 text-newsprint lg:col-span-4 lg:p-8">
        <p className="font-mono text-xs uppercase tracking-widest text-neutral-400">Current brief</p>
        <div className="mt-8 grid grid-cols-2 border-l border-t border-newsprint">
          {stats.map((stat) => (
            <div className="border-b border-r border-newsprint p-4" key={stat.label}>
              <p className="font-mono text-3xl font-bold">{stat.value}</p>
              <p className="mt-2 font-mono text-xs uppercase tracking-widest text-neutral-400">
                {stat.label}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-6 font-mono text-xs uppercase tracking-widest text-neutral-400">
          Status: {status}
        </p>
      </aside>
    </div>
  );
}

function StepNav({
  activeStep,
  onSelect,
}: {
  activeStep: StepId;
  onSelect: (step: StepId) => void;
}) {
  return (
    <nav aria-label="Workflow steps" className="grid border-b border-ink md:grid-cols-5">
      {steps.map((step, index) => (
        <button
          className={`min-h-20 border-r border-ink px-4 py-3 text-left transition-colors ${
            activeStep === step.id ? "bg-ink text-newsprint" : "bg-newsprint hover:bg-muted"
          }`}
          key={step.id}
          onClick={() => onSelect(step.id)}
          type="button"
        >
          <span className="font-mono text-xs uppercase tracking-widest">Step {index + 1}</span>
          <span className="mt-1 block font-serif text-2xl font-bold">{step.label}</span>
          <span className="mt-1 block font-mono text-xs uppercase tracking-widest">{step.caption}</span>
        </button>
      ))}
    </nav>
  );
}

function StudentPanel({
  query,
  runFactorInsights,
  runFullAnalysis,
  runningAction,
  setNumericField,
  setQuery,
  setStudent,
  student,
}: {
  query: string;
  runFactorInsights: () => void;
  runFullAnalysis: () => void;
  runningAction: ActionId | null;
  setNumericField: (field: NumericStudentField, value: string) => void;
  setQuery: (value: string) => void;
  setStudent: (value: StudentDraft) => void;
  student: StudentDraft;
}) {
  const isBusy = runningAction !== null;

  return (
    <section className="grid grid-cols-12 border-b border-ink" id="search">
      <form className="col-span-12 border-r border-ink p-6 lg:col-span-7">
        <PanelHeading eyebrow="Case intake" title="Enter one student" />
        <div className="mt-6 grid grid-cols-2 gap-4">
          <label className="field-label col-span-2">
            Advisor query
            <textarea
              className="newsprint-input mt-2 min-h-24 w-full resize-y"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label className="field-label">
            School
            <input
              className="newsprint-input mt-2 w-full"
              value={student.school}
              onChange={(event) => setStudent({ ...student, school: event.target.value })}
            />
          </label>
          <label className="field-label">
            Student ID
            <input
              className="newsprint-input mt-2 w-full"
              value={student.student_id ?? ""}
              onChange={(event) => setStudent({ ...student, student_id: event.target.value })}
            />
          </label>
          <label className="field-label col-span-2 sm:col-span-1">
            Parent email
            <input
              className="newsprint-input mt-2 w-full"
              type="email"
              value={student.parent_email ?? ""}
              onChange={(event) => setStudent({ ...student, parent_email: event.target.value })}
            />
          </label>
          {numericFields.map(([key, label, min, max]) => (
            <label className="field-label" key={key}>
              {label}
              <input
                className="newsprint-input mt-2 w-full"
                max={max}
                min={min}
                type="number"
                value={student[key] ?? ""}
                onChange={(event) => setNumericField(key, event.target.value)}
              />
            </label>
          ))}
        </div>
      </form>
      <aside className="col-span-12 p-6 lg:col-span-5">
        <PanelHeading eyebrow="Actions" title="Choose a workflow" />
        <div className="mt-6 grid gap-3">
          <Button
            disabled={isBusy}
            isLoading={runningAction === "full-analysis"}
            loadingLabel="Running"
            onClick={runFullAnalysis}
          >
            Run complete analysis
          </Button>
          <Button
            disabled={isBusy}
            isLoading={runningAction === "factors"}
            loadingLabel="Analyzing"
            variant="secondary"
            onClick={runFactorInsights}
          >
            Explore success factors
          </Button>
        </div>
      </aside>
    </section>
  );
}

function FactorsPanel({
  datasetPath,
  factorInsights,
  factorMeta,
  factorPrompt,
  pendingFactorPrompt,
  runningAction,
  runFactorInsights,
  setFactorPrompt,
}: {
  datasetPath: string;
  factorInsights: FactorInsightResponse | null;
  factorMeta: { prompt: string; updatedAt: string } | null;
  factorPrompt: string;
  pendingFactorPrompt: string | null;
  runningAction: ActionId | null;
  runFactorInsights: () => void;
  setFactorPrompt: (value: string) => void;
}) {
  const isBusy = runningAction !== null;
  const isAnalyzingFactors = runningAction === "factors";

  return (
    <section className="grid grid-cols-12 border-b border-ink" id="factors">
      <div className="col-span-12 border-r border-ink p-6 lg:col-span-5">
        <PanelHeading eyebrow="Factor prompt" title="Ask about success signals" />
        <label className="field-label mt-6">
          Question
          <textarea
            className="newsprint-input mt-2 min-h-28 w-full resize-y"
            disabled={isBusy}
            value={factorPrompt}
            onChange={(event) => setFactorPrompt(event.target.value)}
          />
        </label>
        <div className="mt-4 grid gap-2">
          {[
            "What factors influence student success or failure the most?",
            "Which habits seem protective for medium-risk students?",
            "Which features should advisors watch before grades drop?",
          ].map((prompt) => (
            <button
              className="border border-ink px-3 py-2 text-left font-mono text-xs uppercase tracking-widest hover:bg-ink hover:text-newsprint disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-newsprint disabled:hover:text-ink"
              disabled={isBusy}
              key={prompt}
              onClick={() => setFactorPrompt(prompt)}
              type="button"
            >
              {prompt}
            </button>
          ))}
        </div>
        <Button
          className="mt-6 w-full"
          disabled={isBusy}
          isLoading={runningAction === "factors"}
          loadingLabel="Analyzing"
          onClick={runFactorInsights}
        >
          Analyze factors
        </Button>
      </div>
      <div aria-live="polite" className="col-span-12 p-6 lg:col-span-7">
        {isAnalyzingFactors ? (
          <FactorLoadingState datasetPath={datasetPath} prompt={pendingFactorPrompt ?? factorPrompt} />
        ) : (
          <FactorResultState datasetPath={datasetPath} factorInsights={factorInsights} factorMeta={factorMeta} />
        )}
      </div>
    </section>
  );
}

function FactorLoadingState({ datasetPath, prompt }: { datasetPath: string; prompt: string }) {
  return (
    <>
      <PanelHeading eyebrow="Merged dataset" title="Analyzing new response" />
      <div className="mt-6 border border-ink p-6">
        <div className="flex items-center gap-3 font-mono text-xs font-bold uppercase tracking-widest text-red-700">
          <LoaderCircle aria-hidden="true" className="h-5 w-5 animate-spin" />
          Refreshing factor output
        </div>
        <p className="mt-4 text-justify font-body text-base leading-relaxed">
          Building a fresh answer from {datasetPath}. The previous result has been cleared so this
          panel only shows the new response when it is ready.
        </p>
        <p className="mt-4 border-l-4 border-ink pl-4 font-mono text-xs uppercase tracking-widest">
          Prompt: {prompt}
        </p>
      </div>
    </>
  );
}

function FactorResultState({
  datasetPath,
  factorInsights,
  factorMeta,
}: {
  datasetPath: string;
  factorInsights: FactorInsightResponse | null;
  factorMeta: { prompt: string; updatedAt: string } | null;
}) {
  return (
    <>
      <PanelHeading eyebrow="Merged dataset" title={`${factorInsights?.row_count ?? "--"} student records`} />
      {factorMeta ? (
        <p className="mt-3 font-mono text-xs uppercase tracking-widest text-red-700">
          Updated {factorMeta.updatedAt} | Prompt: {factorMeta.prompt}
        </p>
      ) : null}
      <MarkdownText
        className={`mt-4 text-justify font-body text-base leading-relaxed ${
          factorInsights?.generated_by === "guardrail" ? "border border-ink p-4" : ""
        }`}
        text={
          factorInsights?.answer ??
          `Using ${datasetPath}. Ask a question to get a data-grounded answer about students or success factors.`
        }
      />
      {factorInsights ? (
        <>
          <p className="mt-5 font-mono text-xs uppercase tracking-widest text-red-700">
            Response source: {factorInsights.generated_by}
          </p>
          {factorInsights.generated_by !== "guardrail" ? (
            <p className="mt-3 border-l-4 border-ink pl-4 text-justify font-body text-sm leading-relaxed">
              Grounding: {factorInsights.summary}
            </p>
          ) : null}
        </>
      ) : null}
    </>
  );
}

function AnalysisPanel({
  cases,
  judged,
  prediction,
  recommendation,
  runningAction,
  runEvaluation,
}: {
  cases: RetrievedCase[];
  judged: boolean;
  prediction: PredictionResponse | null;
  recommendation: RecommendationResponse | null;
  runningAction: ActionId | null;
  runEvaluation: () => void;
}) {
  const isBusy = runningAction !== null;

  return (
    <section className="grid grid-cols-12 border-b border-ink" id="recommendations">
      <div className="col-span-12 border-r border-ink p-6 lg:col-span-5">
        <PanelHeading eyebrow="Risk result" title={prediction?.risk_category ?? "Awaiting analysis"} />
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <ResultBlock label="Risk score" value={prediction ? `${Math.round(prediction.risk_score * 100)}%` : "--"} />
          <ResultBlock label="Model" value={prediction?.model_name ?? "--"} />
        </div>
        <LogList
          entries={
            prediction?.top_contributors.length
              ? prediction.top_contributors.map(formatContribution)
              : ["No feature contributions yet"]
          }
        />
      </div>
      <div className="col-span-12 border-r border-ink p-6 lg:col-span-7">
        <PanelHeading
          eyebrow="Recommendation"
          title={recommendation ? recommendation.risk_category : "No recommendation yet"}
        />
        <MarkdownText
          className="mt-4 text-justify font-body text-base leading-relaxed"
          text={
            recommendation?.recommendation ??
            "Run analysis to produce advisor guidance grounded in retrieved cases."
          }
        />
        <p className="mt-4 font-mono text-xs uppercase tracking-widest">
          Evidence: {recommendation?.evidence_case_ids.join(", ") || "None"}
        </p>
        <div className="mt-6">
          <Button
            disabled={isBusy || !recommendation || judged}
            isLoading={runningAction === "evaluate"}
            loadingLabel="Evaluating"
            onClick={runEvaluation}
          >
            Evaluate recommendation
          </Button>
        </div>
        <div className="mt-6 grid border-l border-t border-ink md:grid-cols-2">
          <PipelineBadge icon={Search} label="Search path" value="Hybrid retrieval" />
          <PipelineBadge icon={BrainCircuit} label="Fusion" value="RRF, then BGE rerank" />
          <PipelineBadge
            icon={BarChart3}
            label="Risk model"
            value={prediction?.model_name ?? "Awaiting prediction"}
          />
          <PipelineBadge icon={ShieldAlert} label="Explanation" value="SHAP when ML model is selected" />
        </div>
        <EvidenceList cases={cases} />
      </div>
    </section>
  );
}

function FollowUpPanel({
  assessingCaseId,
  caseRecords,
  onAssessFollowUp,
  onLoadStudent,
  onPatchCase,
  onRemoveCase,
  onSelectCase,
  onUpdateCase,
  runningAction,
  selectedCase,
}: {
  assessingCaseId: string | null;
  caseRecords: StudentCaseRecord[];
  onAssessFollowUp: (record: StudentCaseRecord, directDecision?: string) => void;
  onLoadStudent: (record: StudentCaseRecord) => void;
  onPatchCase: (id: string, changes: Partial<StudentCaseRecord>) => void;
  onRemoveCase: (id: string) => void;
  onSelectCase: (record: StudentCaseRecord) => void;
  onUpdateCase: (id: string, changes: FollowUpCaseUpdateRequest) => void;
  runningAction: ActionId | null;
  selectedCase: StudentCaseRecord | null;
}) {
  const activeRecords = caseRecords.filter((record) => record.status !== "Closed" && record.status !== "Removed");
  const closedRecords = caseRecords.filter((record) => record.status === "Closed");
  const escalatedCount = activeRecords.filter((record) => record.status === "Escalated").length;

  return (
    <section className="border-b border-ink" id="follow-up">
      <div className="grid grid-cols-12 border-b border-ink">
        <div className="col-span-12 border-r border-ink p-6 lg:col-span-5">
          <PanelHeading eyebrow="Follow up" title="Student tickets" />
          <div className="mt-6 grid grid-cols-2 border-l border-t border-ink">
            <ResultBlock label="Active" value={activeRecords.length.toString().padStart(2, "0")} />
            <ResultBlock label="Escalated" value={escalatedCount.toString().padStart(2, "0")} />
            <ResultBlock label="Closed" value={closedRecords.length.toString().padStart(2, "0")} />
            <ResultBlock label="Selected" value={selectedCase ? selectedCase.status : "--"} />
          </div>
        </div>
        <div className="col-span-12 p-6 lg:col-span-7">
          <PanelHeading eyebrow="Decision flow" title="Review evidence, then assess" />
          <div className="mt-6 grid border-l border-t border-ink md:grid-cols-3">
            <PipelineBadge icon={ShieldAlert} label="High risk" value="Counsellor first" />
            <PipelineBadge icon={BrainCircuit} label="Medium risk" value="Advisor review" />
            <PipelineBadge icon={CheckCircle2} label="Low risk" value="Teacher monitor" />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-12 border-b border-ink">
        <div className="col-span-12 border-r border-ink p-4 lg:col-span-5">
          <div className="grid gap-4">
            {riskBoardOrder.map((category) => (
              <FollowUpRiskGroup
                category={category}
                key={category}
                onSelectCase={onSelectCase}
                records={activeRecords.filter((record) => record.risk_category === category)}
                selectedCaseId={selectedCase?.id ?? null}
              />
            ))}
            <ClosedTicketsBranch
              onSelectCase={onSelectCase}
              records={closedRecords}
              selectedCaseId={selectedCase?.id ?? null}
            />
          </div>
        </div>
        <div className="col-span-12 p-4 lg:col-span-7">
          <FollowUpDetailView
            assessingCaseId={assessingCaseId}
            onAssessFollowUp={onAssessFollowUp}
            onLoadStudent={onLoadStudent}
            onPatchCase={onPatchCase}
            onRemoveCase={onRemoveCase}
            onUpdateCase={onUpdateCase}
            record={selectedCase}
            runningAction={runningAction}
          />
        </div>
      </div>
    </section>
  );
}

function FollowUpRiskGroup({
  category,
  onSelectCase,
  records,
  selectedCaseId,
}: {
  category: RiskCategory;
  onSelectCase: (record: StudentCaseRecord) => void;
  records: StudentCaseRecord[];
  selectedCaseId: string | null;
}) {
  return (
    <section className="border border-ink">
      <div className="flex items-center justify-between border-b border-ink px-4 py-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-red-700">Risk group</p>
          <h4 className="mt-1 font-serif text-2xl font-black leading-none">{category}</h4>
        </div>
        <span className="border border-ink px-3 py-1 font-mono text-xs font-bold uppercase tracking-widest">
          {records.length}
        </span>
      </div>
      <div className="grid gap-3 p-3">
        {records.length ? (
          records.map((record) => (
            <FollowUpTicketCard
              isSelected={record.id === selectedCaseId}
              key={record.id}
              onSelectCase={onSelectCase}
              record={record}
            />
          ))
        ) : (
          <p className="p-3 font-mono text-xs uppercase tracking-widest">No open tickets</p>
        )}
      </div>
    </section>
  );
}

function ClosedTicketsBranch({
  onSelectCase,
  records,
  selectedCaseId,
}: {
  onSelectCase: (record: StudentCaseRecord) => void;
  records: StudentCaseRecord[];
  selectedCaseId: string | null;
}) {
  return (
    <section className="border border-ink bg-muted">
      <div className="flex items-center justify-between border-b border-ink px-4 py-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-red-700">Closed branch</p>
          <h4 className="mt-1 font-serif text-2xl font-black leading-none">Closed tickets</h4>
        </div>
        <span className="border border-ink px-3 py-1 font-mono text-xs font-bold uppercase tracking-widest">
          {records.length}
        </span>
      </div>
      <div className="grid gap-3 p-3">
        {records.length ? (
          records.map((record) => (
            <FollowUpTicketCard
              isSelected={record.id === selectedCaseId}
              key={record.id}
              onSelectCase={onSelectCase}
              record={record}
            />
          ))
        ) : (
          <p className="p-3 font-mono text-xs uppercase tracking-widest">No closed tickets yet</p>
        )}
      </div>
    </section>
  );
}

function FollowUpTicketCard({
  isSelected,
  onSelectCase,
  record,
}: {
  isSelected: boolean;
  onSelectCase: (record: StudentCaseRecord) => void;
  record: StudentCaseRecord;
}) {
  return (
    <button
      className={`border border-ink p-4 text-left transition-colors ${
        isSelected ? "bg-ink text-newsprint" : "bg-newsprint hover:bg-muted"
      }`}
      onClick={() => onSelectCase(record)}
      type="button"
    >
      <span className="flex items-start justify-between gap-3">
        <span>
          <span className="block font-serif text-2xl font-bold leading-none">{record.student_id}</span>
          <span className="mt-2 block font-mono text-xs uppercase tracking-widest">
            {record.school} | {Math.round(record.risk_score * 100)}% | {record.status}
          </span>
        </span>
        <span className="border border-current px-2 py-1 font-mono text-[0.65rem] uppercase tracking-widest">
          {record.status}
        </span>
      </span>
      <span className="mt-3 block truncate font-body text-sm">
        {record.last_event || record.recommendation_summary || "Awaiting follow-up"}
      </span>
    </button>
  );
}

function FollowUpDetailView({
  assessingCaseId,
  onAssessFollowUp,
  onLoadStudent,
  onPatchCase,
  onRemoveCase,
  onUpdateCase,
  record,
  runningAction,
}: {
  assessingCaseId: string | null;
  onAssessFollowUp: (record: StudentCaseRecord, directDecision?: string) => void;
  onLoadStudent: (record: StudentCaseRecord) => void;
  onPatchCase: (id: string, changes: Partial<StudentCaseRecord>) => void;
  onRemoveCase: (id: string) => void;
  onUpdateCase: (id: string, changes: FollowUpCaseUpdateRequest) => void;
  record: StudentCaseRecord | null;
  runningAction: ActionId | null;
}) {
  const [advisorSuggestion, setAdvisorSuggestion] = useState("");
  const currentRecord = record ?? null;

  if (!currentRecord) {
    return (
      <div className="min-h-96 border border-ink p-6">
        <PanelHeading eyebrow="Ticket detail" title="No ticket selected" />
        <p className="mt-4 font-mono text-xs uppercase tracking-widest">
          Run analysis to create a follow-up ticket.
        </p>
      </div>
    );
  }

  const isAssessing = runningAction === "follow-up" && assessingCaseId === currentRecord.id;
  const isBusy = runningAction !== null;

  function handleAssess() {
    const directive = parseDirective(advisorSuggestion);
    if (directive) {
      onAssessFollowUp(currentRecord, directive);
    } else {
      const combinedNote = advisorSuggestion
        ? `${currentRecord.note}\n\nAdvisor suggestion: ${advisorSuggestion}`
        : currentRecord.note;
      onAssessFollowUp({ ...currentRecord, note: combinedNote });
    }
    onPatchCase(currentRecord.id, { note: "" });
    setAdvisorSuggestion("");
  }

  function parseDirective(text: string): string | null {
    const trimmed = text.trim().toLowerCase();
    if (/\b(close|closing|remove|removed)\b/.test(trimmed)) return "close";
    if (/\b(downgrade|demote|reduced)\b/.test(trimmed)) return "downgrade";
    if (/\b(escalate|escalated|elevate)\b/.test(trimmed)) return "escalate";
    if (/\b(monitor|monitoring|keep|watch|maintain)\b/.test(trimmed)) return "monitor";
    return null;
  }

  return (
    <article className="border border-ink bg-newsprint">
      <div className="grid grid-cols-12 border-b border-ink">
        <div className="col-span-12 border-r border-ink p-5 lg:col-span-7">
          <p className="font-mono text-xs uppercase tracking-widest text-red-700">Ticket detail</p>
          <h4 className="mt-2 font-serif text-4xl font-black leading-none">{currentRecord.student_id}</h4>
          <p className="mt-3 font-mono text-xs uppercase tracking-widest">
            {currentRecord.risk_category} | {Math.round(currentRecord.risk_score * 100)}% | {formatCaseDate(currentRecord.updated_at)}
          </p>
        </div>
        <div className="col-span-12 grid grid-cols-2 border-l border-t border-ink lg:col-span-5 lg:border-l-0 lg:border-t-0">
          <SmallStat label="Attend" value={`${currentRecord.attendance}%`} />
          <SmallStat label="Fails" value={currentRecord.failures} />
          <SmallStat label="Study" value={currentRecord.study_time} />
          <SmallStat label="Status" value={currentRecord.status} />
        </div>
      </div>
      <div className="grid grid-cols-12">
        <div className="col-span-12 border-r border-ink p-5 lg:col-span-7">
            <label className="field-label">
              What happened after two weeks
              <textarea
                className="newsprint-input mt-2 min-h-32 w-full resize-y"
                disabled={currentRecord.status === "Closed"}
                value={currentRecord.note}
                onChange={(event) => onPatchCase(currentRecord.id, { note: event.target.value })}
              />
            </label>
            <label className="field-label mt-5">
              Advisor suggestion
              <textarea
                className="newsprint-input mt-2 min-h-20 w-full resize-y"
                disabled={currentRecord.status === "Closed"}
                placeholder="Optional: note your recommendation for this case..."
                value={advisorSuggestion}
                onChange={(event) => setAdvisorSuggestion(event.target.value)}
              />
            </label>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            {currentRecord.status === "Closed" ? (
              <Button
                disabled={isBusy}
                variant="secondary"
                onClick={() => onRemoveCase(currentRecord.id)}
              >
                Remove ticket
              </Button>
            ) : (
              <>
                <Button
                  disabled={isBusy && !isAssessing}
                  isLoading={isAssessing}
                  loadingLabel="Assessing"
                  onClick={handleAssess}
                >
                  Assess follow-up
                </Button>
                <Button
                  disabled={isBusy}
                  variant="secondary"
                  onClick={() => onLoadStudent(currentRecord)}
                >
                  Load student
                </Button>
              </>
            )}
          </div>
          <div className="mt-6 border-l-4 border-ink pl-4">
            <p className="font-mono text-xs uppercase tracking-widest text-red-700">Original plan</p>
            <p className="mt-2 text-justify font-body text-sm leading-relaxed">
              {currentRecord.recommendation_summary || "No recommendation saved yet."}
            </p>
            <p className="mt-3 font-mono text-xs uppercase tracking-widest">
              Evidence: {currentRecord.evidence_case_ids.join(", ") || "None"}
            </p>
          </div>
        </div>
        <aside className="col-span-12 p-5 lg:col-span-5">
          <PanelHeading eyebrow="Decision" title={currentRecord.follow_up_decision ?? currentRecord.status} />
          <p className="mt-3 font-mono text-xs uppercase tracking-widest">
            Owner: {currentRecord.escalation_target}
          </p>
          {currentRecord.follow_up_decision ? (
            <div className="mt-5 border border-ink p-4">
              <p className="font-mono text-xs font-bold uppercase tracking-widest">
                Confidence {Math.round((currentRecord.follow_up_confidence ?? 0) * 100)}%
              </p>
              <p className="mt-3 text-justify font-body text-sm leading-relaxed">
                {currentRecord.follow_up_rationale}
              </p>
              <p className="mt-3 text-justify font-body text-sm leading-relaxed">
                {currentRecord.follow_up_next_steps}
              </p>
              <p className="mt-3 font-mono text-[0.65rem] uppercase tracking-widest text-red-700">
                Source: {currentRecord.follow_up_generated_by}
                {currentRecord.follow_up_assessed_at ? ` | ${formatCaseDate(currentRecord.follow_up_assessed_at)}` : ""}
              </p>
            </div>
          ) : (
            <p className="mt-5 border border-ink p-4 font-mono text-xs uppercase tracking-widest">
              Add the two-week note, then assess.
            </p>
          )}
          <GitLine events={currentRecord.events} />
        </aside>
      </div>
    </article>
  );
}

function SelectField({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: string[];
  value: string;
}) {
  return (
    <label className="field-label">
      {label}
      <select
        className="newsprint-input mt-2 w-full"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function GitLine({ events }: { events: FollowUpCaseEvent[] }) {
  return (
    <div className="mt-6">
      <p className="font-mono text-xs uppercase tracking-widest text-red-700">Student history</p>
      <div className="mt-4 border-l-2 border-ink">
        {events.length ? (
          events.map((event) => (
            <div className="relative pb-5 pl-5" key={event.event_id}>
              <span className="absolute -left-[7px] top-1 h-3 w-3 border border-ink bg-newsprint" />
              <p className="font-mono text-xs font-bold uppercase tracking-widest">{event.title}</p>
              <p className="mt-1 font-mono text-[0.65rem] uppercase tracking-widest text-red-700">
                {event.event_type} | {formatCaseDate(event.created_at)}
              </p>
              {event.note ? (
                <p className="mt-2 text-justify font-body text-sm leading-relaxed">{event.note}</p>
              ) : null}
            </div>
          ))
        ) : (
          <p className="pb-5 pl-5 font-mono text-xs uppercase tracking-widest">No events yet</p>
        )}
      </div>
    </div>
  );
}

function SmallStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border-b border-r border-ink p-3">
      <p className="truncate font-mono text-lg font-bold">{value}</p>
      <p className="mt-1 font-mono text-[0.65rem] uppercase tracking-widest">{label}</p>
    </div>
  );
}

function EvaluatePanel({
  evaluation,
  judged,
  parentEmailResult,
  prediction,
  recommendation,
  recordFeedback,
  runningAction,
  runParentEmail,
  runEvaluation,
  onRetryRecommendation,
  student,
}: {
  evaluation: EvaluationResponse | null;
  judged: boolean;
  parentEmailResult: ParentEmailResponse | null;
  prediction: PredictionResponse | null;
  recommendation: RecommendationResponse | null;
  recordFeedback: (rating: "useful" | "not_useful") => void;
  runningAction: ActionId | null;
  runParentEmail: (draft: ParentMailDraft) => void;
  runEvaluation: () => void;
  onRetryRecommendation: () => void;
  student: StudentDraft;
}) {
  const isBusy = runningAction !== null;
  const defaultDraft = useMemo(
    () => buildParentEmailDraft(student, prediction, recommendation),
    [student, prediction, recommendation],
  );
  const [draft, setDraft] = useState<ParentMailDraft>(defaultDraft);
  const [feedbackGiven, setFeedbackGiven] = useState(false);
  const canPrepareParentEmail = prediction ? isParentMailEligible(prediction) : false;
  const canSendParentEmail =
    canPrepareParentEmail &&
    recommendation !== null &&
    draft.parent_email.trim() !== "" &&
    draft.subject.trim() !== "" &&
    draft.body.trim() !== "";

  useEffect(() => {
    setDraft(defaultDraft);
  }, [defaultDraft]);

  useEffect(() => {
    setFeedbackGiven(false);
  }, [recommendation]);

  return (
    <section className="grid grid-cols-12 border-b border-ink" id="evaluation">
      <div className="col-span-12 border-r border-ink p-6 lg:col-span-5">
        <PanelHeading eyebrow="Judge" title="Recommendation quality" />
        <div className="mt-6 grid grid-cols-2 border-l border-t border-ink">
          {[
            { label: "Relevance", value: evaluation?.scores.relevance },
            { label: "Grounded", value: evaluation?.scores.groundedness },
            { label: "Consistent", value: evaluation?.scores.consistency },
            { label: "Useful", value: evaluation?.scores.usefulness },
          ].map(({ label, value }) => (
            <div className="border-b border-r border-ink p-4" key={label}>
              <p className="font-mono text-3xl font-bold">{value ?? "--"}</p>
              <p className="mt-2 font-mono text-xs uppercase tracking-widest">{label}</p>
            </div>
          ))}
        </div>
        <Button
          className="mt-6 w-full"
          disabled={isBusy || !recommendation || judged}
          isLoading={runningAction === "evaluate"}
          loadingLabel="Judging"
          onClick={runEvaluation}
        >
          Run judge
        </Button>
      </div>
      <div className="col-span-12 p-6 lg:col-span-7">
        <PanelHeading eyebrow="Feedback" title="Advisor response" />
        <p className="mt-4 text-justify font-body text-base leading-relaxed">
          {evaluation?.notes ??
            "Judge notes and advisor feedback controls appear here after a recommendation exists."}
        </p>
        <MarkdownText
          className="mt-4 text-justify font-body text-base leading-relaxed"
          text={recommendation?.recommendation ?? "No recommendation is ready yet."}
        />
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Button
            disabled={isBusy || !recommendation || feedbackGiven}
            isLoading={runningAction === "feedback-useful"}
            loadingLabel="Saving"
            onClick={() => { recordFeedback("useful"); setFeedbackGiven(true); }}
          >
            Useful
          </Button>
          <Button
            disabled={isBusy || !recommendation || feedbackGiven}
            isLoading={runningAction === "feedback-not-useful" || runningAction === "recommend"}
            loadingLabel="Retrying"
            variant="secondary"
            onClick={async () => {
              await recordFeedback("not_useful");
              onRetryRecommendation();
            }}
          >
            Not useful
          </Button>
        </div>
      </div>
      {canPrepareParentEmail ? (
      <div className="col-span-12 border-t border-ink p-6">
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <div className="flex items-start gap-3">
              <Mail aria-hidden="true" className="mt-1 h-5 w-5 stroke-1 text-red-700" />
              <div>
                <PanelHeading eyebrow="Parent mail" title="Prepare outreach" />
              </div>
            </div>
            <p className="mt-4 text-justify font-body text-base leading-relaxed">
              This student is medium or high risk, so parent outreach can be prepared and sent.
            </p>
            {parentEmailResult ? (
              <p className="mt-4 border border-ink p-3 font-mono text-xs uppercase tracking-widest">
                {parentEmailResult.delivery_status}: {parentEmailResult.message}
              </p>
            ) : null}
          </div>
          <div className="lg:col-span-8">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="field-label">
                Parent email
                <input
                  className="newsprint-input mt-2 w-full"
                  disabled={isBusy || !canPrepareParentEmail}
                  type="email"
                  value={draft.parent_email}
                  onChange={(event) => setDraft({ ...draft, parent_email: event.target.value })}
                />
              </label>
              <label className="field-label">
                Subject
                <input
                  className="newsprint-input mt-2 w-full"
                  disabled={isBusy || !canPrepareParentEmail}
                  value={draft.subject}
                  onChange={(event) => setDraft({ ...draft, subject: event.target.value })}
                />
              </label>
              <label className="field-label md:col-span-2">
                Message
                <textarea
                  className="newsprint-input mt-2 min-h-56 w-full resize-y"
                  disabled={isBusy || !canPrepareParentEmail}
                  value={draft.body}
                  onChange={(event) => setDraft({ ...draft, body: event.target.value })}
                />
              </label>
            </div>
            <Button
              className="mt-4"
              disabled={isBusy || !canSendParentEmail}
              isLoading={runningAction === "parent-email"}
              loadingLabel="Sending"
              onClick={() => runParentEmail(draft)}
            >
              <Send aria-hidden="true" className="mr-2 inline h-4 w-4" />
              Send parent email
            </Button>
          </div>
        </div>
      </div>
      ) : null}
    </section>
  );
}

function EvidenceList({ cases }: { cases: RetrievedCase[] }) {
  return (
    <div className="mt-8">
      <p className="font-mono text-xs uppercase tracking-widest text-red-700">Similar cases</p>
      <div className="mt-4 grid border-l border-t border-ink md:grid-cols-2">
        {cases.length ? (
          cases.map((item) => (
            <article className="border-b border-r border-ink p-4" key={item.case_id}>
              <p className="font-mono text-xs uppercase tracking-widest">
                {item.case_id} | Score {item.score.toFixed(2)}
              </p>
              <h4 className="mt-3 font-serif text-2xl font-bold">{item.student_id}</h4>
              <p className="mt-3 text-justify font-body text-sm leading-relaxed">{item.case_text}</p>
            </article>
          ))
        ) : (
          <p className="border-b border-r border-ink p-4 font-mono text-xs uppercase tracking-widest">
            Search results will appear here
          </p>
        )}
      </div>
    </div>
  );
}

function PanelHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <>
      <p className="font-mono text-xs uppercase tracking-widest text-red-700">{eyebrow}</p>
      <h3 className="mt-3 font-serif text-4xl font-black leading-none">{title}</h3>
    </>
  );
}

function MetricPanel({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
}) {
  return (
    <div className="border border-ink p-4">
      <Icon aria-hidden="true" className="h-5 w-5 stroke-1" />
      <p className="mt-4 font-mono text-2xl font-bold">{value}</p>
      <p className="mt-1 font-mono text-xs uppercase tracking-widest">{label}</p>
    </div>
  );
}

function PipelineBadge({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="border-b border-r border-ink p-4">
      <Icon aria-hidden="true" className="h-5 w-5 stroke-1 text-red-700" />
      <p className="mt-3 font-mono text-xs uppercase tracking-widest text-red-700">{label}</p>
      <p className="mt-2 font-serif text-xl font-bold leading-tight">{value}</p>
    </div>
  );
}

function ResultBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-ink p-4">
      <p className="font-mono text-xs uppercase tracking-widest">{label}</p>
      <p className="mt-2 break-words font-mono text-2xl font-bold">{value}</p>
    </div>
  );
}

function LogList({ entries }: { entries: string[] }) {
  return (
    <div className="mt-6 border-l border-t border-ink">
      {entries.map((entry) => (
        <p className="border-b border-r border-ink p-3 font-mono text-xs uppercase" key={entry}>
          {entry}
        </p>
      ))}
    </div>
  );
}

function upsertCaseRecord(records: StudentCaseRecord[], nextRecord: StudentCaseRecord): StudentCaseRecord[] {
  return sortCaseRecords([
    nextRecord,
    ...records.filter((record) => record.id !== nextRecord.id),
  ]);
}

function caseRecordFromResponse(response: FollowUpCaseResponse): StudentCaseRecord {
  return {
    id: response.case_id,
    student_id: response.student_id,
    school: response.student.school,
    parent_email: response.student.parent_email,
    risk_category: response.risk_category,
    risk_score: response.risk_score,
    model_name: response.model_name,
    age: response.student.age,
    attendance: response.student.attendance,
    failures: response.student.failures,
    study_time: response.student.study_time,
    previous_grade_average: response.student.previous_grade_average,
    note: response.note,
    status: normalizeCaseStatus(response.status),
    escalation_target: normalizeEscalationTarget(response.escalation_target),
    last_event: response.last_event,
    plan_followed: response.plan_followed,
    attendance_trend: response.attendance_trend,
    marks_trend: response.marks_trend,
    failures_trend: response.failures_trend,
    follow_up_assessed_at: response.follow_up_assessed_at ?? undefined,
    follow_up_confidence: response.follow_up_confidence ?? undefined,
    follow_up_decision: response.follow_up_decision ?? undefined,
    follow_up_generated_by: response.follow_up_generated_by ?? undefined,
    follow_up_next_steps: response.follow_up_next_steps ?? undefined,
    follow_up_rationale: response.follow_up_rationale ?? undefined,
    closed_at: response.closed_at ?? undefined,
    recommendation_text: response.recommendation,
    recommendation_summary: response.recommendation_summary,
    evidence_case_ids: response.evidence_case_ids,
    events: response.events,
    created_at: response.created_at,
    updated_at: response.updated_at,
  };
}

function studentDraftFromRecord(record: StudentCaseRecord): StudentDraft {
  return {
    student_id: record.student_id,
    parent_email: record.parent_email ?? "",
    school: record.school,
    age: record.age,
    attendance: record.attendance,
    failures: record.failures,
    absences: 100 - record.attendance,
    study_time: record.study_time,
    previous_grade_average: record.previous_grade_average,
  };
}

function sortCaseRecords(records: StudentCaseRecord[]): StudentCaseRecord[] {
  return [...records].sort((left, right) => {
    if (left.status === "Closed" && right.status !== "Closed") {
      return 1;
    }
    if (right.status === "Closed" && left.status !== "Closed") {
      return -1;
    }
    const riskDifference =
      riskBoardOrder.indexOf(left.risk_category) - riskBoardOrder.indexOf(right.risk_category);
    if (riskDifference !== 0) {
      return riskDifference;
    }
    return Date.parse(right.updated_at) - Date.parse(left.updated_at);
  });
}

function firstOpenCase(records: StudentCaseRecord[]): StudentCaseRecord | null {
  return records.find((record) => record.status !== "Closed") ?? null;
}

function summarizeRecommendation(text: string | undefined): string {
  const summary = plainTextForEmail(text) ?? "";
  return summary.length > 220 ? `${summary.slice(0, 217).trim()}...` : summary;
}

function formatCaseDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "date unknown";
  }
  return date.toLocaleString([], {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  });
}

function isCaseStatus(value: unknown): value is CaseStatus {
  return caseStatuses.includes(value as CaseStatus);
}

function isEscalationTarget(value: unknown): value is EscalationTarget {
  return escalationTargets.includes(value as EscalationTarget);
}

function normalizeCaseStatus(value: string): CaseStatus {
  return isCaseStatus(value) ? value : "Monitoring";
}

function normalizeEscalationTarget(value: string): EscalationTarget {
  return isEscalationTarget(value) ? value : "Academic advisor";
}

function bestF1(training: TrainingResult | null): string | number {
  if (!training) {
    return "--";
  }
  const metric = training.metrics.find((item) => item.model_name === training.best_model);
  return metric?.f1 ?? "--";
}

function isParentMailEligible(prediction: PredictionResponse): boolean {
  return prediction.risk_category === "Medium Risk" || prediction.risk_category === "High Risk";
}

function buildParentEmailDraft(
  student: StudentDraft,
  prediction: PredictionResponse | null,
  recommendation: RecommendationResponse | null,
): ParentMailDraft {
  const studentLabel = student.student_id?.trim() || "your child";
  const riskLabel = prediction?.risk_category.toLowerCase() ?? "current risk";
  const riskScore = prediction ? `${Math.round(prediction.risk_score * 100)}%` : "not yet scored";
  const recommendationText =
    plainTextForEmail(recommendation?.recommendation) ??
    "An advisor support plan will be added here after the recommendation is generated.";

  return {
    parent_email: student.parent_email ?? "",
    subject: `Support plan for ${studentLabel}`,
    body:
      `Dear Parent/Guardian,\n\n` +
      `We are reaching out because ${studentLabel} is currently marked as ${riskLabel} ` +
      `with a risk score of ${riskScore}. We would like to coordinate early support before ` +
      `the concern becomes harder to address.\n\n` +
      `Recommended next steps:\n${recommendationText}\n\n` +
      `Please reply to confirm a convenient time for a short parent-teacher conversation.\n\n` +
      `Regards,\nAcademic Advisor`,
  };
}

function plainTextForEmail(text: string | undefined): string | undefined {
  if (!text) {
    return undefined;
  }
  return text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .trim();
}

function MarkdownText({ className, text }: { className: string; text: string }) {
  return (
    <div className={className}>
      {text.split("\n").map((line, lineIndex) => (
        <p className={lineIndex > 0 ? "mt-2" : ""} key={`${line}-${lineIndex}`}>
          {renderBoldSegments(line)}
        </p>
      ))}
    </div>
  );
}

function renderBoldSegments(line: string) {
  return line.split(/(\*\*[^*]+\*\*)/g).map((segment, index) => {
    if (segment.startsWith("**") && segment.endsWith("**")) {
      return <strong key={`${segment}-${index}`}>{segment.slice(2, -2)}</strong>;
    }
    return <span key={`${segment}-${index}`}>{segment}</span>;
  });
}

function formatContribution(item: FeatureContribution): string {
  const magnitude = Math.round(Math.abs(item.contribution) * 100);
  const direction = item.contribution < 0 ? "lowers risk by" : "raises risk by";
  return `${formatFeatureName(item.feature)} ${direction} ${magnitude}%`;
}

function formatFeatureName(feature: string): string {
  const labels: Record<string, string> = {
    attendance_gap: "attendance gap",
    base_risk: "base risk",
    grade_gap: "grade gap",
    score_cap: "score cap",
    score_floor: "score floor",
    study_time: "study time",
  };
  return labels[feature] ?? feature.replaceAll("_", " ");
}
