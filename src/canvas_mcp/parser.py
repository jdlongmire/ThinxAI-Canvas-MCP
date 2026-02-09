"""YAML recipe parser for Canvas-MCP.

Supports two formats:
1. Hierarchical full canvas YAML (with networks/factories/machines)
2. Simplified recipe format (flat list of nodes + connections)
"""

from __future__ import annotations
from pathlib import Path

import yaml

from .models import (
    Canvas,
    CanvasFactory,
    CanvasMachine,
    CanvasNetwork,
    CanvasNode,
    ContainerStyle,
    NodeStyle,
)


def parse_yaml(yaml_str: str) -> Canvas:
    """Parse a YAML string into a Canvas model."""
    data = yaml.safe_load(yaml_str)
    if not data:
        raise ValueError("Empty YAML input")

    # Check if it's a hierarchical-format canvas
    if "canvas" in data:
        return _parse_hierarchical_format(data["canvas"])

    # Otherwise, treat as simplified format
    return _parse_simple_format(data)


def parse_file(path: str) -> Canvas:
    """Parse a YAML file into a Canvas model."""
    content = Path(path).read_text()
    return parse_yaml(content)


def _parse_hierarchical_format(data: dict) -> Canvas:
    """Parse the hierarchical canvas YAML format (networks/factories/machines/nodes)."""
    canvas = Canvas(
        version=data.get("version", "2.0"),
        title=data.get("title", "Untitled Canvas"),
        theme=data.get("theme", "dark"),
    )

    for net_data in data.get("networks", []):
        network = CanvasNetwork(
            id=net_data.get("id", "network-1"),
            label=net_data.get("label"),
            description=net_data.get("description"),
        )

        for fac_data in net_data.get("factories", []):
            fac_style = None
            if "style" in fac_data:
                fac_style = ContainerStyle(**fac_data["style"])
            factory = CanvasFactory(
                id=fac_data.get("id", "factory-1"),
                label=fac_data.get("label"),
                description=fac_data.get("description"),
                style=fac_style,
            )

            for mach_data in fac_data.get("machines", []):
                mach_style = None
                if "style" in mach_data:
                    mach_style = ContainerStyle(**mach_data["style"])
                machine = CanvasMachine(
                    id=mach_data.get("id", "machine-1"),
                    label=mach_data.get("label"),
                    description=mach_data.get("description"),
                    style=mach_style,
                )

                for node_data in mach_data.get("nodes", []):
                    node = _parse_node(node_data)
                    machine.nodes.append(node)

                factory.machines.append(machine)
            network.factories.append(factory)
        canvas.networks.append(network)

    canvas.model_post_init(None)
    return canvas


def _parse_simple_format(data: dict) -> Canvas:
    """Parse simplified recipe format.

    Example:
        title: My Diagram
        nodes:
          - id: start
            type: input
            content: "Begin here"
          - id: process
            type: process
            content: "Do something"
            inputs: [start]
          - id: end
            type: output
            content: "Result"
            inputs: [process]
    """
    canvas = Canvas(
        title=data.get("title", "Untitled Canvas"),
        background_color=data.get("background", "#11111b"),
        theme=data.get("theme", "dark"),
    )

    # Build nodes
    nodes = []
    for node_data in data.get("nodes", []):
        node = _parse_node(node_data)
        nodes.append(node)

    # Group into a single machine in a single factory in a single network
    machine = CanvasMachine(id="machine-1", nodes=nodes)
    factory = CanvasFactory(id="factory-1", machines=[machine])
    network = CanvasNetwork(id="network-1", factories=[factory])
    canvas.networks = [network]

    canvas.model_post_init(None)
    return canvas


def _parse_node(data: dict) -> CanvasNode:
    """Parse a single node from YAML data."""
    style = None
    if "style" in data:
        style = NodeStyle(**data["style"])

    return CanvasNode(
        id=data["id"],
        type=data.get("type", "default"),
        content=data.get("content", ""),
        label=data.get("label"),
        x=float(data.get("x", 0)),
        y=float(data.get("y", 0)),
        width=float(data.get("width", 250)),
        height=float(data.get("height", 120)),
        inputs=data.get("inputs", []),
        outputs=data.get("outputs", []),
        style=style,
    )


def canvas_to_yaml(canvas: Canvas) -> str:
    """Serialize a Canvas model back to YAML."""
    data = {
        "canvas": {
            "version": canvas.version,
            "title": canvas.title,
            "theme": canvas.theme,
            "networks": [],
        }
    }

    for network in canvas.networks:
        net_data = {"id": network.id, "factories": []}
        if network.label:
            net_data["label"] = network.label
        if network.description:
            net_data["description"] = network.description

        for factory in network.factories:
            fac_data = {"id": factory.id, "machines": []}
            if factory.label:
                fac_data["label"] = factory.label
            if factory.description:
                fac_data["description"] = factory.description
            if factory.style:
                fac_style_dict = {
                    k: v for k, v in factory.style.model_dump().items()
                    if v is not None
                }
                if fac_style_dict:
                    fac_data["style"] = fac_style_dict

            for machine in factory.machines:
                mach_data = {"id": machine.id, "nodes": []}
                if machine.label:
                    mach_data["label"] = machine.label
                if machine.description:
                    mach_data["description"] = machine.description
                if machine.style:
                    mach_style_dict = {
                        k: v for k, v in machine.style.model_dump().items()
                        if v is not None
                    }
                    if mach_style_dict:
                        mach_data["style"] = mach_style_dict

                for node in machine.nodes:
                    node_data = {
                        "id": node.id,
                        "type": node.type,
                        "x": node.x,
                        "y": node.y,
                        "content": node.content,
                    }
                    if node.label:
                        node_data["label"] = node.label
                    if node.inputs:
                        node_data["inputs"] = node.inputs
                    if node.outputs:
                        node_data["outputs"] = node.outputs
                    if node.width != 250:
                        node_data["width"] = node.width
                    if node.height != 120:
                        node_data["height"] = node.height

                    mach_data["nodes"].append(node_data)
                fac_data["machines"].append(mach_data)
            net_data["factories"].append(fac_data)
        data["canvas"]["networks"].append(net_data)

    return yaml.dump(data, default_flow_style=False, sort_keys=False)
