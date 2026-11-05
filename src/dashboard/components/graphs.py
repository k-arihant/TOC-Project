"""Graphviz diagram generator and execution path highlighter."""

from __future__ import annotations

import re
from typing import List, Optional

import streamlit as st


def highlight_dot_diagram(
    base_dot: str,
    visited_states: Optional[List[str]] = None,
    failing_state: Optional[str] = None,
    failing_event: Optional[str] = None,
    fail_from_state: Optional[str] = None,
) -> str:
    """Enhance Graphviz DOT text with bold blue visited paths and bold red failing edges.

    Adheres strictly to Doc 09 §2:
      - Visited states/edges: bold blue (#1f77b4, penwidth=2.5).
      - Failing transition: red edge (#d62728, penwidth=3.0), offending state outlined in red.
      - Unvisited states/edges: subtle grey.
    """
    if not base_dot:
        return ""

    visited = set(visited_states or [])
    dot_lines = base_dot.strip().splitlines()
    highlighted_lines = []

    # Insert global styling if not present
    for line in dot_lines:
        trimmed = line.strip()
        if trimmed.startswith("digraph") and "{" in trimmed:
            highlighted_lines.append(line)
            highlighted_lines.append('  graph [rankdir=LR, bgcolor="transparent", fontname="Helvetica"];')
            highlighted_lines.append('  node [fontname="Helvetica", fontsize=11];')
            highlighted_lines.append('  edge [fontname="Helvetica", fontsize=10];')
            continue

        # Check edge definition: "S0" -> "S1" [label="..."]
        edge_match = re.search(r'^\s*"?(\w+)"?\s*->\s*"?(\w+)"?\s*(\[.*\])?', trimmed)
        if edge_match:
            u, v, attrs = edge_match.group(1), edge_match.group(2), edge_match.group(3) or "[]"
            # Is this the failing transition?
            is_failing_edge = False
            if fail_from_state and u == fail_from_state:
                if failing_event and failing_event in attrs:
                    is_failing_edge = True
                elif not failing_event:
                    is_failing_edge = True

            if is_failing_edge:
                new_attrs = (
                    attrs.rstrip("]")
                    + ', color="#d62728", fontcolor="#d62728", penwidth=3.2, style="bold", weight=5]'
                )
                highlighted_lines.append(f'  "{u}" -> "{v}" {new_attrs}')
            elif u in visited and v in visited:
                new_attrs = (
                    attrs.rstrip("]")
                    + ', color="#1f77b4", fontcolor="#1f77b4", penwidth=2.5, style="bold", weight=3]'
                )
                highlighted_lines.append(f'  "{u}" -> "{v}" {new_attrs}')
            else:
                new_attrs = (
                    attrs.rstrip("]")
                    + ', color="#cccccc", fontcolor="#888888", penwidth=1.0]'
                )
                highlighted_lines.append(f'  "{u}" -> "{v}" {new_attrs}')
            continue

        # Check state node styling: "S0" [label="..."]
        node_match = re.search(r'^\s*"?(\w+)"?\s*(\[.*\])', trimmed)
        if node_match:
            s_name, attrs = node_match.group(1), node_match.group(2)
            if s_name == failing_state:
                new_attrs = (
                    attrs.rstrip("]")
                    + ', color="#d62728", style="filled,bold", fillcolor="#ffebee", fontcolor="#b71c1c", penwidth=3.0]'
                )
                highlighted_lines.append(f'  "{s_name}" {new_attrs}')
            elif s_name in visited:
                new_attrs = (
                    attrs.rstrip("]")
                    + ', color="#1f77b4", style="filled,bold", fillcolor="#e3f2fd", fontcolor="#0d47a1", penwidth=2.2]'
                )
                highlighted_lines.append(f'  "{s_name}" {new_attrs}')
            else:
                new_attrs = (
                    attrs.rstrip("]")
                    + ', color="#b0bec5", style="filled", fillcolor="#f5f5f5", fontcolor="#546e7a"]'
                )
                highlighted_lines.append(f'  "{s_name}" {new_attrs}')
            continue

        highlighted_lines.append(line)

    return "\n".join(highlighted_lines)


def render_automaton(
    dot_text: str,
    title: Optional[str] = None,
    visited_states: Optional[List[str]] = None,
    failing_state: Optional[str] = None,
    failing_event: Optional[str] = None,
    fail_from_state: Optional[str] = None,
) -> None:
    """Render a Graphviz automaton chart with automatic path highlighting and fallback."""
    if title:
        st.subheader(title)

    styled_dot = highlight_dot_diagram(
        dot_text,
        visited_states=visited_states,
        failing_state=failing_state,
        failing_event=failing_event,
        fail_from_state=fail_from_state,
    )

    try:
        st.graphviz_chart(styled_dot, use_container_width=True)
    except Exception as exc:
        st.warning(
            "Graphviz rendering engine could not display the graph image directly. "
            "Displaying raw DOT source code below:"
        )
        st.code(styled_dot, language="dot")
        st.caption(f"Engine detail: {exc}")
