#!/usr/bin/env python3
"""Create a static and optional interactive report from coverage-benchmark CSV.

Dependencies: matplotlib (required), plotly (optional for HTML).
Example:
    python plot_benchmark.py results/synthetic_smoke.csv --out results/figures

Each map/algorithm is aggregated to the median across successful seeds. Original
run-level CSV is kept unchanged. Failed runs are displayed as an explicit count.
"""
from __future__ import annotations

import argparse
import csv
import html
import math
from collections import defaultdict
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

COLORS = {
    "gtsp": "#02A696",
    "tsp-2opt": "#4E76E8",
    "tsp-greedy": "#F1AD4C",
    "gtsp-exact": "#8A63D2",
}
LABELS = {
    "gtsp": "GTSP (direction-aware)",
    "tsp-2opt": "TSP + 2-opt",
    "tsp-greedy": "Greedy TSP",
    "gtsp-exact": "Exact GTSP",
}
NAVY = "#142A41"
MUTED = "#6A7988"
BG = "#F3F6FA"
GRID = "#E6ECF3"


def read_results(source: Path):
    with source.open(encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))
    if not data:
        raise ValueError(f"No benchmark rows found in {source}")
    return data


def numerical(row, key):
    try:
        x = float(row.get(key, ""))
        return x if math.isfinite(x) else float("nan")
    except (ValueError, TypeError):
        return float("nan")


def summarize(rows):
    ok = [r for r in rows if r.get("status", "ok").lower() == "ok"]
    grouped = defaultdict(list)
    for row in ok:
        grouped[(row["map"], row["algorithm"])].append(row)
    if not grouped:
        raise ValueError("No successful benchmark runs to plot")
    fields = [
        "total_length", "service_length", "transit_length", "coverage_percent",
        "overlap_excess_percent", "planning_seconds", "solver_seconds",
        "vertex_turn_count", "lane_reversal_count", "holes", "num_cells",
    ]
    stats = {}
    for key, subset in grouped.items():
        record = {"map": key[0], "algorithm": key[1], "runs": len(subset)}
        for field in fields:
            values = [numerical(row, field) for row in subset]
            values = [v for v in values if math.isfinite(v)]
            record[field] = median(values) if values else float("nan")
        stats[key] = record
    maps = sorted(set(map_name for map_name, _ in grouped), key=lambda m: (
        min((numerical(r, "holes") for r in ok if r["map"] == m), default=0), m))
    algorithms = sorted(set(algo for _, algo in grouped), key=lambda a: (
        ["tsp-greedy", "tsp-2opt", "gtsp", "gtsp-exact"].index(a)
        if a in ["tsp-greedy", "tsp-2opt", "gtsp", "gtsp-exact"] else 99, a))
    return stats, maps, algorithms, ok


def value(stats, name, algorithm, field):
    return stats.get((name, algorithm), {}).get(field, float("nan"))


def format_percent(x, digits=1):
    return "—" if not math.isfinite(x) else f"{x:.{digits}f}%"


def improvement(stats, maps, baseline="tsp-greedy", optimized="gtsp"):
    data = {}
    for name in maps:
        a = value(stats, name, baseline, "total_length")
        b = value(stats, name, optimized, "total_length")
        if math.isfinite(a) and math.isfinite(b) and a > 0:
            data[name] = (a - b) / a * 100
    return data


def style_axis(ax):
    ax.set_facecolor("white")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="both", colors=MUTED, length=0, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.9)
    ax.set_axisbelow(True)
    ax.title.set_color(NAVY)
    ax.title.set_fontsize(13)
    ax.title.set_fontweight("bold")


def figure_overview(source, out, rows, stats, maps, algorithms, ok):
    plt.rcParams.update({"font.family": "DejaVu Sans", "savefig.facecolor": BG})
    fig = plt.figure(figsize=(17, 13.6), facecolor=BG)
    gs = fig.add_gridspec(3, 2, left=0.055, right=0.965, top=0.690,
                          bottom=0.075, hspace=0.42, wspace=0.23,
                          height_ratios=[1.18, 1, 0.75])
    fig.text(0.055, 0.954, "BENCHMARK / COVERAGE PLANNING", fontsize=12, color=COLORS["gtsp"], weight="bold")
    fig.text(0.055, 0.913, "BCD + GTSP  |  Performance overview", fontsize=25, color=NAVY, weight="bold")
    failures = len(rows) - len(ok)
    seeds = len(set(r.get("seed", "") for r in rows))
    fig.text(0.055, 0.874, f"{len(maps)} polygon maps  ·  {len(algorithms)} algorithms  ·  {seeds} seed(s)  ·  {len(ok)}/{len(rows)} successful runs", fontsize=12, color=MUTED)
    gains = improvement(stats, maps)
    median_gain = median(gains.values()) if gains else float("nan")
    wins = sum(v > 1e-8 for v in gains.values())
    cov_values = [numerical(r, "coverage_percent") for r in ok]
    cov_values = [v for v in cov_values if math.isfinite(v)]
    cov_min = min(cov_values) if cov_values else float("nan")
    gtsp_times = [value(stats, m, "gtsp", "planning_seconds") for m in maps]
    gtsp_times = [v for v in gtsp_times if math.isfinite(v)]
    median_gtsp_sec = median(gtsp_times) if gtsp_times else float("nan")
    cards = [
        ("MEDIAN DISTANCE SAVED", format_percent(median_gain, 2), "GTSP vs greedy, paired maps"),
        ("MAPS IMPROVED", f"{wins} / {len(gains)}" if gains else "—", "GTSP route shorter than greedy"),
        ("MINIMUM COVERAGE", format_percent(cov_min, 1), "Across successful benchmark runs"),
        ("MEDIAN GTSP RUNTIME", f"{median_gtsp_sec:.3f}s" if gtsp_times else "—", "Preprocessing + solver"),
    ]
    left = 0.055
    width = 0.212
    for i, (label, number, description) in enumerate(cards):
        x = left + i * 0.232
        rect = FancyBboxPatch((x, 0.752), width, 0.095, boxstyle="round,pad=0.007,rounding_size=0.008",
                              transform=fig.transFigure, facecolor="white", edgecolor="#DFE7F0", linewidth=0.85)
        fig.add_artist(rect)
        fig.text(x+0.012, 0.823, label, fontsize=9.2, color=MUTED, weight="bold")
        fig.text(x+0.012, 0.782, number, fontsize=22, color=NAVY, weight="bold")
        fig.text(x+0.012, 0.759, description, fontsize=8.3, color=MUTED)

    ax = fig.add_subplot(gs[0, 0]); style_axis(ax)
    positions = np.arange(len(maps))
    group_w = 0.78
    bw = group_w / len(algorithms)
    for i, algo in enumerate(algorithms):
        vals = [value(stats, m, algo, "total_length") / 1000 for m in maps]
        ax.bar(positions - group_w/2 + bw*(i+0.5), vals, width=bw*0.91,
               color=COLORS.get(algo,"#7F91A4"), label=LABELS.get(algo,algo))
    ax.set_title("01  Total route length  ·  lower is better", loc="left", pad=15)
    ax.set_xticks(positions, [m.replace("synthetic_", "S") for m in maps], rotation=0)
    ax.set_ylabel("Distance (km)", color=MUTED, fontsize=10)
    ax.legend(loc="upper left", frameon=False, ncols=3, fontsize=8.5)
    ax.set_ylim(bottom=0)

    ax = fig.add_subplot(gs[0, 1]); style_axis(ax)
    if gains:
        ranked = sorted(gains, key=lambda m: gains[m])
        ys = np.arange(len(ranked))
        colors = [COLORS["gtsp"] if gains[m] > 0 else "#99A7B7" if gains[m] == 0 else "#E27F73" for m in ranked]
        ax.barh(ys, [gains[m] for m in ranked], height=0.65, color=colors)
        ax.set_yticks(ys, [m.replace("synthetic_", "S") for m in ranked])
        ax.axvline(0, color="#A2B0BE", linewidth=1.2)
        for y, m in zip(ys, ranked):
            x = gains[m]
            ax.text(x + (0.23 if x >= 0 else -0.2), y, f"{x:+.1f}%", fontsize=9,
                    va="center", ha="left" if x >= 0 else "right", color=NAVY)
        ax.set_xlim(left=min(-1.2, min(gains.values())-0.5), right=max(3, max(gains.values())+2.2))
        ax.set_xlabel("Distance reduction vs Greedy TSP (%)", fontsize=10, color=MUTED)
        ax.grid(axis="x", color=GRID)
        ax.grid(axis="y", visible=False)
    else:
        ax.text(0.5,0.5,"No paired GTSP / Greedy results",ha="center",va="center",transform=ax.transAxes)
    ax.set_title("02  GTSP improvement by sample", loc="left", pad=15)

    ax = fig.add_subplot(gs[1, 0]); style_axis(ax)
    for algo in algorithms:
        sub = [(value(stats,m,algo,"num_cells"), value(stats,m,algo,"planning_seconds")) for m in maps]
        sub = [(c,t) for c,t in sub if math.isfinite(c) and math.isfinite(t) and t>0]
        if sub:
            ax.scatter([a for a,_ in sub], [b for _,b in sub], s=55, alpha=.86,
                       color=COLORS.get(algo,"#7F91A4"), label=LABELS.get(algo,algo), edgecolor="white", linewidth=.7)
    ax.set_yscale("log")
    ax.set_xlabel("Number of BCD cells", fontsize=10, color=MUTED)
    ax.set_ylabel("Planning time (seconds, log scale)", fontsize=10, color=MUTED)
    ax.set_title("03  Runtime scaling", loc="left", pad=15)
    ax.legend(frameon=False, fontsize=8, ncols=2, loc="upper left")

    ax = fig.add_subplot(gs[1, 1]); style_axis(ax)
    for algo in algorithms:
        arr=[(value(stats,m,algo,"total_length")/1000, value(stats,m,algo,"vertex_turn_count")) for m in maps]
        arr=[(x,y) for x,y in arr if math.isfinite(x) and math.isfinite(y)]
        if arr:
            ax.scatter([a for a,_ in arr], [b for _,b in arr], s=55,
                       color=COLORS.get(algo,"#7F91A4"), alpha=.85, label=LABELS.get(algo,algo),
                       edgecolor="white", linewidth=.7)
    ax.set_xlabel("Total route length (km)", fontsize=10, color=MUTED)
    ax.set_ylabel("Heading changes (> 1°)", fontsize=10, color=MUTED)
    ax.set_title("04  Distance vs turning trade-off", loc="left", pad=15)

    ax = fig.add_subplot(gs[2, 0]); style_axis(ax)
    xs = np.arange(len(algorithms))
    service = [np.nanmedian([value(stats,m,a,"service_length") for m in maps])/1000 for a in algorithms]
    transit = [np.nanmedian([value(stats,m,a,"transit_length") for m in maps])/1000 for a in algorithms]
    ax.bar(xs, service, color="#8FB8D1", width=.55, label="Service")
    ax.bar(xs, transit, bottom=service, color=COLORS["gtsp"], width=.55, label="Transit")
    ax.set_xticks(xs, [LABELS.get(a,a) for a in algorithms], rotation=0, fontsize=8)
    ax.set_ylabel("Median distance (km)", color=MUTED, fontsize=9)
    ax.set_title("05  Where distance goes  ·  median", loc="left", pad=15)
    ax.legend(frameon=False, ncols=2, fontsize=8.5, loc="upper right")
    ax.set_ylim(bottom=0, top=max((s+t for s,t in zip(service,transit)))*1.27)

    ax = fig.add_subplot(gs[2, 1]); style_axis(ax)
    overlaps = [np.nanmedian([value(stats,m,a,"overlap_excess_percent") for m in maps]) for a in algorithms]
    bars = ax.bar(xs, overlaps, color=[COLORS.get(a,"#7F91A4") for a in algorithms], width=.55)
    for rect, val in zip(bars, overlaps):
        if math.isfinite(val):
            ax.text(rect.get_x()+rect.get_width()/2,rect.get_height()+.35,f"{val:.1f}%",ha="center",fontsize=9,color=NAVY,weight="bold")
    ax.set_xticks(xs, [LABELS.get(a,a) for a in algorithms], fontsize=8)
    ax.set_title("06  Overlap excess  ·  median", loc="left", pad=15)
    ax.set_ylabel("Overlap excess (%)", color=MUTED, fontsize=9)
    ax.set_ylim(bottom=0, top=max(2,max(v for v in overlaps if math.isfinite(v))*1.28))

    fig.text(0.055, 0.025,
             f"Source: {source.name}  ·  Across maps, medians are descriptive only  ·  "
             f"{seeds} seed(s); no statistical significance claim  ·  {failures} failed run(s)",
             fontsize=9, color=MUTED)
    target=out/"benchmark_overview.png"
    fig.savefig(target, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return target


def figure_detail(out, stats, maps, algorithms):
    metrics=[("total_length","Total path length", "m",False),
             ("transit_length","Transit distance", "m",False),
             ("vertex_turn_count","Heading changes", "",False),
             ("lane_reversal_count","Lane reversals", "",False),
             ("overlap_excess_percent","Overlap excess", "%",False),
             ("planning_seconds","Planning runtime", "s",True)]
    fig, axes = plt.subplots(3,2,figsize=(17,13),facecolor=BG)
    fig.subplots_adjust(left=.075,right=.98,top=.89,bottom=.08,hspace=.47,wspace=.2)
    fig.suptitle("Per-sample benchmark metrics",fontsize=24,fontweight="bold",color=NAVY,x=.075,ha="left",y=.975)
    fig.text(.075,.93,"Same maps, same sensor model  ·  One point = median across successful seeds",fontsize=12,color=MUTED)
    x=np.arange(len(maps))
    for ax,(key,title,unit,is_log) in zip(axes.flat,metrics):
        style_axis(ax)
        for algo in algorithms:
            ys=[value(stats,m,algo,key) for m in maps]
            ax.plot(x,ys,linewidth=2,marker="o",markersize=5,label=LABELS.get(algo,algo),color=COLORS.get(algo,"#7F91A4"))
        ax.set_xticks(x,[m.replace("synthetic_","S") for m in maps],rotation=0)
        ax.set_title(title + (f"  ({unit})" if unit else ""),loc="left",pad=13)
        if is_log: ax.set_yscale("log")
        else: ax.set_ylim(bottom=0)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="upper right",bbox_to_anchor=(.97,.956),ncol=len(labels),frameon=False,fontsize=10)
    fig.text(.075,.027,"Interpret values per sample; algorithms may trade shorter paths for more turns or compute time.",fontsize=10,color=MUTED)
    target=out/"per_sample_metrics.png"
    fig.savefig(target,dpi=180,bbox_inches="tight",facecolor=BG)
    plt.close(fig)
    return target


def html_dashboard(source,out,rows,stats,maps,algorithms,ok):
    try:
        import plotly.graph_objects as go
        from plotly.offline import plot as plot_html
    except ImportError:
        return None

    def panel(fig):
        fig.update_layout(
            template="plotly_white", margin=dict(t=20,b=70,l=70,r=30),
            paper_bgcolor="white", plot_bgcolor="white", height=410,
            font=dict(family="Arial, sans-serif",size=12,color=NAVY),
            hoverlabel=dict(bgcolor="white",font_color=NAVY),
            legend=dict(orientation="h",y=1.15,x=0),
        )
        fig.update_xaxes(gridcolor=GRID,zerolinecolor=GRID)
        fig.update_yaxes(gridcolor=GRID,zerolinecolor=GRID)
        return plot_html(fig,include_plotlyjs=False,output_type="div",config={"responsive":True,"displaylogo":False})

    fig=go.Figure()
    for a in algorithms:
        y=[value(stats,m,a,"total_length") for m in maps]
        fig.add_trace(go.Bar(name=LABELS.get(a,a),x=maps,y=y,marker_color=COLORS.get(a,"#7F91A4"),
                             customdata=[[int(value(stats,m,a,"num_cells")) if math.isfinite(value(stats,m,a,"num_cells")) else 0,
                                          value(stats,m,a,"coverage_percent")] for m in maps],
                             hovertemplate="<b>%{x}</b><br>Length: %{y:,.1f} m<br>Cells: %{customdata[0]}<br>Coverage: %{customdata[1]:.1f}%<extra>%{fullData.name}</extra>"))
    fig.update_layout(barmode="group",yaxis_title="Total route length (m)")
    distance=panel(fig)

    gains=improvement(stats,maps)
    fig=go.Figure(go.Bar(x=[gains[m] for m in maps if m in gains],
                         y=[m for m in maps if m in gains], orientation="h",
                         marker_color=[COLORS["gtsp"] if gains[m]>=0 else "#E27F73" for m in maps if m in gains],
                         text=[f"{gains[m]:+.1f}%" for m in maps if m in gains],textposition="outside",
                         hovertemplate="<b>%{y}</b><br>Distance saved: %{x:.2f}%<extra></extra>"))
    fig.update_layout(xaxis_title="GTSP distance reduction relative to greedy (%)",yaxis=dict(autorange="reversed"))
    gain_panel=panel(fig)

    fig=go.Figure()
    for a in algorithms:
        fig.add_trace(go.Scatter(x=[value(stats,m,a,"num_cells") for m in maps],
                                 y=[value(stats,m,a,"planning_seconds") for m in maps],
                                 mode="markers+lines",name=LABELS.get(a,a),marker=dict(size=11,color=COLORS.get(a,"#7F91A4")),
                                 customdata=maps,hovertemplate="<b>%{customdata}</b><br>Cells: %{x}<br>Runtime: %{y:.4f}s<extra>%{fullData.name}</extra>"))
    fig.update_layout(xaxis_title="Number of BCD cells",yaxis_title="Planning time (s)",yaxis_type="log")
    runtime=panel(fig)

    fig=go.Figure()
    for a in algorithms:
        fig.add_trace(go.Scatter(x=[value(stats,m,a,"total_length") for m in maps],
                                 y=[value(stats,m,a,"vertex_turn_count") for m in maps],
                                 mode="markers",name=LABELS.get(a,a),marker=dict(size=12,color=COLORS.get(a,"#7F91A4"),opacity=.85),
                                 customdata=maps,hovertemplate="<b>%{customdata}</b><br>Length: %{x:.1f} m<br>Heading changes: %{y}<extra>%{fullData.name}</extra>"))
    fig.update_layout(xaxis_title="Route length (m)",yaxis_title="Heading changes")
    turns=panel(fig)

    results=[(m,a,value(stats,m,a,"total_length"),value(stats,m,a,"coverage_percent"),
              value(stats,m,a,"vertex_turn_count"),value(stats,m,a,"overlap_excess_percent"),
              value(stats,m,a,"planning_seconds")) for m in maps for a in algorithms if (m,a) in stats]
    table="".join(f"<tr><td>{html.escape(m)}</td><td><span class='dot' style='background:{COLORS.get(a, '#7F91A4')}'></span>{html.escape(LABELS.get(a,a))}</td><td>{length:,.1f}</td><td>{cover:.1f}%</td><td>{turns:.0f}</td><td>{overlap:.2f}%</td><td>{rt:.4f}</td></tr>" for m,a,length,cover,turns,overlap,rt in results)
    imp=median(gains.values()) if gains else float("nan")
    wins=sum(x>1e-8 for x in gains.values())
    covervals=[numerical(r,"coverage_percent") for r in ok];covervals=[x for x in covervals if math.isfinite(x)]
    gtsp_times=[value(stats,m,"gtsp","planning_seconds") for m in maps]
    gtsp_times=[v for v in gtsp_times if math.isfinite(v)]
    kpi=[("Median GTSP distance saved",format_percent(imp,2)),
         ("Maps with GTSP improvement",f"{wins} / {len(gains)}" if gains else "—"),
         ("Min observed coverage",format_percent(min(covervals),1) if covervals else "—"),
         ("Median GTSP runtime",f"{median(gtsp_times):.3f}s" if gtsp_times else "—")]
    cards="".join(f"<section class='kpi'><span>{html.escape(k)}</span><strong>{html.escape(v)}</strong></section>" for k,v in kpi)
    page=f"""<!doctype html><html lang='en'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/>
<title>Coverage planning benchmark dashboard</title><style>
:root{{--ink:#142A41;--muted:#6A7988;--bg:#F3F6FA;--accent:#02A696}}*{{box-sizing:border-box}}
body{{font-family:Inter,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:0;background:var(--bg);color:var(--ink)}}
.container{{max-width:1500px;margin:0 auto;padding:44px 30px 65px}}.eyebrow{{font-size:12px;color:var(--accent);font-weight:800;letter-spacing:.12em}}
h1{{font-size:clamp(28px,3vw,42px);margin:9px 0 8px;letter-spacing:-.035em}}p.lead{{color:var(--muted);font-size:15px;margin:0 0 25px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:27px 0 22px}}.kpi{{background:white;border:1px solid #E2EAF3;border-radius:16px;padding:23px;box-shadow:0 2px 5px #142a410a}}
.kpi span{{display:block;color:var(--muted);font-size:13px;margin-bottom:12px}}.kpi strong{{font-size:29px;letter-spacing:-.025em}}
.layout{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.panel{{background:white;border:1px solid #E2EAF3;border-radius:16px;padding:16px 13px 4px;overflow:hidden}}
.panel h2{{margin:6px 18px 0;font-size:17px;letter-spacing:-.015em}}.wide{{grid-column:1/-1}}.tablewrap{{overflow-x:auto;margin:13px 10px 20px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{text-align:right;padding:11px 13px;border-bottom:1px solid #E9EFF5;white-space:nowrap}}th{{color:var(--muted);background:#F8FAFC;font-weight:600}}td:first-child,th:first-child,td:nth-child(2),th:nth-child(2){{text-align:left}}
tr:hover td{{background:#F4F9FB}}.dot{{display:inline-block;height:9px;width:9px;border-radius:50%;margin-right:9px}}
.note{{background:#E8F3F2;border-radius:11px;padding:15px 20px;color:#3B6C69;font-size:13px;margin:23px 0 0}}
footer{{margin-top:20px;color:var(--muted);font-size:12px}}@media(max-width:1000px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.layout{{grid-template-columns:1fr}}.wide{{grid-column:auto}}}}@media(max-width:520px){{.container{{padding:24px 14px}}.kpis{{grid-template-columns:1fr 1fr;gap:9px}}.kpi{{padding:14px}}.kpi strong{{font-size:19px}}}}
</style></head><body><div class='container'><div class='eyebrow'>BCD / GTSP RESEARCH</div><h1>Coverage-planning benchmark</h1>
<p class='lead'>{len(maps)} maps · {len(algorithms)} planners · {len(ok)}/{len(rows)} successful runs · Input: {html.escape(source.name)} · Hover charts for per-sample metrics</p>
<div class='kpis'>{cards}</div><div class='layout'>
<section class='panel'><h2>01 — Path length by sample</h2>{distance}</section>
<section class='panel'><h2>02 — GTSP distance reduction</h2>{gain_panel}</section>
<section class='panel'><h2>03 — Planning time vs BCD cells</h2>{runtime}</section>
<section class='panel'><h2>04 — Turning vs route length</h2>{turns}</section>
<section class='panel wide'><h2>Per-sample numerical results</h2><div class='tablewrap'><table><thead><tr><th>Map</th><th>Algorithm</th><th>Route (m)</th><th>Coverage</th><th>Turns</th><th>Overlap excess</th><th>Runtime (s)</th></tr></thead><tbody>{table}</tbody></table></div></section>
</div><p class='note'>Benchmark note: values are medians for each map / algorithm when multiple seeds are present. Current smoke results use a small number of seeds and do not establish statistical significance. Sensor footprints, transit and turn counts follow this project's metric definitions.</p>
<footer>Generated from {html.escape(str(source.name))} · Offline interactive report · No external connection required</footer>
</div></body></html>"""
    import plotly.offline as po
    page=page.replace("</head><body>", "<script>" + po.get_plotlyjs() + "</script></head><body>", 1)
    output=out/"benchmark_dashboard.html"
    output.write_text(page,encoding="utf-8")
    return output


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv",type=Path,help="Per-run CSV produced by coverage-benchmark")
    ap.add_argument("--out",type=Path,default=Path("results/figures"),help="Figure output directory")
    args=ap.parse_args(argv)
    args.out.mkdir(parents=True,exist_ok=True)
    rows=read_results(args.csv)
    stats,maps,algorithms,ok=summarize(rows)
    outputs=[figure_overview(args.csv,args.out,rows,stats,maps,algorithms,ok),
             figure_detail(args.out,stats,maps,algorithms)]
    html_result=html_dashboard(args.csv,args.out,rows,stats,maps,algorithms,ok)
    if html_result: outputs.append(html_result)
    else: print("Interactive HTML skipped (install optional dependency: pip install plotly)")
    for path in outputs: print(path)
    print(f"Plotted {len(ok)} successful of {len(rows)} total runs across {len(maps)} maps.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
