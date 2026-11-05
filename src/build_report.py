"""Assemble the one-page report: KPIs + SVG charts -> docs/index.html -> PDF/PNG.

Usage:  python src/build_report.py            (HTML + PDF + PNG)
        python src/build_report.py --no-pdf   (HTML only, no Chrome needed)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import charts
import kpis as kpi_module

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BUILD = ROOT / "build"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chrome") or "",
]


def filters(env: Environment) -> None:
    env.filters["int_"] = lambda v: f"{int(round(v)):,}"
    env.filters["round0"] = lambda v: f"{v:.0f}"
    env.filters["round1"] = lambda v: f"{v:.1f}"
    env.filters["round2"] = lambda v: f"{v:.2f}"
    env.filters["eur_m"] = lambda v: f"{v / 1_000_000:.2f}M" if v >= 1_000_000 else f"{int(round(v)):,}"


def render(kpis: dict) -> str:
    env = Environment(loader=FileSystemLoader(ROOT / "src"), autoescape=False)
    filters(env)
    tpl = env.get_template("template.html")

    choices = {c["key"]: c for c in kpis["choices"]}
    monthly = kpis["monthly"]
    # opt-out share per month comes from the raw data, so recompute it here
    import pandas as pd

    b = pd.read_csv(ROOT / "data" / "bookings.csv", parse_dates=["booking_date"])
    off_by_month = (b.assign(month=b["booking_date"].dt.strftime("%Y-%m"))
                    .groupby("month")["saf_choice"].apply(lambda s: (s == "switched_off").mean() * 100))
    m_first = {"off_pct": float(off_by_month.iloc[0]), "uptake": monthly[0]["uptake_pct"]}
    m_last = {"off_pct": float(off_by_month.iloc[-1]), "uptake": monthly[-1]["uptake_pct"]}

    routes = kpis["routes"]
    lcy = next(r for r in routes if r["destination"] == "London City")
    iberia = {"Barcelona", "Alicante", "Faro", "Malaga", "Lisbon"}
    iberia_share = sum(r["co2e_avoided_t"] for r in routes if r["destination"] in iberia) / kpis["totals"]["co2e_avoided_t"] * 100

    return tpl.render(
        period=kpis["period"],
        lcy=lcy,
        iberia_share=iberia_share,
        t=kpis["totals"],
        dev=kpis["uptake_by_device_pct"],
        m_first=m_first,
        m_last=m_last,
        c_off=choices["switched_off"],
        kept_or_more=choices["kept_default"]["share_pct"] + choices["increased"]["share_pct"],
        chart_monthly=charts.stacked_columns(monthly, width=337, height=156),
        chart_choices=charts.segmented_bar(kpis["choices"], width=337),
        chart_routes=charts.ranked_bars(kpis["routes"], width=400, row_h=18, bar_h=12),
    )


def export_with_chrome(html_path: Path) -> None:
    chrome = next((c for c in CHROME_CANDIDATES if c and Path(c).exists()), None)
    if not chrome:
        print("Chrome not found: skipping PDF/PNG export (HTML is ready).")
        return
    url = html_path.resolve().as_uri()
    common = ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check"]
    subprocess.run([chrome, *common, "--no-pdf-header-footer", f"--print-to-pdf={DOCS / 'report.pdf'}", url],
                   check=True, capture_output=True)
    # 2x A4 at 96 dpi for a crisp preview image
    subprocess.run([chrome, *common, "--force-device-scale-factor=2", "--window-size=842,1171",
                    f"--screenshot={DOCS / 'report.png'}", url], check=True, capture_output=True)
    print(f"PDF  -> {DOCS / 'report.pdf'}")
    print(f"PNG  -> {DOCS / 'report.png'}")


def main() -> None:
    kpis = kpi_module.main()
    DOCS.mkdir(exist_ok=True)
    html = render(kpis)
    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"HTML -> {out}")
    if "--no-pdf" not in sys.argv:
        export_with_chrome(out)


if __name__ == "__main__":
    main()
