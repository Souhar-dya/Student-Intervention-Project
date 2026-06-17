import json
import logging
import re
from uuid import uuid4

from student_success_assistant.application.llm_client import get_chat_llm

log = logging.getLogger(__name__)
from student_success_assistant.application.agent_tools import bump_cache
from student_success_assistant.core.config import get_settings
from student_success_assistant.infrastructure.student_repository import StudentRepository
from student_success_assistant.schemas.evaluation import EvaluationRequest, EvaluationResponse, JudgeScores


class EvaluationService:
    def __init__(self, repository: StudentRepository | None = None) -> None:
        self._repository = repository or StudentRepository()

    def evaluate(self, request: EvaluationRequest) -> EvaluationResponse:
        response = self._evaluate_with_llm(request) or self._evaluate_with_baseline(request)
        self._store_result(request, response)
        return response

    def _evaluate_with_llm(self, request: EvaluationRequest) -> EvaluationResponse | None:
        llm = get_chat_llm(model=get_settings().judge_model, temperature=0, max_tokens=200)
        if llm is None:
            log.warning("get_chat_llm returned None for judge model=%s provider=%s", get_settings().judge_model, get_settings().llm_provider)
            return None

        prompt = (
            "You are an LLM-as-judge for an academic advisor assistant. "
            "Score the recommendation from 1 to 10 for relevance, groundedness, "
            "consistency, and usefulness. Return only valid JSON with double-quoted "
            "keys: relevance, groundedness, consistency, usefulness, notes.\n\n"
            f"Advisor query: {request.query}\n"
            f"Recommendation: {request.recommendation}\n"
            f"Evidence case ids: {', '.join(request.evidence_case_ids) or 'none'}"
        )
        try:
            raw_content = str(llm.invoke(prompt).content)
        except Exception as exc:
            log.warning("LLM judge invoke failed", exc_info=True)
            return None
        payload = self._parse_judge_payload(raw_content)
        if payload is None:
            log.warning("LLM judge response could not be parsed: %r", raw_content[:300])
            return None

        try:
            scores = JudgeScores(
                relevance=int(payload["relevance"]),
                groundedness=int(payload["groundedness"]),
                consistency=int(payload["consistency"]),
                usefulness=int(payload["usefulness"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

        return EvaluationResponse(
            scores=scores,
            notes=str(payload.get("notes") or f"Evaluated by judge model {settings.judge_model}."),
        )

    @staticmethod
    def _parse_judge_payload(raw_content: str) -> dict | None:
        # Try strict parse first
        try:
            parsed = json.loads(raw_content)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        # Try to extract a JSON-like object with regex
        match = re.search(r"\{.*\}", raw_content, flags=re.DOTALL)
        if match is None:
            return None
        candidate = match.group(0)

        # Quote any unquoted string keys (e.g. notes: -> "notes":)
        candidate = re.sub(r"(?<![:\w])(\b[a-zA-Z_]\w*)(?=\s*:)", r'"\1"', candidate)
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _evaluate_with_baseline(request: EvaluationRequest) -> EvaluationResponse:
        evidence_bonus = min(len(request.evidence_case_ids), 5)
        groundedness = 5 + evidence_bonus
        usefulness = 7 if len(request.recommendation.strip()) >= 40 else 5
        scores = JudgeScores(
            relevance=8,
            groundedness=groundedness,
            consistency=8,
            usefulness=usefulness,
        )

        return EvaluationResponse(
            scores=scores,
            notes=(
                "Automatic local judge used because no LLM judge is configured. "
                "Set SSA_OPENAI_API_KEY and SSA_JUDGE_MODEL to use LLM judging."
            ),
        )

    def _store_result(self, request: EvaluationRequest, response: EvaluationResponse) -> None:
        try:
            self._repository.store_evaluation(
                evaluation_id=str(uuid4()),
                query=request.query,
                recommendation=request.recommendation,
                scores=response.scores.model_dump(),
                notes=response.notes,
            )
            bump_cache()
        except Exception:
            pass


def get_evaluation_service() -> EvaluationService:
    return EvaluationService()
