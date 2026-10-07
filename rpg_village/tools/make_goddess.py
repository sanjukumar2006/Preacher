"""Builds the goddess statue sprite -> assets/objects/goddess.png from your own artwork.

Source art : assets/objects/_source/goddess_original.png   (the pixel-art angel shrine, 1024x1536)
Output     : assets/objects/goddess.png                      (128x192 = 4x6 tiles, bottom-anchored like the other objects)

Run:  python tools/make_goddess.py        (needs Pillow + numpy:  pip install pillow numpy)
To use different art later, overwrite goddess_original.png and run this again.
If you change OUT_W / OUT_H, also update ORB_Y in main.py (statue_orb) and FOOT["goddess"] in world.py.
"""
import os
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "..", "assets", "objects", "_source", "goddess_original.png")
OUT = os.path.join(HERE, "..", "assets", "objects", "goddess.png")
OUT_W = 128
OUTLINE = (34, 30, 52, 255)          # same dark outline colour as the other props


def make():
    im = Image.open(SRC).convert("RGBA")
    a = np.array(im)
    a[:, :, 3] = np.where(a[:, :, 3] < 60, 0, a[:, :, 3])        # kill the faint background haze
    im = Image.fromarray(a)
    bbox = im.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()
    im = im.crop(bbox)
    h = round(im.height * OUT_W / im.width)
    # alpha-aware resize (premultiplied) so edges don't get a white fringe
    arr = np.array(im).astype(np.float32)
    arr[:, :, :3] *= arr[:, :, 3:4] / 255.0
    pm = Image.fromarray(arr.astype(np.uint8), "RGBA").resize((OUT_W, h), Image.LANCZOS)
    arr = np.array(pm).astype(np.float32)
    al = arr[:, :, 3:4]
    arr[:, :, :3] = np.where(al > 0, arr[:, :, :3] * 255.0 / np.maximum(al, 1), 0)
    arr[:, :, 3] = np.where(arr[:, :, 3] < 110, 0, 255)           # hard pixel-art edge
    spr = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    spr = spr.filter(ImageFilter.UnsharpMask(radius=1, percent=60, threshold=2))
    # 1px outline
    m = np.array(spr)[:, :, 3] > 0
    pad = np.pad(m, 1)
    edge = np.zeros_like(pad)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        edge |= np.roll(np.roll(pad, dy, 0), dx, 1)
    edge &= ~pad
    out = Image.new("RGBA", (OUT_W + 2, h + 2), (0, 0, 0, 0))
    ol = np.zeros((h + 2, OUT_W + 2, 4), np.uint8)
    ol[edge] = OUTLINE
    out = Image.alpha_composite(Image.fromarray(ol, "RGBA"), Image.new("RGBA", out.size, (0, 0, 0, 0)))
    out.alpha_composite(spr, (1, 1))
    out.save(OUT)
    print("saved", OUT, out.size)


if __name__ == "__main__":
    make()
