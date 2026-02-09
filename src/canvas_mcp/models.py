"""
Data models for Canvas-MCP — the canvas ontology.

The Canvas ontology is a four-level hierarchy that models visual computation
as nested containers of increasing specificity:

    Canvas
    └── Network    — a system boundary (the broadest scope)
        └── Factory    — a functional domain (groups related pipelines)
            └── Machine    — a pipeline (a connected chain of operations)
                └── Node       — a single operation (the atomic unit)

Each level has an ``id`` (unique identifier) and an optional ``label``
(human-readable display name).  When no label is provided, the id is used
for rendering.  Every level also exposes a ``get_label()`` method so
rendering code never has to handle the fallback itself.

This module also defines the **node type system** — eight semantic types
that control color-coding and carry domain meaning:

    input    — user-provided data entering the system
    output   — final results leaving the system
    process  — a transformation or computation step
    decision — a branching / conditional gate
    ai       — an AI/LLM processing step
    source   — an external data source (API, database, file)
    static   — immutable seed content or constants
    default  — generic / unspecified
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

class NodeStyle(BaseModel):
    """Visual styling for a node.

    Attributes:
        border_color: The accent color drawn as the top bar and outline.
        fill_color:   Interior background of the node.
        text_color:   Color for the content body text.
        label_color:  Override color for the label text (defaults to text_color).
        icon:         Reserved for future icon support.
        corner_radius: Border radius in pixels.
        border_width:  Width of the node border in pixels (before scaling).
    """
    border_color: str = "#999999"
    fill_color: str = "#1e1e2e"
    text_color: str = "#cdd6f4"
    label_color: Optional[str] = None
    icon: str = ""
    corner_radius: int = 12
    border_width: int = 3


class ContainerStyle(BaseModel):
    """Visual styling for a machine or factory container.

    Machines and factories are drawn as subtle background containers
    around their child elements.  This style controls their appearance.

    Attributes:
        border_color: Outline color for the container rectangle.
        fill_color:   Background fill color (use with alpha for transparency).
        label_color:  Color for the container's label text.
        alpha:        Opacity for the fill (0=transparent, 255=opaque).
                      Only applies to fill_color.  Default varies by level:
                      machines default to 120, factories default to 0.
        corner_radius: Border radius in pixels.
        border_width:  Width of the container border in pixels.
    """
    border_color: Optional[str] = None
    fill_color: Optional[str] = None
    label_color: Optional[str] = None
    alpha: Optional[int] = None
    corner_radius: Optional[int] = None
    border_width: Optional[int] = None


# Default styles per node type (Catppuccin Mocha palette)
NODE_STYLES: dict[str, NodeStyle] = {
    "input":    NodeStyle(border_color="#2196F3"),  # Blue
    "output":   NodeStyle(border_color="#FFC107"),  # Amber
    "process":  NodeStyle(border_color="#00BCD4"),  # Cyan
    "decision": NodeStyle(border_color="#F44336"),  # Red
    "ai":       NodeStyle(border_color="#9C27B0"),  # Purple
    "source":   NodeStyle(border_color="#FF9800"),  # Orange
    "static":   NodeStyle(border_color="#4CAF50"),  # Green
    "default":  NodeStyle(border_color="#999999"),    # Gray
}


# ---------------------------------------------------------------------------
# Node (Level 4 — the atomic unit)
# ---------------------------------------------------------------------------

class CanvasNode(BaseModel):
    """A node — the atomic unit of the canvas ontology.

    Nodes are the leaves of the hierarchy.  Each node represents a single
    operation, data source, decision point, or output within a machine.

    Labeling
    --------
    Every node has an ``id`` (must be globally unique across the canvas)
    and an optional ``label``.  The ``get_label()`` method returns the label
    if set, otherwise falls back to the id.  This keeps YAML recipes concise
    — you only need to specify a label when you want a human-friendly name
    that differs from the id.

    Connections
    -----------
    ``inputs`` and ``outputs`` are lists of *other node ids*.  Connections
    are bidirectionally deduped at the Canvas level; specifying a connection
    on either end is sufficient, though declaring both is harmless.

    Type System
    -----------
    The ``type`` field selects from the eight semantic types defined in
    ``NODE_STYLES``.  Type determines the accent color and carries domain
    meaning (see module docstring).

    Custom Styling
    --------------
    Set ``style`` to override the default palette for this node.  Any
    field left unset inherits from the type's default style.
    """
    id: str
    type: str = "default"
    content: str = ""
    label: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    width: float = 360.0
    height: float = 180.0
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    style: Optional[NodeStyle] = None

    def get_style(self) -> NodeStyle:
        """Get the effective style for this node.

        Returns the custom style if set, otherwise the default for the
        node's type.
        """
        if self.style:
            return self.style
        return NODE_STYLES.get(self.type, NODE_STYLES["default"])

    def get_label(self) -> str:
        """Get the display label for this node.

        Returns ``label`` if explicitly set, otherwise returns ``id``.
        """
        return self.label if self.label else self.id


# ---------------------------------------------------------------------------
# Machine (Level 3 — a pipeline)
# ---------------------------------------------------------------------------

class CanvasMachine(BaseModel):
    """A machine — a pipeline of connected nodes.

    Machines group nodes that form a connected processing chain.  In the
    rendered diagram, a machine is drawn as a subtle container background
    with a label in the top-left corner.

    Labeling
    --------
    Like nodes, machines have an ``id`` and optional ``label``.
    ``get_label()`` returns the label if set, otherwise the id.

    In the simplified YAML format, machines are auto-detected from node
    connectivity — each connected component of nodes becomes a machine.
    In the full hierarchical format, machines are declared explicitly.

    Visual Appearance
    -----------------
    Rendered as a rounded rectangle with defaults:
    - Fill: ``#181825`` at 120 alpha (semi-transparent)
    - Border: ``#313244`` at 1px
    - Label: ``#6c7086`` (muted), bold 12pt, top-left corner

    Custom colors can be set via the ``style`` field using ``ContainerStyle``.
    """
    id: str
    label: Optional[str] = None
    description: Optional[str] = None
    nodes: list[CanvasNode] = Field(default_factory=list)
    style: Optional[ContainerStyle] = None

    def get_label(self) -> str:
        """Get the display label for this machine.

        Returns ``label`` if explicitly set, otherwise returns ``id``.
        """
        return self.label if self.label else self.id


# ---------------------------------------------------------------------------
# Factory (Level 2 — a functional domain)
# ---------------------------------------------------------------------------

class CanvasFactory(BaseModel):
    """A factory — a functional domain grouping related machines.

    Factories represent a higher level of organization.  A factory might
    be "Data Ingestion", "Analysis", or "Output Generation" — a coherent
    functional domain that contains one or more pipelines (machines).

    Labeling
    --------
    Same pattern: ``id`` + optional ``label``, with ``get_label()``
    providing the fallback.

    Visual Appearance
    -----------------
    Rendered as an outline container (no fill by default) with defaults:
    - Border: ``#45475a`` at 1px
    - Label: ``#a6adc8`` (lighter than machine labels), bold 12pt
    - Corner radius: 12px
    - Expanded 15px beyond its contained machine containers

    Custom colors can be set via the ``style`` field using ``ContainerStyle``.
    """
    id: str
    label: Optional[str] = None
    description: Optional[str] = None
    machines: list[CanvasMachine] = Field(default_factory=list)
    style: Optional[ContainerStyle] = None

    def get_label(self) -> str:
        """Get the display label for this factory.

        Returns ``label`` if explicitly set, otherwise returns ``id``.
        """
        return self.label if self.label else self.id


# ---------------------------------------------------------------------------
# Network (Level 1 — a system boundary)
# ---------------------------------------------------------------------------

class CanvasNetwork(BaseModel):
    """A network — a system-level boundary containing factories.

    Networks are the broadest organizational unit.  A complex system might
    have multiple networks representing separate subsystems, services, or
    deployment boundaries.

    Labeling
    --------
    Same pattern: ``id`` + optional ``label``, with ``get_label()``
    providing the fallback.

    Rendering
    ---------
    Networks are not currently rendered as visible containers (they are
    transparent groupings), but their label is available for future use
    in multi-network diagrams.
    """
    id: str
    label: Optional[str] = None
    description: Optional[str] = None
    factories: list[CanvasFactory] = Field(default_factory=list)

    def get_label(self) -> str:
        """Get the display label for this network.

        Returns ``label`` if explicitly set, otherwise returns ``id``.
        """
        return self.label if self.label else self.id


# ---------------------------------------------------------------------------
# Canvas (Root — the diagram itself)
# ---------------------------------------------------------------------------

class Canvas(BaseModel):
    """The root canvas model — a complete diagram.

    The Canvas is the top-level container.  It holds global settings
    (title, dimensions, background color) and a list of networks.

    For simple diagrams, there's typically one network > one factory >
    one or more machines > nodes.  The simplified YAML format creates
    this structure automatically.

    Theme Support
    -------------
    Set ``theme`` to "dark" (default) or "light" to switch color palettes.
    The theme affects all colors: background, text, containers, and nodes.

    Flat Access
    -----------
    The canvas maintains a ``_node_map`` for O(1) node lookup by id.
    Use ``get_node(id)`` for single lookups, ``all_nodes()`` for iteration,
    and ``all_connections()`` for the deduplicated edge list.
    """
    version: str = "2.0"
    title: str = "Untitled Canvas"
    width: int = 1920
    height: int = 1080
    background_color: str = "#11111b"
    theme: str = "dark"  # "dark" or "light"
    networks: list[CanvasNetwork] = Field(default_factory=list)

    # Flat access helpers
    _node_map: dict[str, CanvasNode] = {}

    def model_post_init(self, __context):
        """Build lookup maps after initialization."""
        self._node_map = {}
        for network in self.networks:
            for factory in network.factories:
                for machine in factory.machines:
                    for node in machine.nodes:
                        self._node_map[node.id] = node

    def get_node(self, node_id: str) -> Optional[CanvasNode]:
        """Look up a node by its globally unique id."""
        return self._node_map.get(node_id)

    def all_nodes(self) -> list[CanvasNode]:
        """Return a flat list of every node in the canvas."""
        nodes = []
        for network in self.networks:
            for factory in network.factories:
                for machine in factory.machines:
                    nodes.extend(machine.nodes)
        return nodes

    def all_connections(self) -> list[tuple[str, str]]:
        """Return all (source_id, target_id) connections, deduplicated.

        Connections are declared on nodes via ``inputs`` and ``outputs``.
        This method collects them all and removes duplicates (since a
        connection declared as an output on node A and an input on node B
        is the same edge).
        """
        connections = []
        for node in self.all_nodes():
            for input_id in node.inputs:
                connections.append((input_id, node.id))
            for output_id in node.outputs:
                connections.append((node.id, output_id))
        # Deduplicate
        return list(set(connections))
