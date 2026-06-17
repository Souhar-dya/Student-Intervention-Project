from student_success_assistant.application.agent_workflow import AgentWorkflow, GroundingContext
from student_success_assistant.application.intervention_planner import draft_intervention_plan
from student_success_assistant.application.prediction_service import PredictionService
from student_success_assistant.application.retrieval_service import RetrievalService
from student_success_assistant.schemas.recommendation import RecommendationRequest, RecommendationResponse
from student_success_assistant.schemas.retrieval import SearchFilters


class RecommendationService:
    def __init__(
        self,
        prediction_service: PredictionService,
        retrieval_service: RetrievalService,
        agent_workflow: AgentWorkflow | None = None,
    ) -> None:
        self._prediction_service = prediction_service
        self._retrieval_service = retrieval_service
        self._agent_workflow = agent_workflow or AgentWorkflow()

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        prediction = self._prediction_service.predict(request.prediction)
        student = request.prediction.student
        focused_search = request.search.model_copy(
            update={
                "top_k": 3,
                "query": (
                    f"{request.search.query} Current student: school={student.school}, "
                    f"attendance={student.attendance}%, failures={student.failures}, "
                    f"study_time={student.study_time}, previous_grade_average="
                    f"{student.previous_grade_average}/20."
                ),
                "filters": SearchFilters(
                    school=student.school,
                    min_attendance=max(0, student.attendance - 15),
                    max_attendance=min(100, student.attendance + 15),
                    min_failures=max(0, student.failures - 1),
                    max_failures=min(4, student.failures + 1),
                ),
            },
        )
        retrieval = self._retrieval_service.search(focused_search)

        evidence = [case.case_id for case in retrieval.results[:3]]
        intervention = draft_intervention_plan(prediction, retrieval.results[:3])

        agent_response = self._agent_workflow.generate_recommendation(
            student_id=prediction.student_id,
            evidence_case_ids=evidence,
            context=GroundingContext(
                query=request.search.query,
                prediction=prediction,
                retrieved_cases=retrieval.results[:3],
                student_profile_summary=(
                    f"school={student.school}, attendance={student.attendance}%, "
                    f"absences={student.absences}, failures={student.failures}, "
                    f"study_time={student.study_time}, previous_grade_average="
                    f"{student.previous_grade_average}/20"
                ),
                baseline_recommendation=intervention,
                baseline_reasoning=(
                    "Recommendation generated from validated student risk signals and "
                    "the currently retrieved similar-case evidence."
                ),
            ),
        )
        if agent_response is not None:
            return agent_response

        return RecommendationResponse(
            student_id=prediction.student_id,
            risk_category=prediction.risk_category,
            recommendation=intervention,
            reasoning=(
                "Recommendation generated from validated student risk signals and "
                "the currently retrieved similar-case evidence."
            ),
            evidence_case_ids=evidence,
        )


def get_recommendation_service() -> RecommendationService:
    return RecommendationService(
        prediction_service=PredictionService(),
        retrieval_service=RetrievalService(),
    )
