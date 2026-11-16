from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_run(run, output: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 7))
    for cell in run.decomposition.cells:
        x, y = cell.polygon.exterior.xy
        ax.fill(x, y, alpha=0.12)
        ax.plot(x, y, linewidth=0.8)
        p = cell.polygon.representative_point()
        ax.text(p.x, p.y, f"C{cell.id}", fontsize=11, ha="center")
    for hole in run.region.interiors:
        x, y = hole.xy
        ax.fill(x, y, hatch="///", alpha=0.35)
    for i, state in enumerate(run.solution.states):
        x, y = zip(*state.path)
        ax.plot(x, y, linewidth=1.2, label="Cell service" if i == 0 else None)
        ax.scatter(*state.entry, marker="o", s=18)
        a, b = state.lanes[0]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        ax.annotate("", xy=mid, xytext=a, arrowprops={"arrowstyle": "->", "lw": 1.5})
    for i, path in enumerate(run.model.connectors(run.solution.states)):
        x, y = zip(*path)
        ax.plot(x, y, linestyle="--", linewidth=1.2, label="Transit" if i == 0 else None)
    ax.scatter(*run.model.start, marker="*", s=160, label="Depot", zorder=5)
    m = run.metrics
    ax.set_title(
        f"{run.solution.algorithm} | {m['num_cells']} cells | "
        f"length {m['total_length']:.2f} | coverage {m['coverage_ratio']:.1%}"
    )
    ax.set_xlabel("x (map units)")
    ax.set_ylabel("y (map units)")
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.tight_layout()
    fig.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(fig)
