from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"

MERGE_KEYS = (
    "school",
    "sex",
    "age",
    "address",
    "famsize",
    "Pstatus",
    "Medu",
    "Fedu",
    "Mjob",
    "Fjob",
    "reason",
    "nursery",
    "internet",
)

CANONICAL_FIELDS = [
    "student_id",
    *MERGE_KEYS,
    "studytime",
    "failures",
    "absences",
    "G1",
    "G2",
    "G3",
]


def main() -> None:
    math_rows = _read_csv(RAW_DIR / "student-mat.csv")
    portuguese_rows = _read_csv(RAW_DIR / "student-por.csv")

    math_fieldnames = list(math_rows[0])
    portuguese_fieldnames = list(portuguese_rows[0])
    subject_fields = _subject_fields(math_fieldnames, portuguese_fieldnames)

    portuguese_by_key: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in portuguese_rows:
        portuguese_by_key[_merge_key(row)].append(row)

    merged_rows = []
    for math_row in math_rows:
        for portuguese_row in portuguese_by_key.get(_merge_key(math_row), []):
            merged_rows.append(
                _canonical_row(
                    index=len(merged_rows) + 1,
                    math_row=math_row,
                    portuguese_row=portuguese_row,
                    subject_fields=subject_fields,
                )
            )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DIR / "student-merged.csv"
    output_fields = [
        *CANONICAL_FIELDS,
        *(f"math_{field}" for field in subject_fields),
        *(f"por_{field}" for field in subject_fields),
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(merged_rows)

    print(f"Wrote {len(merged_rows)} rows to {output_path}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        delimiter = ";" if ";" in handle.readline() else ","
        handle.seek(0)
        return list(csv.DictReader(handle, delimiter=delimiter))


def _subject_fields(math_fieldnames: list[str], portuguese_fieldnames: list[str]) -> list[str]:
    shared = [field for field in math_fieldnames if field in portuguese_fieldnames]
    return [field for field in shared if field not in MERGE_KEYS]


def _merge_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[key] for key in MERGE_KEYS)


def _canonical_row(
    *,
    index: int,
    math_row: dict[str, str],
    portuguese_row: dict[str, str],
    subject_fields: list[str],
) -> dict[str, str | int]:
    merged: dict[str, str | int] = {key: math_row[key] for key in MERGE_KEYS}
    merged.update(
        {
            "student_id": f"merged-{index:04d}",
            "studytime": _rounded_average(math_row["studytime"], portuguese_row["studytime"]),
            "failures": max(int(math_row["failures"]), int(portuguese_row["failures"])),
            "absences": _rounded_average(math_row["absences"], portuguese_row["absences"]),
            "G1": _rounded_average(math_row["G1"], portuguese_row["G1"]),
            "G2": _rounded_average(math_row["G2"], portuguese_row["G2"]),
            "G3": _rounded_average(math_row["G3"], portuguese_row["G3"]),
        }
    )
    for field in subject_fields:
        merged[f"math_{field}"] = math_row.get(field, "")
        merged[f"por_{field}"] = portuguese_row.get(field, "")
    return merged


def _rounded_average(left: str, right: str) -> int:
    return round((int(left) + int(right)) / 2)


if __name__ == "__main__":
    main()
