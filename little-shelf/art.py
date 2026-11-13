"""식물 이미지 합성.

assets/ 폴더에 PNG가 있으면 그것을 합성하고, 없으면 Pillow로 직접 그려서
에셋 없이도 앱이 항상 실행되도록 합니다. 외부 이미지 생성 API는 쓰지 않습니다.
"""
from __future__ import annotations

import base64
import io
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ASSET_DIR = Path(__file__).parent / "assets"
CANVAS = 480      # 작업 캔버스(정사각형). 출력할 때 원하는 크기로 줄입니다.
OPEN_Y = 332      # 용기 입구 높이

# key: (표시 이름, 종류, 최대 꽃 개수)
CONTAINERS = {
    "basic_pot": ("🪴 기본 화분", "pot", 2),
    "round_pot": ("⚪ 둥근 화분", "pot", 2),
    "striped_pot": ("〰️ 줄무늬 화분", "pot", 2),
    "glass_vase": ("🫧 유리 꽃병", "vase", 3),
    "ribbon_vase": ("🎀 리본 꽃병", "vase", 3),
}
FLOWERS = {
    "tulip": "🌷 튤립",
    "rose": "🌹 장미",
    "daisy": "🌼 데이지",
    "sunflower": "🌻 해바라기",
    "babys_breath": "✨ 안개꽃",
    "leaf": "🌿 초록 잎사귀",
    "cactus": "🌵 선인장",
}
COLORS = {  # key: (표시 이름, 색)
    "pink": ("🩷 핑크", "#F4B6C6"),
    "cream": ("🤍 크림", "#F6E6BF"),
    "sky": ("🩵 하늘색", "#B5DBEF"),
    "green": ("💚 연두색", "#BFE0A8"),
    "lavender": ("💜 라벤더", "#CFC0EC"),
}
FILLERS = {"leaf", "babys_breath"}   # 뒤쪽에 먼저 그리는 식물
POT_ONLY = {"cactus"}                # 꽃병에는 꽂을 수 없는 식물

# 꽃 개수별 (x 오프셋, 머리 높이). 첫 번째로 고른 꽃이 가장 높은 자리에 놓입니다.
POSITIONS = {
    0: [],
    1: [(0, 150)],
    2: [(34, 135), (-40, 178)],
    3: [(0, 112), (-58, 185), (58, 172)],
}

STEM = (112, 160, 100)


def allowed_flowers(container: str) -> list[str]:
    kind = CONTAINERS[container][1]
    return [k for k in FLOWERS if not (kind == "vase" and k in POT_ONLY)]


def sanitize(container: str, color: str, flowers) -> tuple[str, str, list[str]]:
    """저장된 값이 이상해도 항상 그릴 수 있게 정리합니다."""
    if container not in CONTAINERS:
        container = "basic_pot"
    if color not in COLORS:
        color = "pink"
    ok = set(allowed_flowers(container))
    picked = [f for f in (flowers or []) if f in ok][: CONTAINERS[container][2]]
    return container, color, picked


# ---------- 색 유틸 ----------
def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _shade(rgb, f: float):
    """f<1 이면 어둡게, f>1 이면 흰색 쪽으로 밝게."""
    if f <= 1:
        return tuple(int(c * f) for c in rgb)
    return tuple(int(c + (255 - c) * (f - 1)) for c in rgb)


# ---------- 에셋 ----------
@lru_cache(maxsize=64)
def _asset(kind: str, key: str):
    path = ASSET_DIR / kind / f"{key}.png"
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def _tint(im: Image.Image, rgb) -> Image.Image:
    """밝은 회색조 에셋에 색을 곱해 용기 색상을 바꿉니다."""
    r, g, b, a = im.split()
    out = ImageChops.multiply(Image.merge("RGB", (r, g, b)), Image.new("RGB", im.size, rgb))
    out.putalpha(a)
    return out


# ---------- 도형 도우미 ----------
def _petal(d, bx, by, ang, length, width, fill, outline=None):
    """(bx,by)에서 ang도 방향으로 뻗는 타원형 꽃잎/잎."""
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for i in range(28):
        t = 2 * math.pi * i / 28
        u = (math.cos(t) + 1) / 2 * length
        v = math.sin(t) * width / 2
        pts.append((bx + u * ca - v * sa, by + u * sa + v * ca))
    d.polygon(pts, fill=fill, outline=outline)


def _stem(d, x0, y0, x1, y1, bend):
    pts = []
    for i in range(17):
        t = i / 16
        pts.append((x0 + (x1 - x0) * t + math.sin(math.pi * t) * bend, y0 + (y1 - y0) * t))
    d.line(pts, fill=STEM, width=7, joint="curve")


# ---------- 꽃 머리 ----------
def _daisy(d, x, y):
    for i in range(12):
        _petal(d, x, y, i * 30, 34, 14, (255, 255, 255), (226, 214, 200))
    d.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(247, 200, 70), outline=(222, 170, 40))


def _sunflower(d, x, y):
    for i in range(18):
        _petal(d, x, y, i * 20 + 10, 46, 15, (245, 196, 52), (222, 160, 30))
    for i in range(18):
        _petal(d, x, y, i * 20, 38, 13, (250, 214, 80))
    d.ellipse((x - 19, y - 19, x + 19, y + 19), fill=(110, 72, 44), outline=(80, 50, 30), width=2)
    for a in range(0, 360, 60):
        px, py = x + math.cos(math.radians(a)) * 9, y + math.sin(math.radians(a)) * 9
        d.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(150, 108, 66))


def _tulip(d, x, y):
    c = (240, 130, 160)
    edge = (212, 100, 130)
    _petal(d, x, y + 26, -112, 56, 32, _shade(c, 0.93), edge)
    _petal(d, x, y + 26, -68, 56, 32, _shade(c, 0.93), edge)
    _petal(d, x, y + 28, -90, 62, 34, c, edge)


def _rose(d, x, y):
    layers = [
        (30, 0, 0, (232, 106, 130)),
        (24, -2, 1, (217, 80, 107)),
        (17, 2, -1, (232, 106, 130)),
        (11, -1, 1, (199, 62, 90)),
        (5, 0, 0, (217, 80, 107)),
    ]
    for r, ox, oy, col in layers:
        d.ellipse((x + ox - r, y + oy - r, x + ox + r, y + oy + r), fill=col, outline=(190, 56, 84))


def _babys_breath(d, x, y):
    by = y + 22
    for ang in (-130, -110, -90, -70, -50):
        a = math.radians(ang)
        ex, ey = x + math.cos(a) * 44, by + math.sin(a) * 44
        d.line((x, by, ex, ey), fill=STEM, width=3)
        for k in range(5):
            ka = math.radians(k * 72)
            px, py = ex + math.cos(ka) * 7, ey + math.sin(ka) * 7
            d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(255, 246, 248), outline=(231, 207, 214))


def _leaf(d, x, y):
    g, gd = (125, 179, 111), (92, 148, 84)
    _petal(d, x, y + 30, -128, 64, 26, g, gd)
    _petal(d, x, y + 30, -52, 64, 26, g, gd)
    _petal(d, x, y + 34, -90, 80, 30, _shade(g, 1.1), gd)
    d.line((x, y + 34, x, y - 44), fill=gd, width=2)


HEADS = {
    "daisy": _daisy,
    "sunflower": _sunflower,
    "tulip": _tulip,
    "rose": _rose,
    "babys_breath": _babys_breath,
    "leaf": _leaf,
}


def _cactus(d, x, top):
    g, gd = (120, 178, 120), (86, 146, 90)
    base = OPEN_Y + 20
    d.rounded_rectangle((x - 50, top + 58, x - 20, top + 76), radius=9, fill=g, outline=gd, width=3)
    d.rounded_rectangle((x - 50, top + 36, x - 34, top + 76), radius=8, fill=g, outline=gd, width=3)
    d.rounded_rectangle((x + 20, top + 78, x + 50, top + 96), radius=9, fill=g, outline=gd, width=3)
    d.rounded_rectangle((x + 34, top + 54, x + 50, top + 96), radius=8, fill=g, outline=gd, width=3)
    d.rounded_rectangle((x - 26, top, x + 26, base), radius=26, fill=g, outline=gd, width=3)
    for dx in (-10, 10):
        d.line((x + dx, top + 22, x + dx, base - 6), fill=_shade(g, 1.25), width=3)
    for sx, sy in ((-14, 40), (14, 60), (-12, 90), (12, 110), (0, 28)):
        d.line((x + sx, top + sy, x + sx + 3, top + sy - 4), fill=(255, 250, 235), width=2)
    d.ellipse((x - 9, top - 7, x + 9, top + 11), fill=(244, 150, 180), outline=(214, 110, 140))
    d.ellipse((x - 3, top - 1, x + 3, top + 5), fill=(250, 220, 90))


# ---------- 용기 (대체 이미지) ----------
VASE = [(212, 326), (268, 326), (272, 350), (302, 388), (320, 424),
        (304, 450), (176, 450), (160, 424), (178, 388), (208, 350)]
POT_BODY = [(168, 358), (312, 358), (296, 450), (184, 450)]


def _poly_mask(points) -> Image.Image:
    m = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(m).polygon(points, fill=255)
    return m


def _container_fallback(img: Image.Image, container: str, rgb) -> Image.Image:
    d = ImageDraw.Draw(img)
    dark, light = _shade(rgb, 0.82), _shade(rgb, 1.3)

    if container == "basic_pot":
        d.polygon(POT_BODY, fill=rgb)
        d.polygon([(176, 366), (192, 366), (206, 448), (192, 448)], fill=light)
        d.rounded_rectangle((152, OPEN_Y, 328, 366), radius=10, fill=_shade(rgb, 1.12))
        d.rectangle((166, 366, 314, 372), fill=dark)

    elif container == "round_pot":
        d.ellipse((146, 336, 334, 452), fill=rgb)
        d.arc((162, 352, 318, 440), 150, 205, fill=light, width=7)
        d.rounded_rectangle((186, 326, 294, 352), radius=12, fill=_shade(rgb, 1.12))

    elif container == "striped_pot":
        body = Image.new("RGBA", (CANVAS, CANVAS), rgb + (255,))
        bd = ImageDraw.Draw(body)
        for i, sx in enumerate(range(144, 340, 24)):
            if i % 2:
                bd.rectangle((sx, 350, sx + 24, 460), fill=_shade(rgb, 1.55) + (255,))
        layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        layer.paste(body, (0, 0), _poly_mask(POT_BODY))
        img = Image.alpha_composite(img, layer)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((152, OPEN_Y, 328, 366), radius=10, fill=_shade(rgb, 1.12))
        d.rectangle((166, 366, 314, 372), fill=dark)

    elif container == "glass_vase":
        glass = Image.new("RGBA", (CANVAS, CANVAS), rgb + (60,))
        ImageDraw.Draw(glass).rectangle((0, 392, CANVAS, CANVAS), fill=rgb + (140,))
        layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        layer.paste(glass, (0, 0), _poly_mask(VASE))
        img = Image.alpha_composite(img, layer)
        d = ImageDraw.Draw(img)
        d.line(VASE + [VASE[0]], fill=(255, 255, 255, 215), width=4, joint="curve")
        d.line((188, 398, 192, 432), fill=(255, 255, 255, 230), width=5)

    elif container == "ribbon_vase":
        d.polygon(VASE, fill=rgb)
        d.polygon([(186, 395), (198, 395), (206, 446), (190, 440)], fill=light)
        ribbon = (255, 251, 244)
        d.polygon([(236, 364), (222, 400), (234, 394)], fill=_shade(ribbon, 0.92))
        d.polygon([(244, 364), (258, 400), (246, 394)], fill=_shade(ribbon, 0.92))
        d.polygon([(206, 348), (274, 348), (284, 368), (196, 368)], fill=ribbon)
        d.polygon([(240, 358), (204, 342), (204, 374)], fill=ribbon, outline=_shade(ribbon, 0.85))
        d.polygon([(240, 358), (276, 342), (276, 374)], fill=ribbon, outline=_shade(ribbon, 0.85))
        d.ellipse((231, 349, 249, 367), fill=_shade(ribbon, 0.88))
    return img


# ---------- 합성 ----------
def render_plant(container: str, color: str, flowers, size: int = 240) -> Image.Image:
    container, color, flowers = sanitize(container, color, flowers)
    kind = CONTAINERS[container][1]
    rgb = _rgb(COLORS[color][1])
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    container_asset = _asset("containers", container)
    if kind == "pot" and container_asset is None:
        d.ellipse((176, OPEN_Y - 12, 304, OPEN_Y + 12), fill=(110, 82, 62))  # 흙

    stem_y = 430 if container == "glass_vase" else OPEN_Y + 14
    plan = [(f, *POSITIONS[len(flowers)][i]) for i, f in enumerate(flowers)]
    plan.sort(key=lambda p: p[0] not in FILLERS)  # 잎·안개꽃을 뒤로

    for name, dx, hy in plan:
        x0, x1 = 240 + dx * 0.3, 240 + dx
        flower_asset = _asset("flowers", name)
        if flower_asset is not None:
            h = int(stem_y - hy + 60)
            w = max(1, int(flower_asset.width * h / flower_asset.height))
            fa = flower_asset.resize((w, h), Image.LANCZOS)
            img.alpha_composite(fa, (int(x1 - w / 2), int(stem_y + 8 - h)))
            continue
        if name == "cactus":
            _cactus(d, int(x1), max(hy + 40, 236))
            continue
        _stem(d, x0, stem_y, x1, hy, -dx * 0.25)
        HEADS[name](d, x1, hy)

    if container_asset is not None:
        img.alpha_composite(_tint(container_asset.resize((CANVAS, CANVAS), Image.LANCZOS), rgb))
    else:
        img = _container_fallback(img, container, rgb)

    return img.resize((size, size), Image.LANCZOS)


def to_data_uri(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def plant_data_uri(container: str, color: str, flowers, size: int = 240) -> str:
    return to_data_uri(render_plant(container, color, list(flowers), size))
