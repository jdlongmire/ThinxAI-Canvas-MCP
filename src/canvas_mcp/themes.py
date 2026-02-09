"""
Theme definitions for Canvas-MCP.

Provides dark and light color palettes for rendering diagrams.
Each theme defines colors for:
- Canvas background
- Text (title, labels, body)
- Containers (machine and factory backgrounds/borders)
- Node styles per type
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class ThemePalette:
    """Color palette for a theme."""

    # Canvas
    background: str

    # Text
    title_color: str
    label_color: str
    body_text_color: str
    muted_text_color: str

    # Machine containers
    machine_fill: str
    machine_fill_alpha: int
    machine_border: str
    machine_label: str

    # Factory containers
    factory_border: str
    factory_label: str

    # Node colors
    node_fill: str
    node_text: str
    node_label: str

    # Connection color (base - will be adjusted per source type)
    connection_base: str


# Catppuccin Mocha (dark theme) - current default
DARK_THEME = ThemePalette(
    background="#11111b",
    title_color="#cdd6f4",
    label_color="#cdd6f4",
    body_text_color="#a6adc8",
    muted_text_color="#6c7086",
    machine_fill="#181825",
    machine_fill_alpha=120,
    machine_border="#313244",
    machine_label="#6c7086",
    factory_border="#45475a",
    factory_label="#a6adc8",
    node_fill="#1e1e2e",
    node_text="#cdd6f4",
    node_label="#cdd6f4",
    connection_base="#585b70",
)


# Light theme - clean white background with darker accents
LIGHT_THEME = ThemePalette(
    background="#ffffff",
    title_color="#1e1e2e",
    label_color="#1e1e2e",
    body_text_color="#4c4f69",
    muted_text_color="#6c6f85",
    machine_fill="#e6e9ef",
    machine_fill_alpha=180,
    machine_border="#bcc0cc",
    machine_label="#5c5f77",
    factory_border="#9ca0b0",
    factory_label="#4c4f69",
    node_fill="#eff1f5",
    node_text="#1e1e2e",
    node_label="#1e1e2e",
    connection_base="#8c8fa1",
)


# Theme registry
THEMES: dict[str, ThemePalette] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
}


def get_theme(name: str) -> ThemePalette:
    """Get a theme palette by name.

    Args:
        name: Theme name ("dark" or "light")

    Returns:
        ThemePalette for the requested theme

    Raises:
        ValueError: If theme name is not recognized
    """
    if name not in THEMES:
        valid = ", ".join(THEMES.keys())
        raise ValueError(f"Unknown theme '{name}'. Valid themes: {valid}")
    return THEMES[name]
