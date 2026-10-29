# -*- coding: utf-8 -*-
"""Build a contact sheet of corpus images with their ids, so a batch can be
classified by eye in one look.

The corpus has more art than one image at a time is practical for: 111
backgrounds, 112 faces, 247 frames, 1565 CGs. This composites a batch into a
grid PNG, one cell per image, the id printed under it, so a whole batch is read
in a single look and written into a notes table.

    python tools/corpus_grid.py --dir <dir> --out sheet.png --cols 4 --cell 480
    python tools/corpus_grid.py --dir <dir> --ids a,b,c --out sheet.png
    python tools/corpus_grid.py --dir <dir> --batch 16 --out sheets/     # many sheets

`--cell` is the width of one cell in the sheet; a background reads at 480, a
face at 160. `--batch N` splits the set into sheets of N images, numbered, so a
large family is classified a sheet at a time. The corpus is read-only.
"""

import argparse
import io
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

PAD = 6
LABEL_H = 20


def _font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf", "consola.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _ids_from_dir(directory, exts=(".png", ".jpg", ".webp")):
    names = []
    for n in sorted(os.listdir(directory)):
        stem, ext = os.path.splitext(n)
        if ext.lower() in exts:
            names.append(stem)
    return names


def sheet(paths, ids, out, cols, cell):
    rows = max(1, math.ceil(len(paths) / cols))
    width = cols * (cell + PAD) + PAD
    height = rows * (cell + LABEL_H + PAD) + PAD
    canvas = Image.new("RGB", (width, height), (242, 240, 236))
    draw = ImageDraw.Draw(canvas)
    font = _font(13)
    for i, (path, cid) in enumerate(zip(paths, ids)):
        r, c = divmod(i, cols)
        x = PAD + c * (cell + PAD)
        y = PAD + r * (cell + LABEL_H + PAD)
        try:
            im = Image.open(path)
            im.load()
        except Exception:
            draw.text((x + 2, y + cell // 2), cid + " (unreadable)", fill=(160, 40, 40), font=font)
            continue
        im = im.convert("RGBA")
        im.thumbnail((cell, cell))
        tile = Image.new("RGB", (cell, cell), (232, 230, 226))
        tile.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2), im)
        canvas.paste(tile, (x, y))
        draw.text((x + 2, y + cell + 3), cid, fill=(20, 20, 20), font=font)
    canvas.save(out)
    return width, height


def main():
    ap = argparse.ArgumentParser(description="Contact sheet of corpus images with ids.")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ids", default="", help="comma-separated ids; default every image in --dir")
    ap.add_argument("--out", required=True, help="a .png file, or a directory when --batch is set")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--cell", type=int, default=480)
    ap.add_argument("--batch", type=int, default=0, help="images per sheet; 0 is one sheet")
    args = ap.parse_args()

    ids = [s.strip() for s in args.ids.split(",") if s.strip()] or _ids_from_dir(args.dir)
    paths = [os.path.join(args.dir, cid + ".png") for cid in ids]
    missing = [p for p in paths if not os.path.isfile(p)]
    if missing:
        print(f"[grid] {len(missing)} id(s) have no .png (first: {missing[0]})")
        ids = [cid for cid, p in zip(ids, paths) if os.path.isfile(p)]
        paths = [p for p in paths if os.path.isfile(p)]
    if not ids:
        print("[grid] nothing to draw")
        return 1

    if args.batch and args.batch > 0:
        os.makedirs(args.out, exist_ok=True)
        n = 0
        for start in range(0, len(ids), args.batch):
            chunk_ids = ids[start:start + args.batch]
            chunk_paths = paths[start:start + args.batch]
            name = os.path.join(args.out, f"sheet_{start // args.batch + 1:02d}.png")
            w, h = sheet(chunk_paths, chunk_ids, name, args.cols, args.cell)
            print(f"[grid] {name}  {len(chunk_ids)} image(s)  {w}x{h}")
            n += 1
        print(f"[grid] {n} sheet(s) over {len(ids)} image(s)")
        return 0

    w, h = sheet(paths, ids, args.out, args.cols, args.cell)
    print(f"[grid] {args.out}  {len(ids)} image(s)  {w}x{h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
