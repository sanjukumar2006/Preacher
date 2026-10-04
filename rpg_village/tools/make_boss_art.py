"""Turns assets/boss/boss_reference.png into the pixel-art boss sprite assets/boss/grimhorn.png.

Dev-only tool (the game itself needs just pygame):  pip install pillow numpy scipy opencv-python
    python tools/make_boss_art.py

Steps: cut the creature out of the (baked-in) checkerboard -> local-contrast boost -> area downscale to
~92px tall -> limited palette -> paint glowing red eyes -> 1px dark outline.
"""
import os

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
BOSS_DIR = os.path.join(HERE, "..", "assets", "boss")
SRC = os.path.join(BOSS_DIR, "boss_reference.png")
DST = os.path.join(BOSS_DIR, "grimhorn.png")

TARGET_H = 92
PALETTE = 34
EYES_SRC = [(226, 128), (243, 131)]        # eye centres in the reference image
EYE_COLOR = (255, 70, 60)                  # boss.py finds the eyes again by this exact colour


def cut_out(rgb):
    """Remove the neutral grey/white checkerboard (edge-connected or big enclosed patches)."""
    a = rgb.astype(int)
    mx, mn = a.max(2), a.min(2)
    cand = ((mx - mn) <= 7) & (mn >= 222)
    lab, n = ndi.label(cand)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    sizes = ndi.sum(cand, lab, range(1, n + 1))
    big = {i + 1 for i, z in enumerate(sizes) if z > 120}
    bg = np.isin(lab, list(border | big))
    bg |= ndi.binary_dilation(bg, iterations=2) & (((mx - mn) <= 14) & (mn >= 190))
    fg = ~bg
    lab2, n2 = ndi.label(fg)
    sz = ndi.sum(fg, lab2, range(1, n2 + 1))
    return np.isin(lab2, [i + 1 for i, s in enumerate(sz) if s > 150])


def boost_reds(arr):
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV).astype(np.float32)
    hue, sat = hsv[..., 0], hsv[..., 1]
    red = ((hue < 12) | (hue > 165)) & (sat > 60)
    hsv[..., 1][red] = np.minimum(255, sat[red] * 1.35)
    hsv[..., 2][red] = np.minimum(255, hsv[..., 2][red] * 1.08)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def main():
    rgb = np.array(Image.open(SRC).convert("RGB"))
    keep = cut_out(rgb)
    ys, xs = np.where(keep)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    rgb, keep = rgb[y0:y1 + 1, x0:x1 + 1], keep[y0:y1 + 1, x0:x1 + 1]
    h, w = keep.shape
    scale = TARGET_H / h
    tw, th = max(1, round(w * scale)), TARGET_H

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(6, 8)).apply(lab[..., 0])
    rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    al = keep.astype(np.float32)[..., None]
    sp = cv2.resize(rgb.astype(np.float32) * al, (tw, th), interpolation=cv2.INTER_AREA)
    sa = cv2.resize(al[..., 0], (tw, th), interpolation=cv2.INTER_AREA)
    mask = sa > 0.5
    col = np.clip(sp / np.maximum(sa[..., None], 1e-3), 0, 255).astype(np.uint8)
    col = boost_reds(col)
    img = Image.fromarray(col)
    img = ImageEnhance.Color(img).enhance(1.25)
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=1))
    arr = np.array(img)
    arr[~mask] = (40, 24, 30)
    arr = np.array(Image.fromarray(arr).quantize(colors=PALETTE, method=Image.Quantize.MEDIANCUT,
                                                 dither=Image.Dither.NONE).convert("RGB"))
    for ex, ey in EYES_SRC:
        sx, sy = int(round((ex - x0) * scale)), int(round((ey - y0) * scale))
        arr[sy, sx] = EYE_COLOR
        arr[sy, min(tw - 1, sx + 1)] = (200, 30, 40)

    ring = ndi.binary_dilation(mask, structure=np.ones((3, 3))) & ~mask
    out = np.zeros((th + 2, tw + 2, 4), np.uint8)
    out[..., :3] = np.pad(arr, ((1, 1), (1, 1), (0, 0)))
    out[np.pad(mask, 1), 3] = 255
    r2 = np.pad(ring, 1)
    out[r2, :3] = (20, 11, 17)
    out[r2, 3] = 255
    Image.fromarray(out, "RGBA").save(DST)
    print("wrote", os.path.normpath(DST), out.shape[1], "x", out.shape[0])


if __name__ == "__main__":
    main()
