#!/usr/bin/env python3
"""
Repariert den Schnittkanten-Defekt des PocketClot-Logos und exportiert daraus
alle App-Ressourcen in den korrekten Groessen.

Zwei Probleme werden behoben:

1. Der Zacken bei 5:30 Uhr. Die Silhouette wird in Polarkoordinaten ueberfuehrt
   und per FFT tiefpassgefiltert. Die sechs Lappen sind niederfrequent und
   bleiben erhalten, die harte Stufe ist hochfrequent und verschwindet. Die
   dunkle Kantenschattierung, die der alte Defekt im RGB hinterlassen hat,
   wird zusaetzlich harmonisch weginpaintet, sonst bleibt eine Farbnarbe.

2. Die Groesse. Das Motiv im Adaptive-Icon-Vordergrund war so gross, dass es
   die Kreismaske der Launcher komplett ausfuellte. Es sitzt jetzt auf
   ADAPTIVE_FRACTION der 108dp-Flaeche und bekommt Luft.

Aufruf: python3 Animation/repair_and_export_icons.py
"""
from __future__ import annotations

import os
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "Animation", "original_logo_flawless_768.png")
RES = os.path.join(ROOT, "app", "app", "src", "main", "res")
MASTER = os.path.join(ROOT, "Animation", "original_logo_smoothed.png")

# Grenzfrequenz der Silhouetten-Glaettung. 6 Lappen brauchen Harmonische bis 6;
# 10 laesst der Form ihre organische Unregelmaessigkeit und killt trotzdem die Stufe.
HARMONICS = 10

# Anteil der Kantenlaenge, den das Motiv einnimmt.
ADAPTIVE_FRACTION = 0.52   # 108dp-Viewport, Safe Zone waere 0.61 -> bewusst kleiner
BRAND_FRACTION = 0.92      # freistehendes Markenzeichen im Chat-Header
LEGACY_TILE_FRACTION = 0.85
LEGACY_BLOB_OF_TILE = 0.66

DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def polar_profile(mask: np.ndarray, cx: float, cy: float, n: int = 2048):
    """Radius der Silhouette je Winkel."""
    h, w = mask.shape
    theta = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    max_r = float(np.hypot(h, w))
    steps = np.linspace(0.0, max_r, int(max_r * 2))
    xs = cx + np.outer(steps, np.cos(theta))
    ys = cy + np.outer(steps, np.sin(theta))
    ix, iy = np.round(xs).astype(int), np.round(ys).astype(int)
    ok = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
    inside = ok & mask[np.clip(iy, 0, h - 1), np.clip(ix, 0, w - 1)]
    return theta, np.max(np.where(inside, steps[:, None], 0.0), axis=0)


def lowpass(r: np.ndarray, harmonics: int) -> np.ndarray:
    spec = np.fft.rfft(r)
    spec[harmonics + 1:] = 0
    return np.fft.irfft(spec, n=len(r))


def render_mask(theta, radius, cx, cy, size, supersample=4):
    """Polygon aus dem Radiusprofil, supersampled fuer saubere Kanten."""
    big = Image.new("L", (size * supersample, size * supersample), 0)
    pts = [
        ((cx + rr * np.cos(t)) * supersample, (cy + rr * np.sin(t)) * supersample)
        for t, rr in zip(theta, radius)
    ]
    ImageDraw.Draw(big).polygon(pts, fill=255)
    return big.resize((size, size), Image.LANCZOS)


def grow_colors(rgb: np.ndarray, known: np.ndarray, target: np.ndarray):
    """Farbe vom sicheren Inneren nach aussen nachziehen (Nearest-Fill).

    Die aeussersten Pixel des Originals sind durch Anti-Aliasing und den
    weichen Schlagschatten dunkel verfaelscht. Wuerde man sie stehen lassen und
    ihnen volle Deckkraft geben, bekaeme das Logo einen schwarzen Rand. Also
    gelten nur voll deckende Pixel als vertrauenswuerdig, der Rest wird aus der
    Nachbarschaft aufgefuellt.
    """
    rgb = rgb.astype(np.float64).copy()
    filled = known.copy()
    todo = target & ~filled
    while todo.any():
        acc = np.zeros_like(rgb)
        cnt = np.zeros(rgb.shape[:2])
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            s = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
            m = np.roll(np.roll(filled, dy, axis=0), dx, axis=1)
            acc += s * m[:, :, None]
            cnt += m
        upd = todo & (cnt > 0)
        if not upd.any():
            break
        rgb[upd] = acc[upd] / cnt[upd, None]
        filled |= upd
        todo &= ~upd
    return rgb


def inpaint(rgb: np.ndarray, unknown: np.ndarray, valid: np.ndarray, iters: int = 4000):
    """Harmonische Interpolation (Jacobi) auf dem Reparaturbereich.

    Loest naeherungsweise die Laplace-Gleichung, fuellt den Bereich also mit
    einem glatten Verlauf, der stetig an die bekannten Raender anschliesst.
    Genau richtig fuer einen weichen Farbverlauf, nichts wird "erfunden".
    """
    ys, xs = np.nonzero(unknown)
    if len(ys) == 0:
        return rgb
    pad = 6
    y0, y1 = max(0, ys.min() - pad), min(rgb.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(rgb.shape[1], xs.max() + pad + 1)

    sub = rgb[y0:y1, x0:x1].astype(np.float64).copy()
    unk = unknown[y0:y1, x0:x1]
    val = valid[y0:y1, x0:x1]

    # Startwert: Mittelwert der bekannten Nachbarschaft, damit Jacobi schneller konvergiert.
    known = val & ~unk
    if known.any():
        sub[unk] = sub[known].mean(axis=0)

    for _ in range(iters):
        acc = np.zeros_like(sub)
        cnt = np.zeros(sub.shape[:2])
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            s = np.roll(np.roll(sub, dy, axis=0), dx, axis=1)
            m = np.roll(np.roll(val, dy, axis=0), dx, axis=1)
            acc += s * m[:, :, None]
            cnt += m
        upd = unk & (cnt > 0)
        sub[upd] = acc[upd] / cnt[upd, None]

    rgb = rgb.astype(np.float64)
    rgb[y0:y1, x0:x1][unk] = sub[unk]
    return rgb


def build_master() -> Image.Image:
    img = Image.open(SRC).convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.float64)
    alpha = arr[:, :, 3]
    mask = alpha > 127

    ys, xs = np.nonzero(mask)
    cy, cx = ys.mean(), xs.mean()

    theta, r_orig = polar_profile(mask, cx, cy)
    r_smooth = lowpass(r_orig, HARMONICS)

    # Wo weicht das Original stark vom geglaetteten Verlauf ab? Das ist der Defekt.
    dev = np.abs(r_orig - r_smooth)
    tol = 0.015 * r_smooth.mean()
    bad = dev > tol
    # Winkelbereich grosszuegig ausweiten, damit auch die dunkle Kantenlinie
    # neben der Stufe mit in die Reparatur faellt.
    # Periodisch falten, das Winkelprofil ist zyklisch. Ein np.convolve auf dem
    # nackten Array wuerde die Naht bei 0 Grad als Rand behandeln und einen
    # Defekt, der genau dort liegt, nur einseitig ausweiten.
    span = 45
    tripled = np.concatenate([bad.astype(float)] * 3)
    smeared = np.convolve(tripled, np.ones(2 * span + 1), mode="same")
    bad = smeared[len(bad):2 * len(bad)] > 0

    new_mask_img = render_mask(theta, r_smooth, cx, cy, w)
    new_alpha = np.array(new_mask_img)
    new_solid = new_alpha > 127
    # Auch die halbtransparenten Kantenpixel brauchen eine gueltige Farbe,
    # sonst schimmert dort das schwarze RGB der urspruenglich leeren Flaeche
    # durch und man haette den dunklen Rand ueber die Hintertuer zurueck.
    new_any = new_alpha > 0

    # Die Polarmethode setzt voraus, dass jeder Strahl vom Schwerpunkt die
    # Silhouette genau einmal verlaesst. Trifft das nicht zu, wuerde das
    # Polygon Einbuchtungen zuschuetten. Gegen stille Formaenderungen hilft
    # ein Flaechenvergleich.
    delta_area = abs(new_solid.sum() - mask.sum()) / mask.sum()
    if delta_area > 0.02:
        print(f"WARNUNG: Flaeche weicht um {delta_area:.1%} ab, Form pruefen.")

    # Reparaturzone: in den betroffenen Winkeln ein radiales Band rund um die
    # alte Kante, nach innen breit genug fuer die Schattierungs-Narbe.
    yy, xx = np.mgrid[0:h, 0:w]
    rad = np.hypot(xx - cx, yy - cy)
    ang = np.mod(np.arctan2(yy - cy, xx - cx), 2 * np.pi)
    idx = np.minimum((ang / (2 * np.pi) * len(theta)).astype(int), len(theta) - 1)

    band = 0.13 * r_smooth.mean()
    inner = np.minimum(r_orig, r_smooth)[idx] - band
    outer = r_smooth[idx] + 2.0
    zone = bad[idx] & (rad >= inner) & (rad <= outer)

    # Nur voll deckende Pixel ausserhalb der Defektzone sind farblich sauber.
    trusted = (alpha >= 250) & ~zone
    # Erst die Farbe bis an die neue Kante nachziehen, dann die Defektzone
    # glatt ueberbruecken. Ohne den ersten Schritt saehe der Rand schwarz aus,
    # ohne den zweiten bliebe die Schattierungs-Narbe des alten Zackens stehen.
    rgb = grow_colors(rgb, trusted, new_any)
    rgb = inpaint(rgb, zone & new_solid, new_solid)

    out = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), new_alpha])
    return Image.fromarray(out, "RGBA")


def trimmed(img: Image.Image) -> Image.Image:
    a = np.array(img)[:, :, 3]
    ys, xs = np.nonzero(a > 8)
    return img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def place(blob: Image.Image, canvas: int, fraction: float) -> Image.Image:
    """Motiv zentriert auf transparente Flaeche, laengste Kante = fraction."""
    target = max(1, int(round(canvas * fraction)))
    w, h = blob.size
    scale = target / max(w, h)
    new = blob.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    # alpha_composite statt paste(..., mask=new): paste wuerde das Quell-Alpha
    # zusaetzlich als Maske anwenden und es damit quadrieren, was die
    # Antialias-Kante ausduennt.
    out.alpha_composite(new, dest=((canvas - new.size[0]) // 2, (canvas - new.size[1]) // 2))
    return out


def rounded_mask(size: int, radius_frac: float) -> Image.Image:
    m = Image.new("L", (size * 4, size * 4), 0)
    r = int(size * 4 * radius_frac)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size * 4 - 1, size * 4 - 1], radius=r, fill=255)
    return m.resize((size, size), Image.LANCZOS)


def circle_mask(size: int) -> Image.Image:
    m = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    return m.resize((size, size), Image.LANCZOS)


def main():
    master = build_master()
    master.save(MASTER)
    print(f"Master geschrieben: {MASTER}")

    blob = trimmed(master)
    written = 0

    for dens, factor in DENSITIES.items():
        # --- Adaptive Icon: Vordergrund + Monochrom (108dp) ---
        canvas = int(round(108 * factor))
        fg = place(blob, canvas, ADAPTIVE_FRACTION)
        fg.save(os.path.join(RES, f"drawable-{dens}", "ic_launcher_foreground.png"))

        mono = np.zeros((canvas, canvas, 4), dtype=np.uint8)
        mono[:, :, :3] = 255
        mono[:, :, 3] = np.array(fg)[:, :, 3]
        Image.fromarray(mono, "RGBA").save(
            os.path.join(RES, f"drawable-{dens}", "ic_launcher_monochrome.png")
        )
        written += 2

        # --- Freistehendes Markenzeichen (24dp) ---
        bm_canvas = int(round(24 * factor))
        place(blob, bm_canvas, BRAND_FRACTION).save(
            os.path.join(RES, f"drawable-{dens}", "ic_brand_mark.png")
        )
        written += 1

        # --- Legacy-Launcher (48dp), vorgerendert inkl. Hintergrund ---
        leg = int(round(48 * factor))
        bg_src = Image.open(
            os.path.join(RES, f"drawable-{dens}", "ic_launcher_background.png")
        ).convert("RGBA")
        tile_px = int(round(leg * LEGACY_TILE_FRACTION))
        tile = bg_src.resize((tile_px, tile_px), Image.LANCZOS)
        art = place(blob, tile_px, LEGACY_BLOB_OF_TILE)

        for name, mask in (
            ("ic_launcher.png", rounded_mask(tile_px, 0.22)),
            ("ic_launcher_round.png", circle_mask(tile_px)),
        ):
            tl = tile.copy()
            tl.alpha_composite(art)
            tl.putalpha(mask)
            out = Image.new("RGBA", (leg, leg), (0, 0, 0, 0))
            out.alpha_composite(tl, dest=((leg - tile_px) // 2, (leg - tile_px) // 2))
            out.save(os.path.join(RES, f"mipmap-{dens}", name))
            written += 1

    print(f"{written} Ressourcen geschrieben.")


if __name__ == "__main__":
    main()
