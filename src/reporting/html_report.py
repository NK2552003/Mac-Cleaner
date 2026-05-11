"""
Mac Deep Cleaner v1.0.0 — HTML Report Exporter
============================================
Generates a self-contained HTML report with:
- Collapsible sections per category
- Doughnut chart (Chart.js via CDN) for space breakdown
- Treemap-style table for large file / duplicate findings
- Embedded CSS (no external dependencies except CDN Chart.js)

All data is serialised into an inline <script> block so the file can be
opened offline after the CDN scripts are cached.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.models import DevJunkEntry, JunkEntry, OrphanEntry
from utils import bytes_human


# ── HTML template ──────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mac Deep Cleaner — Scan Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f0f0f; --surface: #1a1a1a; --border: #2a2a2a;
    --text: #e0e0e0; --dim: #888; --accent: #00bcd4;
    --red: #ef5350; --yellow: #ffd54f; --green: #66bb6a;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: var(--bg); color: var(--text); line-height: 1.6; }}
  header {{ background: var(--surface); border-bottom: 1px solid var(--border);
            padding: 24px 32px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 1.4rem; color: var(--accent); }}
  header .meta {{ color: var(--dim); font-size: .85rem; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 24px 32px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border);
           border-radius: 8px; padding: 20px; }}
  .card h3 {{ font-size: .8rem; text-transform: uppercase; letter-spacing: .08em;
              color: var(--dim); margin-bottom: 8px; }}
  .card .big {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
  .section {{ margin-bottom: 24px; }}
  .section-header {{ background: var(--surface); border: 1px solid var(--border);
                     border-radius: 8px 8px 0 0; padding: 14px 20px;
                     cursor: pointer; display: flex; justify-content: space-between;
                     align-items: center; user-select: none; }}
  .section-header:hover {{ background: #222; }}
  .section-header h2 {{ font-size: 1rem; }}
  .section-header .badge {{ background: var(--accent); color: #000;
                            border-radius: 12px; padding: 2px 10px;
                            font-size: .75rem; font-weight: 700; }}
  .section-body {{ border: 1px solid var(--border); border-top: 0;
                   border-radius: 0 0 8px 8px; overflow: hidden; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ background: #111; color: var(--dim); text-align: left;
        padding: 10px 14px; border-bottom: 1px solid var(--border); }}
  td {{ padding: 9px 14px; border-bottom: 1px solid var(--border); }}
  tr:last-child td {{ border-bottom: 0; }}
  tr:hover td {{ background: #1e1e1e; }}
  .size {{ font-variant-numeric: tabular-nums; color: var(--yellow); text-align: right; }}
  .path {{ font-family: "SF Mono", Menlo, monospace; font-size: .78rem;
           color: var(--dim); word-break: break-all; }}
  .tag {{ display: inline-block; padding: 1px 7px; border-radius: 4px;
          font-size: .72rem; font-weight: 600; }}
  .tag-red {{ background: #3b1a1a; color: var(--red); }}
  .tag-yellow {{ background: #2e2800; color: var(--yellow); }}
  .tag-cyan {{ background: #002b30; color: var(--accent); }}
  canvas {{ max-height: 260px; }}
  .chart-wrap {{ display: flex; align-items: center; gap: 24px; }}
  .legend {{ flex: 1; }}
  .legend-item {{ display: flex; align-items: center; gap: 8px;
                  margin-bottom: 6px; font-size: .85rem; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  footer {{ text-align: center; color: var(--dim); font-size: .78rem;
            padding: 24px; border-top: 1px solid var(--border); }}
  .toggle {{ color: var(--dim); transition: transform .2s; }}
  .collapsed .toggle {{ transform: rotate(-90deg); }}
  .collapsed + .section-body {{ display: none; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>◆ Mac Deep Cleaner — Scan Report</h1>
    <div class="meta">Generated {generated_at} &nbsp;·&nbsp; v1.0.0</div>
  </div>
</header>

<div class="container">

  <!-- Summary cards -->
  <div class="grid">
    <div class="card">
      <h3>Total Reclaimable</h3>
      <div class="big">{grand_total}</div>
    </div>
    <div class="card">
      <h3>Orphaned App Data</h3>
      <div class="big" style="color:var(--red)">{orphan_total}</div>
    </div>
    <div class="card">
      <h3>General Junk</h3>
      <div class="big" style="color:var(--yellow)">{junk_total}</div>
    </div>
    <div class="card">
      <h3>Developer Junk</h3>
      <div class="big" style="color:var(--accent)">{dev_junk_total}</div>
    </div>
    <div class="card">
      <h3>Unique Orphaned Apps</h3>
      <div class="big">{orphan_count}</div>
    </div>
  </div>

  <!-- Chart -->
  <div class="card section" style="margin-bottom:24px">
    <h3 style="margin-bottom:16px">Space Breakdown</h3>
    <div class="chart-wrap">
      <canvas id="pieChart" width="220" height="220" style="max-width:220px"></canvas>
      <div class="legend" id="legend"></div>
    </div>
  </div>

  <!-- Orphan sections -->
  {orphan_sections}

  <!-- Junk section -->
  {junk_section}

  <!-- Developer junk section -->
  {dev_junk_section}

</div>

<footer>Mac Deep Cleaner v1.0.0 &nbsp;·&nbsp; Report generated {generated_at}</footer>

<script>
const chartData = {chart_data};

// Pie chart
const ctx = document.getElementById('pieChart').getContext('2d');
new Chart(ctx, {{
  type: 'doughnut',
  data: {{
    labels: chartData.labels,
    datasets: [{{ data: chartData.values, backgroundColor: chartData.colors,
                 borderWidth: 2, borderColor: '#0f0f0f' }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }}, tooltip: {{
      callbacks: {{ label: (ctx) => ` ${{ctx.label}}: ${{chartData.human[ctx.dataIndex]}}` }}
    }} }},
    cutout: '65%'
  }}
}});

// Legend
const legend = document.getElementById('legend');
chartData.labels.forEach((l, i) => {{
  legend.innerHTML += `<div class="legend-item">
    <div class="dot" style="background:${{chartData.colors[i]}}"></div>
    <span>${{l}}</span><span style="margin-left:auto;color:#ffd54f">${{chartData.human[i]}}</span>
  </div>`;
}});

// Collapsible sections
document.querySelectorAll('.section-header').forEach(h => {{
  h.addEventListener('click', () => h.classList.toggle('collapsed'));
}});
</script>
</body>
</html>"""


# ── Builder helpers ────────────────────────────────────────────────────────────

def _tag(text: str, style: str = "cyan") -> str:
    return f'<span class="tag tag-{style}">{text}</span>'


def _orphan_section(app_name: str, entries: List[OrphanEntry]) -> str:
    total = sum(e.size for e in entries)
    rows = ""
    for e in sorted(entries, key=lambda x: x.size, reverse=True):
        rows += (
            f"<tr>"
            f"<td>{_tag(e.reason, 'cyan')}</td>"
            f"<td class='path'>{e.path}</td>"
            f"<td class='size'>{bytes_human(e.size)}</td>"
            f"</tr>"
        )
    return f"""
<div class="section">
  <div class="section-header">
    <h2>✗ {app_name}</h2>
    <span class="badge">{bytes_human(total)}</span>
    <span class="toggle">▼</span>
  </div>
  <div class="section-body">
    <table>
      <thead><tr><th>Type</th><th>Path</th><th>Size</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


def _junk_section(junk: List[JunkEntry]) -> str:
    user_junk = [j for j in junk if not j.is_system]
    if not user_junk:
        return ""

    from collections import defaultdict
    by_cat: Dict[str, List[JunkEntry]] = defaultdict(list)
    for j in user_junk:
        by_cat[j.category].append(j)

    rows = ""
    for cat in sorted(by_cat):
        items = by_cat[cat]
        cat_total = sum(j.size for j in items)
        rows += (
            f"<tr>"
            f"<td>{_tag(cat, 'yellow')}</td>"
            f"<td>{len(items)} items</td>"
            f"<td class='size'>{bytes_human(cat_total)}</td>"
            f"</tr>"
        )
        for j in sorted(items, key=lambda x: x.size, reverse=True)[:5]:
            rows += (
                f"<tr>"
                f"<td></td>"
                f"<td class='path'>{j.path}</td>"
                f"<td class='size'>{bytes_human(j.size)}</td>"
                f"</tr>"
            )

    total = sum(j.size for j in user_junk)
    return f"""
<div class="section">
  <div class="section-header">
    <h2>◆ General Junk</h2>
    <span class="badge">{bytes_human(total)}</span>
    <span class="toggle">▼</span>
  </div>
  <div class="section-body">
    <table>
      <thead><tr><th>Category</th><th>Items</th><th>Size</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


def _dev_junk_section(entries: List[DevJunkEntry]) -> str:
    if not entries:
        return ""

    from collections import defaultdict
    by_cat: Dict[str, List[DevJunkEntry]] = defaultdict(list)
    for e in entries:
        by_cat[e.category].append(e)

    rows = ""
    for cat in sorted(by_cat):
        items = by_cat[cat]
        cat_total = sum(j.size for j in items)
        rows += (
            f"<tr>"
            f"<td>{_tag(cat, 'yellow')}</td>"
            f"<td>{len(items)} items</td>"
            f"<td class='size'>{bytes_human(cat_total)}</td>"
            f"</tr>"
        )
        for j in sorted(items, key=lambda x: x.size, reverse=True)[:5]:
            rows += (
                f"<tr>"
                f"<td></td>"
                f"<td class='path'>{j.path}</td>"
                f"<td class='size'>{bytes_human(j.size)}</td>"
                f"</tr>"
            )

    total = sum(j.size for j in entries)
    return f"""
<div class="section">
  <div class="section-header">
    <h2>◆ Developer Junk</h2>
    <span class="badge">{bytes_human(total)}</span>
    <span class="toggle">▼</span>
  </div>
  <div class="section-body">
    <table>
      <thead><tr><th>Category</th><th>Items</th><th>Size</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


# ── Public API ─────────────────────────────────────────────────────────────────

_CHART_COLORS = [
    "#ef5350", "#ffd54f", "#00bcd4", "#66bb6a", "#ab47bc",
    "#26c6da", "#ff7043", "#42a5f5", "#26a69a", "#d4e157",
]


def export_html(
  orphans: Dict[str, List[OrphanEntry]],
  junk: List[JunkEntry],
  dev_junk: Optional[List[DevJunkEntry]],
  output_path: str,
) -> None:
    """
    Generate a self-contained HTML scan report.

    Args:
        orphans:     Dict[app_name → list[OrphanEntry]]
        junk:        List[JunkEntry]
        output_path: Path to write the .html file.
    """
    # Sort orphans by total size
    sorted_orphans = sorted(
        orphans.items(),
        key=lambda kv: sum(e.size for e in kv[1]),
        reverse=True,
    )

    orphan_total_bytes = sum(sum(e.size for e in v) for v in orphans.values())
    user_junk = [j for j in junk if not j.is_system]
    junk_total_bytes = sum(j.size for j in user_junk)
    dev_junk = dev_junk or []
    dev_junk_total_bytes = sum(j.size for j in dev_junk)
    grand_total_bytes = orphan_total_bytes + junk_total_bytes + dev_junk_total_bytes

    # Build chart data (top 8 orphans + "Other" + Junk)
    chart_labels: List[str] = []
    chart_values: List[int] = []
    chart_human: List[str] = []
    chart_colors: List[str] = []

    for i, (name, entries) in enumerate(sorted_orphans[:8]):
        sz = sum(e.size for e in entries)
        chart_labels.append(name)
        chart_values.append(sz)
        chart_human.append(bytes_human(sz))
        chart_colors.append(_CHART_COLORS[i % len(_CHART_COLORS)])

    if len(sorted_orphans) > 8:
        rest = sum(
            sum(e.size for e in v)
            for _, v in sorted_orphans[8:]
        )
        chart_labels.append("Other Orphans")
        chart_values.append(rest)
        chart_human.append(bytes_human(rest))
        chart_colors.append("#607d8b")

    if junk_total_bytes > 0:
        chart_labels.append("General Junk")
        chart_values.append(junk_total_bytes)
        chart_human.append(bytes_human(junk_total_bytes))
        chart_colors.append("#ffd54f")

    if dev_junk_total_bytes > 0:
      chart_labels.append("Developer Junk")
      chart_values.append(dev_junk_total_bytes)
      chart_human.append(bytes_human(dev_junk_total_bytes))
      chart_colors.append("#26c6da")

    chart_data = {
        "labels": chart_labels,
        "values": chart_values,
        "human": chart_human,
        "colors": chart_colors,
    }

    # Render orphan sections
    orphan_sections = ""
    for app_name, entries in sorted_orphans:
        orphan_sections += _orphan_section(app_name, entries)

    html = _HTML_TEMPLATE.format(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        grand_total=bytes_human(grand_total_bytes),
        orphan_total=bytes_human(orphan_total_bytes),
        junk_total=bytes_human(junk_total_bytes),
      dev_junk_total=bytes_human(dev_junk_total_bytes),
        orphan_count=len(orphans),
        orphan_sections=orphan_sections,
        junk_section=_junk_section(junk),
        chart_data=json.dumps(chart_data),
        dev_junk_section=_dev_junk_section(dev_junk),
    )

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
    except OSError as e:
        raise RuntimeError(f"Failed to write HTML report: {e}") from e
