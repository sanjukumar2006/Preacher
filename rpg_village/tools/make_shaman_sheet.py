"""Slice assets/boss/shaman_source.png (4 rows x 3 cols) into assets/boss/shaman.png:
a clean grid of equally sized, feet-aligned frames.  Rows: down, left, up, right.  Run once."""
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "boss", "shaman_source.png")
OUT = os.path.join(HERE, "..", "assets", "boss", "shaman.png")
TARGET_H = 112          # tallest frame height in game pixels

im = Image.open(SRC).convert("RGBA")
a = np.array(im)
white = (a[..., 0] > 232) & (a[..., 1] > 232) & (a[..., 2] > 232)
a[white, 3] = 0                                   # make any white backdrop transparent
alpha = a[..., 3] > 40
H, W = alpha.shape


def runs(v, gap):
    out, s, last = [], None, None
    for i, x in enumerate(v):
        if x:
            if s is None:
                s = i
            last = i
        elif s is not None and i - last > gap:
            out.append((s, last)); s = None
    if s is not None:
        out.append((s, last))
    return out


rows = runs(alpha.any(1), 6)
# rows 3 and 4 touch each other: split the tall blob at its thinnest horizontal line
if len(rows) == 3:
    y0, y1 = rows[2]
    mid = (y0 + y1) // 2
    seg = alpha[mid - 60:mid + 60].sum(1)
    cut = mid - 60 + int(np.argmin(seg))
    rows = rows[:2] + [(y0, cut), (cut + 1, y1)]
assert len(rows) == 4, rows
cells = []
for (y0, y1) in rows:
    cols = runs(alpha[y0:y1 + 1].any(0), 12)
    assert len(cols) == 3, (y0, y1, cols)
    cells.append([(c0, y0, c1 + 1, y1 + 1) for (c0, c1) in cols])

crops = []
for r in cells:
    row = []
    for box in r:
        c = Image.fromarray(a).crop(box)
        bb = c.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
        row.append(c.crop(bb))
    crops.append(row)
scale = TARGET_H / max(c.height for r in crops for c in r)
sized = [[c.resize((max(1, round(c.width * scale)), max(1, round(c.height * scale))), Image.LANCZOS) for c in r]
         for r in crops]
cw = max(c.width for r in sized for c in r) + 4
ch = max(c.height for r in sized for c in r) + 2
sheet = Image.new("RGBA", (cw * 3, ch * 4), (0, 0, 0, 0))
for ri, r in enumerate(sized):
    for ci, c in enumerate(r):
        sheet.paste(c, (ci * cw + (cw - c.width) // 2, ri * ch + (ch - c.height)), c)
sheet.save(OUT)
print("saved", OUT, "cell", cw, ch)
