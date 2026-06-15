from __future__ import annotations

from dataclasses import dataclass

from student_success_assistant.application.intervention_planner import draft_intervention_plan
from student_success_assistant.infrastructure.student_repository import StudentRepository
from student_success_assistant.schemas.prediction import PredictionResponse, RiskCategory
from student_success_assistant.schemas.retrieval import RetrievedCase

SYSTEM_SCORE_COMPONENTS = {"base_risk", "score_cap", "score_floor"}


@dataclass(frozen=True)
class AdvisorToolResult:
    name: str
    output: str


class AdvisorToolRuntime:
    def __init__(self, repository: StudentRepository | None = None) -> None:
        self._repository = repository or StudentRepository()

    def summarize_retrieved_cases(self, cases: list[RetrievedCase]) -> AdvisorToolResult:
        if not cases:
            return AdvisorToolResult(
                name="summarize_retrieved_cases",
                output="No similar cases were retrieved.",
            )

        lines = [
            f"{case.case_id}: school={case.school}, failures={case.failures}, "
            f"absences={case.absences}, final_grade={case.final_grade}"
            for case in cases[:5]
        ]
        return AdvisorToolResult(name="summarize_retrieved_cases", output="\n".join(lines))

    def summarize_prediction(self, prediction: PredictionResponse) -> AdvisorToolResult:
        student_drivers = [
            item for item in prediction.top_contributors if item.feature not in SYSTEM_SCORE_COMPONENTS
        ]
        student_drivers.sort(key=lambda item: abs(item.contribution), reverse=True)
        contributors = ", ".join(
            f"{item.feature} {item.contribution:+.2f}" for item in student_drivers[:3]
        )
        return AdvisorToolResult(
            name="summarize_prediction",
            output=(
                f"Risk category={prediction.risk_category}, "
                f"risk_score={prediction.risk_score:.2f}, contributors={contributors}"
            ),
        )

    def retrieve_feedback_examples(self, limit: int) -> AdvisorToolResult:
        try:
            rows = self._repository.list_feedback_examples(limit=limit)
        except RuntimeError:
            rows = []

        if not rows:
            return AdvisorToolResult(
                name="retrieve_feedback_examples",
                output="No historical advisor feedback examples available yet.",
            )

        examples = []
        for row in rows:
            label = "follow this pattern" if row["rating"] == "useful" else "avoid this pattern"
            note = f" | Note: {row['advisor_note']}" if row.get("advisor_note") else ""
            examples.append(
                f"{label}: Query: {row['query']} | Recommendation: {row['recommendation']}{note}"
            )
        return AdvisorToolResult(name="retrieve_feedback_examples", output="\n".join(examples))

    def retrieve_judge_examples(self, limit: int) -> AdvisorToolResult:
        try:
            rows = self._repository.list_judged_recommendations(limit=limit)
        except RuntimeError:
            rows = []

        if not rows:
            return AdvisorToolResult(
                name="retrieve_judge_examples",
                output="No judge-scored recommendation examples available yet.",
            )

        examples = []
        for row in rows:
            scores = row.get("scores") or {}
            overall = scores.get("overall", "unknown") if isinstance(scores, dict) else "unknown"
            examples.append(
                f"overall={overall}: Query: {row['query']} | Recommendation: {row['recommendation']}"
            )
        return AdvisorToolResult(name="retrieve_judge_examples", output="\n".join(examples))

    def draft_intervention(
        self,
        prediction: PredictionResponse,
        cases: list[RetrievedCase] | None = None,
    ) -> AdvisorToolResult:
        return AdvisorToolResult(
            name="draft_intervention",
            output=draft_intervention_plan(prediction, cases or []),
        )

    def as_langchain_tools(self):
        try:
            from langchain_core.tools import tool
        except ImportError:
            return []

        @tool
        def summarize_retrieved_cases_tool(case_count: int) -> str:
            """Summarize the retrieved student cases already attached to graph state."""
            return f"Retrieved case count available to graph: {case_count}"

        @tool
        def draft_intervention_tool(risk_category: str) -> str:
            """Draft an intervention from a risk category."""
            if risk_category == RiskCategory.high:
                return (
                    "High risk: immediate advisor follow-up, named staff owner, attendance barrier "
                    "map, mentor assignment, and twice-weekly progress checks. Add a parent-teacher "
                    "meeting when the first checkpoints are missed or the evidence is severe."
                )
            if risk_category == RiskCategory.medium:
                return (
                    "Medium risk: short improvement plan, advisor check-in, and a varied support "
                    "choice such as skill diagnostic, peer study partner, supervised homework block, "
                    "or teacher checkpoint. Use a parent call only if early progress is weak."
                )
            return "Low risk: maintain support, monitor monthly, and reinforce successful routines."

        return [summarize_retrieved_cases_tool, draft_intervention_tool]
