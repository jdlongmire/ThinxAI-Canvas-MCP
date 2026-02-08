"""Canvas-MCP server — MCP tools for creating hierarchical canvas diagrams."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, ImageContent, Tool

from .models import Canvas, CanvasNetwork, CanvasFactory, CanvasMachine, CanvasNode
from .parser import parse_yaml, canvas_to_yaml
from .renderer import CanvasRenderer


# --- Constants ---
OUTPUT_DIR = Path(os.environ.get("CANVAS_OUTPUT_DIR", Path.home() / ".rhode" / "canvas"))
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

server = Server("canvas-mcp")


def _ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --- Tool definitions ---

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="render_canvas",
            description=(
                "Render a canvas diagram from a YAML recipe string. "
                "Supports hierarchical format (networks/factories/machines/nodes) "
                "or a simplified format (flat list of nodes with inputs/outputs). "
                "Returns the path to the rendered PNG file."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "yaml_recipe": {
                        "type": "string",
                        "description": (
                            "YAML string defining the canvas. Simplified format example:\n"
                            "title: My Diagram\n"
                            "nodes:\n"
                            "  - id: start\n"
                            "    type: input\n"
                            "    content: 'Begin here'\n"
                            "  - id: process\n"
                            "    type: process\n"
                            "    content: 'Do work'\n"
                            "    inputs: [start]\n"
                            "\n"
                            "Node types: static, input, ai, source, output, decision, process, default\n"
                            "Coordinates (x, y) are optional — auto-layout is applied if all are 0."
                        ),
                    },
                    "scale": {
                        "type": "number",
                        "description": "Render scale factor (default 2.0 for crisp, legible output)",
                        "default": 2.0,
                    },
                    "filename": {
                        "type": "string",
                        "description": "Output filename (without extension). Default: auto-generated UUID.",
                    },
                    "organize": {
                        "type": "boolean",
                        "description": (
                            "Apply the hierarchical organize algorithm for "
                            "automatic layout with proper breathing room. Organizes nodes "
                            "within machines, machines within factories, factories within "
                            "networks — each with appropriate spacing. Default: true."
                        ),
                        "default": True,
                    },
                    "spacing_level": {
                        "type": "string",
                        "enum": ["node", "container", "network"],
                        "description": (
                            "Spacing level for organize layout: "
                            "'node' (tight: 60h/110v), "
                            "'container' (medium: 150h/190v, default), "
                            "'network' (spacious: 190h/250v)."
                        ),
                        "default": "container",
                    },
                    "orientation": {
                        "type": "string",
                        "enum": ["horizontal", "vertical"],
                        "description": (
                            "Layout direction: 'horizontal' (left→right, default) "
                            "or 'vertical' (top→bottom tree). Applied at all hierarchy levels."
                        ),
                        "default": "horizontal",
                    },
                },
                "required": ["yaml_recipe"],
            },
        ),
        Tool(
            name="create_canvas",
            description=(
                "Create a canvas diagram from a structured description. "
                "Provide a title, nodes, and connections — the tool handles layout and rendering. "
                "Returns the path to the rendered PNG and the generated YAML recipe."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title for the canvas diagram.",
                    },
                    "nodes": {
                        "type": "array",
                        "description": "List of nodes to place on the canvas.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "Unique node identifier"},
                                "type": {
                                    "type": "string",
                                    "enum": ["static", "input", "ai", "source", "output", "decision", "process", "default"],
                                    "description": "Node type (affects color/styling)",
                                },
                                "content": {"type": "string", "description": "Text content of the node"},
                                "label": {"type": "string", "description": "Display label (defaults to id)"},
                                "inputs": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "IDs of nodes that feed into this one",
                                },
                            },
                            "required": ["id", "type", "content"],
                        },
                    },
                    "machines": {
                        "type": "array",
                        "description": "Optional: group nodes into machines. Each item is a list of node IDs.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "node_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["id", "node_ids"],
                        },
                    },
                    "scale": {
                        "type": "number",
                        "description": "Render scale factor (default 2.0)",
                        "default": 2.0,
                    },
                    "organize": {
                        "type": "boolean",
                        "description": (
                            "Apply the organize algorithm for automatic layout. Default: true."
                        ),
                        "default": True,
                    },
                    "spacing_level": {
                        "type": "string",
                        "enum": ["node", "container", "network"],
                        "description": "Spacing level for organize layout. Default: 'container'.",
                        "default": "container",
                    },
                    "orientation": {
                        "type": "string",
                        "enum": ["horizontal", "vertical"],
                        "description": (
                            "Layout direction: 'horizontal' (left→right, default) "
                            "or 'vertical' (top→bottom tree)."
                        ),
                        "default": "horizontal",
                    },
                },
                "required": ["title", "nodes"],
            },
        ),
        Tool(
            name="list_templates",
            description="List available canvas recipe templates that can be used as starting points.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_template",
            description="Get the YAML content of a specific template by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Template name (from list_templates output)",
                    },
                },
                "required": ["name"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    if name == "render_canvas":
        return await _render_canvas(arguments)
    elif name == "create_canvas":
        return await _create_canvas(arguments)
    elif name == "list_templates":
        return await _list_templates(arguments)
    elif name == "get_template":
        return await _get_template(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _render_canvas(args: dict) -> list[TextContent]:
    """Render a YAML recipe to PNG."""
    _ensure_output_dir()

    yaml_str = args["yaml_recipe"]
    scale = args.get("scale", 2.0)
    filename = args.get("filename", str(uuid.uuid4())[:8])

    try:
        canvas = parse_yaml(yaml_str)
    except Exception as e:
        return [TextContent(type="text", text=f"Failed to parse YAML recipe: {e}")]

    organize = args.get("organize", True)
    spacing_level = args.get("spacing_level", "container")
    orientation = args.get("orientation", "horizontal")

    renderer = CanvasRenderer(scale=scale)
    output_path = str(OUTPUT_DIR / f"{filename}.png")

    try:
        renderer.render(
            canvas,
            output_path=output_path,
            organize=organize,
            spacing_level=spacing_level,
            orientation=orientation,
        )
    except Exception as e:
        return [TextContent(type="text", text=f"Rendering failed: {e}")]

    return [TextContent(
        type="text",
        text=json.dumps({
            "status": "success",
            "path": output_path,
            "title": canvas.title,
            "nodes": len(canvas.all_nodes()),
            "connections": len(canvas.all_connections()),
            "organized": organize,
            "spacing_level": spacing_level if organize else None,
            "orientation": orientation if organize else None,
        }),
    )]


async def _create_canvas(args: dict) -> list[TextContent]:
    """Create a canvas from structured input and render it."""
    _ensure_output_dir()

    title = args["title"]
    node_defs = args["nodes"]
    machine_defs = args.get("machines")
    scale = args.get("scale", 2.0)
    organize = args.get("organize", True)
    spacing_level = args.get("spacing_level", "container")
    orientation = args.get("orientation", "horizontal")

    # Build node objects
    nodes_by_id = {}
    for nd in node_defs:
        node = CanvasNode(
            id=nd["id"],
            type=nd.get("type", "default"),
            content=nd.get("content", ""),
            label=nd.get("label"),
            inputs=nd.get("inputs", []),
        )
        nodes_by_id[node.id] = node

    # Group into machines
    machines = []
    if machine_defs:
        assigned = set()
        for md in machine_defs:
            m_nodes = [nodes_by_id[nid] for nid in md["node_ids"] if nid in nodes_by_id]
            assigned.update(md["node_ids"])
            machines.append(CanvasMachine(
                id=md["id"],
                label=md.get("label"),
                nodes=m_nodes,
            ))
        # Put unassigned nodes in a catch-all machine
        unassigned = [n for nid, n in nodes_by_id.items() if nid not in assigned]
        if unassigned:
            machines.append(CanvasMachine(id="machine-unassigned", nodes=unassigned))
    else:
        # Auto-detect machines from connectivity
        machines = _auto_detect_machines(list(nodes_by_id.values()))

    factory = CanvasFactory(id="factory-1", machines=machines)
    network = CanvasNetwork(id="network-1", factories=[factory])
    canvas = Canvas(title=title, networks=[network])
    canvas.model_post_init(None)

    # Render
    renderer = CanvasRenderer(scale=scale)
    filename = title.lower().replace(" ", "-")[:30] + "-" + str(uuid.uuid4())[:4]
    output_path = str(OUTPUT_DIR / f"{filename}.png")

    try:
        renderer.render(
            canvas,
            output_path=output_path,
            organize=organize,
            spacing_level=spacing_level,
            orientation=orientation,
        )
    except Exception as e:
        return [TextContent(type="text", text=f"Rendering failed: {e}")]

    # Also save the YAML recipe
    yaml_path = str(OUTPUT_DIR / f"{filename}.yaml")
    yaml_content = canvas_to_yaml(canvas)
    Path(yaml_path).write_text(yaml_content)

    return [TextContent(
        type="text",
        text=json.dumps({
            "status": "success",
            "png_path": output_path,
            "yaml_path": yaml_path,
            "title": title,
            "nodes": len(canvas.all_nodes()),
            "connections": len(canvas.all_connections()),
            "machines": len(machines),
        }),
    )]


def _auto_detect_machines(nodes: list[CanvasNode]) -> list[CanvasMachine]:
    """Auto-detect machines as connected components of nodes."""
    if not nodes:
        return []

    # Build adjacency from inputs/outputs
    adj: dict[str, set[str]] = {n.id: set() for n in nodes}
    node_ids = {n.id for n in nodes}

    for n in nodes:
        for inp in n.inputs:
            if inp in node_ids:
                adj[n.id].add(inp)
                adj[inp].add(n.id)
        for out in n.outputs:
            if out in node_ids:
                adj[n.id].add(out)
                adj[out].add(n.id)

    # Find connected components
    visited = set()
    components = []

    for n in nodes:
        if n.id in visited:
            continue
        component = []
        stack = [n.id]
        while stack:
            nid = stack.pop()
            if nid in visited:
                continue
            visited.add(nid)
            component.append(nid)
            stack.extend(adj[nid] - visited)
        components.append(component)

    # Create machines
    nodes_by_id = {n.id: n for n in nodes}
    machines = []
    for i, comp in enumerate(components):
        m_nodes = [nodes_by_id[nid] for nid in comp]
        machines.append(CanvasMachine(
            id=f"machine-{i+1}",
            nodes=m_nodes,
        ))

    return machines


async def _list_templates(args: dict) -> list[TextContent]:
    """List available template files."""
    templates = []

    if TEMPLATES_DIR.exists():
        for f in sorted(TEMPLATES_DIR.glob("*.yaml")) + sorted(TEMPLATES_DIR.glob("*.yml")):
            templates.append({
                "name": f.stem,
                "path": str(f),
            })

    return [TextContent(
        type="text",
        text=json.dumps({"templates": templates}),
    )]


async def _get_template(args: dict) -> list[TextContent]:
    """Get template content by name."""
    name = args["name"]

    # Check local templates first
    for ext in [".yaml", ".yml"]:
        path = TEMPLATES_DIR / f"{name}{ext}"
        if path.exists():
            return [TextContent(type="text", text=path.read_text())]

    return [TextContent(type="text", text=f"Template not found: {name}")]


def main():
    """Entry point for the MCP server."""
    import asyncio
    asyncio.run(_run())


async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
