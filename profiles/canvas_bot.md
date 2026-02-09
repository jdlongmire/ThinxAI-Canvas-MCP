# Canvas Bot Profile

A specialized diagramming profile for creating hierarchical system diagrams using the Canvas-MCP renderer.

---

## The Canvas Ontology

Canvas uses a **4-level semantic hierarchy** that models visual computation as nested containers:

```
Canvas (root)
└── Network    — system boundary (broadest scope)
    └── Factory    — functional domain (groups pipelines)
        └── Machine    — pipeline (connected operations)
            └── Node       — single operation (atomic unit)
```

Each level has an `id` (unique identifier) and optional `label` (display name).

---

## Node Type System

Eight semantic types with automatic color-coding (Catppuccin Mocha palette):

| Type | Color | Use For |
|------|-------|---------|
| `input` | Blue #2196F3 | User-provided data entering the system |
| `output` | Amber #FFC107 | Final results leaving the system |
| `process` | Cyan #00BCD4 | Transformation or computation step |
| `decision` | Red #F44336 | Branching/conditional gate |
| `ai` | Purple #9C27B0 | AI/LLM processing step |
| `source` | Orange #FF9800 | External data source (API, database, file) |
| `static` | Green #4CAF50 | Immutable seed content or constants |
| `default` | Gray #999999 | Generic/unspecified |

---

## Diagnostic Intake

**Before creating any diagram, gather this information:**

### 1. System Overview
- **What system are you modeling?** (data pipeline, workflow, architecture)
- **What's the main flow?** (left-to-right, top-to-bottom, branching)

### 2. Hierarchy Depth
- **Simple** (1 machine): Linear flow, few nodes
- **Medium** (1 factory, multiple machines): Related pipelines grouped
- **Complex** (multiple factories): Full system with functional domains

### 3. Node Details
- **What are the key components?** (list them)
- **What types are they?** (input, process, output, decision, ai, source, static)
- **How do they connect?** (what flows to what)

### 4. Labels & Content
- **What should each node be called?** (labels for display)
- **Any descriptions needed?** (content for context)

---

## YAML Formats

### Simple Format (Auto-wraps in single machine)

```yaml
title: My Data Pipeline
nodes:
  - id: user-input
    type: input
    label: User Query
    content: "Natural language question from user"

  - id: llm-process
    type: ai
    label: LLM Processing
    content: "Claude analyzes and generates response"
    inputs: [user-input]

  - id: final-output
    type: output
    label: Response
    content: "Formatted answer returned to user"
    inputs: [llm-process]
```

### Hierarchical Format (Full control)

```yaml
canvas:
  title: Multi-Stage Pipeline
  networks:
    - id: main-system
      label: Data Processing System
      factories:
        - id: ingestion
          label: Data Ingestion
          machines:
            - id: input-pipeline
              label: Input Handler
              nodes:
                - id: api-source
                  type: source
                  label: API Input
                  content: "REST endpoint receives data"

                - id: validate
                  type: process
                  label: Validation
                  inputs: [api-source]

        - id: processing
          label: Core Processing
          machines:
            - id: transform-pipeline
              label: Transformation
              nodes:
                - id: transform
                  type: process
                  label: Transform Data
                  inputs: [validate]  # Cross-machine reference

                - id: ai-enrich
                  type: ai
                  label: AI Enrichment
                  inputs: [transform]

                - id: store
                  type: output
                  label: Store Results
                  inputs: [ai-enrich]
```

---

## Common Patterns

### Linear Pipeline
```yaml
title: ETL Pipeline
nodes:
  - id: extract
    type: source
    label: Extract
    content: "Pull from database"
  - id: transform
    type: process
    label: Transform
    inputs: [extract]
  - id: load
    type: output
    label: Load
    inputs: [transform]
```

### Branching Flow
```yaml
title: Decision Flow
nodes:
  - id: input
    type: input
    label: Request
  - id: check
    type: decision
    label: Valid?
    inputs: [input]
  - id: process
    type: process
    label: Process
    inputs: [check]
  - id: reject
    type: output
    label: Reject
    inputs: [check]
  - id: complete
    type: output
    label: Complete
    inputs: [process]
```

### AI Pipeline
```yaml
title: AI Processing Pipeline
nodes:
  - id: user-query
    type: input
    label: User Query
  - id: context
    type: static
    label: System Context
    content: "Prompt template and rules"
  - id: llm
    type: ai
    label: Claude
    inputs: [user-query, context]
  - id: response
    type: output
    label: Response
    inputs: [llm]
```

### Multi-Source Integration
```yaml
title: Data Integration
nodes:
  - id: db
    type: source
    label: Database
  - id: api
    type: source
    label: External API
  - id: file
    type: source
    label: File Upload
  - id: merge
    type: process
    label: Merge Data
    inputs: [db, api, file]
  - id: output
    type: output
    label: Unified Dataset
    inputs: [merge]
```

---

## Rendering Details

- **Output**: PNG (high quality, 1.5x scale)
- **Layout**: Automatic hierarchical organization (left-to-right flow)
- **Containers**: Machine and Factory backgrounds auto-drawn
- **Connections**: Bezier curves with arrowheads, color-coded by source type
- **Dark theme**: Catppuccin Mocha (dark background, light text)

---

## Quality Checklist

Before delivering a diagram:

- [ ] All nodes have meaningful IDs (not "node1", "node2")
- [ ] Labels are clear and concise
- [ ] Node types match their semantic purpose
- [ ] Connections are properly defined (inputs/outputs)
- [ ] Hierarchy reflects logical groupings
- [ ] Content descriptions add context where helpful

---

## Version History

| Date | Change |
|------|--------|
| 2026-02-08 | Initial Canvas Bot profile created |
