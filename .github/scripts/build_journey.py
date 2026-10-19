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
    """A proper pixel snake consumes the ENTIRE calendar square, not just its color.

    Three accurate contribution boards (2024/2025/2026). CSS hides each SVG
    rectangle after the snake visits it and restores all rectangles at loop end.
    No invented contributions or fake activity.
    """
    bg = "#0D1117" if dark else "#FFFFFF"
    fg = "#E7F1FF" if dark else "#27374E"
    muted = "#98AAC0" if dark else "#697B90"
    empty = "#263348" if dark else "#E8EDF4"
    levels = [empty] + (
        ["#124254", "#176D88", "#178FAA", "#05C5E8"]
        if dark else ["#C8E9F3", "#91CEE4", "#47A8C8", "#1385AB"]
    )
    snake = "#5FE8FF" if dark else "#007DA5"
    body = "#2FC6DE" if dark else "#279FC3"
    duration = 42
    css = [
        f".background{{fill:{bg}}}",
        f".year{{fill:{fg};font:700 19px system-ui,sans-serif}}",
        f".summary{{fill:{muted};font:12px system-ui,sans-serif}}",
        ".tile{shape-rendering:geometricPrecision}",
        f".moving{{filter:drop-shadow(0 0 2.5px {snake})}}",
        f"@media (prefers-reduced-motion:reduce){{.moving{{display:none}}"
        ".tile{animation:none!important;opacity:1!important}}",
    ]
    shapes = [
        '<rect class="background" width="930" height="446" rx="15"/>',
    ]
    today = datetime.now(timezone.utc).date()
    for idx, year in enumerate(YEARS):
        top = 17 + idx * 142
        first = date(year, 1, 1)
        sunday = first - timedelta(days=(first.weekday() + 1) % 7)
        cols = ((date(year, 12, 31) - sunday).days // 7) + 1
        entries = history[year]
        total = sum(entries.values())
        active = sum(v > 0 for v in entries.values())
        shapes.extend([
            f'<text class="year" x="24" y="{top+58}">{year}</text>',
            f'<text class="summary" x="908" y="{top+17}" text-anchor="end">'
            f'{total} contribuições · {active} dias ativos</text>',
        ])
        y0 = top + 31
        cells = {}
        for col in range(cols):
            for day_of_week in range(7):
                d = sunday + timedelta(days=col * 7 + day_of_week)
                if d.year != year or d > today:
                    continue
                count = entries.get(d.isoformat(), 0)
                level = 0 if count == 0 else 1 if count == 1 else 2 if count <= 3 else 3 if count <= 7 else 4
                x = 94 + col * 14
                y = y0 + day_of_week * 14
                cells[(col, day_of_week)] = (x, y, levels[level])

        # A real grid-following path: straight down one week, then up the next.
        path = []
        for col in range(cols):
            days = range(7) if col % 2 == 0 else range(6, -1, -1)
            for weekday in days:
                cell = cells.get((col, weekday))
                if cell:
                    path.append(cell)
        if len(path) < 2:
            raise RuntimeError(f"Cannot animate empty contribution grid for {year}")

        # One opacity animation per day; the cell itself vanishes entirely.
        for i, (x, y, color) in enumerate(path):
            eaten_at = (i + 0.36) * 100 / len(path)
            gone_at = min(eaten_at + 0.045, 99.93)
            animation = f"e{year}_{i}"
            css.append(
                f"@keyframes {animation}{{0%,{eaten_at:.3f}%{{opacity:1}}"
                f"{gone_at:.3f}%,99.96%{{opacity:0}}100%{{opacity:1}}}}"
                f".{animation}{{animation:{animation} {duration}s linear infinite}}"
            )
            shapes.append(
                f'<rect class="tile {animation}" x="{x}" y="{y}" width="11" height="11" '
                f'rx="2.6" fill="{color}"/>'
            )

        # Snake with a head and three following body segments, not three dots.
        keyframes = "".join(
            f"{i*100/(len(path)-1):.3f}%{{transform:translate({x+5.5:.1f}px,{y+5.5:.1f}px)}}"
            for i, (x, y, _) in enumerate(path)
        )
        css.append(f"@keyframes snake{year}{{{keyframes}}}")
        for n in range(3, 0, -1):
            css.append(
                f".tail{year}_{n}{{animation:snake{year} {duration}s linear infinite;"
                f"animation-delay:{n*duration/len(path):.3f}s;animation-fill-mode:backwards}}"
            )
            size = 12 - (n * 1.0)
            fill = body if n < 3 else snake
            shapes.append(
                f'<rect class="moving tail{year}_{n}" x="{-size/2:.1f}" y="{-size/2:.1f}" '
                f'width="{size:.1f}" height="{size:.1f}" rx="3.1" fill="{fill}"/>'
            )
        css.append(f".head{year}{{animation:snake{year} {duration}s linear infinite}}")
        shapes.extend([
            f'<g class="moving head{year}">',
            f'<rect x="-6.8" y="-6.8" width="13.6" height="13.6" rx="4" fill="{snake}"/>',
            f'<circle cx="2.6" cy="-2.6" r="1.2" fill="{bg}"/>',
            f'<circle cx="2.6" cy="2.6" r="1.2" fill="{bg}"/>',
            '</g>',
        ])
        if idx < len(YEARS) - 1:
            line = "#2D4057" if dark else "#E4EAF1"
            shapes.append(f'<path d="M 23 {top+135} H 907" stroke="{line}" stroke-width="1"/>')

    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 930 446" '
        'width="930" height="446" role="img" '
        'aria-label="Cobrinha que apaga completamente os quadrados das contribuições reais de 2024, 2025 e 2026">',
        '<title>Minha jornada no código — 2024, 2025, 2026</title>',
        '<desc>Uma cobrinha por ano percorre o calendário e remove cada quadrado por completo. '
        'Quando termina, o calendário é restaurado para recomeçar.</desc>',
        '<style>',
        *css,
        '</style>',
        *shapes,
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
