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
    bg = "#0D1117" if dark else "#FFFFFF"
    fg = "#DFE9F8" if dark else "#26344C"
    blank = "#253148" if dark else "#E8EDF4"
    levels = [blank] + (["#123E50", "#166E83", "#1595AF", "#00D9FF"] if dark
                        else ["#CAE9F5", "#90CCE4", "#49A7CC", "#147EAC"])
    snake = "#5FE9FF" if dark else "#086D9B"
    muted = "#8998AD" if dark else "#697A90"
    header = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 930 468" width="930" height="468"'
        ' role="img" aria-label="Cobrinhas animadas com contribuições reais em 2024, 2025 e 2026">',
        '<title>Minha jornada no código: 2024, 2025 e 2026</title>',
        '<desc>Os calendários refletem o histórico real do GitHub. Pontinhos extras são decorativos.</desc>',
        '<style>',
        f'.base{{fill:{bg}}}.label{{fill:{fg};font:700 20px system-ui,sans-serif}}',
        f'.small{{fill:{muted};font:12px system-ui,sans-serif}}',
        '@media (prefers-reduced-motion:reduce){.head,.tail,.dot{animation:none!important;opacity:0}}',
    ]
    shapes = ['<rect width="930" height="468" rx="18" class="base"/>']
    today = datetime.now(timezone.utc).date()

    for idx, year in enumerate(YEARS):
        top = 22 + idx * 142
        grid_y = top + 32
        first = date(year, 1, 1)
        sunday = first - timedelta(days=(first.weekday() + 1) % 7)
        cols = ((date(year, 12, 31) - sunday).days // 7) + 1
        entries = history[year]
        active = sum(count > 0 for count in entries.values())
        total = sum(entries.values())
        shapes.append(f'<text class="label" x="22" y="{top+48}">{year}</text>')
        shapes.append(f'<text class="small" x="917" y="{top+15}" text-anchor="end">'
                      f'{total} contribuições · {active} dias ativos</text>')

        for col in range(cols):
            for weekday in range(7):
                day = sunday + timedelta(days=col*7+weekday)
                if day.year != year or day > today:
                    continue
                val = entries.get(day.isoformat(), 0)
                strength = 0 if val == 0 else 1 if val == 1 else 2 if val <= 3 else 3 if val <= 7 else 4
                x, y = 92+col*14, grid_y+weekday*14
                shapes.append(f'<rect x="{x}" y="{y}" width="11" height="11" rx="2.8" fill="{levels[strength]}"/>')

        path = []
        for col in range(cols):
            for wd in (range(7) if col % 2 == 0 else range(6, -1, -1)):
                path.append((92+col*14+5.5, grid_y+wd*14+5.5))
        keys = ''.join(
            f'{i*100/(len(path)-1):.3f}%{{transform:translate({x:.1f}px,{y:.1f}px)}}'
            for i, (x,y) in enumerate(path)
        )
        header.append(f'@keyframes snake{year}{{{keys}}}')
        header.append(f'.head{year}{{animation:snake{year} 34s linear infinite;animation-delay:-.22s}}')
        header.append(f'.tail{year}{{animation:snake{year} 34s linear infinite}}')
        header.append(f'@keyframes twinkle{year}{{from{{opacity:.3}}to{{opacity:1}}}}')
        header.append(f'.dot{year}{{animation:twinkle{year} 2.2s ease-in-out infinite alternate}}')
        for col in range(3, cols-1, 6):
            wd=(col*3+2)%7
            day=sunday+timedelta(days=col*7+wd)
            if day.year==year and day<=today and entries.get(day.isoformat(),0)==0:
                shapes.append(f'<circle cx="{92+col*14+5.5}" cy="{grid_y+wd*14+5.5}" '
                              f'r="2.4" fill="{snake}" class="dot dot{year}"/>')
        shapes.append(f'<circle cx="0" cy="0" r="5" fill="{snake}" class="tail tail{year}"/>')
        shapes.append(f'<circle cx="0" cy="0" r="5.6" fill="{snake}" class="head head{year}"/>')
        if idx<2:
            shapes.append(f'<path d="M 22 {top+126} H 906" stroke="{blank}" stroke-width="1"/>')

    return "\n".join(header+["</style>"]+shapes+["</svg>"])+"\n"


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
