"""Generate high-resolution PNG and SVG diagrams of the 13-state DFA using q0..q12 notation."""

import os
from pathlib import Path
import matplotlib
os.environ["MPLCONFIGDIR"] = os.path.join(os.environ.get("TEMP", "/tmp"), "matplotlib_cache")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Coordinates layout for states q0 to q12 + q_dead
# Main Happy Path: q0 -> q1 -> q2 -> q4 -> q5 -> q6 -> q7 -> q12
# Payment Retry Loop: q2 <-> q3
# Cancellations & Refunds: q1, q3 -> q8 -> q12
#                          q4, q5 -> q9 -> q10 -> q11 -> q12
#                          q7 -> q10 -> q11 -> q12

coords = {
    "q0": (1.0, 5.0),
    "q1": (3.0, 5.0),
    "q2": (5.0, 5.0),
    "q3": (5.0, 7.2),
    "q4": (7.5, 5.0),
    "q5": (9.8, 5.0),
    "q6": (12.0, 5.0),
    "q7": (14.2, 5.0),
    "q8": (4.0, 2.5),
    "q9": (8.5, 2.5),
    "q10": (11.0, 2.5),
    "q11": (13.5, 2.5),
    "q12": (16.2, 5.0),
}

labels = {
    "q0": "q0\n(Start)",
    "q1": "q1\n(Created)",
    "q2": "q2\n(PayWait)",
    "q3": "q3\n(PayFail)",
    "q4": "q4\n(Paid)",
    "q5": "q5\n(Packed)",
    "q6": "q6\n(Shipped)",
    "q7": "q7\n(Delivered)",
    "q8": "q8\n(CancelUnpaid)",
    "q9": "q9\n(CancelPaid)",
    "q10": "q10\n(RefundWait)",
    "q11": "q11\n(Refunded)",
    "q12": "q12\n(Closed)",
}

fig, ax = plt.subplots(figsize=(19, 9), dpi=300)
ax.set_xlim(-0.2, 17.5)
ax.set_ylim(1.2, 8.5)
ax.axis("off")

# Title and subtitle
plt.title(
    "Formal Deterministic Finite Automaton (DFA) — Online Order & Payment Lifecycle\n"
    "States: Q = {q0, q1, q2, ..., q12} | Alphabet Σ = {OrderCreated, PaymentInitiated, ...} | Final State F = {q12}",
    fontsize=14,
    fontweight="bold",
    pad=20,
    color="#0f172a",
)

# Start arrow pointing to q0
ax.annotate(
    "Start",
    xy=(coords["q0"][0] - 0.45, coords["q0"][1]),
    xytext=(coords["q0"][0] - 1.2, coords["q0"][1]),
    arrowprops=dict(facecolor="#2563eb", edgecolor="#2563eb", width=2, headwidth=8, shrink=0.05),
    fontsize=11,
    fontweight="bold",
    color="#2563eb",
    va="center",
)

# Function to draw arrows
def draw_edge(from_k, to_k, text, rad=0.0, color="#334155", offset=(0, 0), text_rot=0):
    p1 = coords[from_k]
    p2 = coords[to_k]
    arrow = patches.FancyArrowPatch(
        p1,
        p2,
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>",
        mutation_scale=16,
        linewidth=1.8,
        color=color,
        shrinkA=22,
        shrinkB=22,
    )
    ax.add_patch(arrow)
    
    # Calculate midpoint for text
    mx = (p1[0] + p2[0]) / 2 + offset[0]
    my = (p1[1] + p2[1]) / 2 + offset[1]
    if rad != 0:
        my += rad * 0.8
        mx += -rad * 0.3
    
    ax.text(
        mx,
        my,
        text,
        fontsize=8.5,
        fontweight="bold",
        color=color,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#cbd5e1", alpha=0.92),
        rotation=text_rot,
    )

# Transitions:
# Main happy path
draw_edge("q0", "q1", "OrderCreated", rad=0.0, offset=(0, 0.28), color="#1d4ed8")
draw_edge("q1", "q2", "PaymentInitiated", rad=0.0, offset=(0, 0.28), color="#1d4ed8")
draw_edge("q2", "q4", "PaymentAuthorized", rad=0.0, offset=(0, 0.28), color="#1d4ed8")
draw_edge("q4", "q5", "OrderPacked", rad=0.0, offset=(0, 0.28), color="#1d4ed8")
draw_edge("q5", "q6", "OrderShipped", rad=0.0, offset=(0, 0.28), color="#1d4ed8")
draw_edge("q6", "q7", "OrderDelivered", rad=0.0, offset=(0, 0.28), color="#1d4ed8")
draw_edge("q7", "q12", "OrderClosed", rad=0.0, offset=(0, 0.28), color="#16a34a")

# Payment Retry Loop (q2 <-> q3)
draw_edge("q2", "q3", "PaymentFailed", rad=-0.25, offset=(-0.35, 0.0), color="#dc2626")
draw_edge("q3", "q2", "PaymentInitiated (Retry)", rad=-0.25, offset=(0.4, 0.0), color="#ea580c")

# Cancellations to q8 (unpaid)
draw_edge("q1", "q8", "OrderCancelled", rad=0.15, offset=(-0.25, -0.1), color="#64748b")
draw_edge("q3", "q8", "OrderCancelled", rad=-0.15, offset=(0.2, 0.0), color="#64748b")
draw_edge("q8", "q12", "OrderClosed", rad=-0.28, offset=(0.0, -0.25), color="#64748b")

# Cancellations to q9 (paid)
draw_edge("q4", "q9", "OrderCancelled", rad=0.15, offset=(-0.25, 0.0), color="#64748b")
draw_edge("q5", "q9", "OrderCancelled", rad=-0.15, offset=(0.2, 0.0), color="#64748b")

# Refund flow (q9 -> q10 -> q11 -> q12)
draw_edge("q9", "q10", "RefundRequested", rad=0.0, offset=(0, 0.25), color="#9333ea")
draw_edge("q10", "q11", "RefundCompleted", rad=0.0, offset=(0, 0.25), color="#9333ea")
draw_edge("q11", "q12", "OrderClosed", rad=0.18, offset=(0.2, -0.1), color="#16a34a")

# Post-delivery refund (q7 -> q10)
draw_edge("q7", "q10", "RefundRequested", rad=-0.22, offset=(0.2, -0.1), color="#9333ea")

# Draw States (Circles)
for k, (x, y) in coords.items():
    is_accepting = (k == "q12")
    is_start = (k == "q0")
    
    facecolor = "#dcfce7" if is_accepting else ("#dbeafe" if is_start else "#f8fafc")
    edgecolor = "#16a34a" if is_accepting else ("#2563eb" if is_start else "#334155")
    
    # Outer circle
    circle = plt.Circle((x, y), 0.44, facecolor=facecolor, edgecolor=edgecolor, linewidth=2.4, zorder=4)
    ax.add_patch(circle)
    
    # Double ring for accepting state q12
    if is_accepting:
        inner_circle = plt.Circle((x, y), 0.38, facecolor="none", edgecolor=edgecolor, linewidth=1.8, zorder=5)
        ax.add_patch(inner_circle)
        
    ax.text(x, y, labels[k], fontsize=8.5, fontweight="bold", ha="center", va="center", color="#0f172a", zorder=6)

# Output paths
out_dir = Path("D:/5th sem/TOC/TOC-Project-Git/docs/images")
out_dir.mkdir(parents=True, exist_ok=True)
png_path = out_dir / "dfa_13_states.png"
svg_path = out_dir / "dfa_13_states.svg"

plt.tight_layout()
plt.savefig(png_path, dpi=300, bbox_inches="tight")
plt.savefig(svg_path, format="svg", bbox_inches="tight")
plt.close()

print(f"[Success] DFA diagram generated at:\n  - {png_path}\n  - {svg_path}")
