# VascuRounds AI

A guideline-grounded virtual vascular surgery case conference powered by
DataHub.

> For professional education and simulation only. Not for direct patient-care
> decision-making.

The first functional milestone retrieves synthetic acute limb ischemia case
assets from DataHub and presents them in clinical Rutherford order. It does not
accept patient data, connect to hospital systems, call an LLM, or provide
patient-care recommendations.

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
