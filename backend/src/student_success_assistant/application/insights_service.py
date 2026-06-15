from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from student_success_assistant.application.llm_client import get_chat_llm
from student_success_assistant.core.config import get_settings
from student_success_assistant.schemas.insights import (
    FactorInsight,
    FactorInsightRequest,
    FactorInsightResponse,
)


EXCLUDED_FACTOR_FIELDS = {"student_id", "G3", "math_G3", "por_G3"}

LABELS = {
    "G1": "first period grade",
    "G2": "second period grade",
    "Medu": "mother education",
    "Fedu": "father education",
    "Mjob": "mother job",
    "Fjob": "father job",
    "Pstatus": "parent cohabitation status",
    "Dalc": "weekday alcohol consumption",
    "Walc": "weekend alcohol consumption",
    "famrel": "family relationship quality",
    "famsize": "family size",
    "famsup": "family educational support",
    "goout": "going out",
    "schoolsup": "school support",
    "studytime": "study time",
    "traveltime": "travel time",
}

FAMILY_TERMS = (
    "family",
    "famil",
    "famrel",
    "famsize",
    "famsup",
    "parent",
    "mother",
    "father",
    "guardian",
    "mjob",
    "fjob",
    "medu",
    "fedu",
    "pstatus",
)

ALLOWED_PROMPT_TERMS = (
    "student",
    "students",
    "success",
    "failure",
    "fail",
    "pass",
    "risk",
    "grade",
    "grades",
    "g1",
    "g2",
    "g3",
    "mark",
    "marks",
    "score",
    "scores",
    "performance",
    "performing",
    "top",
    "best",
    "factor",
    "factors",
    "feature",
    "features",
    "attendance",
    "absence",
    "absences",
    "study",
    "school",
    "education",
    "support",
    "dataset",
    "data",
    "uci",
    *FAMILY_TERMS,
)

GUARDRAIL_ANSWER = (
    "I can only answer questions about this student performance dataset, student success or "
    "failure factors, risk signals, grades, attendance, family or school context, and top or "
    "at-risk students. Please ask a question in that scope."
)


class InsightsService:
    def summarize_factors(self, request: FactorInsightRequest) -> FactorInsightResponse:
        if not self._is_allowed_prompt(request.prompt):
            return FactorInsightResponse(
                prompt=request.prompt,
                source_path="",
                row_count=0,
                summary="Prompt rejected by dataset-scope guardrail.",
                answer=GUARDRAIL_ANSWER,
                generated_by="guardrail",
                factors=[],
            )

        settings = get_settings()
        source_path = Path(request.path or settings.default_dataset_path)
        rows = self._read_rows(source_path)
        if len(rows) < 2:
            raise ValueError("At least two rows are required to summarize factor influence.")

        factors = self._factor_insights(rows)
        summary = self._summary(factors)
        llm_answer = self._answer_with_llm(
            prompt=request.prompt,
            row_count=len(rows),
            summary=summary,
            factors=factors,
            rows=rows,
        )
        answer = llm_answer or self._fallback_answer(request.prompt, rows, factors, summary)
        return FactorInsightResponse(
            prompt=request.prompt,
            source_path=str(source_path),
            row_count=len(rows),
            summary=summary,
            answer=answer,
            generated_by="llm" if llm_answer else "deterministic",
            factors=factors,
        )

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found: {path} (resolved: {path.resolve()})")

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            delimiter = ";" if ";" in handle.readline() else ","
            handle.seek(0)
            return list(csv.DictReader(handle, delimiter=delimiter))

    def _factor_insights(self, rows: list[dict[str, str]]) -> list[FactorInsight]:
        passed = [row for row in rows if int(row["G3"]) >= 10]
        at_risk = [row for row in rows if int(row["G3"]) < 10]
        if not passed or not at_risk:
            raise ValueError("Factor analysis requires both passing and at-risk outcomes.")

        insights = []
        for feature in rows[0]:
            if feature in EXCLUDED_FACTOR_FIELDS:
                continue
            values = [row.get(feature, "") for row in rows]
            if not any(values):
                continue
            if self._is_numeric(values):
                insights.append(self._numeric_factor(feature, passed, at_risk))
            elif len(set(values)) <= 20:
                insights.append(self._categorical_factor(feature, rows))

        return sorted(insights, key=lambda item: item.strength, reverse=True)

    def _numeric_factor(
        self,
        feature: str,
        passed: list[dict[str, str]],
        at_risk: list[dict[str, str]],
    ) -> FactorInsight:
        label = self._label(feature)
        passed_values = [float(row[feature]) for row in passed]
        at_risk_values = [float(row[feature]) for row in at_risk]
        all_values = passed_values + at_risk_values
        passed_average = sum(passed_values) / len(passed_values)
        at_risk_average = sum(at_risk_values) / len(at_risk_values)
        diff = passed_average - at_risk_average
        value_range = max(all_values) - min(all_values)
        strength = abs(diff) / value_range if value_range else 0
        association = "success" if diff > 0 else "failure"
        direction = "higher" if association == "success" else "lower"
        if any(term in feature.lower() for term in ("failures", "absences")):
            direction = "lower" if association == "success" else "higher"
        explanation = (
            f"{label.title()} averaged {passed_average:.1f} for passing students and "
            f"{at_risk_average:.1f} for at-risk students, so {direction} {label} is "
            f"associated with {association} in this dataset."
        )
        return FactorInsight(
            feature=label,
            association=association,
            strength=round(strength, 3),
            passed_average=round(passed_average, 2),
            at_risk_average=round(at_risk_average, 2),
            explanation=explanation,
        )

    def _categorical_factor(self, feature: str, rows: list[dict[str, str]]) -> FactorInsight:
        label = self._label(feature)
        groups = {}
        for row in rows:
            value = row.get(feature, "unknown") or "unknown"
            groups.setdefault(value, {"passed": 0, "total": 0})
            groups[value]["total"] += 1
            groups[value]["passed"] += 1 if int(row["G3"]) >= 10 else 0

        group_rates = {
            value: counts["passed"] / counts["total"]
            for value, counts in groups.items()
            if counts["total"] >= 3
        }
        if not group_rates:
            group_rates = {
                value: counts["passed"] / counts["total"]
                for value, counts in groups.items()
            }

        best_value, best_rate = max(group_rates.items(), key=lambda item: item[1])
        worst_value, worst_rate = min(group_rates.items(), key=lambda item: item[1])
        strength = best_rate - worst_rate
        explanation = (
            f"{label.title()} has a {best_rate:.0%} pass rate for '{best_value}' and "
            f"{worst_rate:.0%} for '{worst_value}', a {strength:.0%} spread across groups."
        )
        return FactorInsight(
            feature=label,
            association="success",
            strength=round(strength, 3),
            passed_average=round(best_rate, 3),
            at_risk_average=round(worst_rate, 3),
            explanation=explanation,
        )

    @staticmethod
    def _summary(factors: list[FactorInsight]) -> str:
        top = factors[:3]
        factor_names = ", ".join(item.feature for item in top)
        return (
            f"Top signals in the merged dataset are {factor_names}. "
            "The analysis scans canonical fields, subject-specific grade/behavior columns, "
            "and family or social context fields preserved from the raw files."
        )

    def _answer_with_llm(
        self,
        *,
        prompt: str,
        row_count: int,
        summary: str,
        factors: list[FactorInsight],
        rows: list[dict[str, str]],
    ) -> str | None:
        llm = get_chat_llm()
        if llm is None:
            return None

        top_students = self._top_students(rows, limit=8)
        selected_factors = self._select_prompt_factors(prompt, factors)
        factor_lines = "\n".join(
            (
                f"- {factor.feature}: association={factor.association}, "
                f"strength={factor.strength}, passed_avg={factor.passed_average}, "
                f"at_risk_avg={factor.at_risk_average}"
            )
            for factor in selected_factors[:30]
        )
        top_student_lines = "\n".join(
            (
                f"- {student['student_id']}: final={student['final_grade']}, "
                f"g1={student['g1']}, g2={student['g2']}, school={student['school']}, "
                f"failures={student['failures']}, absences={student['absences']}"
            )
            for student in top_students
        )
        llm_prompt = (
            "You are a student-success data analyst. Answer the user's question directly using "
            "only the dataset facts below. If the user asks for students, name the relevant "
            "student IDs from the top-student list. If the user asks about factors, explain the "
            "factor direction in plain language. Keep the answer concise and advisor-facing.\n\n"
            f"User question: {prompt}\n"
            f"Rows analyzed: {row_count}\n"
            f"Dataset summary: {summary}\n\n"
            f"Factor evidence:\n{factor_lines}\n\n"
            f"Top-performing student candidates:\n{top_student_lines}"
        )
        try:
            response = llm.invoke(llm_prompt)
        except Exception:
            return None

        content = str(response.content).strip()
        return content or None

    def _fallback_answer(
        self,
        prompt: str,
        rows: list[dict[str, str]],
        factors: list[FactorInsight],
        summary: str,
    ) -> str:
        normalized_prompt = prompt.lower()
        if any(term in normalized_prompt for term in ("top", "best", "performing", "highest")):
            top_students = self._top_students(rows, limit=5)
            student_text = "; ".join(
                (
                    f"{student['student_id']} scored final {student['final_grade']} "
                    f"(G1 {student['g1']}, G2 {student['g2']}, school {student['school']})"
                )
                for student in top_students
            )
            return (
                "The top-performing students in the merged dataset are ranked by final grade, "
                f"then prior grade history: {student_text}."
            )

        if any(term in normalized_prompt for term in ("habit", "protective", "protect", "medium-risk")):
            study_time = next((factor for factor in factors if factor.feature == "study time"), None)
            grade_factor = next((factor for factor in factors if factor.feature == "second period grade"), None)
            details = []
            if study_time:
                details.append(
                    f"study time is protective: passing students averaged {study_time.passed_average}, "
                    f"while at-risk students averaged {study_time.at_risk_average}"
                )
            if grade_factor:
                details.append(
                    f"grade momentum matters: passing students averaged {grade_factor.passed_average} "
                    f"on second period grade versus {grade_factor.at_risk_average} for at-risk students"
                )
            return "For medium-risk students, the strongest protective patterns are " + "; ".join(details) + "."

        if any(term in normalized_prompt for term in FAMILY_TERMS):
            family_factors = self._family_factors(factors)
            if family_factors:
                details = "; ".join(factor.explanation for factor in family_factors[:5])
                return (
                    "Family context is now included in the merged dataset. The strongest family-related "
                    f"signals I found are: {details}"
                )
            return (
                "Family context columns are present, but none produced a measurable difference in this "
                "merged dataset after comparing passing and at-risk outcomes."
            )

        top_factors = "; ".join(factor.explanation for factor in factors[:3])
        return f"{summary} In plain terms: {top_factors}"

    @staticmethod
    def _is_numeric(values: list[str]) -> bool:
        try:
            for value in values:
                if value == "":
                    return False
                float(value)
        except ValueError:
            return False
        return True

    @staticmethod
    def _is_allowed_prompt(prompt: str) -> bool:
        normalized_prompt = prompt.lower()
        return any(term in normalized_prompt for term in ALLOWED_PROMPT_TERMS)

    def _select_prompt_factors(self, prompt: str, factors: list[FactorInsight]) -> list[FactorInsight]:
        normalized_prompt = prompt.lower()
        if any(term in normalized_prompt for term in FAMILY_TERMS):
            family_factors = self._family_factors(factors)
            return [*family_factors, *[factor for factor in factors if factor not in family_factors]]
        return factors

    @staticmethod
    def _family_factors(factors: list[FactorInsight]) -> list[FactorInsight]:
        return [
            factor
            for factor in factors
            if any(term in factor.feature.lower() for term in FAMILY_TERMS)
        ]

    @staticmethod
    def _label(feature: str) -> str:
        subject = ""
        base = feature
        if feature.startswith("math_"):
            subject = "math "
            base = feature.removeprefix("math_")
        elif feature.startswith("por_"):
            subject = "Portuguese "
            base = feature.removeprefix("por_")

        label = LABELS.get(base, base.replace("_", " "))
        return f"{subject}{label}".strip()

    @staticmethod
    def _top_students(rows: list[dict[str, str]], limit: int) -> list[dict[str, Any]]:
        ranked = sorted(
            rows,
            key=lambda row: (
                int(row["G3"]),
                int(row["G2"]),
                int(row["G1"]),
                -int(row.get("failures", "0")),
                -int(row.get("absences", "0")),
            ),
            reverse=True,
        )
        return [
            {
                "student_id": row.get("student_id", f"row-{index}"),
                "school": row.get("school", "NA"),
                "final_grade": int(row["G3"]),
                "g1": int(row["G1"]),
                "g2": int(row["G2"]),
                "failures": int(row.get("failures", "0")),
                "absences": int(row.get("absences", "0")),
            }
            for index, row in enumerate(ranked[:limit], start=1)
        ]


def get_insights_service() -> InsightsService:
    return InsightsService()
