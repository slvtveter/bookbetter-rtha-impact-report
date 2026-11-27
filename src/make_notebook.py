"""Create and execute notebooks/analysis.ipynb - a readable walk-through of the
same pandas analysis that feeds the one-pager. Run after generate_data.py."""
from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "analysis.ipynb"

cells = [
    new_markdown_cell(
        "# BookBetter × RTHA: partnership KPIs in pandas\n\n"
        "The analysis behind the one-page report. The data is **synthetic** (see `src/generate_data.py`), "
        "so the point is how the metrics are built, not the numbers themselves.\n\n"
        "Period: 1 July – 31 October 2026, the first four months after the RTHA booking engine went live."
    ),
    new_code_cell(
        "import pandas as pd\n"
        "pd.options.display.float_format = '{:,.1f}'.format\n\n"
        "bookings = pd.read_csv('../data/bookings.csv', parse_dates=['booking_date', 'departure_date'])\n"
        "traffic = pd.read_csv('../data/engine_traffic.csv', parse_dates=['booking_date'])\n"
        "bookings['month'] = bookings['booking_date'].dt.to_period('M')\n"
        "bookings['with_saf'] = bookings['saf_coverage_pct'] > 0\n"
        "print(bookings.shape, traffic.shape)\n"
        "bookings.head()"
    ),
    new_markdown_cell("## 1. Headline numbers\n\nThe figures an airport partner asks about first: volume, money, SAF uptake, SAF volume, CO₂e avoided, repeat travellers."),
    new_code_cell(
        "repeat = bookings.duplicated('customer_id', keep='first')\n"
        "headline = pd.Series({\n"
        "    'Bookings': len(bookings),\n"
        "    'Passengers': bookings['passengers'].sum(),\n"
        "    'Gross booking value (EUR)': bookings['gross_booking_value_eur'].sum(),\n"
        "    'Partner revenue share @2.5% (EUR)': bookings['gross_booking_value_eur'].sum() * 0.025,\n"
        "    'SAF uptake (% of bookings)': bookings['with_saf'].mean() * 100,\n"
        "    'SAF funded (litres)': bookings['saf_litres'].sum(),\n"
        "    'Traveller SAF contributions (EUR)': bookings['saf_contribution_eur'].sum(),\n"
        "    'CO2e emitted (t)': bookings['co2e_kg'].sum() / 1000,\n"
        "    'CO2e avoided (t)': bookings['co2e_avoided_kg'].sum() / 1000,\n"
        "    'CO2e avoided (% of emitted)': bookings['co2e_avoided_kg'].sum() / bookings['co2e_kg'].sum() * 100,\n"
        "    'Repeat bookings (%)': repeat.mean() * 100,\n"
        "    'Certificates issued': bookings['certificate_issued'].sum(),\n"
        "})\n"
        "headline.to_frame('value')"
    ),
    new_markdown_cell("## 2. Month by month\n\nDoes the default keep working once the launch effect fades? Uptake should hold or rise."),
    new_code_cell(
        "monthly = (bookings.groupby('month')\n"
        "    .agg(bookings=('booking_id', 'size'),\n"
        "         uptake_pct=('with_saf', lambda s: s.mean() * 100),\n"
        "         saf_litres=('saf_litres', 'sum'),\n"
        "         co2e_avoided_t=('co2e_avoided_kg', lambda s: s.sum() / 1000),\n"
        "         gross_eur=('gross_booking_value_eur', 'sum')))\n"
        "monthly"
    ),
    new_markdown_cell("## 3. What travellers do with the pre-selected 10 %\n\nThe most important behavioural metric: a default only helps if people keep it."),
    new_code_cell(
        "choice = pd.crosstab(bookings['month'], bookings['saf_choice'], normalize='index') * 100\n"
        "choice = choice[['increased', 'kept_default', 'reduced', 'switched_off']]\n"
        "choice.round(1)"
    ),
    new_code_cell(
        "on = bookings[bookings['with_saf']]\n"
        "print(f\"When SAF is on: avg coverage {on['saf_coverage_pct'].mean():.1f}% of emissions, \"\n"
        "      f\"avg contribution EUR {on['saf_contribution_eur'].mean():.0f} per booking, \"\n"
        "      f\"EUR {(on['saf_contribution_eur'] / on['passengers']).mean():.0f} per passenger\")"
    ),
    new_markdown_cell("## 4. Routes\n\nWhere the tonnes come from. Long leisure routes dominate, London City is busy but short."),
    new_code_cell(
        "routes = (bookings.groupby('destination')\n"
        "    .agg(bookings=('booking_id', 'size'), passengers=('passengers', 'sum'),\n"
        "         distance_km=('distance_km', 'first'),\n"
        "         uptake_pct=('with_saf', lambda s: s.mean() * 100),\n"
        "         co2e_avoided_t=('co2e_avoided_kg', lambda s: s.sum() / 1000))\n"
        "    .sort_values('co2e_avoided_t', ascending=False))\n"
        "routes"
    ),
    new_markdown_cell("## 5. Funnel and devices\n\nSession, search, booking, booking with SAF. Conversion matters more to BookBetter, the SAF step matters more to the partner."),
    new_code_cell(
        "funnel = pd.Series({\n"
        "    'Sessions': traffic['sessions'].sum(),\n"
        "    'Searches': traffic['searches'].sum(),\n"
        "    'Bookings': len(bookings),\n"
        "    'Bookings with SAF': bookings['with_saf'].sum(),\n"
        "}).to_frame('count')\n"
        "funnel['step_conversion_pct'] = funnel['count'] / funnel['count'].shift(1) * 100\n"
        "funnel"
    ),
    new_code_cell(
        "bookings.groupby('device').agg(bookings=('booking_id', 'size'),\n"
        "                               uptake_pct=('with_saf', lambda s: s.mean() * 100))"
    ),
    new_markdown_cell(
        "## 6. Baseline: compared to what?\n\n"
        "A number without a comparison is easy to wave away, so the report uses two baselines. "
        "Both are **assumptions**, not data:\n\n"
        "- **SAF:** if the contribution were an unticked checkbox instead of a pre-selected default, "
        "assume 5 % of bookings would add it, with the same average coverage as today.\n"
        "- **Bookings:** assume 3,000 bookings through RTHA's previous booking flow in the same four months of 2025."
    ),
    new_code_cell(
        "OPT_IN_UPTAKE = 5.0\n"
        "PRIOR_YEAR_BOOKINGS = 3000\n\n"
        "uptake = bookings['with_saf'].mean() * 100\n"
        "avoided_t = bookings['co2e_avoided_kg'].sum() / 1000\n"
        "opt_in_t = avoided_t * OPT_IN_UPTAKE / uptake\n\n"
        "pd.Series({\n"
        "    'SAF uptake with default (%)': uptake,\n"
        "    'SAF uptake, opt-in assumption (%)': OPT_IN_UPTAKE,\n"
        "    'CO2e avoided with default (t)': avoided_t,\n"
        "    'CO2e avoided with opt-in (t)': opt_in_t,\n"
        "    'Extra CO2e from the default (t)': avoided_t - opt_in_t,\n"
        "    'Bookings vs same months 2025 (%)': (len(bookings) / PRIOR_YEAR_BOOKINGS - 1) * 100,\n"
        "}).to_frame('value')"
    ),
    new_markdown_cell(
        "## 7. Assumptions used in the data\n\n"
        "| Assumption | Value |\n|---|---|\n"
        "| CO₂e per passenger-km | 0.17 (< 800 km), 0.14 (800–1600 km), 0.12 (> 1600 km) kg |\n"
        "| CO₂e avoided per litre of SAF | 2.0 kg (about 80 % lifecycle reduction vs fossil jet) |\n"
        "| SAF price gap paid by traveller | €2.00 per litre |\n"
        "| Default contribution | 10 % of the booking's emissions, adjustable |\n"
        "| Partner revenue share | 2.5 % of gross booking value (illustrative) |\n"
        "| Opt-in baseline uptake | 5 % (assumed) |\n"
        "| Same months of 2025 | 3,000 bookings (assumed) |\n\n"
        "The constants can be changed in `src/generate_data.py` and `src/kpis.py`, then rebuild."
    ),
]

nb = new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
OUT.parent.mkdir(exist_ok=True)
client = NotebookClient(nb, timeout=120, kernel_name="python3", resources={"metadata": {"path": str(OUT.parent)}})
client.execute()
nbformat.write(nb, OUT)
print(f"notebook -> {OUT}")
