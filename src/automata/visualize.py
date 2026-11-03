"""Graphviz DOT export for DFAs with execution path and failing transition highlighting."""

from typing import Dict, List, Optional, Tuple

from src.automata.dfa import DFA


def to_dot(
    dfa: DFA,
    highlight_path: Optional[List[str]] = None,
    fail_edge: Optional[Tuple[str, str, str]] = None,  # (from_state, event, to_state)
    show_dead: bool = False,
    edge_frequencies: Optional[Dict[Tuple[str, str], int]] = None,
) -> str:
    """Generate Graphviz DOT string for a DFA with path highlighting.

    Args:
        dfa: The DFA to visualize.
        highlight_path: Ordered list of visited state IDs (highlighted in bold blue).
        fail_edge: Tuple (from_state, event, to_state) for the invalid transition (highlighted in red).
        show_dead: Whether to include the S_dead state and its incoming edges (default False).
        edge_frequencies: Optional map of ((from_state, to_state), count) to scale edge penwidth.

    Returns:
        Graphviz DOT formatted string.
    """
    lines: List[str] = [
        "digraph WorkflowDFA {",
        '    rankdir="LR";',
        '    node [fontname="Helvetica", fontsize=11];',
        '    edge [fontname="Helvetica", fontsize=10];',
        "",
    ]

    path_states = set(highlight_path) if highlight_path else set()
    path_edges = set()
    if highlight_path and len(highlight_path) > 1:
        for i in range(len(highlight_path) - 1):
            path_edges.add((highlight_path[i], highlight_path[i + 1]))

    # Invisible start node pointing to start_state
    lines.append('    __start [shape=none, label="", width=0, height=0];')
    lines.append(f'    __start -> "{dfa.start_state}";')
    lines.append("")

    # 1. State nodes
    sorted_states = sorted(dfa.states)
    for q in sorted_states:
        if q == dfa.dead_state and not show_dead:
            continue

        label_name = dfa.state_names.get(q, q)
        node_label = f"{q}\\n{label_name}" if label_name != q else q

        shape = "doublecircle" if q in dfa.accepting_states else "circle"
        style = "solid"
        color = "#777777"
        fillcolor = "#ffffff"
        fontcolor = "#000000"
        penwidth = 1.0

        if q in path_states:
            color = "#1f77b4"  # Bold blue
            penwidth = 2.2
            fillcolor = "#e8f1f8"
            style = "filled"

        if fail_edge and q == fail_edge[0]:
            color = "#d62728"  # Red outline for failure origin
            penwidth = 2.5
            fillcolor = "#fde8e8"
            style = "filled"

        lines.append(
            f'    "{q}" [shape={shape}, style="{style}", fillcolor="{fillcolor}", '
            f'color="{color}", fontcolor="{fontcolor}", penwidth={penwidth}, label="{node_label}"];'
        )

    lines.append("")

    # 2. Group transitions between same states to avoid multiple duplicate edges
    grouped_transitions: Dict[Tuple[str, str], List[str]] = {}
    for (src, sym), dst in dfa.delta.items():
        if not show_dead and (src == dfa.dead_state or dst == dfa.dead_state):
            continue
        grouped_transitions.setdefault((src, dst), []).append(sym)

    for (src, dst), symbols in sorted(grouped_transitions.items()):
        label = "\\n".join(sorted(symbols))
        color = "#888888"
        fontcolor = "#444444"
        penwidth = 1.0

        is_path_edge = (src, dst) in path_edges
        if is_path_edge:
            color = "#1f77b4"
            fontcolor = "#1f77b4"
            penwidth = 2.5

        # Edge frequency scaling if available
        if edge_frequencies and (src, dst) in edge_frequencies:
            freq = edge_frequencies[(src, dst)]
            penwidth = max(1.0, min(5.0, 1.0 + freq / 20.0))

        lines.append(
            f'    "{src}" -> "{dst}" [label="{label}", color="{color}", '
            f'fontcolor="{fontcolor}", penwidth={penwidth}];'
        )

    # 3. Failing transition edge (if present)
    if fail_edge:
        f_src, f_sym, f_dst = fail_edge
        target_display = f_dst if (show_dead or f_dst != dfa.dead_state) else "Violation"
        if target_display == "Violation":
            lines.append(
                '    "Violation" [shape=note, color="#d62728", fontcolor="#d62728", label="FAIL"];'
            )
        lines.append(
            f'    "{f_src}" -> "{target_display}" [label="{f_sym}", color="#d62728", '
            f'fontcolor="#d62728", penwidth=3.0, style="dashed"];'
        )

    lines.append("}")
    return "\n".join(lines)
