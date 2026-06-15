from fastapi.testclient import TestClient

from student_success_assistant.application.agent_tools import AdvisorToolRuntime
from student_success_assistant.domain.model_names import ADVISOR_SCORE_MODEL
from student_success_assistant.main import create_app
from student_success_assistant.schemas.prediction import PredictionResponse, RiskCategory


def authenticated_client() -> TestClient:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "advisor", "password": "advisor-demo"},
    )
    assert response.status_code == 200
    client.headers.update({"Authorization": f"Bearer {response.json()['token']}"})
    return client


def test_login_rejects_invalid_credentials() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "advisor", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_protected_endpoints_require_login() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/predict",
        json={
            "student": {
                "school": "GP",
                "age": 17,
                "attendance": 90,
                "failures": 0,
                "absences": 10,
                "study_time": 2,
                "previous_grade_average": 12,
            }
        },
    )

    assert response.status_code == 401


def test_predict_returns_risk_category() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/predict",
        json={
            "student": {
                "student_id": "student-001",
                "school": "GP",
                "age": 17,
                "attendance": 62,
                "failures": 2,
                "absences": 14,
                "study_time": 1,
                "previous_grade_average": 8,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == "student-001"
    assert body["risk_category"] == "Medium Risk"
    assert body["model_name"] == ADVISOR_SCORE_MODEL
    assert 0 <= body["risk_score"] <= 1
    assert any(item["feature"] == "base_risk" for item in body["top_contributors"])
    assert round(sum(item["contribution"] for item in body["top_contributors"]), 3) == body["risk_score"]


def test_predict_rejects_invalid_attendance() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/predict",
        json={
            "student": {
                "school": "GP",
                "age": 17,
                "attendance": 140,
                "failures": 0,
                "absences": 3,
                "study_time": 2,
                "previous_grade_average": 12,
            }
        },
    )

    assert response.status_code == 422


def test_low_previous_average_pushes_risk_higher() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/predict",
        json={
            "student": {
                "student_id": "student-low-grade",
                "school": "GP",
                "age": 17,
                "attendance": 62,
                "failures": 2,
                "absences": 38,
                "study_time": 1,
                "previous_grade_average": 5,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_category"] == "High Risk"
    assert body["risk_score"] > 0.62
    assert any(
        item["feature"] == "grade_gap" and item["contribution"] > 0.12
        for item in body["top_contributors"]
    )


def test_search_returns_baseline_cases() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/search",
        json={"query": "students with attendance problems", "top_k": 1, "filters": {"school": "GP"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["results"]) == 1
    assert body["results"][0]["school"] == "GP"


def test_feedback_is_accepted() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/feedback",
        json={
            "query": "How should I support this student?",
            "recommendation": "Schedule weekly advisor follow-up.",
            "rating": "useful",
        },
    )

    assert response.status_code == 201
    assert response.json()["stored"] is True


def test_recommend_returns_grounded_response() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/recommend",
        json={
            "prediction": {
                "student": {
                    "student_id": "student-002",
                    "school": "GP",
                    "age": 17,
                    "attendance": 55,
                    "failures": 2,
                    "absences": 20,
                    "study_time": 1,
                    "previous_grade_average": 7,
                }
            },
            "search": {
                "query": "attendance and prior failures",
                "top_k": 2,
                "filters": {"school": "GP"},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == "student-002"
    assert body["recommendation"]
    assert body["evidence_case_ids"]


def test_ingest_csv_without_persistence(tmp_path) -> None:
    client = authenticated_client()
    csv_path = tmp_path / "student-mat.csv"
    csv_path.write_text(
        "school;age;studytime;failures;absences;G1;G2;G3\n"
        "GP;17;2;0;4;12;13;14\n",
        encoding="utf-8",
    )

    response = client.post(
        "/api/v1/admin/ingest",
        json={"path": str(csv_path), "persist": False},
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1


def test_readiness_reports_dependency_configuration() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "degraded"}
    assert {"database", "qdrant", "llm", "langgraph", "langchain"} <= set(body["checks"])


def test_explain_returns_feature_contributions() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/explain",
        json={
            "prediction": {
                "student": {
                    "student_id": "student-003",
                    "school": "GP",
                    "age": 18,
                    "attendance": 70,
                    "failures": 1,
                    "absences": 8,
                    "study_time": 2,
                    "previous_grade_average": 11,
                }
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == "student-003"
    assert body["top_contributors"]
    assert "Risk is" in body["explanation"]


def test_batch_ingest_csv_without_persistence(tmp_path) -> None:
    client = authenticated_client()
    csv_path = tmp_path / "student-por.csv"
    csv_path.write_text(
        "school,age,studytime,failures,absences,G1,G2,G3\n"
        "MS,18,3,1,2,11,12,13\n",
        encoding="utf-8",
    )

    response = client.post(
        "/api/v1/admin/ingest/batch",
        json={"paths": [str(csv_path)], "persist": False},
    )

    assert response.status_code == 200
    assert response.json()[0]["imported"] == 1


def test_factor_insights_use_default_merged_dataset() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/insights/factors",
        json={"prompt": "What factors influence student success or failure?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 382
    assert body["answer"]
    assert body["generated_by"] == "deterministic"
    assert body["factors"]
    assert "student-merged.csv" in body["source_path"]


def test_factor_insights_answer_custom_top_students_prompt() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/insights/factors",
        json={"prompt": "which of the students are top performing students?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "top-performing students" in body["answer"]
    assert "merged-" in body["answer"]
    assert body["summary"] not in body["answer"]


def test_factor_insights_include_family_features() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/insights/factors",
        json={"prompt": "how does family influence student performance?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "Family context is now included" in body["answer"]
    assert len(body["factors"]) > 20
    assert any("family" in factor["feature"].lower() for factor in body["factors"])


def test_factor_insights_reject_unrelated_prompts() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/insights/factors",
        json={"prompt": "write me a recipe for pasta"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["generated_by"] == "guardrail"
    assert body["row_count"] == 0
    assert body["factors"] == []
    assert "student performance dataset" in body["answer"]


def test_advisor_tool_runtime_drafts_intervention() -> None:
    runtime = AdvisorToolRuntime()
    prediction = PredictionResponse(
        student_id="student-tool",
        risk_score=0.8,
        risk_category=RiskCategory.high,
        model_name=ADVISOR_SCORE_MODEL,
        top_contributors=[],
    )

    result = runtime.draft_intervention(prediction)

    assert result.name == "draft_intervention"
    assert "Immediate action:" in result.output
    assert "Support plan:" in result.output
    assert "Follow-up check:" in result.output


def test_parent_email_sends_only_for_medium_or_high_risk() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/parent-email/send",
        json={
            "student": {
                "student_id": "student-parent-001",
                "parent_email": "parent@example.edu",
                "school": "GP",
                "age": 17,
                "attendance": 62,
                "failures": 2,
                "absences": 38,
                "study_time": 1,
                "previous_grade_average": 8,
            },
            "prediction": {
                "student_id": "student-parent-001",
                "risk_score": 0.55,
                "risk_category": "Medium Risk",
                "model_name": ADVISOR_SCORE_MODEL,
                "top_contributors": [],
            },
            "recommendation": "Schedule an advisor check-in and a two-week support plan.",
            "parent_email": "parent@example.edu",
            "subject": "Student support plan",
            "body": "We would like to share a support plan for the next two weeks.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is True
    assert body["sent"] is True
    assert body["delivery_status"] in {"sent", "simulated"}


def test_parent_email_skips_low_risk_students() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/parent-email/send",
        json={
            "student": {
                "student_id": "student-parent-002",
                "parent_email": "parent@example.edu",
                "school": "GP",
                "age": 16,
                "attendance": 96,
                "failures": 0,
                "absences": 4,
                "study_time": 3,
                "previous_grade_average": 15,
            },
            "prediction": {
                "student_id": "student-parent-002",
                "risk_score": 0.1,
                "risk_category": "Low Risk",
                "model_name": ADVISOR_SCORE_MODEL,
                "top_contributors": [],
            },
            "recommendation": "Keep monitoring monthly.",
            "parent_email": "parent@example.edu",
            "subject": "Student support plan",
            "body": "This message should not be sent for low risk.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is False
    assert body["sent"] is False
    assert body["delivery_status"] == "skipped"


def test_follow_up_assessment_escalates_when_two_week_progress_is_weak() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/follow-up/assess",
        json={
            "student": {
                "student_id": "student-demo-001",
                "parent_email": "parent@example.edu",
                "school": "GP",
                "age": 17,
                "attendance": 62,
                "failures": 2,
                "absences": 38,
                "study_time": 1,
                "previous_grade_average": 8,
            },
            "current_risk_category": "Medium Risk",
            "current_risk_score": 0.58,
            "recommendation": "Start an advisor check-in and a two-week improvement plan.",
            "advisor_note": (
                "The student study time has stayed low and attendance improved only a tiny bit."
            ),
            "weeks_since_plan": 2,
            "plan_followed": "Partially followed",
            "attendance_trend": "No clear change",
            "marks_trend": "No new evidence",
            "failures_trend": "No change",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "Escalate"
    assert body["recommended_status"] == "Escalated"
    assert body["escalation_target"] == "Counsellor"


def test_follow_up_assessment_closes_when_progress_is_clear() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/follow-up/assess",
        json={
            "student": {
                "student_id": "student-progress-001",
                "parent_email": "parent@example.edu",
                "school": "GP",
                "age": 16,
                "attendance": 88,
                "failures": 1,
                "absences": 12,
                "study_time": 3,
                "previous_grade_average": 12,
            },
            "current_risk_category": "Medium Risk",
            "current_risk_score": 0.42,
            "recommendation": "Use a two-week advisor plan.",
            "advisor_note": "The student followed the plan and completed the test revision.",
            "weeks_since_plan": 2,
            "plan_followed": "Fully followed",
            "attendance_trend": "Improved",
            "marks_trend": "Improved",
            "failures_trend": "No change",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "Close ticket"
    assert body["recommended_status"] == "Closed"


def test_advisor_tool_runtime_uses_feedback_as_prompt_examples() -> None:
    class FakeRepository:
        def list_feedback_examples(self, limit: int) -> list[dict[str, str | None]]:
            assert limit == 2
            return [
                {
                    "query": "Support attendance",
                    "recommendation": "Schedule weekly check-ins.",
                    "rating": "useful",
                    "advisor_note": None,
                },
                {
                    "query": "Support homework",
                    "recommendation": "Send a generic note.",
                    "rating": "not_useful",
                    "advisor_note": "Too vague",
                },
            ]

    runtime = AdvisorToolRuntime(repository=FakeRepository())  # type: ignore[arg-type]

    result = runtime.retrieve_feedback_examples(limit=2)

    assert "follow this pattern" in result.output
    assert "avoid this pattern" in result.output
    assert "Too vague" in result.output
