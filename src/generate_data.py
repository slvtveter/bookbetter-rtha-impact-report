"""Generate an illustrative (fully synthetic) dataset for the BookBetter x RTHA
white-label booking engine, 1 July - 31 October 2026.

Nothing here is real data. The volumes, prices and shares are invented to tell a
plausible story; the physical constants (emission factors, SAF reduction) are
rounded public figures and are documented in README.md.

Outputs
-------
data/bookings.csv        one row per booking made through the RTHA booking engine
data/engine_traffic.csv  one row per day: sessions, searches, bookings (funnel)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SEED = 42
PERIOD_START = pd.Timestamp("2026-07-01")  # partnership go-live
PERIOD_END = pd.Timestamp("2026-10-31")

# --- Physical / commercial assumptions (documented in README) -----------------
CO2E_AVOIDED_PER_LITRE_SAF_KG = 2.0   # ~80 % lifecycle reduction vs ~2.5 kg CO2e per litre fossil jet
SAF_PREMIUM_EUR_PER_LITRE = 2.0        # traveller pays the price gap between SAF and fossil jet fuel
PARTNER_REVENUE_SHARE = 0.025          # illustrative share of gross booking value paid to RTHA

# Destinations served from Rotterdam The Hague Airport (great-circle km, rounded)
DESTINATIONS = pd.DataFrame(
    [
        ("Barcelona", 1240, 0.14),
        ("Alicante", 1700, 0.12),
        ("Malaga", 1870, 0.11),
        ("Faro", 1950, 0.09),
        ("Lisbon", 1880, 0.09),
        ("London City", 320, 0.10),
        ("Vienna", 960, 0.07),
        ("Nice", 1020, 0.06),
        ("Porto", 1620, 0.06),
        ("Palma de Mallorca", 1480, 0.07),
        ("Valencia", 1530, 0.05),
        ("Marrakech", 2420, 0.04),
    ],
    columns=["destination", "distance_km", "weight"],
)

# Probabilities of what travellers do with the default 10 % SAF contribution,
# per month. The story: the default is mostly kept, and opt-out slowly falls.
SAF_CHOICE_BY_MONTH = {
    #          kept default, increased, reduced, switched off
    "2026-07": (0.56, 0.07, 0.07, 0.30),
    "2026-08": (0.58, 0.08, 0.06, 0.28),
    "2026-09": (0.61, 0.10, 0.05, 0.24),
    "2026-10": (0.62, 0.11, 0.05, 0.22),
}
INCREASED_LEVELS = ([20, 30, 50], [0.55, 0.30, 0.15])  # % of emissions covered when increased


def emission_factor_kg_per_pkm(distance_km: float) -> float:
    """Approximate CO2e per passenger-km; short hops are less efficient per km."""
    if distance_km < 800:
        return 0.17
    if distance_km < 1600:
        return 0.14
    return 0.12


def daily_volume(day: pd.Timestamp, rng: np.random.Generator) -> int:
    """Expected bookings per day: launch ramp in July, summer peak, autumn-break bump."""
    base = 30.0
    month_mult = {7: 0.85, 8: 1.25, 9: 0.95, 10: 1.05}[day.month]
    if day.month == 7:  # first weeks after go-live ramp up
        base *= 0.55 + 0.45 * min(day.day / 20, 1.0)
    weekday_mult = {0: 1.15, 1: 1.0, 2: 0.95, 3: 0.95, 4: 0.9, 5: 0.85, 6: 1.2}[day.weekday()]
    return int(rng.poisson(base * month_mult * weekday_mult))


def pick(rng: np.random.Generator, options: list, p: list[float]):
    """Weighted choice that returns the Python object itself (keeps str/int types)."""
    return options[int(rng.choice(len(options), p=p))]


def generate_bookings(rng: np.random.Generator) -> pd.DataFrame:
    days = pd.date_range(PERIOD_START, PERIOD_END, freq="D")
    rows = []
    customers: list[str] = []
    booking_no = 0
    dest_records = DESTINATIONS.to_dict("records")
    dest_weights = (DESTINATIONS["weight"] / DESTINATIONS["weight"].sum()).tolist()
    choice_keys = ["kept_default", "increased", "reduced", "switched_off"]

    for day in days:
        n = daily_volume(day, rng)
        month_key = day.strftime("%Y-%m")
        p_choice = list(SAF_CHOICE_BY_MONTH[month_key])
        for _ in range(n):
            booking_no += 1
            dest = pick(rng, dest_records, dest_weights)
            pax = pick(rng, [1, 2, 3, 4], [0.35, 0.40, 0.12, 0.13])
            trip_type = "return" if rng.random() < 0.72 else "one-way"
            legs = 2 if trip_type == "return" else 1

            # fare per passenger per leg: distance-driven, summer premium, noise
            distance = dest["distance_km"]
            fare_leg = 45 + 0.055 * distance
            fare_leg *= 1.18 if day.month == 8 else 1.0
            fare_leg *= float(rng.lognormal(0, 0.22))
            gross_eur = round(fare_leg * legs * pax, 2)

            co2e_per_pax = distance * emission_factor_kg_per_pkm(distance) * legs
            co2e_total = co2e_per_pax * pax

            choice = pick(rng, choice_keys, p_choice)
            if choice == "kept_default":
                pct = 10
            elif choice == "increased":
                pct = pick(rng, INCREASED_LEVELS[0], INCREASED_LEVELS[1])
            elif choice == "reduced":
                pct = 5
            else:
                pct = 0
            co2e_avoided = co2e_total * pct / 100
            saf_litres = co2e_avoided / CO2E_AVOIDED_PER_LITRE_SAF_KG
            contribution = saf_litres * SAF_PREMIUM_EUR_PER_LITRE

            # repeat customers: a growing pool, ~1 in 8 bookings from a returning traveller
            if customers and rng.random() < 0.13:
                customer_id = customers[int(rng.integers(0, len(customers)))]
            else:
                customer_id = f"C{len(customers) + 1:05d}"
                customers.append(customer_id)

            lead_days = int(np.clip(rng.gamma(2.2, 14), 1, 120))
            departure = day + pd.Timedelta(days=lead_days)
            last_flight = departure + pd.Timedelta(days=int(rng.integers(2, 15))) if legs == 2 else departure
            certificate_issued = bool(pct > 0 and last_flight <= PERIOD_END)

            rows.append(
                {
                    "booking_id": f"RTM-{booking_no:06d}",
                    "booking_date": day.date(),
                    "departure_date": departure.date(),
                    "destination": dest["destination"],
                    "distance_km": int(distance),
                    "trip_type": trip_type,
                    "passengers": pax,
                    "device": "mobile" if rng.random() < 0.58 else "desktop",
                    "customer_id": customer_id,
                    "gross_booking_value_eur": gross_eur,
                    "co2e_kg": round(co2e_total, 1),
                    "saf_choice": choice,
                    "saf_coverage_pct": pct,
                    "saf_litres": round(saf_litres, 2),
                    "saf_contribution_eur": round(contribution, 2),
                    "co2e_avoided_kg": round(co2e_avoided, 1),
                    "certificate_issued": certificate_issued,
                }
            )
    return pd.DataFrame(rows)


def generate_traffic(bookings: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Daily funnel for the booking engine: sessions -> searches -> bookings."""
    per_day = bookings.groupby("booking_date").size().rename("bookings").reset_index()
    per_day["booking_date"] = pd.to_datetime(per_day["booking_date"])
    conv = 0.021 + rng.normal(0, 0.002, len(per_day))        # ~2 % session-to-booking
    per_day["sessions"] = (per_day["bookings"] / conv).round().astype(int)
    search_rate = 0.62 + rng.normal(0, 0.03, len(per_day))
    per_day["searches"] = (per_day["sessions"] * search_rate).round().astype(int)
    per_day["booking_date"] = per_day["booking_date"].dt.date
    return per_day[["booking_date", "sessions", "searches", "bookings"]]


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA.mkdir(exist_ok=True)
    bookings = generate_bookings(rng)
    traffic = generate_traffic(bookings, rng)
    bookings.to_csv(DATA / "bookings.csv", index=False)
    traffic.to_csv(DATA / "engine_traffic.csv", index=False)
    print(f"bookings: {len(bookings):,} rows -> {DATA / 'bookings.csv'}")
    print(f"traffic:  {len(traffic):,} rows -> {DATA / 'engine_traffic.csv'}")


if __name__ == "__main__":
    main()
