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
    """One continuous 2024–2026 board; the snake grows on active days.

    Source is always GitHub GraphQL, never synthetic contributions. Every visited
    tile becomes transparent (the whole tile, not just a change of color).
    """
    bg = "#0D1117" if dark else "#FFFFFF"
    fg = "#DFE9F8" if dark else "#26344C"
    muted = "#91A8BC" if dark else "#657B8E"
    colors = (
        ["#263348", "#124254", "#176D88", "#178FAA", "#05C5E8"]
        if dark else
        ["#E8EDF4", "#C8E9F3", "#91CEE4", "#47A8C8", "#1385AB"]
    )
    head_color = "#74E9FF" if dark else "#0679A5"
    body_color = "#00BBDD" if dark else "#0B91B2"
    dates = sorted(
        (day, number) for year in YEARS for day, number in history[year].items()
        if day <= datetime.now(timezone.utc).date().isoformat()
    )
    if not dates:
        raise RuntimeError("No real GitHub contribution dates")
    if dates[0][0] != "2024-01-01":
        raise RuntimeError("Incomplete contribution history: 2024 must start on January 1")

    cols, step, x0, y0 = 54, 14, 88, 93
    duration = 156  # About 6.5 tiles per second: moderate and easy to follow.
    positions = []
    css = [
        f".board{{fill:{bg}}}",
        f".heading{{fill:{fg};font:700 22px system-ui,sans-serif;letter-spacing:.4px}}",
        f".caption{{fill:{muted};font:13px system-ui,sans-serif}}",
        ".tile{shape-rendering:geometricPrecision}",
        ".body{fill:none;stroke-linecap:round;stroke-linejoin:round;stroke-width:10}",
        f".body{{stroke:{body_color};filter:drop-shadow(0 0 2px {body_color})}}",
        f".snake-head{{fill:{head_color};filter:drop-shadow(0 0 4px {head_color})}}",
        "@media (prefers-reduced-motion:reduce){.body,.snake-head{animation:none!important;"
        "opacity:0!important}.tile{animation:none!important;opacity:1!important}}",
    ]
    tiles = []
    active = 0
    n = len(dates)
    for i, (day, amount) in enumerate(dates):
        row, offset = divmod(i, cols)
        col = offset if row % 2 == 0 else cols - 1 - offset
        x, y = x0 + col * step, y0 + row * step
        cx, cy = x + 5.5, y + 5.5
        positions.append((cx, cy, amount > 0))
        level = 0 if amount == 0 else 1 if amount == 1 else 2 if amount <= 3 else 3 if amount <= 7 else 4
        # The rectangle vanishes completely as the snake's head reaches it.
        t = (i + 0.35) * 100 / n
        after = min(t + 0.035, 99.95)
        key = f"e{i}"
        css.append(
            f"@keyframes {key}{{0%,{t:.3f}%{{opacity:1}}"
            f"{after:.3f}%,99.97%{{opacity:0}}100%{{opacity:1}}}}"
            f".{key}{{animation:{key} {duration}s linear infinite}}"
        )
        tiles.append(
            f'<rect class="tile {key}" x="{x}" y="{y}" width="11" height="11" '
            f'rx="2.6" fill="{colors[level]}"/>'
        )

    # Each day is adjacent to the next; the path crosses rows without jumping.
    path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y, _ in positions)
    length = (n - 1) * step
    gap = length + 240
    path_animations = []
    head_animations = []
    for i, (cx, cy, has_activity) in enumerate(positions):
        if has_activity:
            active += 1
        travelled = i * step
        body_length = min(travelled, (3 + active) * step)
        tail_start = travelled - body_length
        percent = i * 100 / (n - 1)
        head_animations.append(
            f"{percent:.4f}%{{transform:translate({cx:.1f}px,{cy:.1f}px)}}"
        )
        path_animations.append(
            f"{percent:.4f}%{{stroke-dasharray:{body_length:.1f}px {gap}px;"
            f"stroke-dashoffset:{-tail_start:.1f}px}}"
        )

    css.extend([
        f"@keyframes follow{{{''.join(head_animations)}}}",
        f"@keyframes grow{{{''.join(path_animations)}}}",
        f".snake-head{{animation:follow {duration}s linear infinite}}",
        f".body{{animation:grow {duration}s linear infinite}}",
    ])
    markup = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 930 420" '
        'width="930" height="420" role="img" '
        'aria-label="Uma única cobrinha percorre as contribuições de 2024, 2025 e 2026; '
        'os quadrados desaparecem e a cobra cresce nos dias de atividade">',
        '<title>Minha jornada no código · 2024 — 2026</title>',
        '<desc>Calendário contínuo de contribuições reais. A cobra come cada quadrado inteiro, '
        'e seu corpo cresce quando encontra um dia com contribuições.</desc>',
        '<style>',
        *css,
        '</style>',
        '<rect class="board" width="930" height="420" rx="18"/>',
        '<text class="heading" x="28" y="42">MINHA JORNADA NO CÓDIGO</text>',
        '<text class="caption" x="28" y="63">2024 — 2025 — 2026 · Um único caminho</text>',
        *tiles,
        f'<path class="body" d="{path}" stroke-dasharray="0 {gap}" stroke-dashoffset="0"/>',
        '<g class="snake-head">',
        '<rect x="-7" y="-7" width="14" height="14" rx="4.5"/>',
        f'<circle cx="3" cy="-2.5" r="1.3" fill="{bg}"/>',
        f'<circle cx="3" cy="2.5" r="1.3" fill="{bg}"/>',
        '</g>',
        '</svg>',
    ]
    return "\n".join(markup) + "\n"


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
