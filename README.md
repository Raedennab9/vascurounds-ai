# VascuRounds AI

A guideline-grounded virtual vascular surgery case conference powered by
DataHub.

> For professional education and simulation only. Not for direct patient-care
> decision-making.

The application retrieves synthetic acute limb ischemia case assets from
DataHub and presents them in clinical Rutherford order. The Rutherford IIa
asset now opens a six-stage educational case conference with five scored MCQs
and a performance report. It does not accept patient data, connect to hospital
systems, call an LLM, or provide patient-care recommendations.

## Rutherford IIa conference

The five clinical stages award 100 deterministic points:

| Stage | Topic | Points |
| --- | --- | ---: |
| 1 | Initial recognition and focused assessment | 20 |
| 2 | Rutherford classification | 20 |
| 3 | Immediate management | 20 |
| 4 | Diagnostic imaging and treatment planning | 20 |
| 5 | Definitive management and escalation | 20 |

Stage 6 reports performance and awards no additional points. Each new attempt
randomizes the A–D option order while retaining stable internal answer IDs.
The structured local content is bound at runtime only to:

```text
urn:li:dataset:(urn:li:dataPlatform:file,vascurounds.synthetic_cases.ali_marginally_threatened,DEV)
```

DataHub remains the source of the case metadata. Other Rutherford assets remain
overview-only.

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
