#!/usr/bin/env python3
"""Generate an SVG word cloud from the topics of a user's starred repos.

Live mode (CI):   GITHUB_TOKEN=... python gen_wordcloud.py --user natesubra
Offline mode:     python gen_wordcloud.py --topics-file topics.txt
"""

from __future__ import annotations

import argparse
import colorsys
import json
import os
import random
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from wordcloud import WordCloud

DEFAULT_FONT = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Medium.ttf"
DEFAULT_EXCLUDE = {"hacktoberfest"}

# Bright terminal/neon hues; every pick gets a lightness floor so nothing
# disappears into the black background.
PALETTE_HUES = [0, 20, 40, 55, 90, 140, 170, 190, 210, 260, 290, 320]


def fetch_topics(user: str, token: str | None) -> Counter:
    """Count topics across every repo the user has starred."""
    counts: Counter = Counter()
    page = 1
    while True:
        url = f"https://api.github.com/users/{user}/starred?per_page=100&page={page}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            repos = json.load(resp)
        if not repos:
            break
        for repo in repos:
            counts.update(repo.get("topics") or [])
        page += 1
    return counts


def load_topics_file(path: Path) -> Counter:
    """Read 'topic count' lines (or bare topics, one per line)."""
    counts: Counter = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        word, _, num = line.partition(" ")
        counts[word] += int(num) if num else 1
    return counts


def circle_mask(size: int, margin: int) -> np.ndarray:
    """255 = blocked, 0 = drawable (wordcloud's mask convention)."""
    y, x = np.ogrid[:size, :size]
    c = size / 2
    r = c - margin
    return np.where((x - c) ** 2 + (y - c) ** 2 > r**2, 255, 0).astype(np.uint8)


def neon_color(rng: random.Random) -> str:
    h = rng.choice(PALETTE_HUES) / 360 + rng.uniform(-0.02, 0.02)
    l = rng.uniform(0.55, 0.75)
    s = rng.uniform(0.75, 1.0)
    r, g, b = colorsys.hls_to_rgb(h % 1.0, l, s)
    return f"rgb({int(r * 255)},{int(g * 255)},{int(b * 255)})"


def build_cloud(counts: Counter, args: argparse.Namespace) -> WordCloud:
    rng = random.Random(args.seed)
    focus = args.focus_word
    others = {w: c for w, c in counts.most_common(args.max_words) if w != focus}

    mask = circle_mask(args.size, args.margin)
    focus_entry = None

    if focus:
        # Pin the focus word dead-center, horizontal. Block only its glyph
        # pixels (dilated by the padding) so small words can tuck in around
        # the letter shapes instead of leaving a rectangular void.
        font = ImageFont.truetype(args.font, args.focus_size)
        left, top, right, bottom = font.getbbox(focus)
        x0 = (args.size - (right - left)) // 2
        y0 = (args.size - (bottom - top)) // 2

        ink = Image.new("L", (args.size, args.size), 0)
        ImageDraw.Draw(ink).text((x0 - left, y0 - top), focus, font=font, fill=255)
        if args.word_padding:
            ink = ink.filter(ImageFilter.MaxFilter(2 * args.word_padding + 1))
        mask[np.asarray(ink) > 0] = 255

        # layout_ positions are the top-left of the ink box; to_svg() applies
        # the glyph offsets itself, so pass (y0, x0) unadjusted.
        focus_entry = ((focus, 1.0), args.focus_size, (y0, x0), None, "rgb(235,235,235)")

    wc = WordCloud(
        width=args.size,
        height=args.size,
        mask=mask,
        font_path=args.font,
        background_color="black",
        mode="RGB",
        max_words=args.max_words,
        max_font_size=int(args.focus_size * 0.6),
        min_font_size=8,
        prefer_horizontal=0.6,
        relative_scaling=0.5,
        margin=args.word_padding,
        random_state=args.seed,
        color_func=lambda *a, **k: neon_color(rng),
    )
    wc.generate_from_frequencies(others)
    if focus_entry:
        wc.layout_.insert(0, focus_entry)
    return wc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--user", help="GitHub user whose stars to read")
    src.add_argument("--topics-file", type=Path, help="offline 'topic count' list")
    p.add_argument("--out", type=Path, default=Path("wordcloud.svg"))
    p.add_argument("--png", type=Path, help="also write a PNG preview")
    p.add_argument("--font", default=DEFAULT_FONT)
    p.add_argument("--size", type=int, default=2048)
    p.add_argument("--margin", type=int, default=40, help="circle inset in px")
    p.add_argument("--max-words", type=int, default=254)
    p.add_argument("--focus-word", default="security")
    p.add_argument("--focus-size", type=int, default=260)
    p.add_argument("--word-padding", type=int, default=4)
    p.add_argument("--exclude", nargs="*", default=sorted(DEFAULT_EXCLUDE))
    p.add_argument("--seed", type=int, default=None, help="fix for reproducible layout")
    args = p.parse_args()

    if args.user:
        counts = fetch_topics(args.user, os.environ.get("GITHUB_TOKEN"))
    else:
        counts = load_topics_file(args.topics_file)
    for word in args.exclude:
        counts.pop(word, None)
    if not counts:
        print("no topics found", file=sys.stderr)
        return 1

    wc = build_cloud(counts, args)
    svg = wc.to_svg(embed_font=True, optimize_embedded_font=True)
    # wordcloud omits viewBox; without it the SVG will not scale in <img>.
    svg = svg.replace(
        f'width="{args.size}" height="{args.size}"',
        f'width="{args.size}" height="{args.size}" viewBox="0 0 {args.size} {args.size}"',
        1,
    )
    args.out.write_text(svg, encoding="utf-8")
    if args.png:
        wc.to_file(str(args.png))
    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB), {len(wc.layout_)} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
