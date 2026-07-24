# VascuRounds AI

A guideline-grounded virtual vascular surgery case conference powered by
DataHub.

> For professional education and simulation only. Not for direct patient-care
> decision-making.

The application retrieves synthetic acute limb ischemia case assets from
DataHub and presents them in clinical Rutherford order. Interactive conferences
are available for Rutherford I, IIa, IIb, and III. The application does not
accept patient data, connect to hospital systems, call an LLM, or provide
patient-care recommendations.

## Acute limb ischemia conferences

Every case uses the same six-stage workflow:

| Stage | Topic | Points |
| --- | --- | ---: |
| 1 | Initial recognition and focused assessment | 20 |
| 2 | Rutherford classification | 20 |
| 3 | Immediate management | 20 |
| 4 | Diagnostic imaging and treatment planning | 20 |
| 5 | Definitive management and escalation | 20 |
| 6 | Performance report | — |

The first five stages contain one four-option MCQ each. Scoring is
deterministic—five questions at 20 points each for a total of 100. Answer
display order is randomized while stable internal answer IDs preserve
correctness. Submissions lock immediately and show the selected answer, correct
answer, rationale, and safety principle. The report summarizes results,
strengths, and review topics; restart clears progress and reshuffles every
stage.

DataHub remains the source of case metadata. A registry links the four exact
synthetic DataHub URNs to repository-local JSON content. Mock mode exposes the
same URNs for offline development and tests. Unknown URNs remain overview-only.
All content is synthetic, educational, contains no real patient information,
and is not direct clinical decision support.

## Requirements

- Python 3.10 or newer
- A DataHub OSS instance reachable at `http://localhost:8080`, unless mock mode
  is used

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATAHUB_GMS_URL` | `http://localhost:8080` | DataHub GMS base URL |
| `DATAHUB_MODE` | `real` | `real`, `mock`, or `auto` |

`real` fails safely when DataHub is unavailable. `mock` uses the bundled
synthetic catalog for tests and offline development. `auto` tries DataHub first
and falls back to the visibly labeled mock catalog.

## Launch

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit listens on port `8501` by default:
<http://localhost:8501>

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```
