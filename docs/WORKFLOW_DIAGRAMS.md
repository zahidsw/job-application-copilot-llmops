# Job Application Copilot Workflow Diagrams

This document explains how the proposed Python application works, which components participate, and the sequence in which the system should be used.

## 1. System overview

```mermaid
flowchart LR
    U["Operator / Recruiter / Candidate"] --> UI["UI or API Client"]
    UI --> API["FastAPI Application API"]

    API --> WF["LangGraph Workflow"]
    WF --> SI["Source Intake Agent"]
    WF --> REQ["Requirements Agent"]
    WF --> MAT["Matcher Agent"]
    WF --> TAI["Tailorer Agent"]
    WF --> REV["Reviewer Agent"]

    SI --> MCP["Remote Tool Service"]
    REQ --> MCP

    MCP --> POL["Source Policy Check"]
    MCP --> NORM["Job Normalization"]
    MCP --> EXT["Requirement Extraction"]

    API --> DB["Run Repository / Database"]
    API --> ART["Artifacts Storage"]
    API --> SUB["Submission Service"]

    API --> MET["Prometheus Metrics"]
    API --> MLF["MLflow Tracking"]
    MET --> GRA["Grafana Dashboards"]

    EVA["Scheduled Evaluator"] --> API
    EVA --> MLF

    SUB --> EMAIL["Email Dispatch"]
    SUB --> SITE["Company Site Packet"]
    SUB --> HAND["Manual Handoff Packet"]
```

## 2. Runtime sequence

This is the end-to-end sequence for one job application opportunity.

```mermaid
sequenceDiagram
    participant User as Operator
    participant API as FastAPI API
    participant WF as LangGraph Workflow
    participant MCP as Tool Service
    participant DB as Repository
    participant MLF as MLflow
    participant SUB as Submission Service

    User->>API: Submit job opportunity + profile
    API->>MLF: Log input metadata
    API->>WF: Start job-application run

    WF->>MCP: Evaluate source policy
    MCP-->>WF: allowed / restricted / manual-only

    WF->>MCP: Normalize job posting
    MCP-->>WF: structured opportunity

    WF->>MCP: Extract requirements
    MCP-->>WF: required skills + preferred skills + blockers

    WF->>WF: Score fit against profile

    alt Score >= threshold and no hard blockers
        WF->>WF: Generate CV, letter, answers, approval packet
        WF->>DB: Save run as awaiting_approval
        WF->>MLF: Log score and artifact metrics
        API-->>User: Return approval packet

        User->>API: Approve run
        API->>SUB: Dispatch approved application

        alt Email submission
            SUB-->>User: Sent email or prepared draft
        else Company-site submission
            SUB-->>User: Prepared company-site packet
        else Manual handoff
            SUB-->>User: Prepared LinkedIn/Indeed handoff packet
        end

        API->>DB: Save final submission state
        API->>MLF: Log approval/submission outcome
    else Below threshold or hard blockers
        WF->>DB: Save run as blocked
        WF->>MLF: Log blocked outcome
        API-->>User: Return blocked assessment and reasons
    end
```

## 3. Decision logic

```mermaid
flowchart TD
    A["Opportunity received"] --> B["Check source policy"]
    B --> C{"Source allowed?"}
    C -- No --> D["Block or force manual-only path"]
    C -- Yes --> E["Extract requirements"]
    E --> F["Compare with profile, CV history, references"]
    F --> G["Compute fit score"]
    G --> H{"Score >= 70?"}
    H -- No --> I["Stop: do not tailor"]
    H -- Yes --> J{"Any hard blockers?"}
    J -- Yes --> K["Stop: do not tailor"]
    J -- No --> L["Generate tailored CV + letter + answers"]
    L --> M["Prepare approval packet"]
    M --> N{"Operator approves?"}
    N -- No --> O["Mark rejected / archived"]
    N -- Yes --> P["Submit or hand off by channel"]
```

## 4. Operator usage sequence

This is the recommended order in which the system should be used.

```mermaid
flowchart TD
    S1["1. Load or update candidate profile"] --> S2["2. Add job opportunity from allowed source"]
    S2 --> S3["3. Run analysis"]
    S3 --> S4["4. Review extracted requirements"]
    S4 --> S5["5. Review match score and blockers"]
    S5 --> S6{"Ready for tailoring?"}
    S6 -- No --> S7["Stop or keep for manual review"]
    S6 -- Yes --> S8["6. Review generated CV, letter, and answers"]
    S8 --> S9["7. Review approval packet"]
    S9 --> S10{"Approve?"}
    S10 -- No --> S11["Reject or revise profile/evidence"]
    S10 -- Yes --> S12["8. Dispatch by email, company site, or manual handoff"]
    S12 --> S13["9. Track result in dashboard and run history"]
```

## 5. Recommended operating sequence

Use the application in this order:

1. Maintain the candidate profile vault first.
2. Ingest only approved job sources.
3. Run requirement extraction and fit scoring.
4. Allow tailoring only when the score clears the threshold and there are no hard blockers.
5. Review all generated artifacts before approval.
6. Approve only the applications you actually want sent.
7. Let the system dispatch only after approval.
8. Monitor blocked runs, approval rates, and submission outcomes in Grafana and MLflow.

## 6. What each module is responsible for

- `FastAPI API`
  Receives requests, returns results, and exposes health and metrics endpoints.

- `LangGraph Workflow`
  Orchestrates the full multi-agent pipeline.

- `Tool Service`
  Handles source-policy checks, normalization, and structured extraction.

- `Matcher`
  Scores the role against the structured candidate profile and evidence.

- `Tailorer`
  Produces the tailored CV, motivation letter, and application answers.

- `Reviewer`
  Builds the approval packet and stops before dispatch.

- `Submission Service`
  Handles email sending, company-site packets, or manual handoff packages after approval.

- `Repository`
  Stores runs, states, and outcomes.

- `MLflow`
  Tracks run metadata, scores, and evaluation outcomes.

- `Prometheus + Grafana`
  Tracks operational health, throughput, durations, and blocked-vs-approved trends.
