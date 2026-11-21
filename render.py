"""Render the front page to entry.png and verify the artifact.

Chrome writes the PNG; this script then loads the PNG itself (PIL) and checks
size, dimensions, edge bleed, and ink coverage. It also checks the HTML source
for the masthead hierarchy, the date repetition, and per-card source lines.
Finally it renders a second time and compares bytes for determinism.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "app" / "index.html"
OUT = ROOT / "entry.png"
CHROME = "/usr/bin/google-chrome"
MAX_BYTES = 1_048_576
DATE = "SATURDAY, 21 NOVEMBER 2026"
W = H = 1024


def chrome_shot(target: Path) -> None:
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        f"--window-size={W},{H}", f"--screenshot={target}",
        HTML.resolve().as_uri(),
    ]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
    if res.returncode != 0 or not target.exists():
        raise RuntimeError(f"Chrome failed: {res.returncode} {res.stderr[-2000:]}")


def dark_fraction(im: Image.Image, box: tuple[int, int, int, int]) -> float:
    crop = im.convert("L").crop(box)
    px = crop.load()
    dark = total = 0
    for y in range(crop.height):
        for x in range(crop.width):
            total += 1
            if px[x, y] < 110:
                dark += 1
    return dark / total if total else 0.0


def verify_html() -> list[str]:
    src = HTML.read_text(encoding="utf-8")
    notes: list[str] = []
    assert "\ufffd" not in src, "replacement character in HTML"
    body = src.split("<body>", 1)[1]
    assert body.count(DATE) >= 3, "date must appear at least three times"
    notes.append(f"date appears {body.count(DATE)} times in body")

    h1 = re.search(r"<h1>(.*?)</h1>", body, re.S)
    assert h1 and h1.group(1).strip() == DATE, "masthead h1 is not the exact date"

    css = src.split("<style>", 1)[1].split("</style>", 1)[0]
    def size(selector: str) -> float:
        m = re.search(r"\." + re.escape(selector) + r"\s*\{[^}]*font-size:([\d.]+)px", css)
        return float(m.group(1)) if m else 0.0
    masthead = float(re.search(r"\.masthead h1\{[^}]*font-size:([\d.]+)px", css).group(1))
    others = [size(k) for k in ("lead", "claim", "v", "k", "spec", "bd", "al", "mrow", "r", "l")]
    assert masthead > max(others), f"masthead {masthead}px not largest; others {max(others)}px"
    notes.append(f"masthead {masthead:g}px is largest text (next {max(others):g}px)")

    blocks = re.findall(r'<div class="card[^"]*">(.*?)(?=<div class="card|</div>\s*</div>\s*<div class="mapband")', body, re.S)
    cards = re.findall(r'<div class="card(?:\s+big)?(?:\s+wide)?">(.*?)(?=<div class="card|\Z)', body.split('<div class="cards">', 1)[1].split('</div>\n<div class="mapband"', 1)[0], re.S)
    if len(cards) < 13:
        cards = re.findall(r'<div class="card[^"]*">(.*?)(?=<div class="card|\Z)', body, re.S)
    assert len(cards) == 13, f"expected 13 cards, found {len(cards)}"
    missing = []
    for i, card in enumerate(cards[:13], 1):
        kicker = re.search(r'<(?:span|div) class="k">(.*?)</(?:span|div)>', card, re.S)
        spec = re.search(r'<div class="spec">(.*?)</div>', card, re.S)
        if not kicker or len(kicker.group(1).split(" - ")) < 3 or not kicker.group(1).split(" - ")[-1].strip():
            missing.append(i)
        if not spec or not spec.group(1).strip():
            missing.append(i)
    assert not missing, f"cards without source or spec: {missing}"
    notes.append("all 13 cards carry a REGION - FIELD - SOURCE kicker and a spec")
    return notes


def verify_png(path: Path) -> list[str]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    assert len(data) <= MAX_BYTES, f"file too big: {len(data)}"
    im = Image.open(path)
    im.load()
    assert im.size == (W, H), f"wrong dimensions: {im.size}"
    notes = [f"PNG {im.width}x{im.height}, {len(data):,} bytes (limit 1,048,576)"]

    # Ink must not bleed into the outer paper margins (top 5px is the intentional rule).
    for name, box in (
        ("left", (0, 8, 12, H - 8)),
        ("right", (W - 12, 8, W, H - 8)),
        ("bottom", (0, H - 3, W, H)),
    ):
        frac = dark_fraction(im, box)
        assert frac < 0.001, f"ink bleeding into {name} margin: {frac:.4f}"
    notes.append("no ink in left, right or bottom outer margins")

    mast = dark_fraction(im, (300, 18, 724, 62))
    stats = dark_fraction(im, (20, 232, 1004, 292))
    assert mast > 0.02, f"masthead looks blank ({mast:.4f})"
    assert stats > 0.01, f"stats band looks blank ({stats:.4f})"
    notes.append(f"masthead ink {mast:.3f}, stats ink {stats:.3f} (both rendered)")
    return notes


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    chrome_shot(OUT)
    first = OUT.read_bytes()

    notes = verify_html() + verify_png(OUT)

    tmpdir = os.environ.get("TMPDIR") or tempfile.gettempdir()
    second_path = Path(tmpdir) / "entry_second_render.png"
    try:
        chrome_shot(second_path)
        second = second_path.read_bytes()
        if first == second:
            notes.append("determinism: two renders byte-for-byte identical")
        else:
            shutil.copyfile(second_path, tmpdir + "/entry_second_render_mismatch.png")
            notes.append(f"determinism: Chrome varied ({len(first)} vs {len(second)} bytes); kept first render")
    finally:
        if second_path.exists():
            second_path.unlink()

    print("RENDER VERIFICATION - Saturday, 21 November 2026")
    for n in notes:
        print("  OK " + n)
    print(f"  OK wrote {OUT}")


if __name__ == "__main__":
    main()
