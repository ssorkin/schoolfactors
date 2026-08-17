"""Open Graph share cards for every entity page.

One 1200x630 PNG per exported entity, drawn with PIL (fast enough for ~12k
cards), in the site's palette. Numbers mirror the entity's index row; missing
values render as an em dash — suppression is data, never zero. Language stays
comparative ("similar schools"), never judgemental.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = "#faf7f2"
CARD = "#fffdf9"
BORDER = "#e8e1d5"
INK = "#2b2722"
DIM = "#6f6a61"
FAINT = "#898781"
RUST = "#b0552f"

KIND_LABEL = {"school": "School", "district": "School district", "county": "County"}


def _fonts() -> dict:
    import matplotlib

    ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"

    def f(name: str, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(ttf / name), size)

    return {
        "brand": f("DejaVuSans-Bold.ttf", 38),
        "name": f("DejaVuSans-Bold.ttf", 62),
        "name_sm": f("DejaVuSans-Bold.ttf", 46),
        "sub": f("DejaVuSans.ttf", 28),
        "num": f("DejaVuSans-Bold.ttf", 54),
        "num_md": f("DejaVuSans-Bold.ttf", 42),
        "num_sm": f("DejaVuSans-Bold.ttf", 33),
        "label": f("DejaVuSans.ttf", 21),
        "foot": f("DejaVuSans.ttf", 24),
    }


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if draw.textlength(cand, font=font) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _ellipsize(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def _draw_card(fonts: dict, e: dict) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    pad = 64

    # Brand wordmark: "School" in rust, "Factors" in ink (matches the site header).
    d.text((pad, 44), "School", font=fonts["brand"], fill=RUST)
    d.text(
        (pad + d.textlength("School", font=fonts["brand"]), 44),
        "Factors",
        font=fonts["brand"],
        fill=INK,
    )
    kind = KIND_LABEL.get(e.get("kind"), "")
    if kind:
        d.text((W - pad, 52), kind, font=fonts["sub"], fill=FAINT, anchor="ra")

    # Entity name, up to two lines, shrinking once before ellipsizing.
    name = e.get("name") or ""
    font = fonts["name"]
    lines = _wrap(d, name, font, W - 2 * pad)
    if len(lines) > 2:
        font = fonts["name_sm"]
        lines = _wrap(d, name, font, W - 2 * pad)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = _ellipsize(d, lines[1], font, W - 2 * pad)
    y = 132
    for line in lines:
        d.text((pad, y), line, font=font, fill=INK)
        y += font.size + 10

    sub = " · ".join(
        s
        for s in (
            e.get("district") if e.get("kind") == "school" else None,
            f"{e['county']} County" if e.get("county") and e.get("kind") != "county" else None,
            "California",
        )
        if s
    )
    d.text((pad, y + 6), _ellipsize(d, sub, fonts["sub"], W - 2 * pad),
           font=fonts["sub"], fill=DIM)

    # Stat tiles. Percentile labels keep the comparative framing.
    def met(v):
        return "—" if v is None else f"{v}%"

    cat_word = {"gaining": "Gaining", "holding": "Holding", "slipping": "Slipping"}
    tiles = [
        (str(e["adj_pct"]) if e.get("adj_pct") is not None else "—",
         "similar-schools percentile"),
        (cat_word.get(e.get("growth_cat"), "—"),
         "cohort trajectory vs. state"),
        (f"{met(e.get('pass_ela'))} / {met(e.get('pass_math'))}",
         "met standard, ELA / math"),
        (f"{e['enrollment']:,}" if e.get("enrollment") else "—", "students"),
    ]
    tile_w = (W - 2 * pad - 3 * 20) // 4
    ty = 388
    th = 148
    for i, (num, label) in enumerate(tiles):
        x = pad + i * (tile_w + 20)
        d.rounded_rectangle([x, ty, x + tile_w, ty + th], radius=14,
                            fill=CARD, outline=BORDER, width=2)
        num_f = fonts["num"]
        for smaller in ("num_md", "num_sm"):
            if d.textlength(num, font=num_f) <= tile_w - 44:
                break
            num_f = fonts[smaller]
        # Baseline-align shrunken numbers with full-size ones.
        d.text((x + 22, ty + 18 + (fonts["num"].size - num_f.size)), num,
               font=num_f, fill=RUST)
        ly = ty + 92
        for ll in _wrap(d, label, fonts["label"], tile_w - 40)[:2]:
            d.text((x + 22, ly), ll, font=fonts["label"], fill=DIM)
            ly += 26
    d.text((pad, H - 56), "schoolfactors.org — compared in context, not ranked",
           font=fonts["foot"], fill=FAINT)
    return img


def _save(img: Image.Image, path: Path) -> None:
    img.quantize(colors=128, method=Image.Quantize.FASTOCTREE).save(
        path, "PNG", optimize=True
    )


def generate_og_images(index: list[dict], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    fonts = _fonts()
    n = 0
    for e in index:
        _save(_draw_card(fonts, e), out_dir / f"{e['cds']}.png")
        n += 1
    # Site-wide default card for non-entity pages.
    _save(
        _draw_card(
            fonts,
            {"name": "California schools, compared in context", "kind": None},
        ),
        out_dir / "default.png",
    )
    return n
