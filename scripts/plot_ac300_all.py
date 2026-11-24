"""Plot matched-map distributions and median trends from the AC300 run CSVs."""
import base64
import csv
from zipfile import ZIP_DEFLATED, ZipFile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "results/ac300_all"
LABELS = {"tsp-greedy": "Greedy TSP", "tsp-2opt": "TSP + 2-opt", "gtsp": "GTSP",
          "aco": "ACO", "gtsp-exact": "Exact GTSP"}
COLORS = ["#B88112", "#4477AA", "#008579", "#C45132", "#785CA1"]
METRICS = {
    "total_length": "Route length (m)", "planning_seconds": "Planning time (s)",
    "vertex_turn_count": "Heading changes (>1°)", "coverage_percent": "Coverage (%)",
    "overlap_excess_percent": "Overlap excess (%)", "transit_length": "Transit distance (m)",
}
PRIMARY = list(METRICS)[:3]


def write_csv(name, rows):
    with (OUT/name).open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_distributions(cohort, data, maps, algorithms, summary):
    if not maps:
        return
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), layout="constrained")
    for ax, metric in zip(axes, PRIMARY):
        for y, (algo, color) in enumerate(zip(algorithms, COLORS)):
            values = sorted(float(data[m, algo][metric]) for m in maps)
            lo, mid, hi = np.percentile(values, [25, 50, 75])
            ax.plot([lo, hi], [y, y], lw=4, color=color, solid_capstyle="round")
            ax.scatter(mid, y, s=70, color=color, zorder=3, edgecolor="white")
            ax.annotate(f"{mid:,.2f}" if metric == "planning_seconds" else f"{mid:,.1f}",
                        (mid, y), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)
        ax.set(yticks=range(len(algorithms)), yticklabels=[LABELS[a] for a in algorithms],
               ylim=(len(algorithms)-0.5, -0.65), xlabel=METRICS[metric])
        if metric == "planning_seconds":
            ax.set_xscale("log")
        ax.grid(axis="x", alpha=.2)
        ax.spines[["top","right"]].set_visible(False)
    fig.suptitle(f"{len(maps)} matched maps   |   Median and interquartile range", fontsize=15)
    fig.savefig(OUT/f"{cohort}.png", dpi=175)
    plt.close(fig)
    for a in algorithms:
        entry = dict(cohort=cohort, algorithm=a, maps=len(maps))
        for key in METRICS:
            vals = [float(data[m, a][key]) for m in maps]
            for q, v in zip(("q25","median","q75"), np.percentile(vals, [25,50,75])):
                entry[f"{key}_{q}"] = v
        summary.append(entry)


def save_report(summary, counts, processed):
    parts = ["""<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AC300 planner comparison</title><style>
body{font:16px/1.5 system-ui;color:#233142;max-width:1100px;margin:40px auto;padding:0 18px}
img{width:100%;height:auto}table{border-collapse:collapse;width:100%}th,td{text-align:right;padding:.4em;border-bottom:1px solid #ddd}
th:first-child,td:first-child{text-align:left}.scroll{overflow-x:auto}h1,h2{line-height:1.2}
</style><main><h1>AC300 planner comparison</h1>""",
        f"<p>Completed {processed} of 300 maps. Each map has one attempt per planner with seed 0. "
        "The dots show medians across matched maps. Each horizontal bar spans the middle 50%.</p>"]

    def table(headers, rows):
        parts.append("<div class='scroll'><table><thead><tr>" +
                     "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead><tbody>")
        for row in rows:
            parts.append("<tr>" + "".join(f"<td>{x}</td>" for x in row) + "</tr>")
        parts.append("</tbody></table></div>")

    def image(name, caption):
        encoded = base64.b64encode((OUT/name).read_bytes()).decode("ascii")
        parts.append(f'<img src="data:image/png;base64,{encoded}" alt="{caption}">')

    for cohort, title in (("heuristics","Four heuristic planners"), ("exact_subset","Exact-solver comparison")):
        records = [r for r in summary if r["cohort"] == cohort]
        if not records:
            continue
        parts.append(f"<h2>{title}</h2><p>{records[0]['maps']} maps completed by every planner in this table.</p>")
        table(["Planner", "Median length (m)", "Median planning time (s)", "Median turns"],
              [[LABELS[r["algorithm"]], f"{r['total_length_median']:,.2f}",
                f"{r['planning_seconds_median']:,.3f}", f"{r['vertex_turn_count_median']:,.1f}"]
               for r in records])
        image(cohort+".png", title+" medians and interquartile ranges")
    parts.append("<h2>Effect of obstacle count</h2>")
    image("by_holes.png","Median route length, planning time, heading changes, coverage, overlap and transit distance by number of holes")
    parts.append("<h2>Run outcomes</h2>")
    table(["Planner","Attempted","Successful","Eight-cell limit","Other failures"],
          [[LABELS[r["algorithm"]],r["attempted"],r["successful"],r["exact_cell_limit"],r["other_failures"]] for r in counts])
    parts.append("<h2>Experiment settings</h2><p>Every planner uses the same map-specific depot, "
                 "a closed route, 3 m swath and spacing, 90° decomposition, candidate sweep angles of 90° and 0°, "
                 "and zero turn penalty. GTSP uses two restarts. ACO uses 12 ants and 20 iterations. "
                 "A turn is a heading change exceeding one degree. Planning time includes preprocessing and solving, "
                 "and excludes evaluation and plotting. Up to six maps run concurrently. "
                 "The single seed measures variation across maps only. Exact GTSP optimizes the discretized candidate states "
                 "and accepts at most eight cells.</p></main></html>")
    (OUT/"report.html").write_text("".join(parts), encoding="utf8")
    if processed == 300 and (OUT/"runs.csv").exists():
        files = ["runs.csv","completion.csv","median_metrics.csv","by_holes.csv","report.html",
                 "heuristics.png","by_holes.png"]
        if any(r["cohort"] == "exact_subset" for r in summary):
            files.append("exact_subset.png")
        with ZipFile(OUT/"ac300_results.zip.tmp","w",ZIP_DEFLATED) as bundle:
            for name in files:
                bundle.write(OUT/name,name)
        (OUT/"ac300_results.zip.tmp").replace(OUT/"ac300_results.zip")


def main():
    rows = []
    for path in sorted((OUT/"maps").glob("*.csv")):
        with path.open(newline="", encoding="utf8") as f:
            rows.extend(csv.DictReader(f))
    maps = {r["map"] for r in rows}
    data = {(r["map"],r["algorithm"]): r for r in rows if r["status"] == "ok"}
    heuristics = list(LABELS)[:-1]
    paired = sorted(m for m in maps if all((m,a) in data for a in heuristics))
    exact = [m for m in paired if (m,"gtsp-exact") in data]
    summary = []
    plot_distributions("heuristics", data, paired, heuristics, summary)
    plot_distributions("exact_subset", data, exact, list(LABELS), summary)
    if summary:
        write_csv("median_metrics.csv", summary)
    counts = []
    for a in LABELS:
        subset = [r for r in rows if r["algorithm"] == a]
        limits = sum("Exact GTSP is limited to" in r["error"] for r in subset)
        ok = sum(r["status"] == "ok" for r in subset)
        counts.append(dict(algorithm=a,attempted=len(subset),successful=ok,
                           exact_cell_limit=limits,other_failures=len(subset)-ok-limits))
    write_csv("completion.csv", counts)
    if not paired:
        return
    groups = {}
    for m in paired:
        groups.setdefault(int(data[m,heuristics[0]]["holes"]), []).append(m)
    fig, axes = plt.subplots(2,3,figsize=(13,7),layout="constrained")
    trends = []
    for ax,(key,label) in zip(axes.flat,METRICS.items()):
        for a,color in zip(heuristics,COLORS):
            xs = sorted(groups)
            vals = []
            for h in xs:
                values = [float(data[m,a][key]) for m in groups[h]]
                v = float(np.median(values))
                vals.append(v)
                trends.append(dict(holes=h, maps=len(values), algorithm=a,metric=key,median=v))
            ax.plot(xs, vals, color=color, marker=".", label=LABELS[a])
        ax.set(xlabel="Number of holes",ylabel=label,xticks=range(1,16,2))
        if key == "planning_seconds":
            ax.set_yscale("log")
        ax.grid(alpha=.2)
        ax.spines[["top","right"]].set_visible(False)
    axes[0,0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Median performance by obstacle count   |   {len(paired)} matched maps")
    fig.savefig(OUT/"by_holes.png",dpi=175)
    plt.close(fig)
    write_csv("by_holes.csv", trends)
    save_report(summary, counts, len(maps))
    print(f"{len(maps)}/300 maps, {len(paired)} matched heuristics, {len(exact)} matched all five.")


if __name__ == "__main__":
    main()
