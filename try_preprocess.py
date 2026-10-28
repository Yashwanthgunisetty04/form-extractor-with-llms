from pathlib import Path

import cv2
import numpy as np

from engine.load import load_pages
from engine.preprocess import preprocess, make_templates, BLUR_THRESHOLD

SAMPLES = Path("samples")
OUT = Path("output/preprocess")
OUT.mkdir(parents=True, exist_ok=True)

templates = make_templates(load_pages("forms/fda_1932a/templates/blank.pdf")[:5])

files = [f for f in sorted(SAMPLES.iterdir())
         if f.suffix.lower() in (".pdf", ".jpg", ".jpeg", ".png")]

print(f"{'file':30} {'page':>4} {'blur':>7} {'':8} {'angle':>6} {'turn':>5}")
for f in files:
    for i, page in enumerate(load_pages(f), 1):
        cleaned, blur, angle, rotation = preprocess(page, templates)
        flag = "BLURRY" if blur < BLUR_THRESHOLD else "ok"
        print(f"{f.name:30} {i:>4} {blur:>7.0f} {flag:8} {angle:>6.2f} {rotation:>5}")

        # before | after, side by side at half size so it's easy to view
        # (pages can differ in shape after a turn, so pad to the same height)
        h = max(page.shape[0], cleaned.shape[0])
        pad = lambda im: cv2.copyMakeBorder(im, 0, h - im.shape[0], 0, 0,
                                            cv2.BORDER_CONSTANT, value=(255, 255, 255))
        pair = np.hstack([pad(page), pad(cleaned)])
        pair = cv2.resize(pair, None, fx=0.5, fy=0.5)
        cv2.imwrite(str(OUT / f"{f.stem}_p{i}.png"), pair)

print(f"\nBefore/after images saved to {OUT}/")
