from pathlib import Path
from PIL import Image, ImageOps

import cv2
import numpy as np 
import pymupdf

DPI = 300


def load_pdf(path, dpi=DPI):
    pages = []
    zoom = dpi/72
    
    with pymupdf.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom),
                                  colorspace=pymupdf.csRGB, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8)
            img = img.reshape(pix.height, pix.width, 3)
            pages.append(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return pages



def load_photo(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)    
        im = im.convert("RGB")              
        img = np.array(im)                  
        return [cv2.cvtColor(img, cv2.COLOR_RGB2BGR)]



def load_pages(path, dpi=DPI):
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return load_pdf(path, dpi)
    if suffix in (".jpg", ".jpeg", ".png"):
        return load_photo(path)
    raise ValueError(f"Unsupported file type: {path}")