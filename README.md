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
| `DATAHUB_REQUIRED` | `true` in `real` mode | Require the live four-case DataHub catalog and prohibit fallback |

`real` uses DataHub and defaults to required mode. `auto` tries DataHub first
and, only when `DATAHUB_REQUIRED=false`, falls back to the visibly labeled
synthetic catalog. `mock` explicitly uses the offline catalog and never reports
DataHub as connected. `DATAHUB_REQUIRED` accepts `true`, `1`, `yes`, `on` and
`false`, `0`, `no`, `off`.

The public Codespace port-8501 URL is the browser-facing Streamlit URL. It must
never be used as `DATAHUB_GMS_URL`; Streamlit reaches DataHub GMS internally at
`http://localhost:8080`.

## Deployment options

VascuRounds AI has two intentional demonstration deployments:

| Deployment | Case metadata source | Status |
| --- | --- | --- |
| GitHub Codespace | DataHub GMS running alongside Streamlit in the same Codespace | Official live DataHub integration |
| Streamlit Community Cloud | Bundled synthetic catalog | Offline demonstration |

The Streamlit Community Cloud application cannot reach DataHub running inside
a separate Codespace through `localhost`. It therefore uses explicit mock mode
and must identify itself as an offline demonstration. The live integration is
available through the Codespace deployment; no temporary Codespace URL is
embedded in this repository.

## Competition demonstration

Run the live demonstration inside the same GitHub Codespace as DataHub OSS:

```bash
cd /workspaces/vascurounds-ai

export DATAHUB_MODE=real
export DATAHUB_REQUIRED=true
export DATAHUB_GMS_URL=http://localhost:8080

python3 scripts/check_datahub.py
bash scripts/start_competition_demo.sh
```

If the four case assets are absent, seed their canonical URNs idempotently and
run the check again:

```bash
python3 scripts/seed_datahub.py
python3 scripts/check_datahub.py
```

The application must show:

```text
DataHub connected — live integration active.
Synthetic educational cases loaded from DataHub metadata.
```

Then make port `8501` **Public** in the Codespace Ports panel and open its
forwarded URL. Port `8080` may remain private. DataHub's UI is available on
port `9002` when needed.

This warning:

```text
Offline demonstration active — bundled synthetic catalog (automatic fallback).
```

means development fallback mode is active; it is not the live competition
demonstration. Streamlit Community Cloud cannot reach a DataHub service at
`localhost:8080` inside a separate Codespace.

The explicit Streamlit Community Cloud deployment shows:

```text
Offline demonstration active — bundled synthetic catalog (explicit mock mode).
```

Both offline messages direct users to the GitHub Codespace deployment for the
live DataHub integration.

For development fallback:

```bash
export DATAHUB_MODE=auto
export DATAHUB_REQUIRED=false
export DATAHUB_GMS_URL=http://localhost:8080
python3 -m streamlit run app.py
```

For explicit offline development:

```bash
export DATAHUB_MODE=mock
export DATAHUB_REQUIRED=false
python3 -m streamlit run app.py
```

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
