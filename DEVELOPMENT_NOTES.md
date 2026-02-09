# Canvas Bot Development Notes

## Project Overview

**Canvas Bot** is a web-based diagram assistant that uses Claude CLI and Canvas-MCP to convert user requests and sketches into professional hierarchical diagrams.

**Live URL:** http://100.114.240.59:8766 (Tailscale VPN - JDL-Workstation-1)
**Local URL:** http://localhost:8766

---

## Development Timeline

### Session: 2026-02-08

#### Phase 1: Initial Web Application (Based on Draw Bot)

**Commit:** `ad5391b` - "Add Canvas Bot web interface"

Created Canvas Bot as a standalone web application, using the proven Draw Bot architecture as baseline:

| Component | File | Description |
|-----------|------|-------------|
| Web Server | `canvas_bot.py` | aiohttp on port 8766, SSE streaming |
| Web UI | `web/index.html` | Catppuccin Mocha themed chat interface |
| Bot Profile | `profiles/canvas_bot.md` | Diagnostic intake personality |
| Output | `diagrams/` | Auto-created PNG files |
| History | `history/` | JSONL per user |
| Logs | `logs/canvas_bot.log` | Application logging |

**Key Architecture Decisions:**

1. **Pure Canvas-MCP focus** - No fallback to Mermaid/D2, cleaner pipeline
2. **Catppuccin Mocha theme** - Dark theme matching diagram output aesthetics
3. **JSONL history** - Timestamped conversation logs per user
4. **SSE streaming** - Real-time response streaming (same pattern as Draw Bot)

**Features Implemented:**
- Chat interface with message bubbles
- Quick action buttons for common diagram types
- Claude CLI integration for conversation
- Auto-detection of YAML code blocks
- Automatic PNG rendering via Canvas-MCP renderer
- Node type legend showing semantic colors
- Fullscreen image modal
- PNG download button

**Workflow:**
1. User describes diagram requirements
2. Canvas Bot asks clarifying questions (diagnostic intake)
3. Bot generates YAML in 4-level hierarchy format
4. Server detects YAML blocks and renders to PNG
5. Diagram displays inline with download option

---

#### Phase 2: XMI Export for Cameo Modeler Integration

**Added XMI (XML Metadata Interchange) export capability for enterprise modeling tool integration.**

**Backend Changes to `canvas_bot.py`:**
- Added import: `from canvas_mcp.xmi_exporter import export_to_xmi`
- New `/api/export-xmi` POST endpoint
- Accepts parsed Canvas YAML, returns XMI 2.1 file

**New File: `src/canvas_mcp/xmi_exporter.py`:**
- UML 2.1 + SysML namespace headers for Cameo compatibility
- Semantic node type mapping:
  - `input` → `uml:InitialNode`
  - `output` → `uml:ActivityFinalNode`
  - `decision` → `uml:DecisionNode`
  - `process/ai/source/static` → `uml:OpaqueAction` (with stereotypes)
- Full hierarchy preserved: Canvas → Network → Factory → Machine → Node maps to Model → Package → Package → Activity → Node
- `ControlFlow` edges for connections between nodes

**UI Changes to `web/index.html`:**
- "XMI" button (teal) next to "PNG" button for each diagram
- `lastYamlContent` state variable to track exportable YAML
- `exportToXMI()` function handles download

**User Flow:**
1. Generate diagram as usual
2. Click teal "XMI" button next to diagram
3. Downloads `.xmi` file compatible with Cameo Systems Modeler, MagicDraw

---

#### Phase 3: UI Refinements

**Input Improvements:**
- Increased input box height from 40px to 52px for mobile usability

**Navigation Cleanup:**
- Removed "Legend" button from top menu (node types still documented in welcome message)

**Quick Action Buttons:**
- Replaced "Multi-Stage" and "Data Integration" bubbles with:
  - **TOGAF** - Enterprise architecture diagrams
  - **UAF** - Unified Architecture Framework diagrams

---

#### Phase 4: Draw.io Integration

**Added embedded Draw.io editor for freeform diagramming.**

**UI Architecture:**
- Three-tab menu system: Menu (main), Draw.io Editor, Canvas Bot
- Draw.io loads in iframe from `https://embed.diagrams.net/`
- Custom configuration via `DRAWIO_CONFIG`:
  - Catppuccin Mocha dark theme
  - Grid enabled
  - UML/flowchart shapes in sidebar
  - Minimal toolbar

**Draw.io Toolbar Features:**
- "Draw.io ▼" dropdown menu containing:
  - **New Diagram** - Clears canvas with confirmation
  - **Open Diagram** - Load `.drawio` or `.xml` files
  - **Export PNG** - Export current diagram as PNG
  - **Send to Chat** - Convert diagram to PNG and send to Canvas Bot

**PostMessage Protocol:**
- `export: 'png'` → Receive base64 PNG
- `export: 'xmlsvg'` → Get editable XML
- `action: 'load'` → Load diagram from file/blank

**Mobile Responsiveness (2026-02-08):**
- Consolidated toolbar buttons into single dropdown menu
- Prevents horizontal overflow on narrow screens
- Clean mobile UX with all actions accessible via "Draw.io ▼"

---

#### Phase 5: Sketch Upload Feature

**Added image attachment capability for sketch-to-diagram conversion.**

**UI Changes to `web/index.html`:**
- 📎 Paperclip button in input area (left of text input)
- Hidden file input accepting image types
- Drag & drop zone overlay
- Image preview panel with thumbnail, filename, size
- Preview removal button

**Backend Changes to `canvas_bot.py`:**
- New `/api/upload` endpoint for file uploads
- Base64 encoding of images for Claude API
- Updated `/api/chat` to handle both text and image+text
- File size limit: 10MB
- Supported formats: PNG, JPEG, GIF, WebP, SVG

**JavaScript Additions:**
- `attachedImage` state variable
- `handleFileSelect()` - validates and shows preview
- `showImagePreview()` - displays thumbnail with metadata
- `removeAttachment()` - clears attachment state
- Drag & drop event handlers
- Modified `sendMessage()` to include image data

**User Flow:**
1. Click paperclip or drag image onto page
2. Preview shows thumbnail, filename, size
3. Optionally add descriptive message
4. Send - Claude analyzes sketch and converts to professional diagram

---

## File Structure

```
ThinxAI-Canvas-MCP/
├── canvas_bot.py          # Main web server (aiohttp)
├── renderer.py            # Canvas-MCP diagram renderer
├── canvas-mcp.py         # Canvas-MCP server
├── DEVELOPMENT_NOTES.md  # This file
├── web/
│   └── index.html        # Full web UI
├── profiles/
│   └── canvas_bot.md     # Bot personality/instructions
├── diagrams/             # Generated PNG output
├── history/              # JSONL conversation logs
└── logs/
    └── canvas_bot.log    # Application logs
```

---

## Restore Points

| Commit | Description | Restore Command |
|--------|-------------|-----------------|
| `ad5391b` | Pre-sketch upload (clean baseline) | `git checkout ad5391b -- canvas_bot.py web/ profiles/` |

---

## Technical Notes

### Server Configuration
- **Port:** 8766 (to avoid conflicts with other ThinxAI services)
- **Host:** 0.0.0.0 (accessible on all interfaces)
- **Dependencies:** aiohttp, asyncio, subprocess

### Canvas-MCP Integration
- YAML code blocks in Claude responses are auto-detected
- Renderer called via `python renderer.py --yaml <content>`
- Output PNG saved to `diagrams/` with UUID filename
- PNG path returned to frontend for display

### Claude CLI Usage
- Bot uses `claude --print` for non-streaming, `--output-format stream-json` for SSE
- Profile loaded from `profiles/canvas_bot.md`
- Images sent as base64 with appropriate MIME type

---

## Future Enhancements (Backlog)

- [ ] Session persistence (resume conversations)
- [ ] Diagram revision history
- [ ] Export to other formats (SVG, PDF)
- [ ] Diagram templates library
- [ ] Voice input for diagram description
- [ ] Multi-diagram comparison view

---

## Related Projects

- **Draw Bot:** `/media/jdlongmire/Macro-Drive-2TB/GitHub_Repos/ThinxAI-Draw-Bot/` (baseline architecture)
- **Canvas-MCP:** Current repo's MCP server for hierarchical diagrams
- **ThinxAI Web:** `thinxai-web/` (main web interface)
