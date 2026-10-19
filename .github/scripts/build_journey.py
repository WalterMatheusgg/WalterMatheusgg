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
    """Small real-contribution grid, with alternating shuffled snake routes.

    Pure SVG/CSS cannot generate true runtime randomness inside a GitHub README.
    Instead, preload 20 different randomized rounds and regenerate them daily.
    Every round starts AND ends at the same top-left corner, with no teleport.
    Only positive-contribution squares are eaten; empty squares stay intact.
    """
    import math
    import random

    colors = (
        ["#243148", "#134759", "#19768A", "#11A0B7", "#00D9FF"]
        if dark else
        ["#E8EDF4", "#C9E7F1", "#8BCADD", "#48ABC8", "#087EA5"]
    )
    background = "#0D1117" if dark else "#FFFFFF"
    head_color = "#5AE6FF" if dark else "#057BA8"
    body_color = "#11BCD8" if dark else "#127FA3"
    today = datetime.now(timezone.utc).date()
    dates = sorted(
        (date.fromisoformat(day), count)
        for year in YEARS for day, count in history[year].items()
        if date.fromisoformat(day) <= today
    )
    if not dates:
        raise ValueError("No real contribution dates available")

    WIDTH, HEIGHT, COLS = 670, 112, 90
    STEP, X0, Y0, TILE = 6.35, 42, 20, 5.0
    HOME = (17.0, 17.0)
    LAP_TIME = 28.5
    LAPS = 20
    DURATION = LAP_TIME * LAPS

    base_cells = []
    targets = []
    for i, (day, count) in enumerate(dates):
        row, col = divmod(i, COLS)
        x, y = X0 + col * STEP, Y0 + row * STEP
        level = 0 if count == 0 else 1 if count == 1 else 2 if count <= 3 else 3 if count <= 7 else 4
        if count > 0:
            targets.append((i, x, y, colors[level]))
        else:
            base_cells.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{TILE}" height="{TILE}" '
                f'rx="1.2" fill="{colors[0]}"/>'
            )
    if not targets:
        raise ValueError("No real contributed squares to animate")
    seed = int(today.strftime("%Y%m%d"))
    styles = [
        f".panel{{fill:{background}}}",
        f".body{{fill:none;stroke:{body_color};stroke-width:4.4;"
        "stroke-linecap:round;stroke-linejoin:round}}",
        f".head{{fill:{head_color}}}",
        ".scene{opacity:0}.scene0{opacity:1}",
        ".tile{shape-rendering:geometricPrecision}",
        "@media (prefers-reduced-motion:reduce){"
        ".scene{animation:none!important;opacity:0!important}"
        ".scene0{opacity:1!important}"
        ".head,.body{animation:none!important;opacity:0!important}"
        ".tile{animation:none!important;opacity:1!important}}",
    ]
    scenes = []
    prior_route = None
    for lap in range(LAPS):
        order = targets[:]
        random.Random(seed * 131 + lap * 99991).shuffle(order)
        if [x[0] for x in order] == prior_route:
            order = order[1:] + order[:1]
        prior_route = [x[0] for x in order]
        pts = [(None, *HOME, None)] + [
            (i, x + TILE / 2, y + TILE / 2, color)
            for i, x, y, color in order
        ] + [(None, *HOME, None)]
        distances = [0.0]
        for p1, p2 in zip(pts, pts[1:]):
            distances.append(
                distances[-1] + math.hypot(p2[1] - p1[1], p2[2] - p1[2])
            )
        total = distances[-1]
        if total <= 0:
            raise ValueError("Cannot animate an empty route")
        # Travel from home to all targets and home over 97% of each lap.
        # The final ~0.85 s is spent quietly resting in the same corner.
        progress = [d / total * 97 for d in distances]
        progress.append(100.0)
        pts.append(pts[-1])
        target_times = {
            index: percentage for (index, *_), percentage in zip(pts, progress)
            if index is not None
        }
        move_frames = []
        body_frames = []
        growing = 0
        for (index, x, y, _), d, p in zip(pts, distances + [total], progress):
            if index is not None:
                growing += 1
            travelled = d
            # Compact snake, growing with each actual contribution eaten.
            snake_length = min(travelled, 9.0 + growing * 1.15, 66.0)
            tail = max(0.0, travelled - snake_length)
            if p == 100.0:
                snake_length = 0.0
                tail = travelled
            move_frames.append(
                f"{p:.4f}%{{transform:translate({x:.2f}px,{y:.2f}px)}}"
            )
            # Four dash entries: invisible prefix, visible body, invisible rest.
            body_frames.append(
                f"{p:.4f}%{{stroke-dasharray:0px {tail:.2f}px "
                f"{snake_length:.2f}px {total + 100:.2f}px}}"
            )
        styles.extend([
            f"@keyframes move{lap}{{{''.join(move_frames)}}}",
            f"@keyframes body{lap}{{{''.join(body_frames)}}}",
            f".head{lap}{{animation:move{lap} {LAP_TIME}s linear infinite}}",
            f".body{lap}{{animation:body{lap} {LAP_TIME}s linear infinite}}",
        ])

        beginning = lap / LAPS * 100
        ending = (lap + 1) / LAPS * 100
        epsilon = 0.0007
        if lap == 0:
            visibility = (
                f"0%,{ending-epsilon:.4f}%{{opacity:1}}"
                f"{ending+epsilon:.4f}%,100%{{opacity:0}}"
            )
        else:
            visibility = (
                f"0%,{beginning-epsilon:.4f}%{{opacity:0}}"
                f"{beginning+epsilon:.4f}%,{ending-epsilon:.4f}%{{opacity:1}}"
                + (f"{ending+epsilon:.4f}%,100%{{opacity:0}}"
                   if lap < LAPS - 1 else "100%{opacity:0}")
            )
        styles.append(f"@keyframes scene{lap}{{{visibility}}}")
        styles.append(
            f".scene{lap}{{animation:scene{lap} {DURATION}s linear infinite}}"
        )

        scene = [f'<g class="scene scene{lap}">']
        for index, x, y, color in order:
            t = target_times[index]
            disappear = min(99.90, t + 0.075)
            # Fully remove each colored square, leaving transparent space.
            anim = f"eat{lap}_{index}"
            styles.extend([
                f"@keyframes {anim}{{0%,{t:.4f}%{{opacity:1}}"
                f"{disappear:.4f}%,100%{{opacity:0}}}}",
                f".{anim}{{animation:{anim} {LAP_TIME}s linear infinite}}",
            ])
            scene.append(
                f'<rect class="tile {anim}" x="{x:.2f}" y="{y:.2f}" '
                f'width="{TILE}" height="{TILE}" rx="1.2" fill="{color}"/>'
            )
        path = "M " + " L ".join(
            f"{x:.2f} {y:.2f}" for _, x, y, _ in pts[:-1]
        )
        scene.append(
            f'<path class="body body{lap}" d="{path}" '
            f'stroke-dasharray="0 {total+100:.2f}" />'
        )
        scene.extend([
            f'<g class="head head{lap}">',
            '<rect x="-3.1" y="-3.1" width="6.2" height="6.2" rx="2.0"/>',
            f'<circle cx="1.3" cy="-1.1" r=".6" fill="{background}"/>',
            f'<circle cx="1.3" cy="1.1" r=".6" fill="{background}"/>',
            '</g>',
            '</g>',
        ])
        scenes.extend(scene)

    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" '
        'aria-label="Cobrinha compacta de contribuições reais, rotas variadas e '
        'retorno suave ao canto a cada rodada">',
        '<title>Cobrinha animada de contribuições · 2024–2026</title>',
        '<desc>Vinte rotas pré-embaralhadas alternam entre as rodadas; '
        'cada percurso começa e termina no mesmo canto. Apenas dias com '
        'contribuições são comidos.</desc>',
        '<style>', *styles, '</style>',
        f'<rect class="panel" width="{WIDTH}" height="{HEIGHT}" rx="10"/>',
        *base_cells, *scenes, '</svg>', '',
    ])


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
