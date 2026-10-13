#!/usr/bin/env python3
"""Printability check for the rendered STLs.

Three questions per part, all of which cost hours to discover on a printer:

  * Is the mesh watertight? An edge used an odd number of times is a hole.
  * Does the part sit on z = 0? A part floating above the bed, or dipping below
    it, is modelled in the wrong frame and will slice wrong.
  * Is any downward-facing surface unsupported? Downward faces shallower than
    45 degrees are split into *internal* ones — a cavity ceiling, which closes
    over as it prints — and *external* ones, which are open to the air and need
    support. The design constraint is that external is zero.

Run it with `make check`, which renders first.

    python3 check_prints.py stl/*.stl

Exits non-zero if any part has a hole, floats, or has external overhang.
"""
from __future__ import annotations

import math
import struct
import sys
from collections import defaultdict

try:
    import numpy as np
except ImportError:  # pragma: no cover - a dependency note, not a code path
    sys.exit("check_prints.py needs numpy: pip install numpy")

# Vertex merge tolerance for edge pairing, in units of 0.1 um.
QUANT = 1e4
# Downward faces shallower than this (from horizontal) are overhangs.
OVERHANG_DEGREES = 45
# A part whose lowest point is further than this from z = 0 is misplaced.
BED_TOLERANCE_MM = 0.05
# How many of the largest downward facets to ray-test. The rest are scaled from
# the sample, which is plenty for a pass/fail on a number that should be zero.
SAMPLES = 400


def load(path: str) -> np.ndarray:
    """Read an STL, binary or ASCII.

    OpenSCAD writes ASCII by default and binary with `--export-format binstl`,
    and `make stl` does not pin either — so both have to work here, or the
    check silently depends on how the caller happened to render.
    """
    with open(path, "rb") as f:
        head = f.read(84)
        if len(head) < 84:
            raise ValueError(f"{path}: too short to be an STL")
        count = struct.unpack("<I", head[80:84])[0]
        rest = f.read()

    # A binary STL is exactly 84 + 50 * count bytes. Anything else is ASCII —
    # including a binary-looking header on a file that starts with "solid".
    if len(rest) == count * 50:
        tri = np.frombuffer(rest, dtype=np.uint8)
        tri = tri.reshape(count, 50)[:, 12:48].copy().view("<f4")
        return tri.reshape(count, 3, 3).astype(np.float64)

    with open(path, encoding="utf-8", errors="replace") as f:
        values = [
            line.split()[1:4] for line in f if line.lstrip().startswith("vertex ")
        ]
    if not values or len(values) % 3:
        raise ValueError(f"{path}: not a readable STL")
    return np.array(values, dtype=np.float64).reshape(-1, 3, 3)


def holes(tri: np.ndarray) -> int:
    """Edges used an odd number of times.

    Judged on the raw mesh. OpenSCAD's exporter emits zero-area slivers with two
    coincident vertices, which push an edge from two uses to four — benign, and
    dropping them first is what would invent a hole that is not there.
    """
    v = np.round(tri * QUANT).astype(np.int64)
    keys = v[:, :, 0] * 1000003**2 + v[:, :, 1] * 1000003 + v[:, :, 2]
    edges: dict[tuple[int, int], int] = defaultdict(int)
    for a, b, c in keys:
        for x, y in ((a, b), (b, c), (c, a)):
            edges[(min(x, y), max(x, y))] += 1
    return sum(1 for n in edges.values() if n % 2 == 1)


def _material_above(tri: np.ndarray, px: float, py: float, pz: float) -> bool:
    """Whether a ray straight up from a point crosses any facet."""
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    det = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (
        a[:, 1] - c[:, 1]
    )
    ok = np.abs(det) > 1e-12
    # Degenerate facets divide by zero here. They are masked out by `ok`, so the
    # NaNs they produce never reach a comparison that matters — but numpy still
    # warns about them, hence the suppression across the whole block.
    with np.errstate(invalid="ignore", divide="ignore"):
        l1 = (
            (b[:, 1] - c[:, 1]) * (px - c[:, 0])
            + (c[:, 0] - b[:, 0]) * (py - c[:, 1])
        ) / det
        l2 = (
            (c[:, 1] - a[:, 1]) * (px - c[:, 0])
            + (a[:, 0] - c[:, 0]) * (py - c[:, 1])
        ) / det
        l3 = 1.0 - l1 - l2
        inside = ok & (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        z = l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2]
        return bool(np.any(inside & (z > pz + 0.15)))


def analyse(path: str) -> dict:
    tri = load(path)
    pts = tri.reshape(-1, 3)
    lo, hi = pts.min(axis=0), pts.max(axis=0)

    u = tri[:, 1] - tri[:, 0]
    w = tri[:, 2] - tri[:, 0]
    normals = np.cross(u, w)
    twice_area = np.linalg.norm(normals, axis=1)
    area = twice_area / 2.0
    real = twice_area > 1e-12

    nz = np.zeros(len(tri))
    nz[real] = normals[real, 2] / twice_area[real]

    volume = (
        np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0
    )

    lowest = tri[:, :, 2].min(axis=1)
    down = (
        real
        & (nz < -math.sin(math.radians(OVERHANG_DEGREES)))
        & (lowest > lo[2] + 0.3)
    )
    idx = np.flatnonzero(down)

    internal = external = 0.0
    if len(idx):
        ordered = idx[np.argsort(-area[idx])][:SAMPLES]
        scale = area[idx].sum() / area[ordered].sum()
        for i in ordered:
            cx, cy, cz = tri[i].mean(axis=0)
            if _material_above(tri, cx, cy, cz):
                internal += area[i]
            else:
                external += area[i]
        internal *= scale
        external *= scale

    return {
        "name": path.split("/")[-1].removesuffix(".stl"),
        "size": hi - lo,
        "z0": lo[2],
        "grams": volume / 1000.0 * 1.24,
        "holes": holes(tri),
        "internal": internal,
        "external": external,
    }


def main(paths: list[str]) -> int:
    if not paths:
        print("usage: check_prints.py stl/*.stl", file=sys.stderr)
        return 2

    failures = 0
    for path in sorted(paths):
        r = analyse(path)
        problems = []
        if r["holes"]:
            problems.append(f"{r['holes']} unpaired edges")
        if abs(r["z0"]) > BED_TOLERANCE_MM:
            problems.append(f"sits at z={r['z0']:.2f}, not on the bed")
        if r["external"] > 1.0:
            problems.append(f"{r['external']:.0f} mm2 of unsupported overhang")

        size = " x ".join(f"{d:.1f}" for d in r["size"])
        status = "ok  " if not problems else "FAIL"
        print(
            f"{status} {r['name']:<15} {size:>18} mm  {r['grams']:5.1f} g  "
            f"internal overhang {r['internal']:6.0f} mm2"
        )
        for p in problems:
            print(f"       -> {p}")
        failures += bool(problems)

    print()
    print(
        "All parts watertight, on the bed, and printable without support."
        if not failures
        else f"{failures} part(s) need attention."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
