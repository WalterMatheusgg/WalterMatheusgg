#!/usr/bin/env python3
"""Animated 2024–2026 contribution history. Values come from GitHub GraphQL only.

Extra glowing food is decorative and does NOT count as GitHub contributions.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

YEARS = (2024, 2025, 2026)
USER = "WalterMatheusgg"


def github_calendar() -> dict[int, dict[str, int]]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN: real contribution data is required")

    selections = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") '
        "{ contributionCalendar { weeks { contributionDays { date contributionCount } } } }"
        for y in YEARS
    )
    query = f'query {{ user(login: "{USER}") {{ {selections} }} }}'
    req = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "portfolio-journey"},
        method="POST",
    )
    with urlopen(req, timeout=35) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError("GitHub API: " + json.dumps(payload["errors"]))
    user = (payload.get("data") or {}).get("user")
    if user is None:
        raise RuntimeError("GitHub returned no user data")

    years = {}
    for year in YEARS:
        weeks = (((user.get(f"y{year}") or {}).get("contributionCalendar") or {}).get("weeks") or [])
        if not weeks:
            raise RuntimeError(f"No real GitHub contribution calendar for {year}")
        years[year] = {
            d["date"]: int(d["contributionCount"])
            for week in weeks for d in week["contributionDays"]
            if d["date"].startswith(str(year))
        }
    return years


def render(history: dict[int, dict[str, int]], dark: bool) -> str:
    """One compact 2024–2026 calendar; eat ONLY actual contribution days.

    The snake visits positive-count days in a seeded random order, grows a little
    with each eaten square, and completely removes that square from the image.
    Unvisited days and empty days remain visible. No fake contributions.
    """
    import math
    import random

    colors = (
        ["#263348", "#124254", "#176D88", "#178FAA", "#05C5E8"]
        if dark else
        ["#E8EDF4", "#C8E9F3", "#91CEE4", "#47A8C8", "#1385AB"]
    )
    bg = "#0D1117" if dark else "#FFFFFF"
    body_color = "#00BBDD" if dark else "#087FA5"
    head_color = "#70EAFF" if dark else "#006D99"
    today = datetime.now(timezone.utc).date()
    records = sorted(
        (date.fromisoformat(day), count)
        for year in YEARS for day, count in history[year].items()
        if date.fromisoformat(day) <= today
    )
    if not records:
        raise ValueError("No GitHub contribution dates available")

    ncols, step, x0, y0 = 54, 10, 45, 16
    duration = 28.5  # Same speed as the original, more compact snake.
    squares = []
    goals = []
    for i, (day, count) in enumerate(records):
        row, col = divmod(i, ncols)
        x, y = x0 + col * step, y0 + row * step
        intensity = 0 if count == 0 else 1 if count == 1 else 2 if count <= 3 else 3 if count <= 7 else 4
        squares.append((x, y, colors[intensity], count > 0))
        if count > 0:
            goals.append((i, x + 4, y + 4))

    if len(goals) < 2:
        raise ValueError("At least two actual contributed days are needed for a snake")
    rng = random.Random(20242026 + int(today.strftime("%Y%m%d")))
    rng.shuffle(goals)  # Actual contributions only; randomized on each daily rebuild.

    waypoints = []
    path_distance = 0.0
    for index, x, y in goals:
        if waypoints:
            px, py = waypoints[-1][1:3]
            path_distance += math.hypot(x - px, y - py)
        waypoints.append((index, x, y, path_distance))
    total_distance = path_distance
    if total_distance == 0:
        raise ValueError("Snake path cannot be zero length")

    path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for _, x, y, _ in waypoints)
    gap = total_distance + 500
    css = [
        f".board{{fill:{bg}}}",
        f".snake-body{{fill:none;stroke:{body_color};stroke-width:7.2;"
        "stroke-linecap:round;stroke-linejoin:round}}",
        f".snake-head{{fill:{head_color};filter:drop-shadow(0 0 2px {head_color})}}",
        ".sq{shape-rendering:geometricPrecision}",
        "@media (prefers-reduced-motion:reduce){.snake-body,.snake-head{"
        "animation:none!important;opacity:0!important}.sq{animation:none!important;opacity:1!important}}",
    ]

    # Segment lengths and keyframe times follow actual path distance:
    # the snake crosses empty cells but NEVER eats them.
    move_keys = []
    grow_keys = []
    eaten_at = {}
    for position, (square_index, x, y, travelled) in enumerate(waypoints):
        p = travelled / total_distance * 99.8
        length = min(travelled, 9.0 + (position + 1) * 2.4)
        start = max(0.0, travelled - length)
        move_keys.append(f"{p:.4f}%{{transform:translate({x:.1f}px,{y:.1f}px)}}")
        grow_keys.append(
            f"{p:.4f}%{{stroke-dasharray:{length:.1f}px {gap:.1f}px;"
            f"stroke-dashoffset:{-start:.1f}px}}"
        )
        eaten_at[square_index] = p

    move_keys.append(
        f"100%{{transform:translate({waypoints[0][1]:.1f}px,"
        f"{waypoints[0][2]:.1f}px)}}"
    )
    grow_keys.append(f"100%{{stroke-dasharray:0px {gap:.1f}px;stroke-dashoffset:0px}}")
    css.extend([
        f"@keyframes move{{{''.join(move_keys)}}}",
        f"@keyframes grow{{{''.join(grow_keys)}}}",
        f".snake-head{{animation:move {duration}s linear infinite}}",
        f".snake-body{{animation:grow {duration}s linear infinite}}",
    ])
    tiles = []
    for index, (x, y, color, has_contributions) in enumerate(squares):
        tile_class = "sq"
        if has_contributions:
            p = eaten_at[index]
            after = min(99.96, p + 0.055)
            name = f"eat{index}"
            css.append(
                f"@keyframes {name}{{0%,{p:.4f}%{{opacity:1}}"
                f"{after:.4f}%,99.97%{{opacity:0}}100%{{opacity:1}}}}"
                f".{name}{{animation:{name} {duration}s linear infinite}}"
            )
            tile_class += f" {name}"
        tiles.append(
            f'<rect class="{tile_class}" x="{x}" y="{y}" '
            f'width="8" height="8" rx="2" fill="{color}"/>'
        )
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 230" '
        'width="640" height="230" role="img" '
        'aria-label="Uma cobrinha rápida come em ordem aleatória só os quadrados com contribuições reais de 2024 a 2026">',
        '<title>Cobrinha de contribuições de 2024 a 2026</title>',
        '<style>', *css, '</style>',
        '<rect class="board" width="640" height="230" rx="12"/>',
        *tiles,
        f'<path class="snake-body" d="{path}" stroke-dasharray="0 {gap:.1f}" stroke-dashoffset="0"/>',
        '<g class="snake-head">',
        '<rect x="-5" y="-5" width="10" height="10" rx="3"/>',
        f'<circle cx="2.3" cy="-1.8" r="1.0" fill="{bg}"/>',
        f'<circle cx="2.3" cy="1.8" r="1.0" fill="{bg}"/>',
        '</g>',
        '</svg>',
    ]) + "\n"


def main() -> None:
    if len(sys.argv)!=2:
        raise SystemExit("Usage: build_journey.py OUTPUT_DIRECTORY")
    data = github_calendar()
    folder=Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"journey-2024-2026.svg").write_text(render(data,False),encoding="utf-8")
    (folder/"journey-2024-2026-dark.svg").write_text(render(data,True),encoding="utf-8")
    print("Actual GitHub contribution totals:",{year:sum(data[year].values()) for year in YEARS})


if __name__=="__main__":
    main()
