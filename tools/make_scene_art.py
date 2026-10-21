"""Pictures for the live planet in the details pane (draco/gui/planet_scene.py).

    python3 tools/make_scene_art.py

Everything is drawn here from numbers (no photos, nothing downloaded), so the art is Draco's own:
  scene-nebula-a.png  nebula cloud layer, wraps left/right so it can drift forever
  scene-nebula-b.png  second, thinner cloud layer that drifts at another speed
  scene-planet.jpg     96 frames of a turning planet (12 x 8 sheet), sunlight baked in
Needs numpy and Pillow (only to build the art, not to run Draco)."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ART = Path(__file__).resolve().parent.parent / "draco" / "art"
RNG = np.random.default_rng(7)

FRAMES, COLS, FRAME = 96, 12, 200        # globe sheet: 96 frames of 200 px in 12 columns


def periodic_noise(h, w, slope=2.2, seed=0):
    """Smooth fractal noise that wraps on both axes (filtered white noise), scaled to 0..1."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfft2(rng.standard_normal((h, w)))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    k = np.sqrt(fx ** 2 + fy ** 2)
    k[0, 0] = 1
    n = np.fft.irfft2(f / k ** slope, s=(h, w))
    n -= n.min()
    return n / n.max()


# ------------------------------------------------------------------ nebula
def nebula(name, w, h, seed, palette, cover):
    a = periodic_noise(h, w, 1.9, seed)
    b = periodic_noise(h, w, 1.2, seed + 1)
    q = np.quantile(a, 1 - cover)
    m = np.clip((a - q + 0.1) / (1 - q + 0.1), 0, 1) ** 1.5       # soft edges, no hard cut
    m = m * (0.5 + 1.0 * b) + np.clip(b - 0.6, 0, 1) * 0.35 * m ** 0.3
    t = periodic_noise(h, w, 2.3, seed + 2)[..., None]
    c0, c1, c2 = (np.array(p, np.float32) / 255 for p in palette)
    rgb = c0 * (1 - t) + c1 * t
    glow = np.clip((m - 0.55) * 2.5, 0, 1)[..., None]
    rgb = rgb * (1 - glow * 0.5) + c2 * glow * 0.5
    alpha = np.clip(m * 1.15, 0, 0.95)
    # fade out at the top and bottom so the layer has no hard edge (it wraps left/right)
    yy = np.linspace(0, 1, h)[:, None]
    alpha *= np.clip(np.minimum(yy, 1 - yy) * 4, 0, 1)
    img = np.dstack([np.clip(rgb, 0, 1), alpha])
    Image.fromarray((img * 255).astype(np.uint8), "RGBA").save(ART / name, optimize=True)


# ------------------------------------------------------------------ earth
# Coarse coastlines (longitude, latitude), drawn by hand for a small globe.
LAND = [
    # North America
    [(-168, 66), (-162, 70), (-156, 71), (-140, 70), (-128, 70), (-115, 68), (-95, 72), (-82, 73), (-78, 64),
     (-90, 63), (-94, 58), (-85, 55), (-80, 52), (-78, 58), (-70, 60), (-62, 58), (-56, 52), (-60, 47),
     (-66, 45), (-70, 42), (-76, 38), (-76, 35), (-81, 31), (-80, 26), (-82, 26), (-84, 30), (-90, 29),
     (-97, 27), (-97, 21), (-94, 18), (-88, 21), (-87, 16), (-83, 10), (-79, 9), (-77, 8), (-80, 7),
     (-85, 10), (-92, 14), (-105, 20), (-110, 24), (-112, 30), (-117, 32), (-120, 35), (-124, 40),
     (-124, 48), (-130, 55), (-138, 59), (-147, 61), (-152, 59), (-158, 57), (-165, 55), (-160, 59),
     (-166, 62)],
    # Greenland
    [(-73, 78), (-60, 82), (-30, 83), (-20, 80), (-20, 72), (-25, 69), (-40, 65), (-44, 60), (-50, 62),
     (-54, 67), (-60, 75)],
    # South America
    [(-80, 9), (-75, 11), (-71, 12), (-63, 10), (-60, 8), (-52, 5), (-50, 0), (-44, -2), (-35, -6),
     (-35, -10), (-39, -15), (-40, -22), (-48, -26), (-53, -34), (-58, -38), (-63, -41), (-65, -46),
     (-68, -51), (-69, -55), (-73, -53), (-75, -47), (-73, -38), (-71, -30), (-70, -18), (-76, -14),
     (-81, -6), (-80, -1), (-78, 3), (-77, 7)],
    # Eurasia
    [(-9, 37), (-9, 43), (-2, 43.5), (-1, 46), (-4.5, 48), (2, 50.5), (5, 53), (8, 54), (8, 57),
     (10.5, 57.5), (10, 55), (12, 54), (14, 54), (18, 54.5), (21, 55), (21, 57), (24, 57), (24, 59.5),
     (29, 60), (23, 60.5), (21, 61), (22, 65), (25, 65.5), (21, 63), (17.5, 62), (19, 60), (16, 56),
     (12.5, 56), (11, 59), (6, 58), (5, 61), (8, 63), (14, 67), (17, 69), (23, 70.5), (30, 70),
     (33, 69), (41, 67), (44, 68), (53, 68), (60, 69), (68, 69), (73, 72), (80, 73), (87, 75), (98, 76),
     (105, 78), (113, 74), (125, 73), (140, 72), (150, 71), (160, 70), (170, 70), (180, 69), (180, 65),
     (172, 64), (178, 62), (170, 60), (163, 58), (162, 55), (156, 51), (156, 58), (160, 61), (155, 60),
     (143, 59), (136, 54), (140, 50), (140, 46), (135, 43), (130, 42), (129, 36), (126, 35), (126, 38),
     (125, 40), (121, 39), (122, 37), (119, 35), (121, 32), (122, 29), (119, 25), (115, 22), (110, 21),
     (108, 21), (106, 18), (109, 12), (105, 9), (100, 13), (100, 8), (103, 1.5), (101, 3), (98, 8),
     (98, 16), (94, 16), (92, 21), (90, 22), (87, 21), (80, 15), (80, 10), (77, 8), (73, 16), (72, 21),
     (67, 24), (62, 25), (57, 26), (56, 24), (59, 22), (55, 17), (52, 16), (45, 13), (43, 13), (39, 20),
     (35, 28), (34, 31), (35, 36), (31, 36.5), (27, 37), (26, 40), (29, 41), (28, 42), (28, 44),
     (30, 45.5), (33, 44.5), (36, 45), (38, 47), (39, 44), (41, 41.5), (36, 41.5), (32, 41), (28, 41),
     (26, 40.5), (23, 40), (24, 37.5), (22, 37), (21, 39), (19.5, 42), (15.5, 44), (13.5, 45.5),
     (12.5, 44), (16, 41), (18.5, 40), (16, 38), (15.5, 38.5), (15.5, 40.5), (12, 42), (10, 44),
     (7.5, 43.8), (3, 43), (3, 42), (0, 39.5), (-0.5, 38), (-2, 37), (-5.5, 36)],
    # Africa
    [(-17, 21), (-13, 28), (-10, 30), (-6, 35.8), (-2, 35.2), (3, 37), (10, 37), (11, 33), (20, 31),
     (25, 32), (32, 31.5), (34, 28), (37, 22), (39, 15), (43, 12), (51, 12), (51, 10), (48, 4), (42, -1),
     (40, -5), (40, -11), (41, -15), (35, -21), (35, -25), (33, -27), (30, -31), (27, -34), (20, -35),
     (18, -32), (16, -28), (14, -22), (12, -17), (13, -12), (12, -5), (9, -1), (10, 3), (8, 4.5), (4, 6),
     (-2, 5), (-8, 4.5), (-13, 8), (-15, 11), (-17, 15)],
    [(44, -25), (47, -25), (50, -15), (49, -12), (44, -17)],                                # Madagascar
    # Australia
    [(114, -22), (114, -26), (115, -34), (118, -35), (123, -34), (129, -32), (135, -35), (138, -35),
     (141, -38), (146, -39), (150, -37), (153, -31), (153, -25), (150, -22), (146, -19), (145, -15),
     (143, -11), (142, -14), (141, -17), (136, -12), (132, -11), (129, -15), (126, -14), (122, -18)],
    [(-5, 50), (1.5, 51), (1.7, 52.8), (-0.5, 54.5), (-2, 56), (-1.8, 57.6), (-5, 58.6), (-6, 56.5),
     (-5, 54.8), (-3, 54), (-4.5, 53), (-5.2, 51.7)],                                       # Great Britain
    [(-10, 51.5), (-6, 52), (-6, 54.5), (-8, 55.2), (-10, 54)],                             # Ireland
    [(130, 31), (132, 34), (135, 34), (140, 35), (141, 38), (142, 41), (141.5, 45.5), (145, 44), (143, 42),
     (140, 41.5), (140, 39), (137, 37), (133, 35.5), (130, 33.5)],                           # Japan
    [(95, 5.5), (98, 4), (104, -1), (106, -6), (102, -4), (96, 3)],                         # Sumatra
    [(109, 2), (111, 1.5), (117, 7), (119, 5), (118, 1), (116, -4), (110, -3)],             # Borneo
    [(105, -6), (114, -7), (114, -8.5), (106, -7.5)],                                       # Java
    [(131, -1), (138, -1.5), (146, -5), (150, -10), (143, -9), (138, -8), (132, -4)],       # New Guinea
    [(120, 18), (122, 18), (124, 12), (126, 7), (122, 7), (120, 14)],                       # Philippines
    [(172, -34.5), (178, -38), (175, -41.5), (174, -41), (167, -46.5), (171, -44), (173, -41)],  # New Zealand
    [(80, 9.8), (82, 7), (80, 6), (79.7, 8)],                                               # Sri Lanka
    [(-24, 65.5), (-14, 66), (-13.5, 65), (-18, 63.5), (-22, 63.8)],                        # Iceland
    [(-85, 22), (-74, 20), (-77, 20), (-82, 23)],                                           # Cuba
    [(-80, 73), (-68, 70), (-62, 66), (-68, 62), (-78, 64), (-90, 70)],                     # Baffin Island
]


def earth_maps(w=2048, h=1024):
    def px(lon, lat):
        return ((lon + 180) / 360 * w, (90 - lat) / 180 * h)

    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    for poly in LAND:
        d.polygon([px(*p) for p in poly], fill=255)
    ant = [px(-180, -90)] + [px(lon, -71 - 5 * ((lon // 20) % 2) - 2 * np.sin(lon / 13))
                             for lon in range(-180, 181, 10)] + [px(180, -90)]
    d.polygon(ant, fill=255)
    # rough the hand-drawn coasts a little
    land = np.asarray(mask.filter(ImageFilter.GaussianBlur(5)), np.float32) / 255
    rough = periodic_noise(h, w, 1.4, 11)
    land = (land + (rough - 0.5) * 0.5) > 0.5
    lat = np.linspace(90, -90, h)[:, None] * np.ones((1, w))
    lon = np.linspace(-180, 180, w)[None, :] * np.ones((h, 1))
    wet = periodic_noise(h, w, 2.0, 12)
    grain = periodic_noise(h, w, 1.1, 13)
    alat = np.abs(lat) + (periodic_noise(h, w, 2.2, 14) - 0.5) * 18     # wavy climate borders
    ragged = lat + (wet - 0.5) * 10
    desert = np.zeros_like(lat, bool)
    for lo0, lo1, la0, la1 in ((-17, 58, 15, 33), (44, 62, 12, 30), (50, 75, 25, 40), (75, 115, 36, 48),
                               (118, 145, -32, -19), (14, 28, -28, -18), (-118, -103, 27, 37),
                               (-72, -68, -28, -18), (-70, -64, -48, -38)):
        desert |= (lon > lo0) & (lon < lo1) & (ragged > la0) & (ragged < la1)
    soft = np.asarray(Image.fromarray(desert.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(28)),
                      np.float32) / 255
    sandy = np.clip((soft + (grain - 0.5) * 0.7 + (0.5 - wet) * 0.4 - 0.3) * 3, 0, 1)[..., None]
    green = np.array([46, 104, 52], np.float32)
    forest = np.array([28, 78, 40], np.float32)
    sand = np.array([196, 168, 112], np.float32)
    tundra = np.array([132, 124, 96], np.float32)
    ice = np.array([236, 242, 248], np.float32)
    col = green * (1 - wet[..., None]) + forest * wet[..., None]
    col = col * (1 - sandy) + sand * (0.85 + 0.25 * wet[..., None]) * sandy
    col = np.where((alat > 58)[..., None], tundra, col)
    col = np.where(((alat > 70) | ((lon > -60) & (lon < -18) & (lat > 62)))[..., None], ice, col)
    col = col * (0.78 + 0.44 * grain[..., None])
    shelf = np.asarray(Image.fromarray((land * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14)),
                       np.float32)[..., None] / 255
    deep = np.array([8, 34, 86], np.float32)
    shallow = np.array([28, 96, 152], np.float32)
    sea = deep * (1 - shelf) + shallow * shelf
    sea = np.where((np.abs(lat) > 76)[..., None], ice * 0.92, sea)
    tex = np.where(land[..., None], col, sea) / 255
    cl = periodic_noise(h, w, 1.7, 21)
    streak = periodic_noise(h // 2, w, 2.4, 22)
    streak = np.asarray(Image.fromarray((streak * 255).astype(np.uint8)).resize((w, h)), np.float32) / 255
    band = np.exp(-((lat - 4) / 9) ** 2) * 0.25 + np.exp(-((alat - 55) / 12) ** 2) * 0.2
    clouds = np.clip((cl * 0.65 + streak * 0.35 + band - 0.64) * 2.8, 0, 1) ** 1.3
    return tex, clouds


def globe_frames(tex, clouds):
    """Orthographic views of the textured sphere, sunlight from the upper left."""
    ss = 2
    n = FRAME * ss
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    nx = (x + 0.5 - n / 2) / (n / 2 - ss)
    ny = (n / 2 - y - 0.5) / (n / 2 - ss)
    rr = nx ** 2 + ny ** 2
    inside = rr <= 1
    z = np.sqrt(np.clip(1 - rr, 0, 1))
    tilt = np.radians(18)
    yy = ny * np.cos(tilt) + z * np.sin(tilt)
    zz = -ny * np.sin(tilt) + z * np.cos(tilt)
    lat = np.arcsin(np.clip(yy, -1, 1))
    lon0 = np.arctan2(nx, zz)
    sun = np.array([-0.55, 0.45, 0.70])
    sun /= np.linalg.norm(sun)
    light = np.clip(nx * sun[0] + ny * sun[1] + z * sun[2], 0, 1)
    shade = (0.10 + 0.95 * light ** 0.8)[..., None]
    rim = np.clip((rr - 0.82) / 0.18, 0, 1)[..., None] * inside[..., None]
    th, tw = tex.shape[:2]
    rows = np.clip(((np.pi / 2 - lat) / np.pi * th).astype(int), 0, th - 1)
    earth = Image.new("RGB", (COLS * FRAME, (FRAMES // COLS) * FRAME), (0, 0, 0))
    for k in range(FRAMES):
        lon = lon0 + k * 2 * np.pi / FRAMES
        cols_ = (((lon / (2 * np.pi)) % 1.0) * tw).astype(int) % tw
        ca = (clouds[rows, cols_] * 0.6)[..., None]
        rgb = (tex[rows, cols_] * (1 - ca) + ca * 0.95) * shade
        rgb = rgb * (1 - rim * 0.35) + np.array([0.35, 0.6, 1.0]) * rim * 0.35
        rgb = np.where(inside[..., None], rgb, 0)
        fr = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB").resize((FRAME, FRAME), Image.LANCZOS)
        ox, oy = (k % COLS) * FRAME, (k // COLS) * FRAME
        earth.paste(fr, (ox, oy))
    earth.save(ART / "scene-planet.jpg", quality=84, optimize=True)


def main():
    nebula("scene-nebula-a.png", 640, 225, 31, ((70, 60, 190), (200, 70, 170), (140, 200, 255)), 0.66)
    nebula("scene-nebula-b.png", 640, 225, 41, ((40, 110, 220), (150, 90, 230), (255, 170, 225)), 0.50)
    tex, clouds = earth_maps()
    globe_frames(tex, clouds)
    for n in ("scene-nebula-a.png", "scene-nebula-b.png", "scene-planet.jpg"):
        print(n, (ART / n).stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
