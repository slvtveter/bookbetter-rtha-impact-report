"""Turn the raw booking data into the KPIs shown on the one-pager.

Run `python src/kpis.py` to print the numbers and write build/kpis.json.
Every figure in the report comes from this file, so the report and the data
can never disagree.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BUILD = ROOT / "build"

PARTNER_REVENUE_SHARE = 0.025  # illustrative share of gross booking value paid to RTHA

CHOICE_LABELS = {
    "increased": "Increased above 10 %",
    "kept_default": "Kept the 10 % default",
    "reduced": "Reduced to 5 %",
    "switched_off": "Switched off",
}
CHOICE_ORDER = ["increased", "kept_default", "reduced", "switched_off"]


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    bookings = pd.read_csv(DATA / "bookings.csv", parse_dates=["booking_date", "departure_date"])
    traffic = pd.read_csv(DATA / "engine_traffic.csv", parse_dates=["booking_date"])
    return bookings, traffic


def compute(bookings: pd.DataFrame, traffic: pd.DataFrame) -> dict:
    b = bookings.copy()
    b["month"] = b["booking_date"].dt.to_period("M")
    b["with_saf"] = b["saf_coverage_pct"] > 0

    # --- headline totals ------------------------------------------------------
    totals = {
        "bookings": int(len(b)),
        "passengers": int(b["passengers"].sum()),
        "gross_booking_value_eur": float(b["gross_booking_value_eur"].sum()),
        "partner_revenue_share_eur": float(b["gross_booking_value_eur"].sum() * PARTNER_REVENUE_SHARE),
        "saf_uptake_pct": float(b["with_saf"].mean() * 100),
        "saf_litres": float(b["saf_litres"].sum()),
        "saf_contributions_eur": float(b["saf_contribution_eur"].sum()),
        "co2e_avoided_t": float(b["co2e_avoided_kg"].sum() / 1000),
        "co2e_total_t": float(b["co2e_kg"].sum() / 1000),
        "avg_coverage_pct_when_on": float(b.loc[b["with_saf"], "saf_coverage_pct"].mean()),
        "avg_contribution_eur_when_on": float(b.loc[b["with_saf"], "saf_contribution_eur"].mean()),
        "certificates_issued": int(b["certificate_issued"].sum()),
        "unique_customers": int(b["customer_id"].nunique()),
    }
    totals["co2e_avoided_share_pct"] = totals["co2e_avoided_t"] / totals["co2e_total_t"] * 100
    repeat_mask = b.duplicated("customer_id", keep="first")
    totals["repeat_booking_share_pct"] = float(repeat_mask.mean() * 100)

    # --- monthly ------------------------------------------------------------------
    monthly = (
        b.groupby("month")
        .agg(
            bookings=("booking_id", "size"),
            with_saf=("with_saf", "sum"),
            saf_litres=("saf_litres", "sum"),
            co2e_avoided_t=("co2e_avoided_kg", lambda s: s.sum() / 1000),
            gross_eur=("gross_booking_value_eur", "sum"),
        )
        .reset_index()
    )
    monthly["without_saf"] = monthly["bookings"] - monthly["with_saf"]
    monthly["uptake_pct"] = monthly["with_saf"] / monthly["bookings"] * 100
    monthly["label"] = monthly["month"].dt.strftime("%b")
    monthly_out = [
        {
            "month": str(r.month),
            "label": r.label,
            "bookings": int(r.bookings),
            "with_saf": int(r.with_saf),
            "without_saf": int(r.without_saf),
            "uptake_pct": float(r.uptake_pct),
            "saf_litres": float(r.saf_litres),
            "co2e_avoided_t": float(r.co2e_avoided_t),
            "gross_eur": float(r.gross_eur),
        }
        for r in monthly.itertuples()
    ]
    first, last = monthly_out[0], monthly_out[-1]
    totals["uptake_change_pp"] = last["uptake_pct"] - first["uptake_pct"]

    # --- what travellers did with the default ------------------------------------
    choice_counts = b["saf_choice"].value_counts()
    choices = [
        {
            "key": k,
            "label": CHOICE_LABELS[k],
            "bookings": int(choice_counts.get(k, 0)),
            "share_pct": float(choice_counts.get(k, 0) / len(b) * 100),
        }
        for k in CHOICE_ORDER
    ]

    # --- routes -----------------------------------------------------------------------
    routes = (
        b.groupby("destination")
        .agg(
            bookings=("booking_id", "size"),
            passengers=("passengers", "sum"),
            co2e_avoided_t=("co2e_avoided_kg", lambda s: s.sum() / 1000),
            uptake_pct=("with_saf", lambda s: s.mean() * 100),
        )
        .sort_values("co2e_avoided_t", ascending=False)
        .reset_index()
    )
    routes_out = [
        {
            "destination": r.destination,
            "bookings": int(r.bookings),
            "passengers": int(r.passengers),
            "co2e_avoided_t": float(r.co2e_avoided_t),
            "uptake_pct": float(r.uptake_pct),
        }
        for r in routes.itertuples()
    ]

    # --- funnel ---------------------------------------------------------------------------
    sessions = int(traffic["sessions"].sum())
    searches = int(traffic["searches"].sum())
    funnel = [
        {"stage": "Booking-engine sessions", "value": sessions},
        {"stage": "Flight searches", "value": searches},
        {"stage": "Bookings", "value": totals["bookings"]},
        {"stage": "Bookings with SAF", "value": int(b["with_saf"].sum())},
    ]
    totals["session_to_booking_pct"] = totals["bookings"] / sessions * 100

    # --- device ---------------------------------------------------------------------------
    device = b.groupby("device")["with_saf"].mean().mul(100).round(1).to_dict()

    return {
        "period": {"start": "2026-07-01", "end": "2026-10-31", "label": "1 July – 31 October 2026"},
        "totals": totals,
        "monthly": monthly_out,
        "choices": choices,
        "routes": routes_out,
        "funnel": funnel,
        "uptake_by_device_pct": device,
    }


def main() -> dict:
    bookings, traffic = load()
    kpis = compute(bookings, traffic)
    BUILD.mkdir(exist_ok=True)
    (BUILD / "kpis.json").write_text(json.dumps(kpis, indent=2))
    t = kpis["totals"]
    print(f"Bookings {t['bookings']:,} | passengers {t['passengers']:,} | GBV €{t['gross_booking_value_eur']:,.0f}")
    print(f"SAF uptake {t['saf_uptake_pct']:.1f}% ({t['uptake_change_pp']:+.1f} pp Jul→Oct) | SAF {t['saf_litres']:,.0f} L | €{t['saf_contributions_eur']:,.0f}")
    print(f"CO2e avoided {t['co2e_avoided_t']:.1f} t of {t['co2e_total_t']:.0f} t ({t['co2e_avoided_share_pct']:.1f}%)")
    print(f"Repeat bookings {t['repeat_booking_share_pct']:.1f}% | certificates {t['certificates_issued']:,} | conv {t['session_to_booking_pct']:.2f}%")
    return kpis


if __name__ == "__main__":
    main()
