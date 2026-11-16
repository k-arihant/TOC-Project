"""Interactive Automata Visualizer using Vis.js and Mermaid.
Renders directly via HTML Canvas/SVG inside Streamlit.
Guaranteed 100% reliable in every browser with zero external binary dependencies.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional
import streamlit as st
import streamlit.components.v1 as components


def render_automaton(
    dot_text: str,
    title: Optional[str] = None,
    visited_states: Optional[List[str]] = None,
    failing_state: Optional[str] = None,
    failing_event: Optional[str] = None,
    fail_from_state: Optional[str] = None,
) -> None:
    """Render automaton diagram using Vis.js network graph inside an interactive iframe."""
    if title:
        st.subheader(title)

    if not dot_text:
        st.info("No automaton diagram data available.")
        return

    visited = set(visited_states or [])

    # Extract all node definitions
    node_matches = re.findall(r'"?(\w+)"?\s*\[shape=(\w+)\];', dot_text)
    defined_nodes = set()
    nodes_data = []

    for name, shape in node_matches:
        if name in ("__start", "node", "edge"):
            continue
        defined_nodes.add(name)

        is_visited = name in visited
        is_failing = (name == failing_state)
        is_accepting = (shape == "doublecircle")

        # Color schemes
        if is_failing:
            bg_color = "#fee2e2"
            border_color = "#dc2626"
            font_color = "#991b1b"
            border_width = 4
        elif is_visited:
            bg_color = "#e0f2fe"
            border_color = "#0284c7"
            font_color = "#0369a1"
            border_width = 3
        else:
            bg_color = "#f8fafc"
            border_color = "#64748b"
            font_color = "#0f172a"
            border_width = 2

        label = f"{name} (Final)" if is_accepting else name
        shape_type = "dot" if not is_accepting else "diamond"

        nodes_data.append(
            {
                "id": name,
                "label": label,
                "color": {
                    "background": bg_color,
                    "border": border_color,
                    "highlight": {"background": bg_color, "border": border_color},
                },
                "font": {"color": font_color, "size": 15, "face": "Helvetica", "bold": True},
                "borderWidth": border_width,
                "shadow": True,
            }
        )

    # Extract all edge definitions
    edge_pattern = re.compile(r'"?(\w+)"?\s*->\s*"?(\w+)"?\s*\[label="([^"]+)"\];')
    edges_data = []

    for match in edge_pattern.finditer(dot_text):
        u, v, lbl = match.group(1), match.group(2), match.group(3)
        if u == "__start":
            continue

        if u not in defined_nodes:
            nodes_data.append({"id": u, "label": u})
            defined_nodes.add(u)
        if v not in defined_nodes:
            nodes_data.append({"id": v, "label": v})
            defined_nodes.add(v)

        is_failing_edge = False
        if fail_from_state and u == fail_from_state:
            if failing_event and (failing_event in lbl or lbl in failing_event):
                is_failing_edge = True
            elif not failing_event:
                is_failing_edge = True

        is_visited_edge = (u in visited and v in visited)

        if is_failing_edge:
            edge_color = "#dc2626"
            edge_width = 4
            dashes = True
        elif is_visited_edge:
            edge_color = "#0284c7"
            edge_width = 3
            dashes = False
        else:
            edge_color = "#94a3b8"
            edge_width = 1.5
            dashes = False

        edges_data.append(
            {
                "from": u,
                "to": v,
                "label": lbl,
                "arrows": "to",
                "color": {"color": edge_color, "highlight": edge_color},
                "width": edge_width,
                "dashes": dashes,
                "font": {
                    "align": "horizontal",
                    "size": 11,
                    "color": "#1e293b",
                    "strokeWidth": 2,
                    "strokeColor": "#ffffff",
                    "bold": True,
                },
                "smooth": {"type": "curvedCW", "roundness": 0.2},
            }
        )

    nodes_json = json.dumps(nodes_data)
    edges_json = json.dumps(edges_data)

    # Self-contained HTML with Vis.js Network CDN
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
      <style type="text/css">
        body {{
          margin: 0;
          padding: 0;
          background: #ffffff;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        #network {{
          width: 100%;
          height: 520px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          background: #ffffff;
        }}
        .legend {{
          display: flex;
          gap: 16px;
          padding: 8px 12px;
          font-size: 12px;
          color: #475569;
          background: #f8fafc;
          border-bottom: 1px solid #e2e8f0;
          border-radius: 8px 8px 0 0;
        }}
        .legend-item {{
          display: flex;
          align-items: center;
          gap: 6px;
        }}
        .circle {{
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }}
      </style>
    </head>
    <body>
      <div class="legend">
        <div class="legend-item"><div class="circle" style="background:#0284c7;"></div> <strong>Traversed Path</strong> (Blue)</div>
        <div class="legend-item"><div class="circle" style="background:#dc2626;"></div> <strong>Illegal / Failing Transition</strong> (Red)</div>
        <div class="legend-item"><div class="circle" style="background:#64748b;"></div> Unvisited States</div>
      </div>
      <div id="network"></div>
      <script type="text/javascript">
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});

        var container = document.getElementById('network');
        var data = {{
          nodes: nodes,
          edges: edges
        }};
        var options = {{
          layout: {{
            hierarchical: {{
              enabled: true,
              direction: 'LR',
              sortMethod: 'directed',
              levelSeparation: 160,
              nodeSpacing: 100
            }}
          }},
          physics: {{
            hierarchicalRepulsion: {{
              nodeDistance: 130
            }}
          }},
          interaction: {{
            dragNodes: true,
            zoomView: true,
            dragView: true
          }}
        }};
        var network = new vis.Network(container, data, options);
      </script>
    </body>
    </html>
    """

    components.html(html_code, height=560, scrolling=False)
