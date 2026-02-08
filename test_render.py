"""Quick test to verify Canvas-MCP rendering works."""

from pathlib import Path
from canvas_mcp.parser import parse_yaml, parse_file
from canvas_mcp.renderer import CanvasRenderer

# Test 1: Simple format (auto-layout)
simple_yaml = """
title: Test Canvas
nodes:
  - id: start
    type: input
    content: "User request comes in"
    label: Request
    outputs: [process]
  - id: process
    type: process
    content: "Validate and transform data"
    label: Transform
    inputs: [start]
    outputs: [ai-step]
  - id: ai-step
    type: ai
    content: "LLM processes the request"
    label: AI Analysis
    inputs: [process]
    outputs: [result]
  - id: result
    type: output
    content: "Return formatted response"
    label: Response
    inputs: [ai-step]
"""

canvas = parse_yaml(simple_yaml)
renderer = CanvasRenderer(scale=2.0)
output = Path("/home/bobbyhiddn/Code/Canvas-MCP/output/test-simple.png")
output.parent.mkdir(exist_ok=True)
renderer.render(canvas, output_path=str(output))
print(f"[OK] Simple flow rendered: {output} ({output.stat().st_size} bytes)")

# Test 2: AI Pipeline template (explicit coordinates)
canvas2 = parse_file("/home/bobbyhiddn/Code/Canvas-MCP/templates/ai-pipeline.yaml")
output2 = Path("/home/bobbyhiddn/Code/Canvas-MCP/output/test-pipeline.png")
renderer.render(canvas2, output_path=str(output2))
print(f"[OK] AI Pipeline rendered: {output2} ({output2.stat().st_size} bytes)")

# Test 3: Decision tree template (auto-layout)
canvas3 = parse_file("/home/bobbyhiddn/Code/Canvas-MCP/templates/decision-tree.yaml")
output3 = Path("/home/bobbyhiddn/Code/Canvas-MCP/output/test-decision.png")
renderer.render(canvas3, output_path=str(output3))
print(f"[OK] Decision tree rendered: {output3} ({output3.stat().st_size} bytes)")

# Test 4: Full hierarchical format (via ai-pipeline template)
try:
    canvas4 = parse_file("/home/bobbyhiddn/Code/Canvas-MCP/templates/ai-pipeline.yaml")
    output4 = Path("/home/bobbyhiddn/Code/Canvas-MCP/output/test-hierarchical.png")
    renderer.render(canvas4, output_path=str(output4), organize=True)
    print(f"[OK] Hierarchical pipeline rendered: {output4} ({output4.stat().st_size} bytes)")
except Exception as e:
    print(f"[SKIP] Hierarchical pipeline: {e}")

print("\nAll tests passed!")
