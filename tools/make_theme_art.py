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

    # Cosmic Minimal: calm navy, few stars, one soft planet glow.
    img = gradient((7, 12, 32), (5, 9, 24))
    glow(img, W * 0.92, H * 0.08, 260, 220, (60, 110, 255), 0.45)
    glow(img, W * 0.2, H * 1.0, 700, 300, (30, 60, 160), 0.3)
    stars(img, 900, 0.7)
    save_jpg(to_image(img), "bg-cosmic-minimal.jpg")

    # Nebula Glow: magenta/violet nebula with purple mountains.
    img = gradient((20, 6, 40), (34, 8, 46))
    glow(img, W * 0.75, H * 0.15, 600, 300, (255, 60, 200), 0.45)
    glow(img, W * 0.25, H * 0.35, 500, 300, (140, 60, 255), 0.45)
    glow(img, W * 0.5, H * 0.9, 700, 250, (255, 120, 60), 0.25)
    clouds(img, (255, 80, 200), 0.6, seed=5)
    clouds(img, (120, 80, 255), 0.5, scale=12, seed=6)
    stars(img, 2000)
    mountains(img, (24, 8, 40), H * 1.02, 6, seed=2)
    save_jpg(to_image(img), "bg-nebula-glow.jpg")

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


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    backgrounds(src)
    illustrations(src)
    star_textures()
    planets()
