#!/usr/bin/env python3
"""
Canvas Bot - Web interface for hierarchical diagram generation

A lightweight web server providing a chat interface to create hierarchical
system diagrams using the Canvas-MCP renderer with Claude CLI.

Usage:
    python canvas_bot.py [--port 8765] [--host 0.0.0.0]
"""

import asyncio
import base64
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from aiohttp import web

# Add src to path for canvas_mcp imports
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR / 'src'))

from canvas_mcp.parser import parse_yaml
from canvas_mcp.renderer import CanvasRenderer
from canvas_mcp.xmi_exporter import export_to_xmi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
HISTORY_DIR = SCRIPT_DIR / 'history'
DIAGRAMS_DIR = SCRIPT_DIR / 'diagrams'
UPLOADS_DIR = SCRIPT_DIR / 'uploads'
WEB_DIR = SCRIPT_DIR / 'web'
PROFILE_PATH = SCRIPT_DIR / 'profiles' / 'canvas_bot.md'

# Ensure directories exist
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
WEB_DIR.mkdir(parents=True, exist_ok=True)
(SCRIPT_DIR / 'profiles').mkdir(parents=True, exist_ok=True)

# User ID for web sessions
WEB_USER_ID = "canvas_user"


def get_history_path(user_id: str) -> Path:
    """Get the conversation history file path for a user."""
    return HISTORY_DIR / f"{user_id}.jsonl"


def load_history(user_id: str, limit: int = 50) -> list:
    """Load recent conversation history."""
    history_path = get_history_path(user_id)
    if not history_path.exists():
        return []

    messages = []
    try:
        with open(history_path, 'r') as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))
        return messages[-limit:]
    except Exception as e:
        logger.error(f"Error loading history: {e}")
        return []


def save_message(user_id: str, role: str, content: str):
    """Save a message to conversation history."""
    history_path = get_history_path(user_id)
    entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "source": "canvas_bot"
    }
    try:
        with open(history_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        logger.error(f"Error saving message: {e}")


def render_canvas_yaml(yaml_content: str, output_name: str = None, theme: str = None) -> tuple[str, str]:
    """
    Render a Canvas YAML to PNG.

    Args:
        yaml_content: YAML defining the diagram
        output_name: Optional filename (without extension)
        theme: 'dark' or 'light' - overrides theme in YAML if provided

    Returns: (image_path, error_message)
    """
    try:
        canvas = parse_yaml(yaml_content)

        # Override theme if specified (from UI preference or natural language)
        if theme and theme in ('dark', 'light'):
            canvas.theme = theme

        renderer = CanvasRenderer(scale=1.5)

        # Generate filename
        if not output_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_name = f"canvas_{timestamp}"

        output_path = DIAGRAMS_DIR / f"{output_name}.png"
        renderer.render(canvas, output_path=str(output_path), organize=True)

        return str(output_path), None
    except Exception as e:
        logger.error(f"Render error: {e}")
        return None, str(e)


def save_uploaded_image(base64_data: str, filename: str = None) -> str:
    """
    Save a base64 image to the uploads directory.
    Returns the file path.
    """
    try:
        # Strip data URL prefix if present
        if ',' in base64_data:
            base64_data = base64_data.split(',', 1)[1]

        image_data = base64.b64decode(base64_data)

        # Generate filename
        if not filename:
            filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        else:
            # Sanitize filename
            safe_name = re.sub(r'[^\w\-_.]', '_', filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name, ext = os.path.splitext(safe_name)
            filename = f"{name}_{timestamp}{ext}"

        file_path = UPLOADS_DIR / filename
        with open(file_path, 'wb') as f:
            f.write(image_data)

        return str(file_path)
    except Exception as e:
        logger.error(f"Error saving uploaded image: {e}")
        return None


def build_canvas_bot_prompt(user_id: str, message: str, image_path: str = None) -> str:
    """Build the Canvas Bot prompt with specialized context."""
    parts = []

    # System instructions for image display
    system_instructions = """<system_instructions>
You are Canvas Bot, a specialized assistant for creating hierarchical system diagrams.

Your diagrams use a 4-level semantic hierarchy:
- Network: System boundary (broadest scope)
- Factory: Functional domain (groups pipelines)
- Machine: Pipeline (connected chain of operations)
- Node: Single operation (atomic unit)

Node types with semantic colors:
- input (blue): User-provided data entering the system
- output (amber): Final results leaving the system
- process (cyan): Transformation or computation step
- decision (red): Branching/conditional gate
- ai (purple): AI/LLM processing step
- source (orange): External data source (API, database)
- static (green): Immutable seed content or constants
- default (gray): Generic/unspecified

When you create a diagram, output the YAML in a ```yaml block, and I will render it.
After rendering, output the image path like this so it displays in chat:
[ACTION:show_image|/full/path/to/image.png]
</system_instructions>"""
    parts.append(system_instructions)

    # Load Canvas Bot profile if it exists
    if PROFILE_PATH.exists():
        try:
            with open(PROFILE_PATH, 'r') as f:
                profile_content = f.read()
            parts.append(f"<canvas_bot_profile>\n{profile_content}\n</canvas_bot_profile>")
        except Exception as e:
            logger.warning(f"Could not read profile: {e}")

    # Behavior instructions
    behavior = """<behavior>
## Your Workflow

1. **Diagnostic Intake**: When the user first describes what they need, ask clarifying questions:
   - What system/process are you modeling?
   - What's the main flow or hierarchy?
   - How many levels deep? (simple: 1 machine, complex: multiple factories)
   - What nodes need to be included? What types?
   - Any specific connections between nodes?

2. **Generate YAML**: Create the Canvas YAML with proper hierarchy:
   - Use descriptive IDs for all elements
   - Add labels for human-readable names
   - Specify node types for color-coding
   - Define inputs/outputs for connections

3. **Render**: Output the YAML in a ```yaml code block. The system will render it.

4. **Iterate**: Ask if they want adjustments (add nodes, change connections, etc.)

## YAML Format

Simple format (auto-creates single machine):
```yaml
title: My Diagram
nodes:
  - id: start
    type: input
    label: User Input
    content: "Description here"
  - id: process
    type: process
    label: Process Data
    inputs: [start]
  - id: output
    type: output
    label: Final Result
    inputs: [process]
```

Hierarchical format (full control):
```yaml
canvas:
  title: My System
  networks:
    - id: main-network
      factories:
        - id: data-factory
          label: Data Processing
          machines:
            - id: pipeline-1
              label: Main Pipeline
              nodes:
                - id: input-1
                  type: input
                  content: "Start here"
                - id: proc-1
                  type: process
                  inputs: [input-1]

## Important Rules
- Always ask clarifying questions first (unless user provides complete spec)
- Use descriptive IDs (not just "node1", "node2")
- Add content descriptions to nodes for context
- Group related nodes in machines, related machines in factories
- Use appropriate node types for semantic meaning
</behavior>"""
    parts.append(behavior)

    # Load conversation history
    history = load_history(user_id, limit=10)
    if history:
        history_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in history[-6:]
        ])
        parts.append(f"<conversation_history>\n{history_text}\n</conversation_history>")

    # Current message
    parts.append(f"User message: {message}")

    # Add image analysis instructions if an image is attached
    if image_path:
        image_instructions = f"""<image_analysis>
The user has attached an image/sketch at: {image_path}

IMPORTANT: Use the Read tool to view this image file. Analyze the sketch and:
1. Identify the components/nodes shown (boxes, circles, labels)
2. Identify the connections/arrows between them
3. Determine the flow direction (left-to-right, top-to-bottom)
4. Map each sketched element to appropriate Canvas node types:
   - Boxes with data labels → input/output nodes
   - Processing boxes → process nodes
   - Diamond shapes → decision nodes
   - Cloud/AI labels → ai nodes
   - Database/API labels → source nodes
   - Constants/config → static nodes

Then generate the Canvas YAML that recreates the diagram professionally.
</image_analysis>"""
        parts.append(image_instructions)

    return "\n\n".join(parts)


async def call_claude_streaming(prompt: str, skip_permissions: bool = True, on_event=None):
    """Call Claude CLI with streaming output."""
    cmd = [
        'claude',
        '--output-format', 'stream-json',
        '--verbose',
        '-p', prompt
    ]
    if skip_permissions:
        cmd.append('--dangerously-skip-permissions')

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=10 * 1024 * 1024
    )

    result_text = ""
    buffer = b""

    try:
        while True:
            chunk = await process.stdout.read(64 * 1024)
            if not chunk:
                break

            buffer += chunk

            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                if not line.strip():
                    continue

                try:
                    event = json.loads(line.decode().strip())

                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            result_text += delta.get("text", "")

                    if event.get("type") == "result":
                        result = event.get("result", "")
                        if result and not result_text:
                            result_text = result

                    if on_event:
                        await on_event(event)

                except json.JSONDecodeError:
                    continue

        if buffer.strip():
            try:
                event = json.loads(buffer.decode().strip())
                if event.get("type") == "result":
                    result = event.get("result", "")
                    if result and not result_text:
                        result_text = result
                if on_event:
                    await on_event(event)
            except json.JSONDecodeError:
                pass

    except Exception as e:
        logger.error(f"Streaming error: {e}")

    await process.wait()
    stderr = await process.stderr.read()

    return result_text, process.returncode, stderr.decode() if stderr else ""


def detect_theme_from_message(message: str) -> str | None:
    """
    Detect if user requested a specific theme via natural language.

    Returns: 'dark', 'light', or None if no theme mentioned
    """
    message_lower = message.lower()

    # Light theme patterns
    light_patterns = [
        'light theme', 'light mode', 'light color', 'light background',
        'white background', 'bright theme', 'bright background',
        'for presentation', 'for print', 'printable',
        'make it light', 'use light', 'switch to light'
    ]

    # Dark theme patterns
    dark_patterns = [
        'dark theme', 'dark mode', 'dark color', 'dark background',
        'black background', 'make it dark', 'use dark', 'switch to dark'
    ]

    for pattern in light_patterns:
        if pattern in message_lower:
            return 'light'

    for pattern in dark_patterns:
        if pattern in message_lower:
            return 'dark'

    return None


def extract_and_render_yaml(response_text: str, theme: str = None) -> tuple[str, str]:
    """
    Extract YAML from response and render if found.

    Args:
        response_text: Claude's response that may contain YAML
        theme: 'dark' or 'light' to override theme in YAML

    Returns: (modified_response, image_path or None)
    """
    # Look for YAML code blocks
    yaml_pattern = r'```ya?ml\n(.*?)```'
    matches = re.findall(yaml_pattern, response_text, re.DOTALL)

    if not matches:
        return response_text, None

    # Try to render the last YAML block (most likely the final version)
    yaml_content = matches[-1].strip()

    # Check if it looks like a canvas definition
    if 'nodes:' in yaml_content or 'canvas:' in yaml_content:
        image_path, error = render_canvas_yaml(yaml_content, theme=theme)

        if image_path:
            # Add image action if not already present
            if '[ACTION:show_image|' not in response_text:
                response_text += f"\n\n[ACTION:show_image|{image_path}]"
            return response_text, image_path
        else:
            # Add error message
            response_text += f"\n\n**Render Error:** {error}"

    return response_text, None


# =============================================================================
# HTTP Handlers
# =============================================================================

async def handle_index(request):
    """Serve the main web interface."""
    index_path = WEB_DIR / 'index.html'
    if index_path.exists():
        return web.FileResponse(index_path)
    return web.Response(text="Web interface not found.", status=404)


async def handle_status(request):
    """Health check endpoint."""
    return web.json_response({
        "status": "ok",
        "service": "Canvas Bot",
        "timestamp": datetime.now().isoformat()
    })


async def handle_history(request):
    """Return conversation history."""
    history = load_history(WEB_USER_ID, limit=100)
    return web.json_response(history)


async def handle_clear_history(request):
    """Clear conversation history."""
    history_path = get_history_path(WEB_USER_ID)
    if history_path.exists():
        history_path.unlink()
    return web.json_response({"status": "cleared"})


async def handle_message_stream(request):
    """Handle streaming message endpoint."""
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'X-Accel-Buffering': 'no',
        }
    )
    await response.prepare(request)

    MAX_SSE_EVENT_SIZE = 16 * 1024
    keep_alive_active = [True]
    last_event_time = [asyncio.get_event_loop().time()]

    async def keep_alive_task():
        """Send periodic keep-alive pings."""
        while keep_alive_active[0]:
            await asyncio.sleep(5)
            if keep_alive_active[0]:
                elapsed = asyncio.get_event_loop().time() - last_event_time[0]
                if elapsed >= 4:
                    try:
                        await response.write(b': keepalive\n\n')
                        last_event_time[0] = asyncio.get_event_loop().time()
                    except Exception:
                        break

    async def send_sse_data(data_dict):
        """Send SSE data, truncating if needed."""
        nonlocal last_event_time
        event_data = json.dumps(data_dict)
        if len(event_data) <= MAX_SSE_EVENT_SIZE:
            await response.write(f'data: {event_data}\n\n'.encode())
        else:
            summary = {
                "type": data_dict.get("type", "status"),
                "message": data_dict.get("message", "Processing...")[:500] + "...",
                "truncated": True
            }
            await response.write(f'data: {json.dumps(summary)}\n\n'.encode())
        last_event_time[0] = asyncio.get_event_loop().time()

    async def send_event(event):
        """Send streaming event to client."""
        event_type = event.get("type", "")

        if event_type == "system" and event.get("subtype") == "init":
            status = {"type": "status", "message": "Initializing Canvas Bot..."}
            await send_sse_data(status)
        elif event_type == "assistant":
            msg = event.get("message", {})
            content = msg.get("content", [])
            for block in content:
                if block.get("type") == "tool_use":
                    tool_name = block.get("name", "tool")
                    status = {"type": "tool", "name": tool_name, "message": f"{tool_name}"}
                    await send_sse_data(status)
        elif event_type == "user":
            msg = event.get("message", {})
            content = msg.get("content", [])
            for block in content:
                if block.get("type") == "tool_result":
                    status = {"type": "tool_result", "message": "Got result"}
                    await send_sse_data(status)

    # Start keep-alive task
    ping_task = asyncio.create_task(keep_alive_task())

    try:
        data = await request.json()
        user_message = data.get("message", "").strip()
        image_base64 = data.get("image", None)
        image_name = data.get("image_name", None)
        output_theme = data.get("output_theme", "dark")  # Default to dark

        # Natural language can override UI setting
        nl_theme = detect_theme_from_message(user_message)
        if nl_theme:
            output_theme = nl_theme
            logger.info(f"Theme override from natural language: {output_theme}")

        if not user_message and not image_base64:
            await response.write(b'data: {"type":"error","message":"No message provided"}\n\n')
            return response

        # Handle image upload
        image_path = None
        if image_base64:
            image_path = save_uploaded_image(image_base64, image_name)
            if image_path:
                logger.info(f"Saved uploaded image: {image_path}")
                await send_sse_data({"type": "status", "message": "Analyzing your sketch..."})
            else:
                await send_sse_data({"type": "status", "message": "Warning: Could not save image"})

        if not user_message:
            user_message = "Convert this sketch to a professional diagram"

        logger.info(f"Canvas Bot: {user_message[:50]}..." + (f" [with image]" if image_path else ""))

        full_prompt = build_canvas_bot_prompt(WEB_USER_ID, user_message, image_path)

        result, returncode, stderr = await call_claude_streaming(
            full_prompt,
            on_event=send_event
        )

        if returncode != 0 or not result:
            error_msg = stderr if stderr else "No response"
            error_msg = error_msg[:500].replace('"', '\\"').replace('\n', '\\n')
            await response.write(f'data: {{"type":"error","message":"{error_msg}"}}\n\n'.encode())
            return response

        # Extract and render any YAML in the response
        result, image_path = extract_and_render_yaml(result, theme=output_theme)

        # Clean response
        result = re.sub(r'\[ACTION:check_inbox(?::\d+)?\]\n?', '', result)
        result = re.sub(r'\[ACTION:send_email\|[^\]]+\]\n?', '', result)
        result = result.strip()

        # Save to history
        save_message(WEB_USER_ID, "user", user_message)
        save_message(WEB_USER_ID, "assistant", result)

        # Send final response
        MAX_SSE_CHUNK = 16 * 1024
        if len(result) > MAX_SSE_CHUNK:
            for i in range(0, len(result), MAX_SSE_CHUNK):
                chunk = result[i:i + MAX_SSE_CHUNK]
                is_last = (i + MAX_SSE_CHUNK >= len(result))
                chunk_event = {
                    "type": "response_chunk" if not is_last else "response",
                    "content": chunk,
                    "partial": not is_last
                }
                await response.write(f'data: {json.dumps(chunk_event)}\n\n'.encode())
        else:
            final = {"type": "response", "content": result}
            await response.write(f'data: {json.dumps(final)}\n\n'.encode())

        # Send done signal
        await response.write(b'data: {"type":"done"}\n\n')

    except (ConnectionResetError, BrokenPipeError) as e:
        logger.debug(f"Client disconnected: {e}")
    except Exception as e:
        error_str = str(e)
        if "closing transport" in error_str.lower() or "connection reset" in error_str.lower():
            logger.debug(f"Client disconnected: {e}")
        else:
            logger.error(f"Stream error: {e}")
            try:
                error_msg = error_str[:500].replace('"', '\\"').replace('\n', '\\n')
                await response.write(f'data: {{"type":"error","message":"{error_msg}"}}\n\n'.encode())
            except Exception:
                pass
    finally:
        keep_alive_active[0] = False
        ping_task.cancel()
        try:
            await ping_task
        except asyncio.CancelledError:
            pass

    return response


async def handle_render(request):
    """Direct YAML render endpoint."""
    try:
        data = await request.json()
        yaml_content = data.get("yaml", "")
        name = data.get("name", None)
        theme = data.get("theme", None)  # Optional theme override

        if not yaml_content:
            return web.json_response({"error": "No YAML provided"}, status=400)

        image_path, error = render_canvas_yaml(yaml_content, name, theme=theme)

        if error:
            return web.json_response({"error": error}, status=400)

        return web.json_response({
            "success": True,
            "path": image_path
        })

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_image(request):
    """Serve images from the filesystem."""
    path = request.query.get('path', '')

    if not path:
        return web.Response(text="No path specified", status=400)

    path = Path(path).resolve()

    # Security: only allow certain directories
    allowed_roots = [
        DIAGRAMS_DIR.resolve(),
        UPLOADS_DIR.resolve(),
        SCRIPT_DIR.resolve(),
    ]

    allowed = any(
        str(path).startswith(str(root))
        for root in allowed_roots
    )

    if not allowed or not path.exists():
        return web.Response(text="File not found or not allowed", status=404)

    return web.FileResponse(path)


async def handle_download(request):
    """Serve images as downloadable attachments (mobile-friendly)."""
    path = request.query.get('path', '')
    filename = request.query.get('filename', 'diagram.png')

    if not path:
        return web.Response(text="No path specified", status=400)

    path = Path(path).resolve()

    # Security: only allow certain directories
    allowed_roots = [
        DIAGRAMS_DIR.resolve(),
        UPLOADS_DIR.resolve(),
        SCRIPT_DIR.resolve(),
    ]

    allowed = any(
        str(path).startswith(str(root))
        for root in allowed_roots
    )

    if not allowed or not path.exists():
        return web.Response(text="File not found or not allowed", status=404)

    # Read file and serve with download headers
    with open(path, 'rb') as f:
        content = f.read()

    return web.Response(
        body=content,
        headers={
            'Content-Type': 'image/png',
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(content)),
        }
    )


async def handle_static_file(request):
    """Serve static files from web directory."""
    filename = request.match_info['filename']
    file_path = WEB_DIR / filename
    if file_path.exists() and file_path.is_file():
        return web.FileResponse(file_path)
    return web.Response(text="File not found", status=404)


async def handle_export_xmi(request):
    """Export a diagram to XMI format for Cameo Modeler integration."""
    try:
        data = await request.json()
        yaml_content = data.get("yaml", "")
        name = data.get("name", "diagram")

        if not yaml_content:
            return web.json_response({"error": "No YAML provided"}, status=400)

        # Parse YAML to Canvas
        canvas = parse_yaml(yaml_content)

        # Export to XMI
        xmi_content = export_to_xmi(canvas, pretty=True)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{name}_{timestamp}.xmi"
        xmi_path = DIAGRAMS_DIR / filename

        # Save to file
        with open(xmi_path, 'w', encoding='utf-8') as f:
            f.write(xmi_content)

        logger.info(f"Exported XMI: {xmi_path}")

        return web.json_response({
            "success": True,
            "path": str(xmi_path),
            "filename": filename
        })

    except Exception as e:
        logger.error(f"XMI export error: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_download_xmi(request):
    """Serve XMI files as downloadable attachments."""
    path = request.query.get('path', '')
    filename = request.query.get('filename', 'diagram.xmi')

    if not path:
        return web.Response(text="No path specified", status=400)

    path = Path(path).resolve()

    # Security: only allow diagrams directory
    if not str(path).startswith(str(DIAGRAMS_DIR.resolve())):
        return web.Response(text="File not allowed", status=403)

    if not path.exists():
        return web.Response(text="File not found", status=404)

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    return web.Response(
        body=content,
        headers={
            'Content-Type': 'application/xml',
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(content.encode('utf-8'))),
        }
    )


def create_app():
    """Create the aiohttp application."""
    # Allow up to 20MB request body for image uploads
    app = web.Application(client_max_size=20 * 1024 * 1024)

    # API routes
    app.router.add_get('/api/status', handle_status)
    app.router.add_get('/api/history', handle_history)
    app.router.add_post('/api/history/clear', handle_clear_history)
    app.router.add_post('/api/message/stream', handle_message_stream)
    app.router.add_post('/api/render', handle_render)
    app.router.add_get('/api/image', handle_image)
    app.router.add_get('/api/download', handle_download)
    app.router.add_post('/api/export/xmi', handle_export_xmi)
    app.router.add_get('/api/download/xmi', handle_download_xmi)

    # Static files and pages
    app.router.add_get('/', handle_index)
    app.router.add_get('/{filename}', handle_static_file)

    if WEB_DIR.exists():
        app.router.add_static('/static/', WEB_DIR, name='static')

    return app


async def main(host: str = '0.0.0.0', port: int = 8766):
    """Run the web server."""
    app = create_app()

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Canvas Bot running at http://{host}:{port}")
    logger.info(f"History: {HISTORY_DIR}")
    logger.info(f"Diagrams: {DIAGRAMS_DIR}")

    # Keep running
    while True:
        await asyncio.sleep(3600)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Canvas Bot Web Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8766, help='Port to listen on')
    args = parser.parse_args()

    try:
        asyncio.run(main(host=args.host, port=args.port))
    except KeyboardInterrupt:
        logger.info("Shutting down...")
