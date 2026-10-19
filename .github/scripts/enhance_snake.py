#!/usr/bin/env python3
"""Add decorative food dots along the existing contribution-snake path.

These dots are purely visual and do not represent additional GitHub contributions.
They fade out as the snake passes, and this step runs after each daily SVG generation.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_DOTS = 20
HEAD_FRAMES = re.compile(r"@keyframes s0\{(.*?)\}\.s\.s0", re.DOTALL)
POSITION = re.compile(
    r"(?P<times>\d+(?:\.\d+)?%(?:,\d+(?:\.\d+)?%)*)"
    r"\{transform:translate\((?P<x>-?\d+)px,(?P<y>-?\d+)px\)\}"
)


def enhance(source: Path) -> int:
    original = source.read_text(encoding="utf-8")
    if "decorative-snake-snack" in original:
        return 0

    head = HEAD_FRAMES.search(original)
    if not head:
        raise ValueError(f"{source}: snake head keyframes not found")

    candidates = []
    visited = set()
    for frame in POSITION.finditer(head.group(1)):
        when = float(frame["times"].split(",")[0].removesuffix("%"))
        if not (1 < when < 90):
            continue

        # Snake positions use 16px cells with a 2px offset in the background grid.
        x, y = int(frame["x"]) + 2, int(frame["y"]) + 2
        key = (x, y)
        if key in visited:
            continue
        visited.add(key)

        # Only add decorations to otherwise empty cells, not to contribution cells.
        element = f'<rect class="c" x="{x}" y="{y}" rx="2" ry="2"/>'
        if element in original:
            candidates.append((when, element))

    if len(candidates) < 2:
        raise ValueError(f"{source}: too few empty snake-path cells for decorations")

    count = min(MAX_DOTS, len(candidates))
    indices = [round(i * (len(candidates) - 1) / (count - 1)) for i in range(count)]
    dark = "--ce:#161b22" in original
    palette = ("#55DFFF", "#8B83FF", "#22D3A6") if dark else ("#087EAA", "#6742B9", "#0B9773")
    css_parts = ["/* decorative-snake-snack: animated visual food (not contributions) */"]

    for i, index in enumerate(indices):
        when, element = candidates[index]
        color = palette[i % len(palette)]
        name = f"snack{i:02}"
        new_element = element.replace('class="c"', f'class="c {name}"', 1)
        original = original.replace(element, new_element, 1)
        finish = min(when + 0.10, 99.9)
        css_parts.append(
            f"@keyframes {name}{{0%,{when:.2f}%{{fill:{color}}}"
            f"{finish:.2f}%,100%{{fill:var(--ce)}}}}"
            f".c.{name}{{fill:{color};animation-name:{name}}}"
        )

    original = original.replace("</style>", "".join(css_parts) + "</style>", 1)
    source.write_text(original, encoding="utf-8")
    return count


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: enhance_snake.py <generated.svg> [generated2.svg...]")
    for path in sys.argv[1:]:
        total = enhance(Path(path))
        print(f"Added {total} decorative snake snacks to {path}")
