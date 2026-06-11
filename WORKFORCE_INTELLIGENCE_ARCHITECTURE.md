# Workforce Intelligence Module — Architecture

Companion to `WORKFORCE_INTELLIGENCE_SPEC.md`. Two views: the **data-flow / pipeline** (how a
request travels through the system) and the **entity relationships** (how the new tables attach
to the existing schema). Diagrams are Mermaid so they render on GitHub and are editable by Claude
Code.

---

## 1. The separation boundary (read this first)

The module is built *inside* the app but is **walled off**. Everything new lives in its own
service, router, page, reference tables, and a single results table. The **only** place it
touches the existing schema is one foreign key: `workforce_intelligence_result.analysis_id →
org_analyses.id`. Remove the module by deleting its files and dropping its five tables; nothing
else in the app depends on it.

Three layers:

1. **Reference layer (static, seeded):** the pluggable taxonomies — SkillsFuture (SFw, default
   for SATS), O*NET (the bridge), and the WORKBank overlay. Loaded once from seed files.
2. **Pipeline layer (per analysis):** extract tasks from free-text activities → benchmark against
   the taxonomy → attach the human-AI overlay → roll up the org graph. Claude does the language
   work; the org graph already lives in `OrgAnalysis.raw_data`.
3. **Presentation layer:** a new React page with the zone scatter, HAS distribution, AI-opportunity
   levels, and a benchmark table — plus a caveats box so provenance is always visible.

---

## 2. Data-flow / pipeline

```mermaid
flowchart TD
    subgraph EXIST["Existing app (unchanged)"]
        CSV["CSV upload<br/>(incl. Work Activities column)"] --> PARSE["OrgCSVParser"]
        PARSE --> OA[("org_analyses<br/>raw_data.employees[]")]
    end

    subgraph REF["Reference layer (seeded once)"]
        SEED["taxonomy_seed.starter.json"] --> LOAD["load_taxonomies.py"]
        LOAD --> TS[("taxonomy_source")]
        LOAD --> TT[("taxonomy_task")]
        LOAD --> OV[("task_ai_overlay")]
        LOAD --> CW[("taxonomy_crosswalk")]
    end

    subgraph WI["Workforce Intelligence service (per analysis)"]
        E["1. extract_tasks<br/>free-text → normalised tasks"]
        B["2. benchmark<br/>match to SFw (primary) + O*NET (bridge)<br/>flag MISSING / EXTRA"]
        H["3. ai_opportunity<br/>join via O*NET → HAS H1-H5, zone,<br/>AI level L0-L3 (tag source)"]
        R["4. rollup<br/>by role / department / layer"]
        E --> B --> H --> R
    end

    OA -->|employees + activities| E
    TT --> B
    CW --> B
    OV --> H
    CLAUDE{{"Claude API<br/>(claude_service singleton)<br/>MOCKED in tests"}}
    E -.calls.-> CLAUDE
    B -.calls.-> CLAUDE
    H -.calls.-> CLAUDE

    R --> RES[("workforce_intelligence_result")]
    RES --> API["/api/v1/workforce-intelligence/*"]
    API --> UI["React page:<br/>zone scatter · HAS distribution ·<br/>AI-opportunity levels · benchmark table · caveats"]
```

**Notes on the flow:**
- The pipeline reads the org graph from the existing `org_analyses` table — it never re-parses
  the CSV and never modifies that table.
- Every Claude call is routed through the existing `claude_service` singleton and is
  monkeypatched in tests, so the suite runs offline and free.
- The human-AI overlay (`task_ai_overlay`) is reached **only via the O*NET code**, because
  WORKBank is keyed to O*NET. Tasks with no overlay row (e.g. physical ramp handling) are tagged
  `model-inferred` and surfaced as a different (robotics/GSE) automation lever, not a software-agent
  opportunity.

---

## 3. Entity relationships

```mermaid
erDiagram
    grade_salaries {
        string id PK
    }
    org_analyses {
        string id PK
        json raw_data
        json metrics
        json ai_analysis
    }
    settings {
        string key PK
    }

    taxonomy_source {
        string id PK
        string code UK
        string region
        bool is_default
        text license_note
    }
    taxonomy_task {
        string id PK
        string source_id FK
        string role_label
        string task_text
        string task_code
        json skills
        string track
    }
    task_ai_overlay {
        string id PK
        string onet_task_code
        int has_level
        float desire_score
        float capability_score
        string zone
        string source
    }
    taxonomy_crosswalk {
        string id PK
        string from_source_id FK
        string from_task_id FK
        string to_source_code
        string to_task_code
        float confidence
        string method
    }
    workforce_intelligence_result {
        string id PK
        string analysis_id FK
        string taxonomy_source_code
        string result_type
        json payload
        text summary
    }

    org_analyses ||--o{ workforce_intelligence_result : "the ONLY cross-boundary FK"
    taxonomy_source ||--o{ taxonomy_task : "has"
    taxonomy_source ||--o{ taxonomy_crosswalk : "from"
    taxonomy_task ||--o{ taxonomy_crosswalk : "from"
    taxonomy_task }o..o{ task_ai_overlay : "joined by O*NET code (logical, not FK)"
```

**Notes on the schema:**
- `grade_salaries`, `org_analyses`, and `settings` are existing tables — shown only to make the
  boundary explicit. They are **not modified**; migration `002` is additive.
- `task_ai_overlay` is joined to tasks *logically* by `onet_task_code` (via the crosswalk),
  not by a hard FK — this keeps the overlay independently replaceable when you swap in real
  WORKBank pulls.
- `workforce_intelligence_result.analysis_id → org_analyses.id` is the single dependency that
  crosses into the existing app. Dropping the five new tables fully detaches the module.

---

## 4. How the two requested capabilities map onto this

- **"Calibrate against external benchmark of jobs and tasks"** = the **benchmark** step, reading
  `taxonomy_task` (SFw primary, O*NET bridge) and `taxonomy_crosswalk`, producing MATCHED /
  MISSING / EXTRA per role.
- **"Analyse human-AI opportunity using a human-agency architecture"** = the **ai_opportunity**
  step, reading `task_ai_overlay` (HAS + four zones) and adding the L0–L3 transformation lens,
  then the **rollup** that lifts task-level signals up to department and layer — the thing a
  standalone tool can't do because it lacks your org graph.
