"""Dynamic Matplotlib/SVG Automaton Graph Generator with live path & failure coloring.
Renders directly as high-resolution SVG/PNG via st.image().
100% immune to browser sandboxing, missing system dot binaries, or CDN failures.
"""

from __future__ import annotations

import io
import os
from typing import List, Optional

os.environ["MPLCONFIGDIR"] = os.path.join(os.environ.get("TEMP", "/tmp"), "matplotlib_cache")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import streamlit as st


COORDS = {
    "S0": (1.0, 5.0),
    "S1": (3.0, 5.0),
    "S2": (5.0, 5.0),
    "S3": (5.0, 7.2),
    "S4": (7.5, 5.0),
    "S5": (9.8, 5.0),
    "S6": (12.0, 5.0),
    "S7": (14.2, 5.0),
    "S8": (4.0, 2.5),
    "S9": (8.5, 2.5),
    "S10": (11.0, 2.5),
    "S11": (13.5, 2.5),
    "S12": (16.2, 5.0),
}

LABELS = {
    "S0": "S0\n(Start)",
    "S1": "S1\n(Created)",
    "S2": "S2\n(PayWait)",
    "S3": "S3\n(PayFail)",
    "S4": "S4\n(Paid)",
    "S5": "S5\n(Packed)",
    "S6": "S6\n(Shipped)",
    "S7": "S7\n(Delivered)",
    "S8": "S8\n(CancelUnpaid)",
    "S9": "S9\n(CancelPaid)",
    "S10": "S10\n(RefundWait)",
    "S11": "S11\n(Refunded)",
    "S12": "S12\n(Closed)",
}

EDGES = [
    # (from, to, label, rad, (dx, dy))
    ("S0", "S1", "OrderCreated", 0.0, (0, 0.28)),
    ("S1", "S2", "PaymentInitiated", 0.0, (0, 0.28)),
    ("S2", "S4", "PaymentAuthorized", 0.0, (0, 0.28)),
    ("S4", "S5", "OrderPacked", 0.0, (0, 0.28)),
    ("S5", "S6", "OrderShipped", 0.0, (0, 0.28)),
    ("S6", "S7", "OrderDelivered", 0.0, (0, 0.28)),
    ("S7", "S12", "OrderClosed", 0.0, (0, 0.28)),
    ("S2", "S3", "PaymentFailed", -0.25, (-0.35, 0.0)),
    ("S3", "S2", "PaymentInitiated (Retry)", -0.25, (0.4, 0.0)),
    ("S1", "S8", "OrderCancelled", 0.15, (-0.25, -0.1)),
    ("S3", "S8", "OrderCancelled", -0.15, (0.2, 0.0)),
    ("S8", "S12", "OrderClosed", -0.28, (0.0, -0.25)),
    ("S4", "S9", "OrderCancelled", 0.15, (-0.25, 0.0)),
    ("S5", "S9", "OrderCancelled", -0.15, (0.2, 0.0)),
    ("S9", "S10", "RefundRequested", 0.0, (0, 0.25)),
    ("S10", "S11", "RefundCompleted", 0.0, (0, 0.25)),
    ("S11", "S12", "OrderClosed", 0.18, (0.2, -0.1)),
    ("S7", "S10", "RefundRequested", -0.22, (0.2, -0.1)),
]


def generate_automaton_image(
    visited_states: Optional[List[str]] = None,
    failing_state: Optional[str] = None,
    failing_event: Optional[str] = None,
    fail_from_state: Optional[str] = None,
) -> bytes:
    """Generate high-resolution PNG bytes with active execution traversal and failing edge highlights."""
    visited = set(visited_states or [])

    # Map visited edges: (from_st, to_st)
    visited_edges = set()
    if visited_states and len(visited_states) > 1:
        for i in range(len(visited_states) - 1):
            visited_edges.add((visited_states[i], visited_states[i + 1]))

    fig, ax = plt.subplots(figsize=(19, 9), dpi=150)
    ax.set_xlim(-0.2, 17.5)
    ax.set_ylim(1.2, 8.5)
    ax.axis("off")

    # Start indicator arrow
    ax.annotate(
        "Start",
        xy=(COORDS["S0"][0] - 0.45, COORDS["S0"][1]),
        xytext=(COORDS["S0"][0] - 1.2, COORDS["S0"][1]),
        arrowprops=dict(facecolor="#2563eb", edgecolor="#2563eb", width=2, headwidth=8, shrink=0.05),
        fontsize=11,
        fontweight="bold",
        color="#2563eb",
        va="center",
    )

    # Draw regular edges
    for u, v, lbl, rad, offset in EDGES:
        if u not in COORDS or v not in COORDS:
            continue

        p1, p2 = COORDS[u], COORDS[v]
        is_visited_edge = (u, v) in visited_edges

        # Base colors
        if is_visited_edge:
            edge_color = "#0284c7"
            penwidth = 3.0
            zord = 3
        else:
            edge_color = "#cbd5e1"
            penwidth = 1.6
            zord = 1

        arrow = patches.FancyArrowPatch(
            p1,
            p2,
            connectionstyle=f"arc3,rad={rad}",
            arrowstyle="-|>",
            mutation_scale=16 if not is_visited_edge else 20,
            linewidth=penwidth,
            color=edge_color,
            shrinkA=22,
            shrinkB=22,
            zorder=zord,
        )
        ax.add_patch(arrow)

        # Label position
        mx = (p1[0] + p2[0]) / 2 + offset[0]
        my = (p1[1] + p2[1]) / 2 + offset[1]
        if rad != 0:
            my += rad * 0.8
            mx += -rad * 0.3

        text_color = "#0369a1" if is_visited_edge else "#475569"
        bbox_bg = "#f0f9ff" if is_visited_edge else "#ffffff"
        bbox_edge = "#0284c7" if is_visited_edge else "#e2e8f0"

        ax.text(
            mx,
            my,
            lbl,
            fontsize=8.5,
            fontweight="bold" if is_visited_edge else "normal",
            color=text_color,
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.25", facecolor=bbox_bg, edgecolor=bbox_edge, alpha=0.95),
            zorder=zord + 1,
        )

    # If there is a failing transition from a state, draw a prominent RED violation arrow
    if fail_from_state and fail_from_state in COORDS:
        fx, fy = COORDS[fail_from_state]
        # Target an offset violation badge
        tx, ty = fx + 1.2, fy + 1.4
        fail_arrow = patches.FancyArrowPatch(
            (fx, fy),
            (tx, ty),
            connectionstyle="arc3,rad=0.1",
            arrowstyle="-|>",
            mutation_scale=22,
            linewidth=3.5,
            color="#dc2626",
            linestyle="--",
            shrinkA=22,
            shrinkB=15,
            zorder=8,
        )
        ax.add_patch(fail_arrow)
        fail_lbl = f"FAIL: {failing_event}" if failing_event else "ILLEGAL TRANSITION"
        ax.text(
            tx,
            ty,
            fail_lbl,
            fontsize=9.5,
            fontweight="bold",
            color="#ffffff",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#dc2626", edgecolor="#991b1b"),
            zorder=9,
        )

    # Draw states (Nodes)
    for sid, (x, y) in COORDS.items():
        is_accepting = (sid == "S12")
        is_start = (sid == "S0")
        is_visited = (sid in visited)
        is_fail = (sid == failing_state)

        if is_fail:
            facecolor = "#fee2e2"
            edgecolor = "#dc2626"
            font_color = "#991b1b"
            penwidth = 3.6
        elif is_visited:
            facecolor = "#e0f2fe"
            edgecolor = "#0284c7"
            font_color = "#0369a1"
            penwidth = 3.2
        elif is_accepting:
            facecolor = "#dcfce7"
            edgecolor = "#16a34a"
            font_color = "#166534"
            penwidth = 2.4
        else:
            facecolor = "#f8fafc"
            edgecolor = "#94a3b8"
            font_color = "#334155"
            penwidth = 2.0

        circle = plt.Circle((x, y), 0.44, facecolor=facecolor, edgecolor=edgecolor, linewidth=penwidth, zorder=5)
        ax.add_patch(circle)

        # Double ring for accepting state S12
        if is_accepting:
            inner_circle = plt.Circle((x, y), 0.38, facecolor="none", edgecolor=edgecolor, linewidth=1.8, zorder=6)
            ax.add_patch(inner_circle)

        ax.text(x, y, LABELS.get(sid, sid), fontsize=8.5, fontweight="bold", ha="center", va="center", color=font_color, zorder=7)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def render_automaton(
    dot_text: str = "",
    title: Optional[str] = None,
    visited_states: Optional[List[str]] = None,
    failing_state: Optional[str] = None,
    failing_event: Optional[str] = None,
    fail_from_state: Optional[str] = None,
) -> None:
    """Render automaton diagram directly using high-res PNG streaming."""
    if title:
        st.subheader(title)

    img_bytes = generate_automaton_image(
        visited_states=visited_states,
        failing_state=failing_state,
        failing_event=failing_event,
        fail_from_state=fail_from_state,
    )

    caption = "Automaton State Machine — Traversed Blue Path | Red Illegal Edge" if visited_states else "Complete 13-State Workflow Automaton Architecture"
    st.image(img_bytes, caption=caption, width="stretch")
