"""Test the hierarchical organize system with a Rhode architecture diagram.

Canvas-MCP ontology rules:
  - Machine = connected component of nodes (nodes with direct edges between them)
  - Factory = machines connected by explicit cross-machine edges
  - Network = factories connected by explicit cross-factory edges
  - A factory is NEVER a bag of disconnected machines
  - Shared upstream input does NOT imply shared factory
"""

import sys
sys.path.insert(0, "src")

from canvas_mcp.models import (
    Canvas, CanvasNetwork, CanvasFactory, CanvasMachine, CanvasNode, ContainerStyle,
)
from canvas_mcp.renderer import CanvasRenderer


def build_rhode_canvas() -> Canvas:
    """Build Rhode architecture following Canvas-MCP ontology rules.

    The key insight: factories are defined by connectivity, not by category.
    Machines in the same factory MUST have explicit cross-machine connections.

    Rhode's data flow:
      telegram ──┐
                 ├──→ task-queue → agent ──→ tools ──→ outputs
      bus-monitor┘        ↑                    ↑
                       memory              (fan-out)

    Factory 1 "Ingestion": input sources → task queue (seed → process pipeline)
    Factory 2 "Core Processing": task-queue → agent ← memory (cross-machine join)
    Factory 3 "Tooling & Output": agent → tools → outputs (fan-out → converge)
      - Tools machine: canvas-mcp, ordinal-mcp, git, shell (parallel from agent)
      - Telegram Output machine: send-photo, send-text (converge from tools+agent)
      - Oracle Output machine: oracle-response (from ordinal-mcp)
      Cross-machine edges: tools→telegram-output (canvas-mcp→send-photo),
                           tools→oracle-output (ordinal-mcp→oracle-response)
    """

    # =================================================================
    # Factory 1: Ingestion
    # One machine — telegram and bus-monitor are parallel input sources
    # that both feed into the task queue. The task queue is the terminus
    # of this factory; it outputs to the next factory.
    # =================================================================
    telegram_node = CanvasNode(
        id="telegram", type="input", label="Telegram Bot",
        content="Receives messages, photos, files from Micah",
        outputs=["task-queue"],
    )
    bus_monitor = CanvasNode(
        id="bus-monitor", type="input", label="Bus Monitor",
        content="Polls oracle bus for requests, routes by ordinal level",
        outputs=["task-queue"],
    )
    task_queue = CanvasNode(
        id="task-queue", type="process", label="Task Queue",
        content="Async task queue with priority handling",
        inputs=["telegram", "bus-monitor"],
    )
    ingestion_machine = CanvasMachine(
        id="ingestion-pipeline", label="Ingestion Pipeline",
        nodes=[telegram_node, bus_monitor, task_queue],
    )
    ingestion_factory = CanvasFactory(
        id="ingestion", label="Ingestion",
        machines=[ingestion_machine],
        style=ContainerStyle(border_color="#2196F3"),
    )

    # =================================================================
    # Factory 2: Core Processing
    # Two machines with an explicit cross-machine connection:
    #   - Processing machine: task-queue input → agent (the main pipeline)
    #   - Memory machine: memory store (feeds into agent)
    # Cross-machine edge: memory → agent (memory-system → processing)
    # This is a valid factory — machines are connected.
    # =================================================================
    agent = CanvasNode(
        id="agent", type="ai", label="Claude Agent",
        content="Opus 4.6 with MCP tools, memory injection, multi-turn",
        inputs=["task-queue", "memory"],
    )
    processing_machine = CanvasMachine(
        id="processing", label="Agent Pipeline",
        nodes=[agent],
    )

    memory = CanvasNode(
        id="memory", type="static", label="Memory Store",
        content="Persistent lessons, preferences, patterns in memory.md",
        outputs=["agent"],
    )
    memory_machine = CanvasMachine(
        id="memory-system", label="Memory System",
        nodes=[memory],
    )

    core_factory = CanvasFactory(
        id="core-engine", label="Core Engine",
        machines=[memory_machine, processing_machine],
        style=ContainerStyle(border_color="#9C27B0"),
    )

    # =================================================================
    # Factory 3: Tooling & Output
    # Three machines, ALL connected by explicit cross-machine edges:
    #
    #   Tools machine (fan-out from agent):
    #     canvas-mcp, ordinal-mcp, git, shell
    #                    │                  │
    #                    ├──────────────────┤
    #                    ↓                  ↓
    #   Telegram Output machine:    Oracle Output machine:
    #     send-photo, send-text       oracle-response
    #
    # Cross-machine edges:
    #   tools → telegram-output (canvas-mcp → send-photo)
    #   tools → oracle-output   (ordinal-mcp → oracle-response)
    #
    # This is a valid factory — all three machines are connected
    # through explicit cross-machine paths.
    # =================================================================
    canvas_mcp = CanvasNode(
        id="canvas-mcp", type="source", label="Canvas MCP",
        content="Hierarchical canvas diagram renderer",
        inputs=["agent"],
        outputs=["send-photo"],
    )
    ordinal_mcp = CanvasNode(
        id="ordinal-mcp", type="source", label="Ordinal MCP",
        content="Oracle bus for human-in-the-loop decisions",
        inputs=["agent"],
        outputs=["oracle-response"],
    )
    git_node = CanvasNode(
        id="git", type="source", label="Git / GitHub",
        content="Code operations, PR creation, branch management",
        inputs=["agent"],
    )
    shell_node = CanvasNode(
        id="shell", type="source", label="Shell Access",
        content="Full system access, uv, podman, systemd",
        inputs=["agent"],
    )
    tools_machine = CanvasMachine(
        id="tools", label="Tools",
        nodes=[canvas_mcp, ordinal_mcp, git_node, shell_node],
    )

    send_photo = CanvasNode(
        id="send-photo", type="output", label="Photo/File Send",
        content="Send diagrams, files to Telegram",
        inputs=["canvas-mcp", "agent"],
    )
    send_text = CanvasNode(
        id="send-text", type="output", label="Text Response",
        content="Send formatted messages to Telegram",
        inputs=["agent"],
    )
    telegram_output_machine = CanvasMachine(
        id="telegram-output", label="Telegram Output",
        nodes=[send_photo, send_text],
    )

    oracle_response = CanvasNode(
        id="oracle-response", type="output", label="Oracle Response",
        content="Write responses to ordinal bus",
        inputs=["ordinal-mcp"],
    )
    oracle_output_machine = CanvasMachine(
        id="oracle-output", label="Oracle Output",
        nodes=[oracle_response],
    )

    output_factory = CanvasFactory(
        id="tooling-and-output", label="Tooling & Output",
        machines=[tools_machine, telegram_output_machine, oracle_output_machine],
        style=ContainerStyle(border_color="#FF9800"),
    )

    # =================================================================
    # Assemble: One network, three factories
    # Cross-factory edges:
    #   ingestion → core-engine  (task-queue → agent)
    #   core-engine → tooling    (agent → canvas-mcp, ordinal-mcp, git, shell)
    # =================================================================
    network = CanvasNetwork(
        id="rhode-system", label="Rhode System",
        factories=[ingestion_factory, core_factory, output_factory],
    )

    canvas = Canvas(
        title="Rhode System Architecture",
        networks=[network],
    )
    canvas.model_post_init(None)
    return canvas


def main():
    canvas = build_rhode_canvas()

    print(f"Nodes: {len(canvas.all_nodes())}")
    print(f"Connections: {len(canvas.all_connections())}")
    print(f"Factories: {sum(len(n.factories) for n in canvas.networks)}")
    print(f"Machines: {sum(len(f.machines) for n in canvas.networks for f in n.factories)}")

    renderer = CanvasRenderer(scale=2.0)
    output_path = "/home/bobbyhiddn/.rhode/canvas/rhode-architecture-hierarchical.png"

    try:
        renderer.render(
            canvas,
            output_path=output_path,
            organize=True,
        )
        print(f"\nRendered to: {output_path}")

        # Print node positions to verify layout
        print("\nNode positions after organize:")
        for node in canvas.all_nodes():
            print(f"  {node.get_label():25s} x={node.x:6.0f}  y={node.y:6.0f}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nFailed: {e}")


if __name__ == "__main__":
    main()
