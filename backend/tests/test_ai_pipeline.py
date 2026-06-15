from student_success_assistant.application.agent_tools import AdvisorToolRuntime
from student_success_assistant.application.agent_workflow import AgentWorkflow, GroundingContext
from student_success_assistant.application.embedding_pipeline import EmbeddingPipeline
from student_success_assistant.application.retrieval_service import RetrievalService
from student_success_assistant.domain.model_names import ADVISOR_SCORE_MODEL, XGBOOST_MODEL
from student_success_assistant.schemas.prediction import PredictionResponse, RiskCategory
from student_success_assistant.schemas.recommendation import RecommendationResponse
from student_success_assistant.schemas.retrieval import RetrievedCase, SearchFilters, SearchRequest


class FakeEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        assert text
        return [1.0, 0.0, 0.0]


class FakeQdrantStore:
    collection_name = "student_cases"

    def __init__(self) -> None:
        self.points: list[dict] = []
        self.collection_ready = False

    def is_configured(self) -> bool:
        return True

    def ensure_collection(self) -> None:
        self.collection_ready = True

    def upsert_cases(self, points: list[dict]) -> int:
        self.points = points
        return len(points)

    def search(self, vector: list[float], filters: dict, limit: int) -> list[dict]:
        assert vector == [1.0, 0.0, 0.0]
        assert filters["school"] == "GP"
        assert limit == 20
        return [
            {
                "id": "dense-1",
                "score": 0.91,
                "payload": {
                    "case_id": "case-dense",
                    "student_id": "student-dense",
                    "school": "GP",
                    "failures": 2,
                    "absences": 28,
                    "final_grade": 8,
                    "case_text": "Student with attendance problems and prior failures.",
                },
            }
        ]


class FakeCaseRepository:
    def list_cases(self, limit: int) -> list[dict]:
        return [
            {
                "case_id": "case-001",
                "student_id": "student-001",
                "case_text": "Student attends GP school. Previous failures: 2. Outcome: At Risk.",
                "payload": {
                    "student_id": "student-001",
                    "school": "GP",
                    "failures": 2,
                    "absences": 20,
                    "final_grade": 8,
                },
            }
        ]

    def search_cases(self, *, filters: dict, limit: int) -> list[dict]:
        assert filters["school"] == "GP"
        return [
            {
                "case_id": "case-sparse",
                "student_id": "student-sparse",
                "case_text": "Attendance problems failures recovery support.",
                "payload": {
                    "school": "GP",
                    "failures": 2,
                    "absences": 30,
                    "final_grade": 7,
                },
            }
        ]

    def list_feedback_examples(self, limit: int) -> list[dict[str, str | None]]:
        return []

    def list_judged_recommendations(self, limit: int) -> list[dict]:
        return []


class FakeReranker:
    def rerank(self, query: str, cases: list[dict], limit: int) -> list[dict]:
        assert "attendance" in query
        assert {case["case_id"] for case in cases} == {"case-dense", "case-sparse"}
        ordered = sorted(cases, key=lambda case: case["case_id"], reverse=True)
        return ordered[:limit]


def test_hybrid_retrieval_uses_dense_sparse_rrf_and_reranker() -> None:
    service = RetrievalService(
        case_store=FakeQdrantStore(),
        embedding_provider=FakeEmbeddingProvider(),
        repository=FakeCaseRepository(),
        reranker=FakeReranker(),
    )

    response = service.search(
        SearchRequest(
            query="attendance problems and failures",
            top_k=2,
            filters=SearchFilters(school="GP"),
        )
    )

    assert [case.case_id for case in response.results] == ["case-sparse", "case-dense"]


def test_embedding_to_qdrant_pipeline_uploads_one_case() -> None:
    store = FakeQdrantStore()
    pipeline = EmbeddingPipeline(
        repository=FakeCaseRepository(),
        case_store=store,
        embedding_provider=FakeEmbeddingProvider(),
    )

    result = pipeline.run(limit=10)

    assert store.collection_ready is True
    assert result.embedded == 1
    assert result.uploaded == 1
    assert store.points[0]["payload"]["case_id"] == "case-001"


def test_workflow_accepts_retrieved_qdrant_cases_for_recommendation_context() -> None:
    prediction = PredictionResponse(
        student_id="student-workflow",
        risk_score=0.7,
        risk_category=RiskCategory.high,
        model_name=ADVISOR_SCORE_MODEL,
        top_contributors=[],
    )
    cases = [
        RetrievedCase(
            case_id="case-001",
            student_id="student-001",
            score=0.9,
            school="GP",
            failures=2,
            absences=20,
            final_grade=8,
            case_text="Student attends GP school. Previous failures: 2. Outcome: At Risk.",
        )
    ]

    workflow = AgentWorkflow(
        repository=FakeCaseRepository(),  # type: ignore[arg-type]
        tool_runtime=AdvisorToolRuntime(FakeCaseRepository()),  # type: ignore[arg-type]
    )

    response = workflow.generate_recommendation(
        student_id="student-workflow",
        evidence_case_ids=["case-001"],
        context=GroundingContext(
            query="Support attendance",
            prediction=prediction,
            retrieved_cases=cases,
            student_profile_summary="school=GP, attendance=60%, failures=2",
            baseline_recommendation="Immediate action: assign advisor follow-up.",
            baseline_reasoning="Test baseline",
        ),
    )

    assert response is None or isinstance(response, RecommendationResponse)


def test_xgboost_model_name_is_available_for_training_results() -> None:
    assert XGBOOST_MODEL == "xgboost"
