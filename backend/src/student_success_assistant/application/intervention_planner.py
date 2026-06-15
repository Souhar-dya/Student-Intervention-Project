from student_success_assistant.schemas.prediction import PredictionResponse, RiskCategory
from student_success_assistant.schemas.retrieval import RetrievedCase


def draft_intervention_plan(
    prediction: PredictionResponse,
    retrieved_cases: list[RetrievedCase] | None = None,
) -> str:
    drivers = {item.feature: item.contribution for item in prediction.top_contributors}
    variant = _variant_index(prediction.student_id or prediction.risk_category, 3)
    actions = _driver_actions(drivers, variant)
    evidence_note = _evidence_note(retrieved_cases or [])
    risk_percent = round(prediction.risk_score * 100)

    if prediction.risk_category is RiskCategory.high:
        immediate_options = [
            (
                f"Risk is high at {risk_percent}%. Start with an advisor meeting in the next 24-48 "
                "hours and assign one staff owner for the recovery plan."
            ),
            (
                f"Risk is high at {risk_percent}%. Open with a short safeguarding-style check-in: "
                "what is blocking attendance, coursework, sleep, transport, or confidence right now?"
            ),
            (
                f"Risk is high at {risk_percent}%. Move quickly, but keep the first meeting practical: "
                "agree on the next three school days, the next two assignments, and who will verify them."
            ),
        ]
        follow_up_options = [
            "Review attendance and grade movement twice a week for the first two weeks.",
            (
                "Use a 10-minute progress huddle every three school days; add a parent-teacher "
                "meeting only when the student misses the agreed checkpoints."
            ),
            (
                "Check the plan after 72 hours, then weekly. If attendance or task completion does "
                "not move, bring parents and subject teachers into a single escalation call."
            ),
        ]
    elif prediction.risk_category is RiskCategory.medium:
        immediate_options = [
            (
                f"Risk is moderate at {risk_percent}%. Start with an advisor check-in and a short "
                "two-week improvement plan before escalating."
            ),
            (
                f"Risk is moderate at {risk_percent}%. Begin with a student-led reflection: what "
                "changed recently, which class feels most recoverable, and what support would be used?"
            ),
            (
                f"Risk is moderate at {risk_percent}%. Treat this as an early recovery window: set "
                "two visible goals for the next week rather than opening with a formal meeting."
            ),
        ]
        follow_up_options = [
            (
                "Review progress after one week; use a parent-teacher meeting only if attendance, "
                "grade gap, or failure signals do not improve."
            ),
            (
                "Check in after five school days using evidence the student can show: attendance, "
                "completed tasks, and one teacher note."
            ),
            (
                "Reassess at the end of next week. If the student improves, keep the plan light; "
                "if not, add a family call and a subject teacher checkpoint."
            ),
        ]
    else:
        immediate_options = [
            (
                f"Risk is low at {risk_percent}%. Keep the intervention light and reinforce what is "
                "already working."
            ),
            (
                f"Risk is low at {risk_percent}%. Use a maintenance check-in focused on habits that "
                "are already helping."
            ),
            (
                f"Risk is low at {risk_percent}%. Avoid over-intervention; name the protective routine "
                "and keep it visible."
            ),
        ]
        follow_up_options = [
            "Review monthly unless a new attendance or grade concern appears.",
            "Check again next month, or sooner if attendance slips.",
            "Use routine monitoring and only escalate if a new risk driver appears.",
        ]

    immediate = immediate_options[variant]
    follow_up = follow_up_options[variant]
    support_plan = " ".join(actions[:3]) if actions else "Maintain routine academic monitoring."
    return (
        f"Immediate action: {immediate}\n"
        f"Support plan: {support_plan} {evidence_note}\n"
        f"Follow-up check: {follow_up}"
    )


def _driver_actions(drivers: dict[str, float], variant: int) -> list[str]:
    ordered = sorted(drivers.items(), key=lambda item: abs(item[1]), reverse=True)
    actions = []
    for feature, contribution in ordered:
        if contribution <= 0:
            continue
        if feature == "failures":
            actions.append(_choose(
                [
                    (
                        "Prior failures are a major driver, so assign a subject catch-up plan with "
                        "one recoverable target for the next two weeks."
                    ),
                    (
                        "Prior failures need a confidence rebuild: ask each subject teacher for the "
                        "smallest pass-critical task the student can complete first."
                    ),
                    (
                        "Failure history should trigger a skills audit, not just extra homework: find "
                        "whether the gap is concepts, missing work, test anxiety, or attendance."
                    ),
                ],
                variant,
            ))
        elif feature == "attendance_gap":
            actions.append(_choose(
                [
                    (
                        "Attendance is pulling risk upward, so set a weekly attendance target and ask "
                        "the student to identify the top reason for missed classes."
                    ),
                    (
                        "For attendance, build a morning arrival plan with one named adult who notices "
                        "quickly when the student is absent."
                    ),
                    (
                        "Use an attendance map: mark which days or periods are missed most often, then "
                        "remove the specific barrier instead of giving a generic warning."
                    ),
                ],
                variant,
            ))
        elif feature == "grade_gap":
            actions.append(_choose(
                [
                    (
                        "The grade gap is important, so schedule one focused tutoring or doubt-clearing "
                        "session for the weakest subject area."
                    ),
                    (
                        "For the grade gap, use a short diagnostic quiz or teacher conference to find "
                        "the exact missing skill before assigning more practice."
                    ),
                    (
                        "Make grade recovery visible: choose one assessment, one rubric target, and "
                        "one revision opportunity the student can complete this week."
                    ),
                ],
                variant,
            ))
        elif feature == "study_time":
            actions.append(_choose(
                [
                    (
                        "Study routine needs support, so use a small daily study tracker rather than a "
                        "broad generic instruction to study more."
                    ),
                    (
                        "For study time, try a supervised homework block or peer study partner until "
                        "the routine becomes reliable."
                    ),
                    (
                        "Turn study time into a habit cue: same place, same 25-minute block, and one "
                        "completed artifact the student can show."
                    ),
                ],
                variant,
            ))
    return actions


def _evidence_note(cases: list[RetrievedCase]) -> str:
    if not cases:
        return ""

    strongest = cases[0]
    return (
        f"Use the closest historical case ({strongest.case_id}, final grade {strongest.final_grade}) "
        "as a reference point, but adapt the plan to this student's current drivers."
    )


def _variant_index(seed: object, count: int) -> int:
    value = sum(ord(character) for character in str(seed))
    return value % count


def _choose(options: list[str], index: int) -> str:
    return options[index % len(options)]
