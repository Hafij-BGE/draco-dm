"""Build the theme artwork in draco/art/ (needs Pillow + numpy; the app itself doesn't).

    python3 tools/make_theme_art.py "<folder with the theme concept images>"

Window backgrounds are generated (star field + nebula/aurora glow) and get the hand-made
art from the concept images placed on top; the progress-window illustrations are cut out of
the concept images. Re-run after replacing a concept image.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "draco" / "art"
W, H = 1600, 1000
rng = np.random.default_rng(7)

GALAXY_UI = "galaxy browser/b3179059-13aa-40fb-a342-0aafa4d2355d.png"
GALAXY_PROGRESS = "galaxy browser/75321517-1c44-4a8c-bfb7-6892e373128b.png"
CATEGORY_SHEET = "12640702-2c71-4705-a2da-9986fb88ef14.png"


def gradient(top, bottom):
    t = np.linspace(0, 1, H)[:, None, None]
    a, b = np.array(top, float), np.array(bottom, float)
    return np.broadcast_to(a + (b - a) * t, (H, W, 3)).copy()


def glow(img, cx, cy, rx, ry, color, strength):
    y, x = np.ogrid[:H, :W]
    d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
    img += np.exp(-d)[..., None] * np.array(color, float) * strength


def clouds(img, color, strength, scale=8, seed=1):
    """Soft cloudy structure: upscaled random noise, blurred."""
    r = np.random.default_rng(seed)
    small = Image.fromarray((r.random((H // scale, W // scale)) * 255).astype("uint8"))
    big = small.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(scale * 3))
    n = (np.asarray(big, float) / 255) ** 3
    img += n[..., None] * np.array(color, float) * strength


def stars(img, count, bright=1.0):
    ys, xs = rng.integers(0, H, count), rng.integers(0, W, count)
    lum = rng.random(count) ** 3 * 255 * bright
    for x, y, l in zip(xs, ys, lum):
        img[y, x] = np.maximum(img[y, x], l)
    for x, y in zip(rng.integers(0, W, count // 40), rng.integers(0, H, count // 40)):
        glow_small(img, x, y)


def glow_small(img, x, y, r=4):
    y0, y1, x0, x1 = max(0, y - r), min(H, y + r + 1), max(0, x - r), min(W, x + r + 1)
    yy, xx = np.ogrid[y0:y1, x0:x1]
    d = np.exp(-(((xx - x) ** 2 + (yy - y) ** 2) / 3.0))
    img[y0:y1, x0:x1] += d[..., None] * np.array([200, 210, 255], float)


def to_image(img):
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"))


def paste_faded(base, art, x, y, fade=60):
    """Paste art with soft transparent edges so it melts into the background."""
    art = art.convert("RGB")
    w, h = art.size
    mask = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(mask)
    for i in range(fade):
        a = int(255 * (i / fade) ** 1.5)
        d.rectangle([i, i, w - 1 - i, h - 1 - i], outline=a)
    base.paste(art, (x, y), mask.filter(ImageFilter.GaussianBlur(fade / 4)))


def mountains(img, color, base_y, rough, seed):
    r = np.random.default_rng(seed)
    pts = np.cumsum(r.normal(0, rough, W // 8 + 2))
    pts = np.interp(np.arange(W), np.linspace(0, W, len(pts)), pts)
    pts = pts - pts.min()
    ridge = base_y - pts / max(1, pts.max()) * 160
    y = np.arange(H)[:, None]
    m = y > ridge[None, :]
    img[m] = img[m] * 0.25 + np.array(color, float) * 0.75


def save_jpg(im, name):
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / name, quality=86, optimize=True, progressive=True)
    print("wrote", OUT / name)


def backgrounds(src):
    ui = Image.open(src / GALAXY_UI).convert("RGB")
    banner = ui.crop((390, 0, 1460, 122))            # galaxy, DRACO constellation, planets
    planet = ui.crop((10, 760, 290, 880))            # planet over the mountains

    # Galaxy Explorer: deep blue-violet space with the concept's galaxy banner.
    img = gradient((6, 9, 30), (9, 8, 34))
    glow(img, W * 0.55, H * 0.05, 520, 260, (90, 60, 255), 0.55)
    glow(img, W * 0.1, H * 0.95, 500, 300, (40, 90, 255), 0.35)
    glow(img, W * 0.9, H * 0.6, 420, 380, (150, 50, 220), 0.25)
    clouds(img, (90, 70, 220), 0.5, seed=3)
    stars(img, 2600)
    im = to_image(img)
    b = banner.resize((int(banner.width * 1.35), int(banner.height * 1.35)), Image.LANCZOS)
    paste_faded(im, b, (W - b.width) // 2 + 120, 0, fade=70)
    paste_faded(im, planet.resize((420, 180), Image.LANCZOS), 0, H - 180, fade=40)
    save_jpg(im, "bg-galaxy-explorer.jpg")

    # Aurora Light: pale sky, aurora ribbons, snowy mountains.
    img = gradient((232, 236, 255), (246, 244, 255))
    glow(img, W * 0.35, H * 0.12, 700, 120, (-60, 30, -40), 0.9)     # green ribbon
    glow(img, W * 0.7, H * 0.1, 600, 140, (-30, -60, 10), 0.8)       # violet ribbon
    glow(img, W * 0.9, H * 0.12, 160, 160, (-40, -30, 0), 0.9)       # planet
    clouds(img, (-30, -20, 0), 0.35, seed=8)
    mountains(img, (205, 210, 240), H * 1.0, 5, seed=9)
    save_jpg(to_image(img), "bg-aurora-light.jpg")


def illustrations(src):
    big = Image.open(src / GALAXY_PROGRESS).convert("RGB")
    sheet = Image.open(src / CATEGORY_SHEET).convert("RGB")
    cuts = {
        "ill-galaxy.png": big.crop((860, 270, 1310, 520)),
        "ill-documents.png": sheet.crop((882, 176, 1012, 286)),
        "ill-music.png": sheet.crop((1345, 178, 1530, 278)),
        "ill-video.png": sheet.crop((556, 672, 722, 782)),
        "ill-compressed.png": sheet.crop((1330, 664, 1500, 780)),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, im in cuts.items():
        im.save(OUT / name, optimize=True)
        print("wrote", OUT / name)
    progress_backgrounds()


def progress_backgrounds():
    """Clean generated backgrounds for the category progress windows."""
    global W, H
    W, H = 900, 760
    # Starlight Forest: deep green, teal glow, tree line.
    img = gradient((4, 30, 24), (3, 22, 18))
    glow(img, W * 0.8, H * 0.05, 420, 220, (20, 200, 150), 0.35)
    glow(img, W * 0.1, H * 0.9, 420, 260, (10, 120, 90), 0.3)
    stars(img, 500, 0.6)
    mountains(img, (2, 26, 18), H * 0.32, 14, seed=11)
    save_jpg(to_image(img), "pw-documents.jpg")
    # Aurora Music: violet night with pink glow.
    img = gradient((22, 6, 44), (30, 6, 52))
    glow(img, W * 0.85, H * 0.1, 420, 260, (255, 60, 170), 0.45)
    glow(img, W * 0.15, H * 0.75, 420, 300, (130, 60, 255), 0.4)
    clouds(img, (200, 70, 255), 0.4, seed=12)
    stars(img, 700)
    save_jpg(to_image(img), "pw-music.jpg")
    # Cinematic Horizon: sunset sky over dark mountains.
    img = gradient((40, 16, 30), (60, 24, 12))
    glow(img, W * 0.7, H * 0.25, 520, 200, (255, 120, 30), 0.55)
    glow(img, W * 0.2, H * 0.1, 400, 200, (120, 40, 90), 0.4)
    mountains(img, (22, 10, 10), H * 0.42, 10, seed=13)
    save_jpg(to_image(img), "pw-video.jpg")
    # Nebula Archive: light lavender with soft mountains.
    img = gradient((228, 230, 255), (244, 242, 255))
    glow(img, W * 0.85, H * 0.1, 300, 200, (-40, -40, 0), 0.8)
    glow(img, W * 0.2, H * 0.05, 400, 160, (-30, -10, -20), 0.6)
    mountains(img, (214, 216, 244), H * 0.3, 8, seed=14)
    save_jpg(to_image(img), "pw-compressed.jpg")
    W, H = 1600, 1000


def star_textures():
    """Transparent star overlays for the toolbar tiles and cards (light and dark variants)."""
    r = np.random.default_rng(21)

    def make(name, w, h, count, color, max_alpha, glints):
        a = np.zeros((h, w), float)
        ys, xs = r.integers(0, h, count), r.integers(0, w, count)
        a[ys, xs] = r.random(count) ** 2 * max_alpha
        big = Image.fromarray(a.astype("uint8")).filter(ImageFilter.GaussianBlur(0.35))
        a = np.maximum(a, np.asarray(big, float) * 1.6)
        for _ in range(glints):                      # a few brighter stars with a soft glow
            x, y = int(r.integers(4, w - 4)), int(r.integers(4, h - 4))
            yy, xx = np.ogrid[:h, :w]
            a = np.maximum(a, np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2.5) * 230)
        rgba = np.zeros((h, w, 4), "uint8")
        rgba[..., :3] = color
        rgba[..., 3] = np.clip(a, 0, 255).astype("uint8")
        OUT.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgba, "RGBA").save(OUT / name, optimize=True)
        print("wrote", OUT / name)

    # shown at real pixel size (repeated), so stars stay crisp inside small buttons
    make("tile-stars.png", 96, 96, 70, (240, 244, 255), 255, 3)
    make("tile-stars-dark.png", 96, 96, 60, (90, 80, 200), 200, 2)
    make("card-stars.png", 600, 600, 260, (220, 228, 255), 150, 5)


def planets():
    """Small planets for the toolbar buttons (one per button), lit from the top left."""
    N = 160
    r = np.random.default_rng(5)
    yy, xx = np.mgrid[:N, :N].astype(float)

    def sphere(cx, cy, rad):
        dx, dy = (xx - cx) / rad, (yy - cy) / rad
        d2 = dx * dx + dy * dy
        inside = d2 <= 1
        z = np.sqrt(np.clip(1 - d2, 0, 1))
        light = np.clip(-0.55 * dx - 0.6 * dy + 0.58 * z, 0, 1) * 0.85 + 0.15
        return inside, dx, dy, z, light

    def noise(scale, seed):
        g = np.random.default_rng(seed)
        small = Image.fromarray((g.random((N // scale, N // scale)) * 255).astype("uint8"))
        return np.asarray(small.resize((N, N), Image.BICUBIC).filter(ImageFilter.GaussianBlur(scale / 2)), float) / 255

    def finish(name, rgb, alpha):
        img = np.zeros((N, N, 4), "uint8")
        img[..., :3] = np.clip(rgb, 0, 255)
        img[..., 3] = np.clip(alpha * 255, 0, 255)
        im = Image.fromarray(img, "RGBA").filter(ImageFilter.GaussianBlur(0.6))
        im.save(OUT / name, optimize=True)
        print("wrote", OUT / name)

    def body(name, base, cx=80, cy=80, rad=70, texture=None, rings=None, glow=None):
        inside, dx, dy, z, light = sphere(cx, cy, rad)
        rgb = np.zeros((N, N, 3)) + np.array(base, float)
        if texture is not None:
            rgb = texture(rgb, dx, dy, z)
        rgb = rgb * light[..., None]
        edge = np.clip((1 - np.sqrt(dx * dx + dy * dy)) * rad / 1.5, 0, 1)
        alpha = inside * edge
        if glow:                                     # thin atmosphere
            d = np.sqrt(dx * dx + dy * dy)
            halo = np.exp(-((d - 1.0) * rad / 3.5) ** 2) * (d > 0.95)
            rgb = np.where(inside[..., None], rgb, np.array(glow, float))
            alpha = np.maximum(alpha, halo * 0.7)
        if rings:
            rcol, tilt = rings
            ex, ey = (xx - cx) / (rad * 1.75), (yy - cy) / (rad * 1.75 * tilt)
            rr = np.sqrt(ex * ex + ey * ey)
            band = ((rr > 0.62) & (rr < 0.98)) * (0.55 + 0.45 * np.sin(rr * 60) ** 2)
            front = (yy > cy) | ~inside
            ring_a = band * front * 0.9
            rgb = np.where((ring_a > alpha)[..., None], np.array(rcol, float) * (0.6 + 0.4 * band[..., None]), rgb)
            alpha = np.maximum(alpha, ring_a)
        finish(name, rgb, alpha)

    def earth(rgb, dx, dy, z):
        n = noise(16, 3)
        land = n > 0.55
        rgb[land] = np.array((70, 150, 80), float) + (n[land, None] - 0.55) * 200 * np.array((0.6, 0.3, 0.1))
        cloud = noise(10, 9) > 0.66
        rgb[cloud] = (235, 240, 250)
        return rgb

    def bands(colors, freq, seed):
        def t(rgb, dx, dy, z):
            wob = noise(20, seed) * 0.25
            k = (np.sin((dy + wob) * freq) + 1) / 2
            c1, c2 = np.array(colors[0], float), np.array(colors[1], float)
            return c1 + (c2 - c1) * k[..., None]
        return t

    def craters(rgb, dx, dy, z):
        n = noise(8, 4)
        return rgb * (0.75 + 0.35 * n[..., None])

    def mars(rgb, dx, dy, z):
        n = noise(12, 6)
        rgb = rgb * (0.8 + 0.35 * n[..., None])
        cap = dy < -0.82
        rgb[cap] = (245, 240, 235)
        return rgb

    OUT.mkdir(parents=True, exist_ok=True)
    body("planet-earth.png", (40, 100, 210), texture=earth, glow=(120, 180, 255))
    body("planet-saturn.png", (220, 190, 130), rad=46, texture=bands([(230, 200, 140), (190, 150, 100)], 14, 2),
         rings=((215, 195, 150), 0.32))
    body("planet-mars.png", (200, 90, 50), texture=mars)
    body("planet-jupiter.png", (210, 170, 130), texture=bands([(235, 210, 175), (175, 115, 75)], 22, 7))
    body("planet-neptune.png", (50, 90, 230), texture=bands([(70, 120, 240), (40, 70, 200)], 9, 8),
         glow=(110, 150, 255))
    body("planet-moon.png", (190, 190, 200), texture=craters)
    body("planet-venus.png", (235, 195, 120), texture=bands([(245, 215, 150), (215, 170, 100)], 6, 11))
    body("planet-uranus.png", (120, 210, 220), rad=50, texture=bands([(140, 225, 230), (110, 195, 210)], 5, 12),
         rings=((180, 230, 240), 0.95))
    body("planet-ice.png", (190, 160, 240), texture=bands([(210, 185, 250), (150, 120, 220)], 10, 13),
         glow=(200, 170, 255))


BRIGHT_KINDS = ["archive", "video", "music", "document", "program", "disc", "image", "unknown", "live"]
BRIGHT_TINTS = {"archive": (59, 130, 246), "video": (249, 115, 22), "music": (217, 70, 239),
                "document": (34, 197, 94), "program": (124, 58, 237), "disc": (234, 179, 8),
                "image": (6, 182, 212), "unknown": (100, 116, 139), "live": (239, 68, 68)}


def _feather(im, fade=14):
    im = im.convert("RGBA")
    w, h = im.size
    mask = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(mask)
    for i in range(fade):
        d.rectangle([i, i, w - 1 - i, h - 1 - i], outline=int(255 * (i / fade) ** 1.4))
    im.putalpha(mask.filter(ImageFilter.GaussianBlur(fade / 3)))
    return im


def _sky(w, h, top, mid, bottom, planet, planet_xy, cloud, mountain, seed):
    """Light sky: gradient, soft clouds, a big faint planet, distant mountains, a few sparkles."""
    global W, H
    W, H = w, h
    t = np.linspace(0, 1, h)[:, None, None]
    top, mid, bottom = (np.array(c, float) for c in (top, mid, bottom))
    img = np.where(t < 0.35, top + (mid - top) * (t / 0.35), mid + (bottom - mid) * ((t - 0.35) / 0.65))
    img = np.broadcast_to(img, (h, w, 3)).copy()
    # planet
    px, py, pr = planet_xy
    yy, xx = np.ogrid[:h, :w]
    dx, dy = (xx - px) / pr, (yy - py) / pr
    d2 = dx * dx + dy * dy
    inside = d2 <= 1
    z = np.sqrt(np.clip(1 - d2, 0, 1))
    light = np.clip(-0.5 * dx - 0.55 * dy + 0.6 * z, 0, 1)
    noise_r = np.random.default_rng(seed)
    small = Image.fromarray((noise_r.random((h // 24, w // 24)) * 255).astype("uint8"))
    tex = np.asarray(small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(10)), float) / 255
    pcol = np.array(planet, float)
    shade = pcol * (0.72 + 0.35 * light[..., None]) + (tex[..., None] - 0.5) * 30
    alpha = (inside * np.clip((1 - np.sqrt(d2)) * pr / 3, 0, 1) * 0.38)[..., None]
    img = img * (1 - alpha) + shade * alpha
    halo = np.exp(-((np.sqrt(d2) - 1) * pr / 30) ** 2) * (~inside) * 0.25
    img = img + halo[..., None] * (255 - img) * 0.6
    # mountains (far, hazy) and clouds
    for base, rough, col, sd, k in ((0.24, 7, mountain, seed + 1, 0.45), (0.27, 9, mountain, seed + 2, 0.65)):
        r = np.random.default_rng(sd)
        pts = np.cumsum(r.normal(0, rough, w // 10 + 2))
        pts = np.interp(np.arange(w), np.linspace(0, w, len(pts)), pts)
        pts = (pts - pts.min()) / max(1, pts.max() - pts.min())
        ridge = h * base - pts * h * 0.10 * np.linspace(0.2, 1.2, w)
        below = np.arange(h)[:, None] - ridge[None, :]
        f = ((below > 0) * np.exp(-np.clip(below, 0, None) / (h * 0.07)) * k * 0.5)[..., None]
        img = img * (1 - f) + np.array(col, float) * f
    r = np.random.default_rng(seed + 3)
    small = Image.fromarray((r.random((h // 40, w // 40)) * 255).astype("uint8"))
    cl = np.asarray(small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(26)), float) / 255
    band = np.exp(-((np.arange(h)[:, None] - h * 0.27) / (h * 0.11)) ** 2)
    c = np.clip((cl - 0.38) * 2.6, 0, 1) * band
    img = img * (1 - c[..., None] * 0.85) + np.array(cloud, float) * c[..., None] * 0.85
    # sparkles
    for _ in range(26):
        x, y = int(r.integers(0, w)), int(r.integers(0, int(h * 0.3)))
        img[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = 255
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"))


def bright_art(src):
    """Light picture themes: window backgrounds from photos, progress-window art per file kind."""
    global W, H
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = Image.open(src / "light themes" / "progress-windows.webp").convert("RGB")
    origins = [(12, 8), (522, 8), (1034, 8), (12, 348), (522, 348), (1034, 348), (12, 690), (522, 690), (1034, 690)]
    for kind, (x, y) in zip(BRIGHT_KINDS, origins):
        ill = _feather(sheet.crop((x + 6, y + 100, x + 128, y + 220)).resize((244, 240), Image.LANCZOS), 22)
        ill.save(OUT / f"pw2-ill-{kind}.png", optimize=True)
        c = BRIGHT_TINTS[kind]
        tint = tuple(int(255 - (255 - v) * 0.16) for v in c)
        mid = tuple(int(255 - (255 - v) * 0.08) for v in c)
        bg = _sky(900, 640, tint, mid, (250, 251, 253), tuple(int(v * 0.7 + 255 * 0.3) for v in c),
                  (760, -120, 160), (255, 255, 255), tuple(int(255 - (255 - v) * 0.28) for v in c),
                  50 + BRIGHT_KINDS.index(kind))
        save_jpg(bg, f"pw2-bg-{kind}.jpg")
    W, H = 1600, 1000


# Header pictures cut out of the theme concept sheets ("light themes/themes-set-1.webp" and
# "-2.webp"). The UI drawn in the concepts (logo, buttons, tiles, captions) is masked out and the
# holes are filled from the surrounding picture; the band then melts into the theme colour.
SET1_ROWS, SET2_ROWS = (0, 338, 676), (0, 340, 680)
SET1_MASKS = [(0, 0, 128, 48), (312, 0, 498, 38), (74, 34, 430, 70)]
SET2_MASKS = [(0, 0, 345, 50), (0, 46, 504, 66), (0, 60, 144, 106), (350, 60, 504, 90), (82, 84, 450, 128)]
HEADERS = {  # out: (sheet, panel index 0-8, base colour, dark)
    "hd-cosmic-sky.jpg": (2, 0, (238, 243, 252), False), "hd-starlight-forest.jpg": (2, 2, (239, 247, 240), False),
    "hd-aurora.jpg": (1, 2, (251, 241, 253), False), "hd-sunrise.jpg": (1, 3, (255, 246, 238), False),
    "hd-ocean.jpg": (1, 4, (238, 248, 253), False), "hd-minimal.jpg": (1, 5, (244, 246, 250), False),
    "hd-lavender.jpg": (1, 6, (246, 243, 254), False), "hd-sandstone.jpg": (1, 7, (251, 246, 236), False),
    "hd-monochrome.jpg": (1, 8, (243, 245, 248), False), "hd-sunset-nebula.jpg": (2, 1, (253, 242, 248), False),
    "hd-aurora-glow.jpg": (2, 3, (11, 12, 34), True), "hd-galaxy-dark.jpg": (2, 4, (9, 11, 32), True),
    "hd-forest-night.jpg": (2, 5, (7, 21, 15), True), "hd-midnight-ocean.jpg": (2, 6, (6, 16, 31), True),
    "hd-royal-purple.jpg": (2, 7, (16, 8, 34), True), "hd-solar-eclipse.jpg": (2, 8, (20, 11, 5), True),
}


def _box(a, r, axis):
    """Float box blur along one axis (edge-padded), via cumulative sums."""
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def _blur(a, r):
    for _ in range(3):                                # 3 box passes ~ gaussian
        a = _box(_box(a, r, 0), r, 1)
    return a


def _inpaint(im, boxes):
    """Fill the boxes from the surrounding picture: normalised blur at growing radius, nearest
    detail first, with a feathered edge so the filled parts blend in."""
    a = np.asarray(im, float)
    m = np.ones(a.shape[:2])
    for x0, y0, x1, y1 in boxes:
        m[y0:y1, x0:x1] = 0
    est = np.zeros_like(a)
    done = m > 0
    for r in (3, 6, 12, 24, 48, 96, 192):
        den = _blur(m, r)
        num = _blur(a * m[..., None], r)
        f = num / np.maximum(den, 1e-6)[..., None]
        take = (~done) & (den > 0.04)
        est[take] = f[take]
        done |= take
    est[~done] = a[m > 0].mean(axis=0)
    est = np.where(m[..., None] > 0, a, est)
    est = np.where(m[..., None] > 0, a, _blur(est, 4))     # smooth the filled area a little
    keep = (_blur(m, 4) * m)[..., None]
    out = a * keep + est * (1 - keep)
    return Image.fromarray(np.clip(out, 0, 255).astype("uint8"))


def _match_window(crop, top=54):
    """Sheet 2 draws the window as a tinted glass panel over the scene: undo the tint by matching
    the panel area's colour statistics to the open sky above it."""
    a = np.asarray(crop, float).copy()
    ref = a[:top - 6, 345:]
    win = a[top + 6:]
    for c in range(3):
        mu, sd = win[..., c].mean(), win[..., c].std() + 1e-3
        a[top + 6:, :, c] = (win[..., c] - mu) / sd * ref[..., c].std() + ref[..., c].mean()
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


def concept_header(src, sheet, idx, base, dark, band=330):
    im = Image.open(src / "light themes" / f"themes-set-{sheet}.webp").convert("RGB")
    r, c = divmod(idx, 3)
    if sheet == 1:
        x0, y0 = c * 512, SET1_ROWS[r]
        crop, masks = im.crop((x0 + 10, y0 + 26, x0 + 508, y0 + 92)), SET1_MASKS
    else:
        x0, y0 = c * 512, SET2_ROWS[r]
        crop, masks = _match_window(im.crop((x0 + 4, y0, x0 + 508, y0 + 128))), SET2_MASKS
    art = _inpaint(crop, masks).resize((1600, band), Image.LANCZOS)
    art = art.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(1.4))
    a = np.asarray(art, float)
    b = np.array(base, float)
    end = np.array((255, 255, 255) if not dark else tuple(min(255, v + 6) for v in base), float)
    t = np.linspace(0, 1, 1000)[:, None, None]
    canvas = np.broadcast_to(b + (end - b) * t * 0.5, (1000, 1600, 3)).copy()
    ys = np.arange(band)[:, None, None]
    fade_from = band * 0.45
    k = np.clip(1 - (ys - fade_from) / (band - fade_from), 0, 1) ** 1.5
    canvas[:band] = canvas[:band] * (1 - k) + a * k
    return Image.fromarray(np.clip(canvas, 0, 255).astype("uint8"))


FROM_BG = {  # out: (existing full-window background, base colour, dark)
    "hd-galaxy-explorer.jpg": ("bg-galaxy-explorer.jpg", (7, 10, 34), True),
    "hd-aurora-light.jpg": ("bg-aurora-light.jpg", (236, 238, 255), False),
}


def header_from_bg(name, base, dark, band=330):
    """Top of an older full-window background as a header band fading into the theme colour."""
    a = np.asarray(Image.open(OUT / name).convert("RGB").resize((1600, 1000)), float)[:band]
    b = np.array(base, float)
    end = np.array((255, 255, 255) if not dark else tuple(min(255, v + 6) for v in base), float)
    t = np.linspace(0, 1, 1000)[:, None, None]
    canvas = np.broadcast_to(b + (end - b) * t * 0.5, (1000, 1600, 3)).copy()
    ys = np.arange(band)[:, None, None]
    k = np.clip(1 - (ys - band * 0.45) / (band * 0.55), 0, 1) ** 1.5
    canvas[:band] = canvas[:band] * (1 - k) + a * k
    return Image.fromarray(np.clip(canvas, 0, 255).astype("uint8"))


def faded_galaxy():
    """The galaxy illustration as a card background: dark space turns transparent, edges fade."""
    im = Image.open(OUT / "ill-galaxy.png").convert("RGB")
    a = np.asarray(im, float)
    h, w = a.shape[:2]
    lum = a.max(axis=2) / 255
    alpha = np.clip((lum - 0.10) * 1.9, 0, 1)
    fx = np.clip((np.linspace(0, 1, w) - 0.05) / 0.45, 0, 1) ** 1.4      # fade in from the left
    fy = np.minimum(np.clip(np.linspace(0, 1, h) / 0.18, 0, 1), np.clip(np.linspace(1, 0, h) / 0.18, 0, 1))
    fx = fx * np.clip(np.linspace(1, 0, w) / 0.08, 0, 1)
    alpha = alpha * fx[None, :] * fy[:, None]
    rgba = np.dstack([a, alpha * 255]).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(OUT / "ill-galaxy-fade.png", optimize=True)
    print("wrote", OUT / "ill-galaxy-fade.png")


def light_card_art():
    """Pastel planet scene for the light Classic window card (transparent, fades in from the left)."""
    w, h = 520, 300
    yy, xx = np.mgrid[:h, :w].astype(float)
    rgb = np.zeros((h, w, 3)); alpha = np.zeros((h, w))

    def over(col, a):
        nonlocal rgb, alpha
        a = np.clip(a, 0, 1)
        rgb = rgb * (1 - a[..., None]) + np.array(col, float) * a[..., None] if np.ndim(col) == 1 else \
            rgb * (1 - a[..., None]) + col * a[..., None]
        alpha = alpha + a * (1 - alpha)

    # soft nebula glow
    for cx, cy, r, col, k in ((380, 120, 170, (196, 181, 253), .55), (300, 200, 150, (249, 168, 212), .35),
                              (470, 60, 120, (165, 243, 252), .35)):
        over(col, np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r)) * k)
    # planet
    cx, cy, r = 380, 140, 78
    dx, dy = (xx - cx) / r, (yy - cy) / r
    d2 = dx * dx + dy * dy
    inside = d2 <= 1
    z = np.sqrt(np.clip(1 - d2, 0, 1))
    light = np.clip(-0.55 * dx - 0.6 * dy + 0.6 * z, 0, 1)
    band = (np.sin((dy + 0.15 * dx) * 9) + 1) / 2
    base = np.array((167, 139, 250)) * (1 - band[..., None] * .35) + np.array((244, 114, 182)) * band[..., None] * .35
    shade = base * (0.55 + 0.6 * light[..., None]) + 255 * (light[..., None] ** 6) * .5
    edge = np.clip((1 - np.sqrt(d2)) * r / 1.5, 0, 1)
    # ring (back half, planet, front half)
    ex, ey = (xx - cx) / (r * 1.9), (yy - cy) / (r * 0.42)
    ry = (xx - cx) * np.sin(-0.32) + (yy - cy) * np.cos(-0.32)
    rx = (xx - cx) * np.cos(-0.32) - (yy - cy) * np.sin(-0.32)
    rr = np.sqrt((rx / (r * 1.85)) ** 2 + (ry / (r * 0.45)) ** 2)
    ring = ((rr > 0.78) & (rr < 1.0)) * (0.55 + 0.45 * np.sin(rr * 70) ** 2)
    ringcol = np.array((224, 231, 255))
    over(ringcol, ring * (ry < 0) * 0.85)
    over(shade, inside * edge)
    over(ringcol, ring * (ry >= 0) * 0.9)
    # clouds at the bottom
    r_ = np.random.default_rng(3)
    small = Image.fromarray((r_.random((h // 20, w // 20)) * 255).astype("uint8"))
    cl = np.asarray(small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(14)), float) / 255
    over((255, 255, 255), np.clip((cl - 0.35) * 2.5, 0, 1) * np.clip((yy - h * 0.62) / (h * 0.3), 0, 1) * .9)
    # sparkles
    for _ in range(40):
        sx, sy = r_.integers(140, w), r_.integers(0, h)
        over((255, 255, 255), np.exp(-((xx - sx) ** 2 + (yy - sy) ** 2) / 2.2) * r_.uniform(.5, 1))
    for sx, sy, s in ((250, 60, 9), (480, 230, 7), (205, 180, 6)):
        cross = np.maximum(np.exp(-((xx - sx) / 0.9) ** 2 - ((yy - sy) / s) ** 2),
                           np.exp(-((xx - sx) / s) ** 2 - ((yy - sy) / 0.9) ** 2))
        over((255, 255, 255), cross)
    straight = np.clip(rgb / np.maximum(alpha, 1e-4)[..., None], 0, 255)      # rgb is premultiplied
    fx = np.clip(np.linspace(0, 1, w) / 0.40, 0, 1) ** 1.4 * np.clip(np.linspace(1, 0, w) / 0.10, 0, 1)
    fy = np.minimum(np.clip(np.linspace(0, 1, h) / 0.15, 0, 1), np.clip(np.linspace(1, 0, h) / 0.15, 0, 1))
    alpha = alpha * fx[None, :] * fy[:, None]
    rgba = np.dstack([straight, alpha * 255]).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(OUT / "ill-sky-fade.png", optimize=True)
    print("wrote", OUT / "ill-sky-fade.png")


def pastel_planet_scene(w, h, seed=8):
    """Soft daytime sky: a big lavender-blue planet with a ring and two moons over snowy peaks."""
    global W, H
    W, H = w, h
    t = np.linspace(0, 1, h)[:, None, None]
    img = np.broadcast_to(np.array((206, 222, 255), float) + (np.array((246, 244, 255), float) -
                          np.array((206, 222, 255), float)) * t, (h, w, 3)).copy()
    glow(img, w * 0.62, h * 0.35, w * 0.5, h * 0.6, (40, 30, 20), 0.6)
    yy, xx = np.mgrid[:h, :w].astype(float)

    def disc(cx, cy, r, c1, c2, bands=0.0):
        nonlocal img
        dx, dy = (xx - cx) / r, (yy - cy) / r
        d2 = dx * dx + dy * dy
        z = np.sqrt(np.clip(1 - d2, 0, 1))
        light = np.clip(-0.55 * dx - 0.55 * dy + 0.62 * z, 0, 1)
        band = (np.sin((dy * 1.0 + 0.25 * dx) * 10 + seed) + 1) / 2 * bands
        col = np.array(c1, float) * (1 - band[..., None]) + np.array(c2, float) * band[..., None]
        col = col * (0.55 + 0.55 * light[..., None]) + 255 * light[..., None] ** 10 * 0.35
        k = np.clip((1 - np.sqrt(d2)) * r / 1.4, 0, 1)[..., None]
        img = img * (1 - k) + col * k
        halo = np.exp(-((np.sqrt(d2) - 1) * r / 10) ** 2) * (d2 > 1) * 0.22
        img = img + halo[..., None] * (255 - img)

    def ring(cx, cy, r, front):
        nonlocal img
        ang = -0.30
        rx = (xx - cx) * np.cos(ang) - (yy - cy) * np.sin(ang)
        ry = (xx - cx) * np.sin(ang) + (yy - cy) * np.cos(ang)
        rr = np.sqrt((rx / (r * 1.75)) ** 2 + (ry / (r * 0.36)) ** 2)
        k = ((rr > 0.80) & (rr < 1.0)) * (0.5 + 0.5 * np.sin(rr * 60) ** 2) * 0.85
        k = k * ((ry > 0) if front else (ry <= 0))
        img = img * (1 - k[..., None]) + np.array((235, 240, 255), float) * k[..., None]

    pcx, pcy, pr = w * 0.62, h * 0.48, h * 0.42
    ring(pcx, pcy, pr, front=False)
    disc(pcx, pcy, pr, (110, 140, 250), (170, 130, 245), bands=0.55)
    ring(pcx, pcy, pr, front=True)
    disc(w * 0.89, h * 0.24, h * 0.09, (170, 185, 245), (200, 190, 250))
    disc(w * 0.40, h * 0.70, h * 0.075, (180, 190, 240), (210, 200, 250))
    mountains(img, (196, 208, 242), h * 1.04, 12, seed=seed)
    mountains(img, (226, 232, 250), h * 1.10, 8, seed=seed + 5)
    r = np.random.default_rng(seed)
    small = Image.fromarray((r.random((h // 16 + 1, w // 16 + 1)) * 255).astype("uint8"))
    cl = np.asarray(small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(10)), float) / 255
    k = np.clip((cl - 0.40) * 2.6, 0, 1) * np.clip((yy - h * 0.70) / (h * 0.22), 0, 1)
    img = img * (1 - k[..., None]) + 255 * k[..., None]
    for _ in range(30):
        sx, sy = r.integers(0, w), r.integers(0, int(h * 0.6))
        img = img + np.exp(-((xx - sx) ** 2 + (yy - sy) ** 2) / 1.5)[..., None] * 160
    W, H = 1600, 1000
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"))


def light_classic_art(src):
    """Light Classic window: planet + mountains scene from the sky concept (UI drawn in it masked out),
    as the status-card picture and as the window's top band."""
    art = pastel_planet_scene(660, 230)
    a = np.asarray(art, float)
    h, w = a.shape[:2]
    fx = np.clip(np.linspace(0, 1, w) / 0.42, 0, 1) ** 1.3
    fy = np.minimum(np.clip(np.linspace(0, 1, h) / 0.08, 0, 1), np.clip(np.linspace(1, 0, h) / 0.10, 0, 1))
    rgba = np.dstack([a, fx[None, :] * fy[:, None] * 255]).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(OUT / "ill-sky-fade.png", optimize=True)
    print("wrote", OUT / "ill-sky-fade.png")
    # window: soft pastel with the scene in a band at the top right
    W2, H2 = 900, 1000
    base = np.array((244, 247, 254), float)
    canvas = np.broadcast_to(base, (H2, W2, 3)).copy()
    band = np.asarray(pastel_planet_scene(W2, 266, seed=4), float)
    ys = np.arange(266)[:, None, None]
    k = np.clip(1 - (ys - 90) / 176, 0, 1) ** 1.4 * np.clip(np.linspace(0, 1, W2) / 0.5, 0, 1)[None, :, None] ** 1.2
    canvas[:266] = canvas[:266] * (1 - k) + band * k
    save_jpg(Image.fromarray(np.clip(canvas, 0, 255).astype("uint8")), "pw-galaxy-light-bg.jpg")


def _edge_fade(im, left=0.40, right=0.04, top=0.06, bottom=0.08):
    a = np.asarray(im.convert("RGB"), float)
    h, w = a.shape[:2]
    fx = np.minimum(np.clip(np.linspace(0, 1, w) / left, 0, 1) ** 1.3, np.clip(np.linspace(1, 0, w) / right, 0, 1))
    fy = np.minimum(np.clip(np.linspace(0, 1, h) / top, 0, 1), np.clip(np.linspace(1, 0, h) / bottom, 0, 1))
    return Image.fromarray(np.dstack([a, fx[None, :] * fy[:, None] * 255]).astype("uint8"), "RGBA")


def _band_background(scene, base, wash, W2=900, H2=1000, band=290):
    """Window background: plain theme colour with the scene softly in a band at the top."""
    b = np.array(base, float)
    canvas = np.broadcast_to(b, (H2, W2, 3)).copy()
    sc = scene.convert("RGB")
    sc = sc.resize((W2, round(sc.height * W2 / sc.width)), Image.LANCZOS).crop((0, 0, W2, band))
    a = np.asarray(sc.filter(ImageFilter.GaussianBlur(1.2)), float)
    a = a * (1 - wash) + b * wash
    ys = np.arange(band)[:, None, None]
    k = np.clip(1 - (ys - band * 0.35) / (band * 0.65), 0, 1) ** 1.4
    canvas[:band] = canvas[:band] * (1 - k) + a * k
    return Image.fromarray(np.clip(canvas, 0, 255).astype("uint8"))


def classic_window_art(src):
    """Classic progress window pictures from the two concept scenes (light: planet over clouds and
    peaks; dark: ringed planet over a lake): card pictures with soft edges and window backgrounds."""
    light = Image.open(src / "light themes" / "classic-light.webp").convert("RGB")
    dark = Image.open(src / "light themes" / "classic-dark.webp").convert("RGB")
    card = light.crop((560, 90, 1914, 720))
    _edge_fade(card.resize((round(card.width * 300 / card.height), 300), Image.LANCZOS)).save(
        OUT / "ill-sky-fade.png", optimize=True)
    card = dark.crop((180, 20, 1000, 560))
    _edge_fade(card.resize((round(card.width * 300 / card.height), 300), Image.LANCZOS), left=0.35).save(
        OUT / "ill-galaxy-fade.png", optimize=True)
    save_jpg(_band_background(light.crop((700, 120, 1914, 640)), (244, 247, 254), 0.45), "pw-galaxy-light-bg.jpg")
    save_jpg(_band_background(dark.crop((0, 0, 1000, 330)), (9, 11, 34), 0.35), "pw-galaxy-bg.jpg")
    print("wrote classic window art")


def galaxy_window_backgrounds():
    """Backgrounds of the Classic progress window: deep space (dark), soft pastel (light)."""
    global W, H
    W, H = 900, 1000
    img = gradient((8, 10, 36), (10, 9, 34))
    glow(img, W * 0.85, H * 0.05, 380, 260, (90, 60, 255), 0.45)
    glow(img, W * 0.05, H * 0.95, 420, 300, (40, 90, 255), 0.30)
    glow(img, W * 0.95, H * 0.7, 300, 300, (150, 50, 220), 0.22)
    clouds(img, (90, 70, 220), 0.45, seed=3)
    stars(img, 1500)
    save_jpg(to_image(img), "pw-galaxy-bg.jpg")
    img = gradient((246, 244, 255), (250, 251, 255))
    glow(img, W * 0.9, H * 0.0, 420, 240, (-18, -22, 0), 1.0)          # faint lavender corner
    glow(img, W * 0.0, H * 1.0, 420, 300, (-10, -4, -18), 1.0)         # faint pink corner
    save_jpg(to_image(img), "pw-galaxy-light-bg.jpg")
    W, H = 1600, 1000


def header_art(src):
    for out, (sheet, idx, base, dark) in HEADERS.items():
        save_jpg(concept_header(src, sheet, idx, base, dark), out)
    for out, (name, base, dark) in FROM_BG.items():
        save_jpg(header_from_bg(name, base, dark), out)


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    if len(sys.argv) > 2 and sys.argv[2] == "headers":
        header_art(src)
        sys.exit()
    backgrounds(src)
    illustrations(src)
    star_textures()
    planets()
    bright_art(src)
    header_art(src)
    classic_window_art(src)
