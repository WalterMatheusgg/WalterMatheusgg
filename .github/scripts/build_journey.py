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


def render(history: dict[int, dict[str, int]], dark: bool, seed: int) -> str:
    """Standard GitHub-like grid: exactly 53 weeks wide and SEVEN days high.

    The three real yearly histories are merged into 53 week/day slots: values
    for the same week-of-year and weekday are added together. This is one
    calendar visualization, NOT a claim that a day belongs to a specific year.
    Empty cells stay visible; only slots with actual contributions get eaten.
    SVG cannot truly randomize at each loop, so render 20 distinct shuffled
    routes and refresh them with a fresh seed whenever GitHub Actions runs.
    """
    import math
    import random

    colors = (
        ["#1D2938", "#13465A", "#16728F", "#11A4BE", "#00D9FF"]
        if dark else
        ["#EBEDF0", "#CEE8F1", "#9FCFE0", "#56AFCA", "#0E86AC"]
    )
    bg = "#0D1117" if dark else "#FFFFFF"
    snake_color = "#4EE1FC" if dark else "#1684B0"
    body_color = "#21C4E1" if dark else "#268FAF"

    # Align each calendar to Sunday -> Saturday, aggregate 2024/25/26 by
    # week-of-year and weekday. Exactly 7 rows, 53 columns.
    merged = {(week, weekday): 0 for week in range(53) for weekday in range(7)}
    today = datetime.now(timezone.utc).date()
    for year in YEARS:
        first = date(year, 1, 1)
        first_sunday = first - timedelta(days=(first.weekday() + 1) % 7)
        for date_str, count in history[year].items():
            current = date.fromisoformat(date_str)
            if current.year != year or current > today:
                continue
            week = (current - first_sunday).days // 7
            weekday = (current.weekday() + 1) % 7
            if not (0 <= week < 53):
                raise ValueError(f"Unexpected week index {week}: {date_str}")
            merged[(week, weekday)] += count

    WIDTH, HEIGHT = 830, 130
    STEP, TILE = 14.0, 11.0
    X0, Y0 = 55.0, 19.0
    HOME = (20.0, 20.0)
    LAP_TIME, LAPS = 28.5, 20
    PERIOD = LAP_TIME * LAPS

    blank_cells, active_cells = [], []
    for week in range(53):
        for weekday in range(7):
            x, y = X0 + week * STEP, Y0 + weekday * STEP
            count = merged[(week, weekday)]
            level = 0 if count == 0 else 1 if count == 1 else 2 if count <= 3 else 3 if count <= 7 else 4
            if count:
                active_cells.append((week * 7 + weekday, x, y, colors[level]))
            else:
                blank_cells.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{TILE:.1f}" '
                    f'height="{TILE:.1f}" rx="2.3" fill="{colors[0]}"/>'
                )
    if len(active_cells) < 2:
        raise RuntimeError("At least two contribution squares required")

    styles = [
        f".background{{fill:{bg}}}",
        f".body{{fill:none;stroke:{body_color};stroke-width:8;"
        "stroke-linecap:round;stroke-linejoin:round}",
        f".head{{fill:{snake_color}}}",
        ".scene{opacity:0}.scene0{opacity:1}",
        ".square{shape-rendering:geometricPrecision}",
        "@media (prefers-reduced-motion:reduce){"
        ".scene{animation:none!important;opacity:0!important}"
        ".scene0{opacity:1!important}"
        ".body,.head{animation:none!important;opacity:0!important}"
        ".square{animation:none!important;opacity:1!important}}",
    ]
    scenes = []
    previous = None
    for lap in range(LAPS):
        order = active_cells[:]
        random.Random(seed + lap * 1000003).shuffle(order)
        selected = tuple(item[0] for item in order)
        if selected == previous:
            order = order[1:] + order[:1]
        previous = tuple(item[0] for item in order)

        # An actual route back to HOME avoids jumping across the screen.
        points = [(None, *HOME)] + [
            (identifier, x + TILE / 2, y + TILE / 2)
            for identifier, x, y, _ in order
        ] + [(None, *HOME)]
        distances = [0.0]
        for left, right in zip(points, points[1:]):
            distances.append(
                distances[-1] + math.hypot(right[1]-left[1], right[2]-left[2])
            )
        path_length = distances[-1]
        if path_length == 0:
            raise RuntimeError("Invalid zero-length snake path")

        # Finish the route by 96.5%, then remain in HOME until the next lap.
        percent = [distance / path_length * 96.5 for distance in distances]
        points.append(points[-1])
        distances.append(path_length)
        percent.append(100.0)
        visiting = {
            identifier: progress
            for (identifier, _, _), progress in zip(points, percent)
            if identifier is not None
        }
        heads, bodies = [], []
        eaten = 0
        for (identifier, x, y), d, p in zip(points, distances, percent):
            if identifier is not None:
                eaten += 1
            # Short, recognizable snake grows as it eats, without taking over
            # the grid. At home it shrinks smoothly at the end of the lap.
            body_len = min(d, 11.0 + eaten * 1.5, 84.0)
            if p == 100.0:
                body_len = 0.0
            tail_offset = max(0.0, d - body_len)
            heads.append(
                f"{p:.4f}%{{transform:translate({x:.2f}px,{y:.2f}px)}}"
            )
            bodies.append(
                f"{p:.4f}%{{stroke-dasharray:0px {tail_offset:.2f}px "
                f"{body_len:.2f}px {path_length+120:.2f}px}}"
            )
        styles += [
            f"@keyframes move{lap}{{{''.join(heads)}}}",
            f"@keyframes grow{lap}{{{''.join(bodies)}}}",
            f".head{lap}{{animation:move{lap} {LAP_TIME}s linear infinite}}",
            f".body{lap}{{animation:grow{lap} {LAP_TIME}s linear infinite}}",
        ]

        beginning, ending = lap / LAPS * 100, (lap+1) / LAPS * 100
        e = .0006
        if lap == 0:
            visibility = (
                f"0%,{ending-e:.4f}%{{opacity:1}}"
                f"{ending+e:.4f}%,100%{{opacity:0}}"
            )
        else:
            visibility = (
                f"0%,{beginning-e:.4f}%{{opacity:0}}"
                f"{beginning+e:.4f}%,{ending-e:.4f}%{{opacity:1}}"
                + (f"{ending+e:.4f}%,100%{{opacity:0}}"
                   if lap < LAPS-1 else "100%{opacity:0}")
            )
        styles.extend([
            f"@keyframes scene{lap}{{{visibility}}}",
            f".scene{lap}{{animation:scene{lap} {PERIOD}s linear infinite}}",
        ])
        scene = [f'<g class="scene scene{lap}">']
        for identifier, x, y, color in order:
            p = visiting[identifier]
            end = min(p+.08, 99.9)
            cls = f"eat{lap}_{identifier}"
            styles.extend([
                f"@keyframes {cls}{{0%,{p:.4f}%{{opacity:1}}"
                f"{end:.4f}%,100%{{opacity:0}}}}",
                f".{cls}{{animation:{cls} {LAP_TIME}s linear infinite}}",
            ])
            scene.append(
                f'<rect class="square {cls}" x="{x:.1f}" y="{y:.1f}" '
                f'width="{TILE:.1f}" height="{TILE:.1f}" '
                f'rx="2.3" fill="{color}"/>'
            )
        path = "M " + " L ".join(f"{x:.2f} {y:.2f}" for _,x,y in points[:-1])
        scene.extend([
            f'<path class="body body{lap}" d="{path}" '
            f'stroke-dasharray="0 {path_length+120:.2f}"/>',
            f'<g class="head head{lap}">',
            '<rect x="-5.8" y="-5.8" width="11.6" height="11.6" rx="3.8"/>',
            f'<circle cx="2.3" cy="-2" r="1.0" fill="{bg}"/>',
            f'<circle cx="2.3" cy="2" r="1.0" fill="{bg}"/>',
            '</g>',
            '</g>',
        ])
        scenes += scene

    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
        f'role="img" aria-label="Grade GitHub com exatamente sete linhas: '
        f'contribuições de 2024, 2025 e 2026 reunidas em uma única visualização '
        f'e uma cobrinha que come apenas os dias com atividade">',
        '<title>Cobrinha: três anos reunidos em sete linhas</title>',
        '<desc>A atividade real dos três anos foi agregada pelo dia da semana e '
        'semana do ano. A cobrinha escolhe novas rotas predefinidas em cada '
        'rodada e retorna ao canto sem saltos.</desc>',
        '<style>', *styles, '</style>',
        f'<rect class="background" width="{WIDTH}" height="{HEIGHT}" rx="9"/>',
        *blank_cells, *scenes, '</svg>', '',
    ])


def main() -> None:
    if len(sys.argv)!=2:
        raise SystemExit("Usage: build_journey.py OUTPUT_DIRECTORY")
    data = github_calendar()
    folder=Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    import secrets
    seed = secrets.randbits(64)
    (folder/"journey-2024-2026.svg").write_text(render(data,False,seed),encoding="utf-8")
    (folder/"journey-2024-2026-dark.svg").write_text(render(data,True,seed),encoding="utf-8")
    print("Actual GitHub contribution totals:",{year:sum(data[year].values()) for year in YEARS})


if __name__=="__main__":
    main()
