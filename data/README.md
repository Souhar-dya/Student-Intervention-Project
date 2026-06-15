# Data Assets

Raw UCI Student Performance files live in `data/raw/`.

- `raw/student-mat.csv`: Mathematics records
- `raw/student-por.csv`: Portuguese records
- `scripts/student-merge.R`: Original merge helper, updated to read from `data/raw/`
- `scripts/merge_student_data.py`: Canonical app merge helper
- `processed/student-merged.csv`: Default app dataset, generated from the two raw files

Backend pipeline examples use these paths from the `backend/` working directory:

- `../data/processed/student-merged.csv`

Regenerate the merged dataset from the project root:

```powershell
python data/scripts/merge_student_data.py
```
