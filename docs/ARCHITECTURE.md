# Job Application Copilot LLMOps Architecture

This project is the Python/LangGraph equivalent of the earlier desktop prototype and is intentionally shaped after the reference project:

- Reference: `C:\Users\marya\Documents\New project\multi-agent-research-llmops`
- Recruiting platform: `C:\Users\marya\Documents\New project\job-application-copilot-llmops`

## Design goal

Use the same production-ready operating model as the research LLMOps system, but replace the research pipeline with a governed recruiting pipeline:

1. ingest job opportunities from allowed sources
2. extract structured requirements
3. compare against the candidate profile, CV history, and reference evidence
4. score fit and block hard policy failures
5. generate tailored artifacts only when the gate passes
6. stop at human approval
7. dispatch only after explicit approval

## Reference-to-domain mapping

| Reference project module | Recruiting equivalent in this project |
| --- | --- |
| Research API | Job Application API |
| Research workflow | Job application workflow |
| Researcher agent | Source intake agent |
| Verifier agent | Requirements extraction and policy agent |
| Writer agent | Tailoring agent |
| Reviewer agent | Approval/review agent |
| MCP tool server | Recruiting tool service |
| Golden dataset evals | Match-quality and policy-gate evals |
| MLflow experiment tracking | Application run and evaluation tracking |
| Prometheus metrics | Run, artifact, tool-call, and submission metrics |
| Grafana dashboard | Job application operations dashboard |
| LangSmith tracing | LangGraph node and LLM-call debugging |

## Production modules used here

### 1. FastAPI service layer

`job_app_ops/api/app.py` exposes:

- `POST /api/v1/applications/run`
- `GET /api/v1/applications/{run_id}`
- `POST /api/v1/applications/{run_id}/approve`
- `POST /api/v1/applications/{run_id}/reject`
- `GET /api/v1/runs`
- `GET /live`
- `GET /ready`
- `GET /metrics`

This is the control plane for the recruiting workflow.

### 2. LangGraph orchestration

`job_app_ops/graph/workflow.py` is the state machine for the full recruiting flow:

- `source_intake`
- `requirements`
- `matcher`
- `tailorer`
- `reviewer`
- `similar_jobs`

The graph persists run outputs, exports artifacts, and emits observability events.

### 3. Remote tool service

`job_app_ops/mcp_app.py` and `job_app_ops/services/tool_gateway.py` provide domain tools for:

- source-policy evaluation
- job normalization
- structured requirement extraction

This mirrors the reference project pattern of keeping tool execution behind a separate service boundary.

### 4. Candidate and run persistence

`job_app_ops/database.py` stores run payloads and run summaries.

For local development the repository defaults to SQLite. In container mode it is configured to use PostgreSQL through `DATABASE_URL`, matching the operational shape of the reference stack.

### 5. Artifact export

`job_app_ops/services/exporter.py` writes generated output for:

- tailored CV
- motivation letter
- application answers
- approval packet
- submission packet

Artifacts are persisted under the configured `ARTIFACTS_DIR`.

### 6. Submission governance

`job_app_ops/services/submission_service.py` enforces the critical approval rule:

- no dispatch before approval
- email only when SMTP is configured
- company-site flow prepares operator-ready submission packets
- LinkedIn and Indeed stay manual-handoff oriented

### 7. MLflow

`job_app_ops/services/mlflow_tracker.py` logs:

- company
- role
- source type
- submission channel
- overall score
- artifact count
- blocked/not-blocked metrics

`ops/mlflow/Dockerfile` and `docker-compose.yml` provision a local MLflow server backed by PostgreSQL and MinIO, just like the reference system.

### 8. Prometheus

`job_app_ops/services/metrics.py` exports:

- total runs by final status
- generated artifact count
- submission/handoff count
- end-to-end run duration
- remote tool request count
- graph node duration and error count
- remote tool duration by tool name

`ops/prometheus/prometheus.yml` scrapes the API, tool service, and evaluator.

### 9. Grafana

Grafana provisioning is defined under:

- `ops/grafana/provisioning/datasources/datasource.yml`
- `ops/grafana/provisioning/dashboards/dashboard.yml`
- `ops/grafana/dashboards/job-application-overview.json`

This provides the same operational dashboard pattern as the reference project, but focused on recruiting throughput, blocked runs, approvals, and submission volume.

### 10. LangSmith

`job_app_ops/services/langsmith_observability.py` configures optional LangSmith tracing for:

- `job_application_graph_run`
- each LangGraph node (`source_intake`, `requirements`, `matcher`, `tailorer`, `reviewer`, `similar_jobs`)
- on-demand similar-job refreshes
- remote tool calls
- custom OpenAI-compatible LLM calls

Trace inputs and outputs are hidden by default with `LANGSMITH_HIDE_INPUTS=true` and `LANGSMITH_HIDE_OUTPUTS=true`, while safe metadata such as node name, duration, status, scores, source type, company, role, and counts remains available for debugging.

### 11. Evaluations

`job_app_ops/evals/runner.py` and `ops/evals/golden_dataset.json` define the evaluation hook for:

- scoring consistency
- blocker detection correctness
- approval packet quality
- artifact generation readiness

This is the recruiting equivalent of the reference project's evaluation loop.

### 12. Docker Compose local stack

`docker-compose.yml` provisions:

- `postgres`
- `mlflow-db`
- `minio`
- `mlflow`
- optional `model`
- `api`
- `mcp`
- `evaluator`
- `prometheus`
- `grafana`

This is the local production mirror for development and demos.

### 13. Cloud deployment placeholders

`ops/azure/main.bicep`, `ops/azure/README.md`, and `ops/azure/stack.env.example` are the infrastructure placeholders for promoting this to a cloud environment later.

## Recommended domain model

The recruiting system should be thought of as four layers:

1. intake layer
   Reads job ads from email alerts, company sites, saved searches, or imported files.

2. reasoning layer
   Extracts requirements, matches against profile evidence, scores fit, and decides if tailoring is allowed.

3. artifact layer
   Produces the tailored CV, motivation letter, concise question answers, and approval packet.

4. governance layer
   Requires operator approval and records the final dispatch or handoff outcome.

## Suggested next implementation steps

1. Replace heuristic extraction with LLM-backed structured output while keeping tool contracts stable.
2. Add profile vault ingestion for past CVs, achievements, and reference letters.
3. Add Gmail or mailbox ingestion for alert-driven job discovery.
4. Add browser-assisted company-site completion for approved opportunities only.
5. Expand eval cases to track false-positive tailoring and blocker misses.

## Short definition

This project is not just a job-application script. It is a governed, production-shaped recruiting operations platform built with the same LLMOps ideas as the research reference project:

- multi-agent workflow
- service boundaries
- observability
- experiment tracking
- evaluation hooks
- approval gates
- deployment-ready local infrastructure
