"""Mermaid diagram generator with path and failing edge highlighting.
Provides 100% native client-side rendering inside Streamlit without requiring
any external 'dot' binary or graphviz executable on the operating system.
"""

from __future__ import annotations

import re
from typing import List, Optional
import streamlit as st


def dot_to_mermaid(
    dot_str: str,
    visited_states: Optional[List[str]] = None,
    failing_state: Optional[str] = None,
    failing_event: Optional[str] = None,
    fail_from_state: Optional[str] = None,
) -> str:
    """Convert Graphviz DOT string into a styled Mermaid flowchart string."""
    visited = set(visited_states or [])
    lines: List[str] = ["flowchart LR"]

    # Extract all node definitions
    # e.g., "S0" [shape=circle];
    node_matches = re.findall(r'"?(\w+)"?\s*\[shape=(\w+)\];', dot_str)
    defined_nodes = set()
    for name, shape in node_matches:
        if name in ("__start", "node", "edge"):
            continue
        defined_nodes.add(name)
        if shape == "doublecircle":
            lines.append(f'    {name}((( "{name}" )))')
        else:
            lines.append(f'    {name}(( "{name}" ))')

    # Extract all edge definitions
    # e.g., "S0" -> "S1" [label="OrderCreated"];
    edge_pattern = re.compile(r'"?(\w+)"?\s*->\s*"?(\w+)"?\s*\[label="([^"]+)"\];')
    edge_index = 0
    failing_edge_index = -1
    visited_edge_indices = []

    for match in edge_pattern.finditer(dot_str):
        u, v, lbl = match.group(1), match.group(2), match.group(3)
        if u == "__start":
            continue

        if u not in defined_nodes:
            lines.append(f'    {u}(( "{u}" ))')
            defined_nodes.add(u)
        if v not in defined_nodes:
            lines.append(f'    {v}(( "{v}" ))')
            defined_nodes.add(v)

        lines.append(f'    {u} -->|"{lbl}"| {v}')

        # Check edge status
        if fail_from_state and u == fail_from_state:
            if failing_event and (failing_event in lbl or lbl in failing_event):
                failing_edge_index = edge_index
            elif not failing_event:
                failing_edge_index = edge_index
        elif u in visited and v in visited:
            visited_edge_indices.append(edge_index)

        edge_index += 1

    # Apply styling classes
    # Visited states: blue outline and light blue fill
    for s in visited:
        if s in defined_nodes and s != failing_state:
            lines.append(f"    style {s} fill:#e0f2fe,stroke:#0284c7,stroke-width:3px,color:#0369a1")

    # Failing state: bright red outline and light red fill
    if failing_state and failing_state in defined_nodes:
        lines.append(f"    style {failing_state} fill:#fee2e2,stroke:#dc2626,stroke-width:4px,color:#991b1b")

    # Style traversed edges: blue
    for e_idx in visited_edge_indices:
        lines.append(f"    linkStyle {e_idx} stroke:#0284c7,stroke-width:3px")

    # Style failing edge: bright red and thicker
    if failing_edge_index >= 0:
        lines.append(f"    linkStyle {failing_edge_index} stroke:#dc2626,stroke-width:4px")

    return "\n".join(lines)


def render_automaton(
    dot_text: str,
    title: Optional[str] = None,
    visited_states: Optional[List[str]] = None,
    failing_state: Optional[str] = None,
    failing_event: Optional[str] = None,
    fail_from_state: Optional[str] = None,
) -> None:
    """Render automaton diagram using native Mermaid with interactive styling."""
    if title:
        st.subheader(title)

    if not dot_text:
        st.info("No automaton diagram data available.")
        return

    # Convert DOT to pure Mermaid
    mermaid_code = dot_to_mermaid(
        dot_str=dot_text,
        visited_states=visited_states,
        failing_state=failing_state,
        failing_event=failing_event,
        fail_from_state=fail_from_state,
    )

    try:
        if hasattr(st, "mermaid_chart"):
            st.mermaid_chart(mermaid_code, width="stretch")
        else:
            # Fallback to markdown mermaid block
            st.markdown(f"```mermaid\n{mermaid_code}\n```")
    except Exception as exc:
        st.warning(f"Could not render diagram: {exc}")
        st.code(mermaid_code, language="mermaid")
