# Agentic Job Copilot

Agentic Job Copilot is a backend-first AI service that analyzes job descriptions against a candidate profile, tailors resumes, drafts outreach, and remembers prior context via semantic memory. It exposes clean FastAPI endpoints backed by LangGraph workflows, Postgres + pgvector persistence, and OpenTelemetry instrumentation.

## Architecture

- **FastAPI** for the HTTP surface with typed Pydantic schemas.
- **LangGraph** orchestrates the business flow (`parse_input → classify_request → retrieve_memory → plan_response → generate_output → review_output → persist_memory → return_result`).
- **Tool layer** implements MCP-style tools for job parsing, profile reading, memory retrieval, and outreach drafting, keeping reusable logic outside workflow nodes.
- **Services** encapsulate LLM interactions (with OpenAI or deterministic fallbacks) for job analysis, resume tailoring, outreach drafting, and semantic memory.
- **PostgreSQL + pgvector** persist users, jobs, applications, memory chunks, and interaction runs. Dev startup auto-creates tables/extension when available.
- **OpenTelemetry** instruments API requests, graph nodes, tool calls, DB work, and LLM completions; defaults to console exporter if OTLP endpoint is not set.
- **Docker & docker-compose** provide a reproducible local stack (API + Postgres + OTEL collector).

```
app/
 ├── api/              # FastAPI routers + deps
 ├── core/             # Settings & configuration
 ├── db/               # SQLAlchemy models & session helpers
 ├── deps/             # External clients (embeddings)
 ├── schemas/          # Pydantic request/response models
 ├── services/         # Business services (LLM, memory, resume, outreach)
 ├── tools/            # MCP-style tool abstractions
 ├── workflows/        # LangGraph state & orchestrator
 ├── telemetry/        # OpenTelemetry setup helpers
 └── main.py           # FastAPI app factory
```

## Getting Started

### 1. Requirements
- Python 3.11+
- Docker + docker-compose (for the full stack)
- OpenAI API key (optional; deterministic fallbacks kick in if absent)

### 2. Local environment
```
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
```

### 3. Database & services
Spin up the stack:
```
docker-compose up --build
```
This starts the API at http://localhost:8000, Postgres with pgvector, and an OTEL collector with simple logging export.

### 4. Running locally without Docker
```
uvicorn app.main:app --reload
```
Set `DATABASE_URL` to your Postgres instance (pgvector extension required). Without a reachable DB, memory persistence gracefully degrades and logs a warning.

### 5. Telemetry
Set `OTEL_EXPORTER_OTLP_ENDPOINT` to your collector (e.g., `http://otel-collector:4317`) to stream traces. Otherwise traces log to stdout via the console exporter.

### 6. LLM provider configuration

By default the service uses OpenAI (`LLM_PROVIDER=openai`). To switch to Gemini:

1. Add the following to your `.env`:
   ```
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your-key-here
   GEMINI_MODEL=gemini-pro  # optional override
   ```
2. Restart the API. The runtime will route all LLM calls through the Gemini client; if no matching provider credentials exist the system falls back to the deterministic stub response used for tests/offline work.

## API Overview

| Endpoint | Description |
| --- | --- |
| `GET /health` | Service liveness | 
| `POST /analyze-job` | Skill gap analysis & resume recommendations |
| `POST /tailor-resume` | Rewrites bullets for the target job |
| `POST /draft-message` | Drafts outreach DM + email |
| `POST /memory/save` | Persist arbitrary artifacts to semantic memory |

### Example: Analyze Job
```bash
curl -X POST http://localhost:8000/analyze-job \
  -H 'Content-Type: application/json' \
  -d '{
        "user_id": "e1bb9e5c-6930-4f97-8a41-36c9348d8c44",
        "job_description": "Own FastAPI services and coach junior engineers.",
        "candidate_profile": "Led platform APIs at Contoso, mentoring 4 devs."
      }'
```
Response
```json
{
  "matched_skills": ["fastapi", "engineers"],
  "missing_skills": ["coach"],
  "fit_summary": "...",
  "resume_recommendations": ["..."],
  "retrieved_memory": []
}
```

Similar payloads exist for `/tailor-resume` (pass `resume_bullets`) and `/draft-message` (pass `company`, `role`, `candidate_profile`, optional `hiring_manager_name`, `tone`). `/memory/save` requires `user_id`, `memory_type`, `content`, and optional metadata; it returns the stored memory id.

## Testing
```
pytest
```
Tests rely on deterministic fallbacks and override DB dependencies, so they run without Postgres. Install dev extras first (`pip install -e .[dev]`).

## Future Improvements
1. **LLM adapters** – add Anthropic / Azure OpenAI adapters and routing per use case (analysis vs generation vs critique).
2. **Auth & tenancy** – integrate authentication + RBAC and scope memory per workspace/org.
3. **Vector hygiene** – switch to background workers for embedding generation + deletion workflows.
4. **Migrations** – ship Alembic scripts and CI guardrails for schema changes.
5. **Evaluation harness** – add regression prompts + judges for each flow using LangSmith / Evals.
