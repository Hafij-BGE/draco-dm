# Live planet in the details pane

The picture themes show a living planet in the right-hand details pane. It is drawn behind the
tabs and their content: the planet sits whole below the Details / Speed limiter / Options on
completion / Preview content, and its sky reaches up to 70 px behind it (`OVERLAP`), so it is
never sliced. It follows the
selected download; with nothing selected it fills the pane and says "Select a download".

## Stages

| Stage | When | Look |
|---|---|---|
| Initializing | connecting, or under 5 % | dark planet, loading spinner, specks gathering on the rings |
| Downloading | 5–70 % | planet turns, data particles ride the rings and stream in |
| High speed | 70–95 % | brighter pink/blue rings, more streams, speed lines |
| Finalizing | 95–100 %, or while the engine joins the parts | orange; rings pull in, particles merge into the planet |
| Completed | done | soft glow, white check mark, calm |
| Paused / Queued | stopped by the user or waiting | streams stop, the planet keeps turning slowly, amber ring |
| Error | failed | restrained red glow, no data motion |

The percentage and state are real GTK labels in the middle of the planet.

## State binding

* `draco/gui/scene_model.py` (no GTK, unit tested in `tests/test_scene.py`):
  `scene_state(item)` turns the engine's item (status, size, downloaded, speed) into a
  `SceneState`; `SceneMotion` eases the drawn values toward it. The progress ring never runs
  ahead of the real fraction, and switching to another download jumps instead of animating.
* `BrightDetails.update()` (every 0.5 s, from the window's tick) calls
  `PlanetScene.set_item()`; nothing in the scene touches the download engine.

## Drawing and cost

* `draco/gui/planet_scene.py` draws with `Gtk.Snapshot` render nodes (GPU when available),
  not Cairo, so it needs no `python3-gi-cairo`.
* 30 frames a second while a download moves, 15 otherwise; a frame takes about 2–3 ms of
  Python. Drawing stops when the pane is hidden, the window is minimised, or less than 40 px
  is free below the content (`MIN_FREE`); the labels go away on a planet smaller than 40 px.
* Pictures are loaded once on a worker thread: `draco/art/scene-planet.jpg` (96 turning frames,
  12 × 8 sheet) and `scene-nebula-a/b.png` (cloud layers that wrap left/right), about 0.8 MB.
  They are drawn from numbers by `tools/make_scene_art.py` (numpy + Pillow, build time only).
* Light themes: a pale lavender sky that fades into the white pane; dark themes: a night sky
  that fades into the dark pane (alpha mask, GTK 4.10+). Older GTK without paths draws the
  ring as dots, skips the orbit rings and draws asteroids as dots.
* A drawing error stops the animation and is printed once; downloads are never affected.

## Settings

Options → General → Dialogs and notifications:
**Live animation in the details pane** (`details_animation`) and **Reduce motion**
(`reduce_motion`, a still picture; GTK's own "animations off" does the same).

## Changing it

* New stage colours: `PALETTE` in `scene_model.py`.
* New layer: add a method to `Planet` in `planet_scene.py` and call it from `Planet.draw()`;
  keep per-frame node counts bounded (particle pools have fixed maximums) and cache anything
  that doesn't move (see the star field).
* New pictures: edit `tools/make_scene_art.py` and run `python3 tools/make_scene_art.py`.

Tests: `python3 -m pytest -q tests`.
