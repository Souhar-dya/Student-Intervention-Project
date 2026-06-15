from student_success_assistant.infrastructure.embeddings import EmbeddingProvider, get_embedding_provider
from student_success_assistant.infrastructure.qdrant_store import QdrantCaseStore
from student_success_assistant.infrastructure.reranker import Reranker, get_reranker
from student_success_assistant.infrastructure.student_repository import StudentRepository
from student_success_assistant.schemas.retrieval import RetrievedCase, SearchRequest, SearchResponse

HYBRID_CANDIDATE_LIMIT = 20
RRF_K = 60


class RetrievalService:
    def __init__(
        self,
        case_store: QdrantCaseStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        repository: StudentRepository | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self._case_store = case_store or QdrantCaseStore()
        self._embedding_provider = embedding_provider or get_embedding_provider()
        self._repository = repository or StudentRepository()
        self._reranker = reranker or get_reranker()

    def search(self, request: SearchRequest) -> SearchResponse:
        if self._case_store.is_configured():
            try:
                return self._search_hybrid(request)
            except Exception:
                pass

        repository_response = self._search_repository(request)
        if repository_response is not None:
            return repository_response

        return self._baseline_search(request)

    def _search_hybrid(self, request: SearchRequest) -> SearchResponse:
        filters = request.filters.model_dump(exclude_none=True)
        dense_matches = self._dense_qdrant_matches(request, filters)
        sparse_matches = self._sparse_bm25_matches(request, filters)
        fused = self._rrf_fuse([dense_matches, sparse_matches])
        reranked = self._reranker.rerank(
            request.query,
            fused[:HYBRID_CANDIDATE_LIMIT],
            limit=request.top_k,
        )
        return self._to_response(request.query, reranked)

    def _dense_qdrant_matches(self, request: SearchRequest, filters: dict) -> list[dict]:
        vector = self._embedding_provider.embed(request.query)
        matches = self._case_store.search(
            vector=vector,
            filters=filters,
            limit=HYBRID_CANDIDATE_LIMIT,
        )
        return [self._match_to_case(match) for match in matches]

    def _search_repository(self, request: SearchRequest) -> SearchResponse | None:
        try:
            rows = self._repository.search_cases(
                filters=request.filters.model_dump(exclude_none=True),
                limit=200,
            )
        except Exception:
            return None

        if not rows:
            return SearchResponse(query=request.query, total=0, results=[])

        query_terms = set(request.query.lower().split())
        scored_rows = []
        for row in rows:
            case_text = row["case_text"]
            text_terms = set(case_text.lower().split())
            sparse_score = len(query_terms & text_terms) / max(len(query_terms), 1)
            payload = row["payload"]
            similarity_score = self._structured_similarity(request.filters.model_dump(), payload)
            scored_rows.append((min(0.99, 0.25 + sparse_score * 0.25 + similarity_score * 0.5), row))

        scored_rows.sort(key=lambda item: item[0], reverse=True)
        results = [
            RetrievedCase(
                case_id=row["case_id"],
                student_id=row["student_id"],
                score=round(score, 3),
                school=row["payload"].get("school", "NA"),
                failures=row["payload"].get("failures", 0),
                absences=row["payload"].get("absences", 0),
                final_grade=row["payload"].get("final_grade", 0),
                case_text=row["case_text"],
            )
            for score, row in scored_rows[: request.top_k]
        ]
        return SearchResponse(query=request.query, total=len(scored_rows), results=results)

    def _sparse_bm25_matches(self, request: SearchRequest, filters: dict) -> list[dict]:
        rows = self._repository.search_cases(filters=filters, limit=500)
        if not rows:
            return []

        tokenized_corpus = [self._tokens(row["case_text"]) for row in rows]
        tokenized_query = self._tokens(request.query)
        if not tokenized_query:
            return []

        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            return self._fallback_sparse_matches(rows, tokenized_query)

        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(tokenized_query)
        query_terms = set(tokenized_query)
        scored = [
            (float(score), self._row_to_case(row, score=float(score)))
            for score, row, row_tokens in zip(scores, rows, tokenized_corpus, strict=False)
            if float(score) > 0 or query_terms & set(row_tokens)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [case for _, case in scored[:HYBRID_CANDIDATE_LIMIT]]

    @staticmethod
    def _fallback_sparse_matches(rows: list[dict], tokenized_query: list[str]) -> list[dict]:
        query_terms = set(tokenized_query)
        scored = []
        for row in rows:
            text_terms = set(RetrievalService._tokens(row["case_text"]))
            score = len(query_terms & text_terms) / max(len(query_terms), 1)
            if score > 0:
                scored.append((score, RetrievalService._row_to_case(row, score=score)))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [case for _, case in scored[:HYBRID_CANDIDATE_LIMIT]]

    @staticmethod
    def _rrf_fuse(rankings: list[list[dict]]) -> list[dict]:
        fused_scores: dict[str, float] = {}
        cases_by_id: dict[str, dict] = {}
        for ranking in rankings:
            for rank, case in enumerate(ranking, start=1):
                case_id = case["case_id"]
                cases_by_id.setdefault(case_id, case)
                fused_scores[case_id] = fused_scores.get(case_id, 0.0) + 1 / (RRF_K + rank)

        fused = [
            {**cases_by_id[case_id], "score": score}
            for case_id, score in fused_scores.items()
        ]
        fused.sort(key=lambda item: item["score"], reverse=True)
        return fused

    @staticmethod
    def _match_to_case(match: dict) -> dict:
        payload = match["payload"]
        return {
            "case_id": payload.get("case_id", match["id"]),
            "student_id": payload.get("student_id", "unknown"),
            "score": float(match["score"]),
            "school": payload.get("school", "NA"),
            "failures": payload.get("failures", 0),
            "absences": payload.get("absences", 0),
            "final_grade": payload.get("final_grade", 0),
            "case_text": payload.get("case_text", ""),
        }

    @staticmethod
    def _row_to_case(row: dict, *, score: float) -> dict:
        payload = row["payload"]
        return {
            "case_id": row["case_id"],
            "student_id": row["student_id"],
            "score": score,
            "school": payload.get("school", "NA"),
            "failures": payload.get("failures", 0),
            "absences": payload.get("absences", 0),
            "final_grade": payload.get("final_grade", 0),
            "case_text": row["case_text"],
        }

    @staticmethod
    def _to_response(query: str, cases: list[dict]) -> SearchResponse:
        results = [
            RetrievedCase(
                case_id=case["case_id"],
                student_id=case["student_id"],
                score=round(float(case["score"]), 3),
                school=case["school"],
                failures=case["failures"],
                absences=case["absences"],
                final_grade=case["final_grade"],
                case_text=case["case_text"],
            )
            for case in cases
        ]
        return SearchResponse(query=query, total=len(cases), results=results)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [
            token.strip(".,:;!?()[]{}").lower()
            for token in text.split()
            if token.strip(".,:;!?()[]{}")
        ]

    @staticmethod
    def _structured_similarity(filters: dict, payload: dict) -> float:
        score = 0.0
        weight = 0.0
        min_attendance = filters.get("min_attendance")
        max_attendance = filters.get("max_attendance")
        if min_attendance is not None and max_attendance is not None:
            target = (min_attendance + max_attendance) / 2
            attendance = float(payload.get("attendance", target))
            score += max(0.0, 1 - abs(attendance - target) / 100)
            weight += 1

        min_failures = filters.get("min_failures")
        max_failures = filters.get("max_failures")
        if min_failures is not None and max_failures is not None:
            target = (min_failures + max_failures) / 2
            failures = float(payload.get("failures", target))
            score += max(0.0, 1 - abs(failures - target) / 4)
            weight += 1

        if weight == 0:
            return 0.5
        return score / weight

    @staticmethod
    def _baseline_search(request: SearchRequest) -> SearchResponse:
        query_terms = request.query.lower().split()
        baseline_score = min(0.5 + (len(query_terms) * 0.03), 0.95)
        min_attendance = request.filters.min_attendance
        max_attendance = request.filters.max_attendance
        attendance = round(((min_attendance or 0) + (max_attendance or 100)) / 2)
        absences = 100 - attendance
        min_failures = request.filters.min_failures
        max_failures = request.filters.max_failures
        failures = min_failures if min_failures is not None else max_failures or 1
        final_grade = 8 if attendance < 50 or failures >= 2 else 14
        outcome = "At Risk" if final_grade < 10 else "Passed"

        results = [
            RetrievedCase(
                case_id="case-baseline-001",
                student_id="historical-001",
                score=round(baseline_score, 3),
                school=request.filters.school or "GP",
                failures=failures,
                absences=absences,
                final_grade=final_grade,
                case_text=(
                    "Student attends GP school. Study time level is high. "
                    f"Previous failures: {failures}. Absences: {absences}. "
                    f"Final grade: {final_grade}. Outcome: {outcome}."
                ),
            ),
            RetrievedCase(
                case_id="case-baseline-002",
                student_id="historical-002",
                score=round(max(baseline_score - 0.09, 0.1), 3),
                school=request.filters.school or "MS",
                failures=min(4, failures + 1),
                absences=min(100, absences + 8),
                final_grade=max(0, final_grade - 2),
                case_text=(
                    "Student attends MS school. Study time level is medium. "
                    f"Previous failures: {min(4, failures + 1)}. "
                    f"Absences: {min(100, absences + 8)}. "
                    f"Final grade: {max(0, final_grade - 2)}. "
                    f"Outcome: {'At Risk' if max(0, final_grade - 2) < 10 else 'Passed'}."
                ),
            ),
        ]

        return SearchResponse(query=request.query, total=len(results), results=results[: request.top_k])


def get_retrieval_service() -> RetrievalService:
    return RetrievalService()
