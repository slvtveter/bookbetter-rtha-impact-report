"""Small, dependency-free SVG chart builders for the one-pager.

Design rules (kept deliberately boring so the data is the loud part):
- bars <= 24px thick, 4px rounded data-end, square at the baseline
- 2px surface gap between touching fills (stacked segments)
- hairline solid gridlines, muted axis text, no dashed lines, no dual axes
- text always in text tokens, never in the series colour
- one hue for one series; ordinal blue ramp for ordered parts; gray = "no SAF"
"""
from __future__ import annotations

from html import escape

# Colour roles (light surface). Values from a validated palette, see README.
SURFACE = "#ffffff"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e6e5df"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"
BLUE_RAMP = ["#1c5cab", "#2a78d6", "#5598e7", "#86b6ef"]  # ordinal, dark -> light
GRAY_FILL = "#d3d2cb"                                      # de-emphasis / "no SAF"
FONT = "font-family='Manrope, system-ui, -apple-system, Segoe UI, sans-serif'"


def fmt_int(n: float) -> str:
    return f"{int(round(n)):,}"




def _nice_ceiling(v: float, steps: int = 3) -> tuple[float, float]:
    """Round the axis top to a clean number and return (top, step)."""
    import math

    raw = v / steps
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step * steps >= v:
            return step * steps, step
    return raw * steps, raw


def _rounded_top_rect(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Rect with rounded top corners only (data-end), square at the baseline."""
    r = min(r, h / 2, w / 2)
    return (
        f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z"
    )


def _rounded_right_rect(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Horizontal bar: rounded right end (data-end), square at the left baseline."""
    r = min(r, h / 2, w / 2)
    return (
        f"M{x:.1f},{y:.1f} H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"V{y + h - r:.1f} Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} H{x:.1f} Z"
    )


def _text(x, y, s, size=11, fill=INK_2, anchor="start", weight=400, extra="") -> str:
    return (
        f"<text x='{x:.1f}' y='{y:.1f}' font-size='{size}' fill='{fill}' text-anchor='{anchor}' "
        f"font-weight='{weight}' {FONT} {extra}>{escape(str(s))}</text>"
    )


# ---------------------------------------------------------------------------------
# 1. Stacked columns: bookings per month, split into with / without SAF
# ---------------------------------------------------------------------------------
def stacked_columns(monthly: list[dict], width=324, height=166) -> str:
    pad_l, pad_r, pad_t, pad_b = 34, 8, 26, 40
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    top, step = _nice_ceiling(max(m["bookings"] for m in monthly) * 1.08)
    sy = plot_h / top
    n = len(monthly)
    slot = plot_w / n
    bar_w = 24
    gap = 2
    out = [f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}' role='img' aria-label='Bookings per month, with and without SAF contribution'>"]

    # gridlines + y ticks
    v = 0.0
    while v <= top + 1e-6:
        y = pad_t + plot_h - v * sy
        out.append(f"<line x1='{pad_l}' x2='{width - pad_r}' y1='{y:.1f}' y2='{y:.1f}' stroke='{GRID if v else BASELINE}' stroke-width='1'/>")
        out.append(_text(pad_l - 6, y + 3.5, fmt_int(v), 9.5, MUTED, "end"))
        v += step

    # legend (two series -> legend required)
    lx = pad_l
    out.append(f"<rect x='{lx}' y='4' width='10' height='10' rx='2' fill='{BLUE}'/>")
    out.append(_text(lx + 14, 13, "With SAF contribution", 10, INK_2))
    lx2 = lx + 150
    out.append(f"<rect x='{lx2}' y='4' width='10' height='10' rx='2' fill='{GRAY_FILL}'/>")
    out.append(_text(lx2 + 14, 13, "Without", 10, INK_2))

    for i, m in enumerate(monthly):
        x = pad_l + slot * i + (slot - bar_w) / 2
        base_y = pad_t + plot_h
        h_with = m["with_saf"] * sy
        h_without = m["without_saf"] * sy
        # bottom segment: with SAF (blue), square at baseline
        out.append(f"<rect x='{x:.1f}' y='{base_y - h_with:.1f}' width='{bar_w}' height='{h_with:.1f}' fill='{BLUE}'>"
                   f"<title>{m['label']}: {fmt_int(m['with_saf'])} bookings with SAF ({m['uptake_pct']:.0f}%)</title></rect>")
        # top segment: without SAF (gray), 2px surface gap, rounded data-end
        y_top = base_y - h_with - gap - h_without
        out.append(f"<path d='{_rounded_top_rect(x, y_top, bar_w, max(h_without - 0, 0))}' fill='{GRAY_FILL}'>"
                   f"<title>{m['label']}: {fmt_int(m['without_saf'])} bookings without SAF</title></path>")
        # cap label: total bookings
        out.append(_text(x + bar_w / 2, y_top - 5, fmt_int(m["bookings"]), 10.5, INK, "middle", 600))
        # x label + uptake share
        out.append(_text(x + bar_w / 2, base_y + 15, m["label"], 10.5, INK_2, "middle"))
        out.append(_text(x + bar_w / 2, base_y + 29, f"{m['uptake_pct']:.0f}% SAF", 9.5, MUTED, "middle"))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------------
# 2. Tall segmented bar: what travellers did with the 10 % default
# ---------------------------------------------------------------------------------
def segmented_bar(choices: list[dict], width=324, bar_h=32) -> str:
    fills = {
        "increased": BLUE_RAMP[0],
        "kept_default": BLUE_RAMP[1],
        "reduced": BLUE_RAMP[3],
        "switched_off": GRAY_FILL,
    }
    gap = 2
    total_gap = gap * (len(choices) - 1)
    height = bar_h + 8 + 2 * 18  # bar + legend (two rows)
    out = [f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}' role='img' aria-label='Share of bookings by SAF choice'>"]
    x = 0.0
    for c in choices:
        w = (width - total_gap) * c["share_pct"] / 100
        fill = fills[c["key"]]
        label = f"{c['share_pct']:.0f}%"
        out.append(f"<rect x='{x:.1f}' y='0' width='{w:.1f}' height='{bar_h}' rx='4' fill='{fill}'>"
                   f"<title>{c['label']}: {c['share_pct']:.1f}% ({fmt_int(c['bookings'])} bookings)</title></rect>")
        text_w = 7 * len(label) + 2
        if w >= text_w + 12:  # only print where it fits with padding
            ink = "#ffffff" if c["key"] in ("increased", "kept_default") else INK
            out.append(_text(x + 7, bar_h / 2 + 4, label, 11, ink, "start", 600))
        x += w + gap
    # legend: names only, block order, two rows
    lx, ly = 0, bar_h + 22
    for i, c in enumerate(choices):
        col, row = i % 2, i // 2
        px = lx + col * (width // 2)
        py = ly + row * 18
        out.append(f"<rect x='{px}' y='{py - 9}' width='10' height='10' rx='2' fill='{fills[c['key']]}'/>")
        out.append(_text(px + 14, py, c["label"], 10, INK_2))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------------
# 3. Ranked horizontal bars: routes by CO2e avoided (one hue)
# ---------------------------------------------------------------------------------
def ranked_bars(routes: list[dict], width=324, max_rows=8, row_h=20, bar_h=13) -> str:
    rows = routes[:max_rows]
    label_w, val_w = 112, 44
    plot_w = width - label_w - val_w
    vmax = max(r["co2e_avoided_t"] for r in rows)
    height = row_h * len(rows) + 4
    out = [f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}' role='img' aria-label='CO2e avoided by route'>"]
    base_x = label_w
    out.append(f"<line x1='{base_x}' x2='{base_x}' y1='0' y2='{height}' stroke='{BASELINE}' stroke-width='1'/>")
    for i, r in enumerate(rows):
        y = 2 + i * row_h
        w = plot_w * r["co2e_avoided_t"] / vmax
        fill = BLUE
        tip = f"{r['destination']}: {r['co2e_avoided_t']:.1f} t CO2e avoided, {fmt_int(r['bookings'])} bookings, {r['uptake_pct']:.0f}% uptake"
        out.append(f"<path d='{_rounded_right_rect(base_x, y + (row_h - bar_h) / 2, w, bar_h)}' fill='{fill}'><title>{escape(tip)}</title></path>")
        out.append(_text(base_x - 8, y + row_h / 2 + 4, r["destination"], 10.5, INK_2, "end"))
        out.append(_text(base_x + w + 6, y + row_h / 2 + 4, f"{r['co2e_avoided_t']:.1f} t", 10, INK, "start", 600))
    out.append("</svg>")
    return "".join(out)
