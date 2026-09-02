# ControlPlane

> AI runtime governance — observe, detect, decide, intervene.

## What It Does

ControlPlane sits between your AI model and the outside world. Every model response passes through a pipeline of detectors that evaluate it across multiple dimensions, then a policy engine produces a control decision: Allow, Modify, Block, or Escalate.

```
Model Response
      |
      v
ControlPlane
      |
      +-- Performance (factual claims vs evidence)
      +-- Cost (tokens, latency, budget)
      +-- Responsibility (PII, secrets, unsafe content)
      |
      v
Findings --> Policy --> Decision --> Intervention --> Audit
```

No access to model internals required. Works with any provider through a normalized adapter interface.

## Control Dimensions

### Performance
Evaluates factual claims against a local evidence corpus. Extracts claims, ranks sources, detects conflicts, and surfaces uncertainty when evidence is insufficient.

### Cost
Tracks input/output tokens, latency, and estimated cost against configurable budgets. Flags responses that exceed resource limits.

### Responsibility
Regex-based detectors for PII (SSN, email, phone, credit card), secrets (AWS keys, GitHub tokens, OpenAI keys, PEM headers), unsafe content (violence, self-harm, illegal activity), and prompt injection patterns.

## Control Decisions

| Decision | Meaning |
|----------|---------|
| **ALLOW** | Response proceeds unchanged |
| **MODIFY** | Response is transformed (e.g., PII redaction) before release |
| **BLOCK** | Response must not be released |
| **ESCALATE** | Human review required |

Policies define which findings trigger which decisions. The same finding can produce different outcomes under different policies (Balanced, Strict, Lenient).

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### Quick Start

```bash
git clone <repository-url>
cd controlplane

# Python environment
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"

# Install frontend dependencies
cd ui && npm install && cd ..

# Start everything
python launch.py
```

This launches:
- **Backend**: `http://localhost:8000` (FastAPI + uvicorn)
- **Frontend**: `http://localhost:5173` (Vite dev server)
- **API docs**: `http://localhost:8000/docs`

### Manual Start

```bash
# Backend
python -m uvicorn controlplane.api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (separate terminal)
cd ui
npm run dev
```

## UI Pages

| Page | Purpose |
|------|---------|
| **Control Room** | Send prompts, run scenarios, see live results |
| **Runs** | Execution history with filtering and search |
| **Effects** | What ControlPlane changed — side-by-side comparisons |
| **Policies** | Balanced, Strict, Lenient policy configurations |
| **Audit** | Full decision evidence trail with findings and interventions |
| **Insights** | Aggregated metrics and trends |
| **Settings** | System configuration |

### Session Behavior

Each UI session starts with a clean state — zero runs, zero audit records, zero metrics. During the session, executions accumulate normally. Closing and reopening the browser resets everything back to zero. Demo scenarios and policies are static configuration and persist across sessions.

## Demo Scenarios

Nine pre-built scenarios covering the full detection spectrum:

| # | Scenario | Expected | Description |
|---|----------|----------|-------------|
| 01 | Clean | ALLOW | No issues detected |
| 02 | Confidently Wrong | BLOCK | Unverifiable factual claim |
| 03 | Expensive | ESCALATE | Exceeds cost budget |
| 04 | Sensitive | ALLOW + MODIFY | PII detected, redacted |
| 05 | Secrets | BLOCK | API keys in response |
| 06 | Unsafe | BLOCK | Harmful content pattern |
| 07 | Multi-Risk | BLOCK | Multiple findings across dimensions |
| 08 | Policy Test | varies | Same scenario under different policies |
| 09 | Unknown Pricing | varies | Cost detection with unavailable pricing |

### Running Demos

**Web UI**: Open `http://localhost:5173`, go to Effects page, select a scenario card, and run it.

**Compare policies**: Switch to "Policy Comparison" mode on the Effects page to see how the same scenario behaves under Balanced, Strict, and Lenient policies.

## Architecture

```
src/controlplane/
  api/            FastAPI endpoints, session management
  runtime/        Core pipeline orchestrator
  detection/      PII, secrets, unsafe, cost, performance detectors
  decision/       Policy evaluation, hard constraints, assurance
  verification/   Evidence retrieval, source ranking, conflict resolution
  persistence/    JSON file-based audit store
  monitoring/     Aggregated metrics and interaction summaries
  traffic/        Real-time interception and demo traffic generation
  schemas/        Data models (Interaction, Finding, Decision, etc.)
  demo/           Scenarios, simulated model, demo runner
  gateway/        Model adapter interface (OpenAI, Anthropic, simulated)

ui/
  src/
    pages/        Control Room, Runs, Effects, Policies, Audit, Insights, Settings
    components/   Finding cards, decision banners, timeline, comparison tables
    api.ts        Frontend API client
    types.ts      TypeScript interfaces
  tailwind.config.js   Design tokens and color system
```

## Configuration

### Environment Variables

```bash
# Optional — only needed for real model providers
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

The demo runs entirely on simulated models with no API keys required.

### Policies

Policies are defined in `src/controlplane/policy_registry.py`:

- **Balanced**: Standard thresholds for all dimensions
- **Strict**: Lower tolerance, more aggressive blocking
- **Lenient**: Higher thresholds, more permissive

### Custom Detectors

Implement the `BaseDetector` interface:

```python
from controlplane.detection.base import BaseDetector

class MyDetector(BaseDetector):
    detector_id = "my_detector"
    version = "1.0.0"

    def detect(self, observation, context, policy):
        # Your detection logic
        return findings  # list[Finding]
```

Register it in the runtime initialization.

## Testing

```bash
python -m pytest tests/ -v
```

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, Pydantic, uvicorn
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Storage**: JSON files (file-based audit store)
- **No database required** for demo/development use

## Limitations

V1 prototype. Known constraints:

- Performance verification depends on a local evidence corpus
- Regex-based detectors have known blind spots
- No multi-turn conversation support
- No real-time streaming interception
- No authentication, rate limiting, or multi-tenant isolation
- Audit storage is file-based; production would use a database
- Traffic interceptor is pull-based, not autonomous

## License

See [LICENSE](LICENSE).
