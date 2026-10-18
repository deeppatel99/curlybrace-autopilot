"""
The Curly Brace — design system.

Renders every visual asset an article needs, in the brand style:
deep navy background, dot-grid texture, layered purple/cyan/green glows,
a faint `{ }` watermark top-right and a small bright `{ }` logo in the footer.

Every renderer takes a plain dict "spec" (the JSON the writer model emits)
and returns a PIL Image (or, for GIFs, writes the file directly).

If you already have your own design.py with build_cover_v2() etc., you can
swap any renderer below for yours — the pipeline only calls render_asset().
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"

# ── Palette ──────────────────────────────────────────────────────────────
BG = (10, 15, 36)
CARD = (18, 25, 56)
CARD_2 = (24, 33, 70)
BORDER = (44, 56, 104)
TEXT = (232, 236, 255)
MUTED = (146, 160, 204)
DIM = (96, 110, 160)
PURPLE = (139, 92, 246)
CYAN = (34, 211, 238)
GREEN = (52, 211, 153)
AMBER = (251, 191, 36)
PINK = (244, 114, 182)
RED = (248, 113, 113)

BRAND = "The Curly Brace"
HANDLE = "medium.com/@thecurlybrace"

# ── Fonts ────────────────────────────────────────────────────────────────
_FONT_FILES = {
    "regular": "Inter-Regular.otf",
    "medium": "Inter-Medium.otf",
    "semibold": "Inter-SemiBold.otf",
    "bold": "Inter-Bold.otf",
    "extrabold": "Inter-ExtraBold.otf",
    "mono": "JetBrainsMono-Regular.ttf",
    "monobold": "JetBrainsMono-Bold.ttf",
}
_font_cache: dict = {}


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    key = (kind, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(FONT_DIR / _FONT_FILES[kind]), size)
    return _font_cache[key]


# ── Text helpers ─────────────────────────────────────────────────────────
def line_height(f: ImageFont.FreeTypeFont, spacing: float = 1.25) -> int:
    asc, desc = f.getmetrics()
    return int((asc + desc) * spacing)


def wrap(text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in str(text).split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if f.getlength(trial) <= max_w:
                cur = trial
                continue
            if cur:
                lines.append(cur)
            # hard-break very long tokens
            while f.getlength(w) > max_w and len(w) > 1:
                cut = len(w)
                while cut > 1 and f.getlength(w[:cut]) > max_w:
                    cut -= 1
                lines.append(w[:cut])
                w = w[cut:]
            cur = w
        lines.append(cur)
    return lines


def draw_lines(d: ImageDraw.ImageDraw, xy, lines, f, fill, spacing=1.25) -> int:
    x, y = xy
    lh = line_height(f, spacing)
    for ln in lines:
        d.text((x, y), ln, font=f, fill=fill)
        y += lh
    return y


def fit_font(text: str, kind: str, max_w: int, max_lines: int, start: int, minimum: int):
    """Largest font size where `text` wraps into <= max_lines within max_w."""
    size = start
    while size > minimum:
        f = font(kind, size)
        if len(wrap(text, f, max_w)) <= max_lines:
            return f
        size -= 2
    return font(kind, minimum)


# ── Background / chrome ──────────────────────────────────────────────────
def base_canvas(w: int, h: int, glow_seed: int = 0) -> Image.Image:
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # dot-grid texture
    step = 28
    for yy in range(step // 2, h, step):
        for xx in range(step // 2, w, step):
            d.point((xx, yy), fill=(30, 40, 78))
            d.point((xx + 1, yy), fill=(24, 33, 66))

    # layered glows (drawn small, blurred, upscaled — fast)
    s = 4
    glow = Image.new("RGBA", (w // s, h // s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    spots = [
        (PURPLE, 0.92, 0.05, 0.42, 70),
        (CYAN, 0.05, 0.95, 0.38, 46),
        (GREEN, 0.55, 1.05, 0.26, 26),
    ]
    rot = glow_seed % 3
    spots = spots[rot:] + spots[:rot]
    for color, cx, cy, r, a in spots:
        R = int(r * max(w, h) / s)
        X, Y = int(cx * w / s), int(cy * h / s)
        gd.ellipse((X - R, Y - R, X + R, Y + R), fill=color + (a,))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(w, h) / s / 9))
    glow = glow.resize((w, h), Image.BICUBIC)
    img = Image.alpha_composite(img.convert("RGBA"), glow)

    # faint { } watermark, top-right
    wm = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    wf = font("monobold", int(min(h, 900) * 0.62))
    tw = wf.getlength("{ }")
    wd.text((w - tw * 0.80, -min(h, 900) * 0.16), "{ }", font=wf, fill=(255, 255, 255, 6))
    img = Image.alpha_composite(img, wm)
    return img.convert("RGB")


def draw_footer(img: Image.Image, pad: int = 70):
    w, h = img.size
    d = ImageDraw.Draw(img)
    y = h - 74
    d.line((pad, y - 22, w - pad, y - 22), fill=(34, 45, 88), width=2)
    lf = font("monobold", 28)
    d.text((pad, y - 6), "{ }", font=lf, fill=CYAN)
    lw = lf.getlength("{ }")
    d.text((pad + lw + 14, y - 1), BRAND, font=font("semibold", 22), fill=TEXT)
    hf = font("regular", 20)
    d.text((w - pad - hf.getlength(HANDLE), y), HANDLE, font=hf, fill=MUTED)


def draw_header(d: ImageDraw.ImageDraw, title: str, w: int, pad: int = 70, kicker: str | None = None) -> int:
    """Draw kicker + title + accent bar. Returns y where content can begin."""
    y = 58
    if kicker:
        kf = font("semibold", 18)
        d.text((pad, y), kicker.upper(), font=kf, fill=CYAN)
        y += 34
    tf = fit_font(title, "bold", w - 2 * pad - 260, 2, 46, 32)
    y = draw_lines(d, (pad, y), wrap(title, tf, w - 2 * pad - 260), tf, TEXT, 1.18)
    y += 10
    accent_bar(d, pad, y, 140)
    return y + 36


def accent_bar(d, x, y, length, thickness=6):
    for i in range(length):
        t = i / max(1, length - 1)
        c = tuple(int(PURPLE[k] + (CYAN[k] - PURPLE[k]) * t) for k in range(3))
        d.line((x + i, y, x + i, y + thickness), fill=c)


def rounded(d, box, fill=CARD, outline=BORDER, radius=18, width=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(d, x, y, text, color=CYAN, size=18):
    f = font("semibold", size)
    tw = f.getlength(text)
    h = int(size * 2.0)
    d.rounded_rectangle((x, y, x + tw + 36, y + h), radius=h // 2, fill=_mix(BG, color, 0.16), outline=_mix(BG, color, 0.55), width=2)
    d.text((x + 18, y + (h - size) / 2 - 3), text, font=f, fill=color)
    return x + tw + 36


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def glow_box(img: Image.Image, box, color, strength=120, radius=22):
    """Soft halo around a box (used for highlighted nodes)."""
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = radius * 2
    layer = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((pad, pad, pad + x1 - x0, pad + y1 - y0), radius=20, fill=color + (strength,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    base = img.convert("RGBA")
    base.alpha_composite(layer, (x0 - pad, y0 - pad))
    img.paste(base.convert("RGB"))


# ── Code highlighting ────────────────────────────────────────────────────
from PIL import features as _pil_features

_RAQM = _pil_features.check("raqm")
_NO_LIGA = ["-liga", "-calt"]  # keep `=>` and `!=` as typed, no ligature glyphs


def _mono_text(d, xy, text, f, fill):
    if _RAQM:
        d.text(xy, text, font=f, fill=fill, features=_NO_LIGA)
    else:
        d.text(xy, text, font=f, fill=fill)

def _token_color(ttype) -> tuple:
    from pygments.token import Comment, Keyword, Name, Number, Operator, String

    if ttype in Comment or str(ttype).startswith("Token.Comment"):
        return DIM
    if ttype in Keyword:
        return (199, 146, 234)
    if ttype in String:
        return (195, 232, 141)
    if ttype in Number:
        return (247, 140, 108)
    if ttype in Name.Class or ttype in Name.Function or ttype in Name.Decorator:
        return (130, 210, 255)
    if ttype in Name.Builtin or ttype in Keyword.Type:
        return (255, 203, 107)
    if ttype in Operator:
        return (137, 221, 255)
    return (214, 222, 245)


def highlight(code: str, language: str = "csharp") -> list[list[tuple[str, tuple]]]:
    from pygments.lexers import TextLexer, get_lexer_by_name

    try:
        lexer = get_lexer_by_name(language or "text")
    except Exception:
        lexer = TextLexer()
    code = code.replace("\t", "    ").rstrip("\n")
    lines: list[list] = [[]]
    for ttype, val in lexer.get_tokens(code):
        parts = val.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                lines.append([])
            if part:
                lines[-1].append((part, _token_color(ttype)))
    while lines and not lines[-1]:
        lines.pop()
    return lines


def code_card(img, box, code, language="csharp", filename="Program.cs",
              highlight_lines: tuple | None = None, max_font=26, min_font=13):
    """macOS-window-chrome code editor card. highlight_lines=(start,end) 1-based."""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    rounded(d, box, fill=(13, 18, 42), outline=BORDER, radius=20)
    # chrome bar
    d.rounded_rectangle((x0, y0, x1, y0 + 52), radius=20, fill=CARD_2)
    d.rectangle((x0, y0 + 30, x1, y0 + 52), fill=CARD_2)
    d.line((x0, y0 + 52, x1, y0 + 52), fill=BORDER, width=2)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = x0 + 28 + i * 26
        d.ellipse((cx - 7, y0 + 19, cx + 7, y0 + 33), fill=c)
    ff = font("medium", 17)
    d.text(((x0 + x1) / 2 - ff.getlength(filename) / 2, y0 + 15), filename, font=ff, fill=MUTED)

    lines = highlight(code, language)
    inner_w = x1 - x0 - 110
    inner_h = y1 - y0 - 52 - 50
    longest = max((sum(len(t) for t, _ in ln) for ln in lines), default=10)
    size = max_font
    while size > min_font:
        f = font("mono", size)
        if f.getlength("M") * longest <= inner_w and line_height(f, 1.5) * len(lines) <= inner_h:
            break
        size -= 1
    f = font("mono", size)
    lh = line_height(f, 1.5)
    max_rows = max(1, inner_h // lh)
    gutter_f = font("mono", max(12, size - 2))
    y = y0 + 52 + 26
    for i, ln in enumerate(lines[:max_rows]):
        n = i + 1
        on = highlight_lines and highlight_lines[0] <= n <= highlight_lines[1]
        if on:
            d.rectangle((x0 + 2, y - 4, x1 - 2, y + lh - 6), fill=(40, 36, 92))
            d.rectangle((x0 + 2, y - 4, x0 + 7, y + lh - 6), fill=CYAN)
        d.text((x0 + 24, y + 2), f"{n:>2}", font=gutter_f, fill=CYAN if on else (70, 82, 128))
        x = x0 + 78
        for text, color in ln:
            if highlight_lines and not on:
                color = _mix(BG, color, 0.45)
            _mono_text(d, (x, y), text, f, color)
            x += f.getlength(text, features=_NO_LIGA) if _RAQM else f.getlength(text)
            if x > x1 - 20:
                break
        y += lh
    return img


# ── Renderers ────────────────────────────────────────────────────────────
def render_cover(spec: dict) -> Image.Image:
    W, H = 1600, 900
    img = base_canvas(W, H, glow_seed=0)
    d = ImageDraw.Draw(img)
    pad = 90
    left_w = 700

    y = 120
    kicker = spec.get("kicker") or "Interview Ready"
    pill(d, pad, y, kicker, CYAN, 19)
    y += 74

    title = spec.get("title", "Untitled")
    tf = fit_font(title, "extrabold", left_w, 5, 74, 40)
    y = draw_lines(d, (pad, y), wrap(title, tf, left_w), tf, TEXT, 1.12)
    y += 16
    accent_bar(d, pad, y, 160, 7)
    y += 34
    sub = spec.get("subtitle")
    if sub:
        sf = fit_font(sub, "medium", left_w, 3, 28, 20)
        draw_lines(d, (pad, y), wrap(sub, sf, left_w), sf, MUTED, 1.35)

    code = spec.get("code")
    if code:
        code_card(img, (860, 130, 1520, 740), code, spec.get("language", "csharp"),
                  spec.get("filename", "Program.cs"), max_font=24)
    draw_footer(img, pad)
    return img


def _col_widths(headers, rows, total, f, min_w=160):
    n = len(headers)
    weights = []
    for c in range(n):
        cells = [str(headers[c])] + [str(r[c]) if c < len(r) else "" for r in rows]
        weights.append(max(f.getlength(x) for x in cells) ** 0.75 + 40)
    s = sum(weights)
    widths = [max(min_w, int(total * w / s)) for w in weights]
    k = total / sum(widths)
    return [int(w * k) for w in widths]


def render_table(spec: dict) -> Image.Image:
    W = 1400
    pad = 70
    headers = spec.get("headers", [])
    rows = spec.get("rows", [])
    hf = font("bold", 22)
    cf = font("regular", 21)
    cf_first = font("semibold", 21)
    widths = _col_widths(headers, rows, W - 2 * pad, cf)
    cell_pad = 22

    def row_layout(cells, fnt, first_fnt):
        wrapped = []
        for c, w in enumerate(widths):
            txt = str(cells[c]) if c < len(cells) else ""
            fu = first_fnt if c == 0 else fnt
            wrapped.append((wrap(txt, fu, w - 2 * cell_pad), fu))
        hgt = max(len(lines) * line_height(fu, 1.32) for lines, fu in wrapped) + 2 * cell_pad - 6
        return wrapped, hgt

    head_layout = row_layout(headers, hf, hf)
    body = [row_layout(r, cf, cf_first) for r in rows]

    note = spec.get("note")
    nf = font("medium", 19)
    note_lines = wrap(note, nf, W - 2 * pad) if note else []

    # measure header height
    tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    top = draw_header(tmp, spec.get("title", ""), W, pad, spec.get("kicker"))
    table_h = head_layout[1] + sum(h for _, h in body)
    H = top + table_h + (len(note_lines) * line_height(nf, 1.35) + 30 if note_lines else 0) + 150

    img = base_canvas(W, H, glow_seed=1)
    d = ImageDraw.Draw(img)
    top = draw_header(d, spec.get("title", ""), W, pad, spec.get("kicker"))

    x0, y = pad, top
    rounded(d, (x0, y, W - pad, y + table_h), fill=CARD, outline=BORDER, radius=18)
    # header row
    d.rounded_rectangle((x0, y, W - pad, y + head_layout[1]), radius=18, fill=_mix(CARD, PURPLE, 0.35))
    d.rectangle((x0, y + 20, W - pad, y + head_layout[1]), fill=_mix(CARD, PURPLE, 0.35))
    x = x0
    for (lines, fu), w in zip(head_layout[0], widths):
        draw_lines(d, (x + cell_pad, y + cell_pad - 4), lines, fu, TEXT, 1.32)
        x += w
    y += head_layout[1]
    for ri, (cells, hgt) in enumerate(body):
        if ri % 2 == 1:
            last = ri == len(body) - 1
            if last:
                d.rounded_rectangle((x0 + 2, y, W - pad - 2, y + hgt - 2), radius=16, fill=CARD_2)
                d.rectangle((x0 + 2, y, W - pad - 2, y + hgt - 20), fill=CARD_2)
            else:
                d.rectangle((x0 + 2, y, W - pad - 2, y + hgt), fill=CARD_2)
        x = x0
        for ci, ((lines, fu), w) in enumerate(zip(cells, widths)):
            draw_lines(d, (x + cell_pad, y + cell_pad - 4), lines, fu, CYAN if ci == 0 else TEXT, 1.32)
            x += w
        y += hgt
        if ri < len(body) - 1:
            d.line((x0 + 2, y, W - pad - 2, y), fill=(36, 47, 92), width=1)
    # column separators
    x = x0
    for w in widths[:-1]:
        x += w
        d.line((x, top + 8, x, top + table_h - 8), fill=(36, 47, 92), width=1)
    if note_lines:
        draw_lines(d, (pad, y + 26), note_lines, nf, MUTED, 1.35)
    draw_footer(img, pad)
    return img


def _flow_geometry(nodes, W, top, pad):
    """Lay out nodes in rows of up to 4, left-to-right, returns boxes."""
    n = len(nodes)
    per_row = 4 if n > 4 else n
    if n in (5, 6):
        per_row = 3
    gap = 70
    bw = (W - 2 * pad - gap * (per_row - 1)) // per_row
    tf = font("bold", 24)
    sf = font("regular", 19)
    heights = []
    for nd in nodes:
        tl = wrap(nd.get("title", ""), tf, bw - 40)
        sl = wrap(nd.get("subtitle", ""), sf, bw - 40) if nd.get("subtitle") else []
        heights.append(len(tl) * line_height(tf, 1.2) + len(sl) * line_height(sf, 1.35) + 60)
    bh = max(heights + [120])
    boxes = []
    rows = math.ceil(n / per_row)
    for i in range(n):
        r, c = divmod(i, per_row)
        x = pad + c * (bw + gap)
        y = top + r * (bh + 80)
        boxes.append((x, y, x + bw, y + bh))
    total_h = rows * bh + (rows - 1) * 80
    return boxes, total_h, per_row


def _arrow(d, p0, p1, color=MUTED, width=3):
    d.line((p0, p1), fill=color, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    L = 14
    a1 = (p1[0] - L * math.cos(ang - 0.45), p1[1] - L * math.sin(ang - 0.45))
    a2 = (p1[0] - L * math.cos(ang + 0.45), p1[1] - L * math.sin(ang + 0.45))
    d.polygon([p1, a1, a2], fill=color)


def _draw_flow(img, nodes, boxes, per_row, states=None):
    """states: list of 'idle' | 'done' | 'active' per node."""
    d = ImageDraw.Draw(img)
    tf = font("bold", 24)
    sf = font("regular", 19)
    states = states or ["idle"] * len(nodes)
    # arrows first
    for i in range(len(boxes) - 1):
        a, b = boxes[i], boxes[i + 1]
        col = GREEN if states[i] in ("done",) and states[i + 1] != "idle" else MUTED
        if (i + 1) % per_row != 0:
            ym = (a[1] + a[3]) // 2
            _arrow(d, (a[2] + 8, ym), (b[0] - 10, ym), col)
        else:  # wrap to next row: down then left then down
            sx, sy = (a[0] + a[2]) // 2, a[3] + 8
            ex, ey = (b[0] + b[2]) // 2, b[1] - 10
            midy = (sy + ey) // 2
            d.line((sx, sy, sx, midy), fill=col, width=3)
            d.line((sx, midy, ex, midy), fill=col, width=3)
            _arrow(d, (ex, midy), (ex, ey), col)
    for i, (nd, box, st) in enumerate(zip(nodes, boxes, states)):
        if st == "active":
            glow_box(img, box, CYAN, 150, 20)
            d = ImageDraw.Draw(img)
        accent = [PURPLE, CYAN, GREEN, PINK][i % 4]
        fill = {"active": _mix(CARD, CYAN, 0.22), "done": _mix(CARD, GREEN, 0.10)}.get(st, CARD)
        outline = {"active": CYAN, "done": _mix(BG, GREEN, 0.7)}.get(st, BORDER)
        rounded(d, box, fill=fill, outline=outline, radius=18, width=3 if st == "active" else 2)
        d.rounded_rectangle((box[0], box[1], box[0] + 8, box[3]), radius=4, fill=accent if st != "idle" or states == ["idle"] * len(nodes) else _mix(BG, accent, 0.5))
        x, y = box[0] + 28, box[1] + 26
        y = draw_lines(d, (x, y), wrap(nd.get("title", ""), tf, box[2] - box[0] - 48), tf, TEXT, 1.2)
        if nd.get("subtitle"):
            draw_lines(d, (x, y + 6), wrap(nd["subtitle"], sf, box[2] - box[0] - 48), sf, MUTED, 1.35)
        # step number badge
        bf = font("monobold", 16)
        lab = f"{i + 1:02d}"
        d.text((box[2] - 22 - bf.getlength(lab), box[1] + 16), lab, font=bf, fill=_mix(BG, accent, 0.8))


def render_diagram(spec: dict) -> Image.Image:
    style = spec.get("style", "flow")
    if style == "layers":
        return _render_layers(spec)
    if style == "compare":
        return _render_compare(spec)
    W, pad = 1400, 70
    nodes = spec.get("nodes", [])
    tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    top = draw_header(tmp, spec.get("title", ""), W, pad, spec.get("kicker")) + 20
    boxes, total_h, per_row = _flow_geometry(nodes, W, top, pad)
    note = spec.get("note")
    nf = font("medium", 20)
    note_lines = wrap(note, nf, W - 2 * pad) if note else []
    H = top + total_h + (len(note_lines) * line_height(nf, 1.35) + 40 if note_lines else 0) + 160
    img = base_canvas(W, H, glow_seed=2)
    d = ImageDraw.Draw(img)
    draw_header(d, spec.get("title", ""), W, pad, spec.get("kicker"))
    _draw_flow(img, nodes, boxes, per_row)
    if note_lines:
        draw_lines(ImageDraw.Draw(img), (pad, top + total_h + 40), note_lines, nf, MUTED, 1.35)
    draw_footer(img, pad)
    return img


def _render_layers(spec):
    W, pad = 1400, 70
    layers = spec.get("layers", [])
    tf, sf = font("bold", 26), font("regular", 20)
    tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    top = draw_header(tmp, spec.get("title", ""), W, pad, spec.get("kicker")) + 10
    label_w = 380
    hs = []
    for ly in layers:
        sl = wrap(ly.get("subtitle", ""), sf, W - 2 * pad - label_w - 60)
        hs.append(max(96, len(sl) * line_height(sf, 1.35) + 52))
    H = top + sum(hs) + 18 * (len(hs) - 1) + 160
    img = base_canvas(W, H, glow_seed=0)
    d = ImageDraw.Draw(img)
    draw_header(d, spec.get("title", ""), W, pad, spec.get("kicker"))
    y = top
    colors = [PURPLE, CYAN, GREEN, PINK, AMBER]
    for i, (ly, h) in enumerate(zip(layers, hs)):
        c = colors[i % len(colors)]
        rounded(d, (pad, y, W - pad, y + h), fill=_mix(CARD, c, 0.12), outline=_mix(BG, c, 0.55), radius=16)
        d.rounded_rectangle((pad, y, pad + 10, y + h), radius=5, fill=c)
        tl = wrap(ly.get("title", ""), tf, label_w - 50)
        ty = y + (h - len(tl) * line_height(tf, 1.2)) // 2
        draw_lines(d, (pad + 36, ty), tl, tf, TEXT, 1.2)
        sl = wrap(ly.get("subtitle", ""), sf, W - 2 * pad - label_w - 60)
        sy = y + (h - len(sl) * line_height(sf, 1.35)) // 2
        draw_lines(d, (pad + label_w, sy), sl, sf, MUTED, 1.35)
        y += h + 18
    draw_footer(img, pad)
    return img


def _render_compare(spec):
    W, pad = 1400, 70
    left, right = spec.get("left", {}), spec.get("right", {})
    gap = 50
    cw = (W - 2 * pad - gap) // 2
    hf, pf = font("bold", 30), font("regular", 21)
    tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    top = draw_header(tmp, spec.get("title", ""), W, pad, spec.get("kicker")) + 10

    def col_h(col):
        h = 110
        for p in col.get("points", []):
            h += len(wrap(p, pf, cw - 90)) * line_height(pf, 1.38) + 18
        return h + 20

    ch = max(col_h(left), col_h(right))
    verdict = spec.get("verdict")
    vf = font("semibold", 22)
    vl = wrap(verdict, vf, W - 2 * pad - 80) if verdict else []
    vh = len(vl) * line_height(vf, 1.35) + 50 if vl else 0
    H = top + ch + (vh + 30 if vh else 0) + 150
    img = base_canvas(W, H, glow_seed=1)
    d = ImageDraw.Draw(img)
    draw_header(d, spec.get("title", ""), W, pad, spec.get("kicker"))
    for i, (col, c) in enumerate([(left, PURPLE), (right, CYAN)]):
        x = pad + i * (cw + gap)
        rounded(d, (x, top, x + cw, top + ch), fill=_mix(CARD, c, 0.10), outline=_mix(BG, c, 0.6), radius=20)
        d.text((x + 36, top + 34), col.get("title", ""), font=hf, fill=c)
        y = top + 100
        for p in col.get("points", []):
            d.ellipse((x + 38, y + 10, x + 50, y + 22), fill=c)
            y = draw_lines(d, (x + 68, y), wrap(p, pf, cw - 90), pf, TEXT, 1.38) + 18
    # VS badge
    vx, vy = W // 2, top + 60
    d.ellipse((vx - 34, vy - 34, vx + 34, vy + 34), fill=BG, outline=BORDER, width=3)
    vsf = font("extrabold", 22)
    d.text((vx - vsf.getlength("VS") / 2, vy - 15), "VS", font=vsf, fill=TEXT)
    if vl:
        y = top + ch + 30
        rounded(d, (pad, y, W - pad, y + vh), fill=_mix(CARD, GREEN, 0.14), outline=_mix(BG, GREEN, 0.6), radius=16)
        draw_lines(d, (pad + 40, y + 24), vl, vf, TEXT, 1.35)
    draw_footer(img, pad)
    return img


def render_revision(spec: dict) -> Image.Image:
    W, pad = 1400, 70
    pts = spec.get("points", [])
    gap = 26
    cw = (W - 2 * pad - gap) // 2
    tf, lf = font("bold", 23), font("regular", 20)
    tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
    title = spec.get("title", "60-Second Revision")
    top = draw_header(tmp, title, W, pad, spec.get("kicker", "Save this")) + 6
    hs = []
    for p in pts:
        h = len(wrap(p.get("term", ""), tf, cw - 70)) * line_height(tf, 1.2)
        h += len(wrap(p.get("line", ""), lf, cw - 70)) * line_height(lf, 1.35)
        hs.append(h + 54)
    rows = [max(hs[i:i + 2]) for i in range(0, len(hs), 2)]
    H = top + sum(rows) + gap * (len(rows) - 1) + 150
    img = base_canvas(W, H, glow_seed=2)
    d = ImageDraw.Draw(img)
    draw_header(d, title, W, pad, spec.get("kicker", "Save this"))
    colors = [PURPLE, CYAN, GREEN, PINK]
    y = top
    for r, rh in enumerate(rows):
        for c in range(2):
            i = r * 2 + c
            if i >= len(pts):
                break
            x = pad + c * (cw + gap)
            col = colors[i % 4]
            rounded(d, (x, y, x + cw, y + rh), fill=CARD, outline=BORDER, radius=16)
            nf = font("monobold", 18)
            d.text((x + 24, y + 26), f"{i + 1:02d}", font=nf, fill=col)
            yy = draw_lines(d, (x + 70, y + 22), wrap(p := pts[i].get("term", ""), tf, cw - 90), tf, col, 1.2)
            draw_lines(d, (x + 70, yy + 4), wrap(pts[i].get("line", ""), lf, cw - 90), lf, TEXT, 1.35)
        y += rh + gap
    draw_footer(img, pad)
    return img


# ── Animated GIFs ────────────────────────────────────────────────────────
def _save_gif(frames: list[Image.Image], path: Path, durations: list[int]):
    # one shared palette built from every frame -> no colour flicker between frames
    w, h = frames[0].size
    sample = Image.new("RGB", (w, h * len(frames)))
    for i, f in enumerate(frames):
        sample.paste(f, (0, h * i))
    sample = sample.resize((w // 2, h * len(frames) // 2))
    pal = sample.quantize(colors=255, method=Image.Quantize.FASTOCTREE)
    q = [f.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=durations, loop=0, optimize=True, disposal=1)


def _caption_bar(img, caption, step, total, y, pad, W):
    d = ImageDraw.Draw(img)
    cf = font("semibold", 26)
    lines = wrap(caption, cf, W - 2 * pad - 140)
    h = len(lines) * line_height(cf, 1.3) + 44
    rounded(d, (pad, y, W - pad, y + h), fill=_mix(CARD, CYAN, 0.10), outline=_mix(BG, CYAN, 0.55), radius=16)
    sf = font("monobold", 20)
    lab = f"{step}/{total}"
    d.text((pad + 28, y + 24), lab, font=sf, fill=CYAN)
    draw_lines(d, (pad + 110, y + 20), lines, cf, TEXT, 1.3)


def render_gif(spec: dict, path: Path) -> Path:
    style = spec.get("style", "flow")
    steps = spec.get("steps", [])
    W, pad = 1200, 60
    cf = font("semibold", 26)
    cap_h = max([len(wrap(s.get("caption", ""), cf, W - 2 * pad - 140)) for s in steps] + [1]) * line_height(cf, 1.3) + 44

    frames, durations = [], []
    if style == "code":
        code = spec.get("code", "")
        n_lines = len(highlight(code, spec.get("language", "csharp")))
        tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
        top = draw_header(tmp, spec.get("title", ""), W, pad, spec.get("kicker"))
        card_h = min(620, 52 + 50 + n_lines * 36)
        H = top + card_h + 30 + cap_h + 140
        bg = base_canvas(W, H, glow_seed=1)
        draw_header(ImageDraw.Draw(bg), spec.get("title", ""), W, pad, spec.get("kicker"))
        for i, s in enumerate(steps):
            f = bg.copy()
            ln = s.get("lines") or [1, 1]
            code_card(f, (pad, top, W - pad, top + card_h), code, spec.get("language", "csharp"),
                      spec.get("filename", "Program.cs"), highlight_lines=(ln[0], ln[-1]), max_font=22)
            _caption_bar(f, s.get("caption", ""), i + 1, len(steps), top + card_h + 30, pad, W)
            draw_footer(f, pad)
            frames.append(f)
            durations.append(int(s.get("ms", 2200)))
    else:
        nodes = spec.get("nodes", [])
        tmp = ImageDraw.Draw(Image.new("RGB", (W, 10)))
        top = draw_header(tmp, spec.get("title", ""), W, pad, spec.get("kicker")) + 20
        boxes, total_h, per_row = _flow_geometry(nodes, W, top, pad)
        H = top + total_h + 40 + cap_h + 140
        bg = base_canvas(W, H, glow_seed=2)
        draw_header(ImageDraw.Draw(bg), spec.get("title", ""), W, pad, spec.get("kicker"))
        if not steps:
            steps = [{"focus": i, "caption": n.get("title", "")} for i, n in enumerate(nodes)]
        for i, s in enumerate(steps):
            f = bg.copy()
            focus = int(s.get("focus", i))
            states = ["done" if j < focus else "active" if j == focus else "idle" for j in range(len(nodes))]
            _draw_flow(f, nodes, boxes, per_row, states)
            _caption_bar(f, s.get("caption", ""), i + 1, len(steps), top + total_h + 40, pad, W)
            draw_footer(f, pad)
            frames.append(f)
            durations.append(int(s.get("ms", 1800)))
    if durations:
        durations[-1] += 1400  # linger on the last frame
    _save_gif(frames, path, durations)
    return path


# ── Dispatcher ───────────────────────────────────────────────────────────
RENDERERS = {
    "cover": render_cover,
    "table": render_table,
    "diagram": render_diagram,
    "revision": render_revision,
}


def render_asset(spec: dict, out_path: Path) -> Path:
    """Render one asset spec to out_path (.png or .gif). Returns the path."""
    kind = spec.get("type")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "gif":
        return render_gif(spec, out_path.with_suffix(".gif"))
    if kind not in RENDERERS:
        raise ValueError(f"Unknown asset type: {kind!r}")
    img = RENDERERS[kind](spec)
    p = out_path.with_suffix(".png")
    img.save(p, optimize=True)
    return p
