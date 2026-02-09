"""Canvas renderer using Pillow — produces hierarchical canvas PNG diagrams."""

from __future__ import annotations

import math
import textwrap
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .models import Canvas, CanvasNode, CanvasFactory, CanvasMachine, ContainerStyle, NodeStyle
from .organize import organize_canvas
from .themes import get_theme, ThemePalette


# --- Font handling ---

def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font, falling back to default if none available."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _load_bold_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a bold font, falling back to regular."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for fp in font_paths:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return _load_font(size)


# --- Color helpers ---

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple. Supports both 3-char and 6-char hex."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = hex_color[0]*2 + hex_color[1]*2 + hex_color[2]*2
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """Convert hex color to RGBA tuple."""
    r, g, b = _hex_to_rgb(hex_color)
    return (r, g, b, alpha)


def _darken(hex_color: str, factor: float = 0.6) -> str:
    """Darken a hex color."""
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _lighten(hex_color: str, factor: float = 0.3) -> str:
    """Lighten a hex color by blending toward white.

    factor=0.0 returns the original color, factor=1.0 returns white.
    """
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


# --- Drawing primitives ---

def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float, float, float],
    radius: int,
    fill: Optional[str] = None,
    outline: Optional[str] = None,
    width: int = 1,
):
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(
        [x1, y1, x2, y2],
        radius=radius,
        fill=fill,
        outline=outline,
        width=width,
    )


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str = "#585b70",
    width: int = 2,
    arrow_size: int = 10,
):
    """Draw a line with an arrowhead."""
    draw.line([start, end], fill=color, width=width)

    # Calculate arrowhead
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length == 0:
        return

    # Normalize
    udx = dx / length
    udy = dy / length

    # Arrowhead points
    ax = end[0] - arrow_size * udx + (arrow_size / 2) * udy
    ay = end[1] - arrow_size * udy - (arrow_size / 2) * udx
    bx = end[0] - arrow_size * udx - (arrow_size / 2) * udy
    by = end[1] - arrow_size * udy + (arrow_size / 2) * udx

    draw.polygon([(end[0], end[1]), (ax, ay), (bx, by)], fill=color)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip() if current else word
        bbox = font.getbbox(test)
        tw = bbox[2] - bbox[0]
        if tw <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            # If single word is too long, force-wrap it
            if font.getbbox(word)[2] - font.getbbox(word)[0] > max_width:
                # Character-level wrap
                for chunk in textwrap.wrap(word, width=max(1, max_width // 8)):
                    lines.append(chunk)
                current = ""
            else:
                current = word

    if current:
        lines.append(current)

    return lines if lines else [""]


# --- Main renderer ---

class CanvasRenderer:
    """Renders a Canvas model to a PNG image."""

    # Layout constants
    PADDING = 60
    NODE_PADDING = 24
    LABEL_HEIGHT = 36
    CONTAINER_PADDING = 45
    CONTAINER_LABEL_HEIGHT = 40

    # Node sizing constants
    MIN_NODE_WIDTH = 180
    MIN_NODE_HEIGHT = 80
    MAX_NODE_WIDTH = 600
    NODE_TOP_BAR = 6        # colored indicator bar at top
    NODE_LABEL_GAP = 12     # gap between bar and label
    NODE_CONTENT_GAP = 10   # gap between label and content
    NODE_BOTTOM_PAD = 36    # room for type badge + padding at bottom
    NODE_LINE_HEIGHT = 24   # line height for body text

    def __init__(self, scale: float = 1.0):
        self.scale = scale
        self.font_body = _load_font(int(18 * scale))
        self.font_label = _load_bold_font(int(20 * scale))
        self.font_title = _load_bold_font(int(28 * scale))
        self.font_container = _load_bold_font(int(16 * scale))
        self.font_small = _load_font(int(14 * scale))
        self.theme: ThemePalette = get_theme("dark")  # Default theme

    def compute_node_size(self, node: CanvasNode) -> tuple[float, float]:
        """Measure the required width and height for a node based on its text.

        Returns (width, height) in unscaled canvas coordinates.  The node's
        ``width`` and ``height`` attributes are NOT modified — the caller
        decides whether to apply the computed values.

        Layout breakdown (top to bottom):
            NODE_TOP_BAR          — colored indicator bar
            NODE_LABEL_GAP        — gap below bar
            label text height     — single line, bold font
            NODE_CONTENT_GAP      — gap between label and content
            content text lines    — wrapped body text
            NODE_BOTTOM_PAD       — room for type badge + breathing room
        """
        padding = self.NODE_PADDING
        line_height = self.NODE_LINE_HEIGHT

        # --- Width ---
        # Start from label width
        label = node.get_label()
        label_bbox = self.font_label.getbbox(label)
        label_width = label_bbox[2] - label_bbox[0]

        # Determine available text width: we want at least label_width,
        # but also consider content lines. Use a target width for wrapping:
        # prefer the larger of label width and a comfortable content width.
        # We'll also measure the type badge to make sure it fits.
        type_text = node.type
        type_bbox = self.font_small.getbbox(type_text)
        type_badge_w = type_bbox[2] - type_bbox[0] + 12 + 10  # badge + right margin

        # Content measurement: wrap at a reasonable width and check
        content_width = 0
        content_lines: list[str] = []
        if node.content:
            # First pass: use a generous wrap width to measure natural line widths
            # Then compute actual required width
            max_wrap = self.MAX_NODE_WIDTH - 2 * padding
            content_lines = _wrap_text(node.content, self.font_body, max_wrap)
            for line in content_lines:
                lbbox = self.font_body.getbbox(line)
                lw = lbbox[2] - lbbox[0]
                content_width = max(content_width, lw)

        # Final width: max of label, content, type badge, all + padding
        inner_width = max(label_width, content_width, type_badge_w)
        width = inner_width + 2 * padding
        width = max(width, self.MIN_NODE_WIDTH)
        width = min(width, self.MAX_NODE_WIDTH)

        # --- Height ---
        label_bbox_h = label_bbox[3] - label_bbox[1]
        height = (
            self.NODE_TOP_BAR
            + self.NODE_LABEL_GAP
            + label_bbox_h
            + self.NODE_CONTENT_GAP
        )

        # Re-wrap content at actual available width (may differ from first pass)
        if node.content:
            actual_text_width = width - 2 * padding
            content_lines = _wrap_text(node.content, self.font_body, int(actual_text_width))
            height += len(content_lines) * line_height

        height += self.NODE_BOTTOM_PAD
        height = max(height, self.MIN_NODE_HEIGHT)

        return (float(round(width)), float(round(height)))

    def auto_size_nodes(self, canvas: Canvas) -> None:
        """Measure all nodes and update their width/height to fit their text.

        This should be called BEFORE layout (organize or auto-layout) so the
        layout algorithm uses correct node dimensions for spacing.
        """
        for node in canvas.all_nodes():
            w, h = self.compute_node_size(node)
            node.width = w
            node.height = h

    def render(
        self,
        canvas: Canvas,
        output_path: Optional[str] = None,
        organize: bool = False,
        spacing_level: str = "container",
        orientation: str = "horizontal",
    ) -> bytes:
        """Render the canvas to PNG bytes. Optionally save to file.

        Args:
            canvas: The canvas to render.
            output_path: Optional path to save the PNG.
            organize: If True, apply the hierarchical organize algorithm for
                      automatic layout with breathing room.
            spacing_level: Spacing level for organize ("node", "container", "network").
            orientation: Layout direction — "horizontal" or "vertical" (top→bottom).
        """
        # Set theme from canvas
        self.theme = get_theme(canvas.theme)

        # Auto-size nodes to fit their text content BEFORE layout
        self.auto_size_nodes(canvas)

        # Auto-layout: always use hierarchical organize by default.
        # The simple fallback only applies when organize is explicitly disabled
        # AND all nodes happen to be at (0,0).
        if organize:
            organize_canvas(canvas, spacing_level=spacing_level, orientation=orientation)
        else:
            self._auto_layout_if_needed(canvas)

        # Calculate canvas bounds from node positions
        bounds = self._calculate_bounds(canvas)
        img_width = int(bounds["width"] * self.scale)
        img_height = int(bounds["height"] * self.scale)

        # Create image - use theme background color
        bg_color = self.theme.background
        img = Image.new("RGBA", (img_width, img_height), _hex_to_rgba(bg_color))
        draw = ImageDraw.Draw(img)

        # Offset for translating node coordinates to image space
        ox = -bounds["min_x"] + self.PADDING
        oy = -bounds["min_y"] + self.PADDING

        # Draw title
        self._draw_title(draw, canvas.title, img_width)

        # Draw containers (machines, factories) as subtle grouped backgrounds
        for network in canvas.networks:
            for factory in network.factories:
                self._draw_factory_container(draw, factory, ox, oy)
                for machine in factory.machines:
                    self._draw_machine_container(draw, machine, ox, oy)

        # Draw connections first (behind nodes)
        self._draw_connections(draw, canvas, ox, oy)

        # Draw nodes
        for node in canvas.all_nodes():
            self._draw_node(draw, node, ox, oy)

        # Convert to bytes
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        png_bytes = buf.getvalue()

        if output_path:
            Path(output_path).write_bytes(png_bytes)

        return png_bytes

    def _auto_layout_if_needed(self, canvas: Canvas):
        """If all nodes are at (0,0), auto-layout them."""
        nodes = canvas.all_nodes()
        if not nodes:
            return

        all_zero = all(n.x == 0 and n.y == 0 for n in nodes)
        if not all_zero:
            return

        # Auto-layout: arrange nodes left-to-right within machines,
        # machines top-to-bottom within factories
        x_offset = self.PADDING * 2
        y_offset = self.PADDING * 2 + 50  # Leave room for title

        for network in canvas.networks:
            for factory in network.factories:
                factory_start_y = y_offset
                for machine in factory.machines:
                    x = x_offset
                    for node in machine.nodes:
                        node.x = x
                        node.y = y_offset
                        x += node.width + 120  # horizontal spacing
                    y_offset += 280  # vertical spacing between machines
                y_offset += 80  # extra gap between factories

    def _calculate_bounds(self, canvas: Canvas) -> dict:
        """Calculate the bounding box of all nodes, including container chrome."""
        nodes = canvas.all_nodes()
        if not nodes:
            return {"min_x": 0, "min_y": 0, "width": 400, "height": 300}

        # Account for container chrome (factory/machine backgrounds extend
        # beyond the node bounds by CONTAINER_PADDING + CONTAINER_LABEL_HEIGHT)
        container_margin = self.CONTAINER_PADDING + self.CONTAINER_LABEL_HEIGHT + 20  # factory expand

        min_x = min(n.x for n in nodes) - self.PADDING - container_margin
        min_y = min(n.y for n in nodes) - self.PADDING - container_margin - 50  # Title space
        max_x = max(n.x + n.width for n in nodes) + self.PADDING + container_margin
        max_y = max(n.y + n.height for n in nodes) + self.PADDING + container_margin

        return {
            "min_x": min_x,
            "min_y": min_y,
            "width": max_x - min_x + self.PADDING,
            "height": max_y - min_y + self.PADDING,
        }

    def _draw_title(self, draw: ImageDraw.ImageDraw, title: str, img_width: int):
        """Draw the canvas title centered at the top."""
        bbox = self.font_title.getbbox(title)
        tw = bbox[2] - bbox[0]
        x = (img_width - tw) / 2
        draw.text((x, 15 * self.scale), title, fill=self.theme.title_color, font=self.font_title)

    def _get_container_bounds(self, nodes: list[CanvasNode]) -> tuple[float, float, float, float]:
        """Get bounding box for a set of nodes."""
        if not nodes:
            return (0, 0, 0, 0)
        pad = self.CONTAINER_PADDING
        min_x = min(n.x for n in nodes) - pad
        min_y = min(n.y for n in nodes) - pad - self.CONTAINER_LABEL_HEIGHT
        max_x = max(n.x + n.width for n in nodes) + pad
        max_y = max(n.y + n.height for n in nodes) + pad
        return (min_x, min_y, max_x, max_y)

    def _draw_machine_container(self, draw: ImageDraw.ImageDraw, machine: CanvasMachine, ox: float, oy: float):
        """Draw a subtle container around a machine's nodes."""
        if not machine.nodes:
            return
        x1, y1, x2, y2 = self._get_container_bounds(machine.nodes)
        x1 = (x1 + ox) * self.scale
        y1 = (y1 + oy) * self.scale
        x2 = (x2 + ox) * self.scale
        y2 = (y2 + oy) * self.scale

        # Resolve style — custom overrides per-field, fallback to theme defaults
        s = machine.style
        fill_hex = s.fill_color if s and s.fill_color else self.theme.machine_fill
        fill_alpha = s.alpha if s and s.alpha is not None else self.theme.machine_fill_alpha
        outline_color = s.border_color if s and s.border_color else self.theme.machine_border
        label_color = s.label_color if s and s.label_color else self.theme.machine_label
        radius = s.corner_radius if s and s.corner_radius is not None else 8
        border_w = s.border_width if s and s.border_width is not None else 1

        _draw_rounded_rect(
            draw, (x1, y1, x2, y2),
            radius=radius,
            fill=_hex_to_rgba(fill_hex, fill_alpha),
            outline=outline_color,
            width=border_w,
        )

        # Machine label (uses get_label() for consistent fallback)
        draw.text(
            (x1 + 14, y1 + 8),
            machine.get_label(),
            fill=label_color,
            font=self.font_container,
        )

    def _draw_factory_container(self, draw: ImageDraw.ImageDraw, factory: CanvasFactory, ox: float, oy: float):
        """Draw a container around a factory's machines."""
        all_nodes = []
        for machine in factory.machines:
            all_nodes.extend(machine.nodes)
        if not all_nodes:
            return

        x1, y1, x2, y2 = self._get_container_bounds(all_nodes)
        # Expand a bit beyond machine containers
        expand = 20
        x1 = (x1 - expand + ox) * self.scale
        y1 = (y1 - expand + oy) * self.scale - self.CONTAINER_LABEL_HEIGHT
        x2 = (x2 + expand + ox) * self.scale
        y2 = (y2 + expand + oy) * self.scale

        # Resolve style — custom overrides per-field, fallback to theme defaults
        s = factory.style
        outline_color = s.border_color if s and s.border_color else self.theme.factory_border
        label_color = s.label_color if s and s.label_color else self.theme.factory_label
        radius = s.corner_radius if s and s.corner_radius is not None else 12
        border_w = s.border_width if s and s.border_width is not None else 1

        # Factory fill: default is transparent (no fill), but honor custom if set
        fill = None
        if s and s.fill_color:
            fill_alpha = s.alpha if s.alpha is not None else 80
            fill = _hex_to_rgba(s.fill_color, fill_alpha)

        _draw_rounded_rect(
            draw, (x1, y1, x2, y2),
            radius=radius,
            fill=fill,
            outline=outline_color,
            width=border_w,
        )

        # Factory label (uses get_label() for consistent fallback)
        draw.text(
            (x1 + 16, y1 + 8),
            factory.get_label(),
            fill=label_color,
            font=self.font_container,
        )

    def _determine_port(
        self, source: CanvasNode, target: CanvasNode
    ) -> tuple[str, str]:
        """Determine connection ports based on relative node positions.

        Uses the spatial relationship between nodes to decide whether
        connections should use side ports (horizontal flow) or top/bottom
        ports (vertical flow).  The "horizon" threshold is based on the
        vertical offset relative to the source node's height — if the
        target center is more than 1.5× the source height away vertically
        and the vertical distance dominates the horizontal distance, we
        switch to vertical connectors.

        Returns (from_port, to_port) where port is one of:
            'output'  → right edge center
            'input'   → left edge center
            'bottom'  → bottom edge center
            'top'     → top edge center
        """
        # Centers of each node
        src_cx = source.x + source.width / 2
        src_cy = source.y + source.height / 2
        tgt_cx = target.x + target.width / 2
        tgt_cy = target.y + target.height / 2

        dx = tgt_cx - src_cx
        dy = tgt_cy - src_cy

        # Horizon threshold: if vertical distance is dominant and significant
        # we switch to vertical connectors. "Significant" = more than 1.5×
        # the source node height AND the vertical component is larger than
        # the horizontal component.
        horizon = source.height * 1.5

        if abs(dy) > horizon and abs(dy) > abs(dx):
            if dy > 0:
                # Target is below source
                return ("bottom", "top")
            else:
                # Target is above source
                return ("top", "bottom")

        # Default: horizontal flow (left-to-right or right-to-left)
        if dx >= 0:
            return ("output", "input")
        else:
            return ("input", "output")

    def _get_port_coordinates(
        self, node: CanvasNode, port: str, ox: float, oy: float
    ) -> tuple[float, float]:
        """Get the anchor point coordinates for a given port on a node.

        Port coordinate mapping:
            input   → left edge, vertical center
            output  → right edge, vertical center
            top     → top edge, horizontal center
            bottom  → bottom edge, horizontal center
        """
        if port == "input":
            x = (node.x + ox) * self.scale
            y = (node.y + node.height / 2 + oy) * self.scale
        elif port == "output":
            x = (node.x + node.width + ox) * self.scale
            y = (node.y + node.height / 2 + oy) * self.scale
        elif port == "top":
            x = (node.x + node.width / 2 + ox) * self.scale
            y = (node.y + oy) * self.scale
        elif port == "bottom":
            x = (node.x + node.width / 2 + ox) * self.scale
            y = (node.y + node.height + oy) * self.scale
        else:
            # Fallback to output
            x = (node.x + node.width + ox) * self.scale
            y = (node.y + node.height / 2 + oy) * self.scale
        return (x, y)

    def _draw_connections(self, draw: ImageDraw.ImageDraw, canvas: Canvas, ox: float, oy: float):
        """Draw all connections between nodes.

        Port selection is emergent from node geometry — if a target node
        sits below a certain horizon from its source, the connection
        automatically switches from side ports (horizontal tree) to
        top/bottom ports (vertical tree).
        """
        for source_id, target_id in canvas.all_connections():
            source = canvas.get_node(source_id)
            target = canvas.get_node(target_id)
            if not source or not target:
                continue

            # Determine ports based on relative position (the key feature)
            from_port, to_port = self._determine_port(source, target)

            # Get anchor coordinates from the chosen ports
            sx, sy = self._get_port_coordinates(source, from_port, ox, oy)
            tx, ty = self._get_port_coordinates(target, to_port, ox, oy)

            # Connection direction for bezier control points
            is_vertical = from_port in ("top", "bottom")

            # Determine connection color based on source type
            # Lighten the source color so connectors are clearly visible
            # against the dark (#11111b) canvas background.
            style = source.get_style()
            conn_color = _lighten(style.border_color, 0.25)

            # Draw bezier-like connection using line segments
            self._draw_bezier_connection(
                draw, (sx, sy), (tx, ty), conn_color, direction="vertical" if is_vertical else "horizontal"
            )

    def _draw_bezier_connection(
        self,
        draw: ImageDraw.ImageDraw,
        start: tuple[float, float],
        end: tuple[float, float],
        color: str,
        width: int = 4,
        direction: str = "horizontal",
    ):
        """Draw a smooth bezier-like connection between two points.

        Supports both horizontal and vertical flow directions:
          - horizontal: control points extend left/right (S-curve)
          - vertical:   control points extend up/down (S-curve)
        """
        sx, sy = start
        ex, ey = end

        if direction == "vertical":
            # Vertical S-curve: control points extend up/down
            dy = abs(ey - sy)
            cp_offset = max(dy * 0.4, 40 * self.scale)

            # CP1 extends downward from start (if going down) or upward
            cp1x = sx
            cp1y = sy + (cp_offset if ey > sy else -cp_offset)
            # CP2 extends upward toward end (if going down) or downward
            cp2x = ex
            cp2y = ey - (cp_offset if ey > sy else -cp_offset)
        else:
            # Horizontal S-curve: control points extend left/right
            dx = abs(ex - sx)
            cp_offset = max(dx * 0.4, 40 * self.scale)

            cp1x = sx + (cp_offset if ex > sx else -cp_offset)
            cp1y = sy
            cp2x = ex - (cp_offset if ex > sx else -cp_offset)
            cp2y = ey

        # Generate bezier points
        points = []
        steps = 30
        for i in range(steps + 1):
            t = i / steps
            # Cubic bezier
            x = (1-t)**3 * sx + 3*(1-t)**2*t * cp1x + 3*(1-t)*t**2 * cp2x + t**3 * ex
            y = (1-t)**3 * sy + 3*(1-t)**2*t * cp1y + 3*(1-t)*t**2 * cp2y + t**3 * ey
            points.append((x, y))

        # Draw the curve
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=color, width=width)

        # Arrowhead at end
        if len(points) >= 2:
            _draw_arrow(draw, points[-2], points[-1], color=color, width=width, arrow_size=int(18 * self.scale))

    def _draw_node(self, draw: ImageDraw.ImageDraw, node: CanvasNode, ox: float, oy: float):
        """Draw a single node.

        Text positioning uses the same constants as ``compute_node_size``
        so auto-sized nodes always have room for their content.
        """
        style = node.get_style()

        x = (node.x + ox) * self.scale
        y = (node.y + oy) * self.scale
        w = node.width * self.scale
        h = node.height * self.scale

        s = self.scale  # shorthand

        # Use theme-aware fill color (custom style overrides theme)
        fill_color = style.fill_color if node.style and node.style.fill_color else self.theme.node_fill

        # Node background
        _draw_rounded_rect(
            draw, (x, y, x + w, y + h),
            radius=int(style.corner_radius * s),
            fill=fill_color,
            outline=style.border_color,
            width=int(style.border_width * s),
        )

        # Node type indicator bar at top
        bar_height = int(self.NODE_TOP_BAR * s)
        _draw_rounded_rect(
            draw,
            (x + 2, y + 2, x + w - 2, y + bar_height + 2),
            radius=int(style.corner_radius * s),
            fill=style.border_color,
        )

        # Label — positioned consistently with compute_node_size
        # Use theme-aware label color
        label = node.get_label()
        label_y = y + bar_height + int(self.NODE_LABEL_GAP * s)
        label_color = style.label_color if node.style and node.style.label_color else self.theme.node_label
        draw.text(
            (x + int(self.NODE_PADDING * s), label_y),
            label,
            fill=label_color,
            font=self.font_label,
        )

        # Content text (wrapped) — positioned consistently with compute_node_size
        label_bbox = self.font_label.getbbox(label)
        label_text_h = label_bbox[3] - label_bbox[1]
        content_y = label_y + label_text_h + int(self.NODE_CONTENT_GAP * s)
        max_text_width = int(w - 2 * self.NODE_PADDING * s)
        line_height = int(self.NODE_LINE_HEIGHT * s)

        if node.content:
            lines = _wrap_text(node.content, self.font_body, max_text_width)
            # With auto-sizing, all lines should fit. But add a safety limit
            # in case the node was manually sized smaller.
            available_h = h - (content_y - y) - int(self.NODE_BOTTOM_PAD * s)
            max_lines = max(1, int(available_h / line_height)) if available_h > 0 else 1
            display_lines = lines[:max_lines]
            if len(lines) > max_lines:
                display_lines[-1] = display_lines[-1][:20] + "..."

            for i, line in enumerate(display_lines):
                draw.text(
                    (x + int(self.NODE_PADDING * s), content_y + i * line_height),
                    line,
                    fill=self.theme.body_text_color,
                    font=self.font_body,
                )

        # Type badge in bottom-right
        type_text = node.type
        type_bbox = self.font_small.getbbox(type_text)
        type_w = type_bbox[2] - type_bbox[0] + 12
        type_h = type_bbox[3] - type_bbox[1] + 6
        type_x = x + w - type_w - int(10 * s)
        type_y = y + h - type_h - int(10 * s)

        _draw_rounded_rect(
            draw, (type_x, type_y, type_x + type_w, type_y + type_h),
            radius=4,
            fill=_darken(style.border_color, 0.3),
        )
        draw.text(
            (type_x + 6, type_y + 2),
            type_text,
            fill=style.border_color,
            font=self.font_small,
        )
