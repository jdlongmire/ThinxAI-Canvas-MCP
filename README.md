# Canvas-MCP

An MCP server that renders hierarchical canvas diagrams as PNGs. Define your system as a hierarchy of **networks**, **factories**, **machines**, and **nodes** — Canvas-MCP handles layout, styling, and rendering.

Built with Python, Pillow, and the [Model Context Protocol](https://modelcontextprotocol.io).

## The Ontology

Canvas-MCP uses a **four-level hierarchical ontology**. Every diagram is a tree of nested containers, from the broadest scope down to the atomic unit:

```
Canvas
└── Network       ← system boundary
    └── Factory   ← functional domain
        └── Machine   ← pipeline
            └── Node      ← atomic operation
```

### Why This Hierarchy?

Most diagramming tools give you boxes and arrows. Canvas-MCP gives you **semantic containers** — each level carries meaning about the *scope* and *role* of what it contains:

- **Network** — the broadest boundary. Think of it as a service, a deployment, or an entire subsystem. A complex architecture might have multiple networks.
- **Factory** — a functional domain within a network. "Data Ingestion", "Analysis", "Output Generation" — a factory groups the pipelines that serve a common purpose.
- **Machine** — a single pipeline or processing chain. A connected sequence of operations that transforms data from input to output.
- **Node** — the atomic unit. A single operation: an API call, a transformation, a decision gate, an AI inference step.

This isn't arbitrary nesting — it mirrors how real systems are organized. The hierarchy lets you express both the micro (individual operations) and the macro (system architecture) in one diagram.

### Labeling

Every level of the ontology follows the same labeling pattern:

| Field | Required | Purpose |
|-------|----------|---------|
| `id` | Yes | Unique identifier used for connections and lookups |
| `label` | No | Human-readable display name |
| `description` | No | Optional longer description (for documentation) |

The rule is simple: **`get_label()` returns the `label` if set, otherwise falls back to the `id`.**

This keeps YAML recipes concise. You only need a label when you want a display name that differs from the id:

```yaml
# No label needed — "preprocess" is clear enough
- id: preprocess
  type: process
  content: "Clean and normalize data"

# Label overrides the id for display
- id: llm-gpt4o-analysis
  type: ai
  label: "AI Analysis"
  content: "Run GPT-4o on cleaned data"
```

The same applies to containers:

```yaml
machines:
  - id: machine-1        # Renders as "machine-1" (fine for auto-generated)
    nodes: [...]

  - id: src-pipeline      # Renders as "Data Sources"
    label: "Data Sources"
    nodes: [...]
```

## Node Types

Nodes are the atomic units of the ontology. Each node has a **type** that determines its color and carries semantic meaning:

| Type | Color | Hex | Meaning |
|------|-------|-----|---------|
| `input` | Blue | `#2196F3` | User-provided data entering the system |
| `output` | Amber | `#FFC107` | Final results leaving the system |
| `process` | Cyan | `#00BCD4` | A transformation or computation step |
| `decision` | Red | `#F44336` | A branching point or conditional gate |
| `ai` | Purple | `#9C27B0` | An AI/LLM processing step |
| `source` | Orange | `#FF9800` | An external data source (API, database, file) |
| `static` | Green | `#4CAF50` | Immutable seed content or constants |
| `default` | Gray | `#999999` | Generic / unspecified |

### Node Anatomy

When rendered, each node displays:

1. **Type bar** — a colored stripe at the top matching the type's accent color
2. **Label** — bold text below the type bar (from `get_label()`)
3. **Content** — word-wrapped body text describing what the node does
4. **Type badge** — small tag in the bottom-right corner showing the type name

### Node Properties

```yaml
- id: analyze              # Required. Globally unique identifier.
  type: ai                 # Optional. One of the 8 types above. Default: "default"
  label: "AI Analysis"     # Optional. Display name. Default: uses id
  content: "Run inference" # Optional. Body text describing the operation
  x: 800                   # Optional. Horizontal position. Default: 0 (auto-layout)
  y: 180                   # Optional. Vertical position. Default: 0 (auto-layout)
  width: 250               # Optional. Node width in pixels. Default: 250
  height: 120              # Optional. Node height in pixels. Default: 120
  inputs: [preprocess]     # Optional. IDs of upstream nodes
  outputs: [report]        # Optional. IDs of downstream nodes
  style:                   # Optional. Override default NodeStyle
    border_color: "#FF00FF"
    fill_color: "#1e1e2e"
    text_color: "#cdd6f4"
    label_color: "#FF00FF"
    corner_radius: 12
```

## Container Styling

Machines and factories can be styled with `ContainerStyle` to customize their visual container:

```yaml
machines:
  - id: my-pipeline
    label: "Custom Pipeline"
    style:
      border_color: "#89b4fa"    # Outline color
      fill_color: "#1e1e2e"      # Background fill
      label_color: "#89b4fa"     # Label text color
      alpha: 100                 # Fill opacity (0-255)
      corner_radius: 12          # Border radius
      border_width: 2            # Outline thickness
```

All `ContainerStyle` fields are optional — unset fields fall back to defaults:

| Field | Machine Default | Factory Default |
|-------|-----------------|-----------------|
| `border_color` | `#313244` | `#45475a` |
| `fill_color` | `#181825` | none (transparent) |
| `label_color` | `#6c7086` | `#a6adc8` |
| `alpha` | 120 | 0 |
| `corner_radius` | 8 | 12 |
| `border_width` | 1 | 1 |

## Connections

Connections are declared on nodes via `inputs` and `outputs` — lists of other node IDs:

```yaml
- id: source
  type: input
  outputs: [transform]     # "I feed into transform"

- id: transform
  type: process
  inputs: [source]         # "I receive from source"
  outputs: [result]
```

Connections are **bidirectionally deduped** — declaring a connection on either end is sufficient. Declaring both is harmless (and often clearer).

### Smart Port Selection

Canvas-MCP automatically selects connection ports based on the **spatial relationship** between nodes:

- **Horizontal flow** (default): Connections exit from the right edge and enter from the left edge. This creates left-to-right diagrams.
- **Vertical flow** (automatic): When a target node sits significantly below or above its source (beyond a "horizon" threshold of 1.5x the source node's height), the connection switches to bottom/top ports. This creates vertical tree structures.

The switching is **emergent from geometry** — you don't configure it. Place nodes side by side and you get horizontal flow. Stack them vertically and you get vertical flow. Mix both and each connection picks the right ports independently.

### Connection Rendering

Connections are drawn as smooth **cubic bezier curves** with:
- Directional S-bend control points (horizontal or vertical)
- Color derived from the source node's type (darkened to 70%)
- Arrowhead at the endpoint

## YAML Formats

Canvas-MCP supports two YAML formats. Use whichever fits your needs.

### Simplified Format

The simplified format is a flat list of nodes. Canvas-MCP auto-wraps them in the hierarchy (one network > one factory > auto-detected machines) and handles layout:

```yaml
title: My Pipeline

nodes:
  - id: ingest
    type: input
    label: "Data Ingest"
    content: "Accept incoming data"
    outputs: [clean]

  - id: clean
    type: process
    label: "Clean"
    content: "Normalize and validate"
    inputs: [ingest]
    outputs: [analyze]

  - id: analyze
    type: ai
    label: "AI Analysis"
    content: "Run LLM inference"
    inputs: [clean]
    outputs: [report]

  - id: report
    type: output
    label: "Report"
    content: "Generated summary"
    inputs: [analyze]
```

**Auto-layout**: When all node coordinates are `(0, 0)` (or omitted), Canvas-MCP arranges them automatically. Use the `organize` flag for intelligent topological layout.

**Auto-machines**: Connected components of nodes are automatically grouped into machines.

### Hierarchical Format

The full format gives you explicit control over the entire hierarchy:

```yaml
canvas:
  version: "2.0"
  title: AI Pipeline

  networks:
    - id: main-system
      label: "Production System"

      factories:
        - id: ingestion
          label: "Data Ingestion"

          machines:
            - id: sources
              label: "Data Sources"
              nodes:
                - id: api-feed
                  type: source
                  x: 100
                  y: 100
                  label: "API Feed"
                  content: "External API data"
                  outputs: [preprocess]

                - id: db-source
                  type: source
                  x: 100
                  y: 260
                  label: "Database"
                  content: "Historical records"
                  outputs: [preprocess]

            - id: processing
              label: "Processing"
              nodes:
                - id: preprocess
                  type: process
                  x: 450
                  y: 180
                  label: "Preprocess"
                  content: "Clean and normalize"
                  inputs: [api-feed, db-source]
                  outputs: [analyze]

        - id: analysis
          label: "Analysis"

          machines:
            - id: ai-stage
              label: "AI Stage"
              nodes:
                - id: analyze
                  type: ai
                  x: 800
                  y: 180
                  label: "AI Analysis"
                  content: "Run LLM analysis"
                  inputs: [preprocess]
                  outputs: [output]

                - id: output
                  type: output
                  x: 1150
                  y: 180
                  label: "Report"
                  content: "Generated report"
                  inputs: [analyze]
```

## Layout System

Canvas-MCP includes a built-in topological layout engine.

### Auto-Layout

When all nodes have coordinates at `(0, 0)`, the basic auto-layout arranges them:
- Left-to-right within machines (80px horizontal spacing)
- Top-to-bottom between machines (200px vertical spacing)
- Extra gap between factories (60px)

### Organize Algorithm

Enable with `organize: true` for intelligent hierarchical layout:

1. **Topological sort** (Kahn's algorithm) assigns hierarchical levels
2. **Parent-center alignment** vertically centers children on their parents
3. **Overlap prevention** enforces minimum spacing
4. **Cycle handling** gracefully positions nodes in cyclic graphs
5. **Grid fallback** arranges disconnected components in a grid

### Spacing Levels

Control breathing room with the `spacing_level` parameter:

| Level | Horizontal | Vertical | Best For |
|-------|-----------|----------|----------|
| `node` | 60px | 110px | Small, tight diagrams |
| `container` | 150px | 190px | Architecture diagrams (default) |
| `network` | 190px | 250px | Large system overviews |

## Visual Theme

Canvas-MCP uses the **Catppuccin Mocha** dark theme:

| Element | Color | Hex |
|---------|-------|-----|
| Canvas background | Dark base | `#11111b` |
| Node fill | Base | `#1e1e2e` |
| Node label text | Light text | `#cdd6f4` |
| Node content text | Muted text | `#a6adc8` |
| Machine container fill | Surface | `#181825` (semi-transparent) |
| Machine container border | Overlay | `#313244` |
| Machine label | Subtext | `#6c7086` |
| Factory container border | Surface 2 | `#45475a` |
| Factory label | Subtext 1 | `#a6adc8` |

## MCP Tools

Canvas-MCP exposes four tools via the Model Context Protocol:

### `render_canvas`

Render a YAML recipe string to PNG.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `yaml_recipe` | string | required | YAML in simplified or hierarchical format |
| `scale` | number | `2.0` | Render scale (2.0 = crisp retina output) |
| `filename` | string | auto-UUID | Output filename (without extension) |
| `organize` | boolean | `false` | Apply hierarchical layout algorithm |
| `spacing_level` | string | `"container"` | One of: `node`, `container`, `network` |

### `create_canvas`

Create a diagram from structured input (title + nodes + optional machines).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | string | required | Canvas title |
| `nodes` | array | required | List of node definitions |
| `machines` | array | optional | Group nodes into named machines |
| `scale` | number | `2.0` | Render scale |
| `organize` | boolean | `true` | Apply layout algorithm |
| `spacing_level` | string | `"container"` | Spacing preset |

Returns both a PNG and a saved YAML recipe.

### `list_templates`

List available starter templates. Returns template names and file paths.

### `get_template`

Retrieve the YAML content of a specific template by name.

## Installation

### As an MCP Server

Add to your MCP client configuration (e.g., `.mcp.json`):

```json
{
  "mcpServers": {
    "canvas-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/Canvas-MCP",
        "canvas-mcp"
      ]
    }
  }
}
```

### Running Directly

```bash
uv run canvas-mcp   # Starts the MCP stdio server
```

### Testing

```bash
uv run python test_render.py   # Renders test PNGs to output/
```

## Project Structure

```
Canvas-MCP/
├── src/canvas_mcp/
│   ├── models.py       # Ontology: Canvas > Network > Factory > Machine > Node
│   ├── parser.py       # YAML parser (simplified + hierarchical formats)
│   ├── renderer.py     # Pillow-based PNG renderer
│   ├── organize.py     # Hierarchical layout algorithm (topological sort)
│   └── server.py       # MCP server with 4 tools
├── templates/
│   ├── simple-flow.yaml      # 3-node linear pipeline
│   ├── decision-tree.yaml    # Branching decision flow
│   └── ai-pipeline.yaml      # Full hierarchical example
├── pyproject.toml
└── test_render.py
```

## Output

PNGs are saved to `~/.rhode/canvas/` by default. Set the `CANVAS_OUTPUT_DIR` environment variable to change this.

## License

MIT
