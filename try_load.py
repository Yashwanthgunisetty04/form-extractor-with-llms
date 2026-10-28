import cv2
from engine.load import load_pages

path = "forms/fda_1932a/templates/blank.pdf"

pages = load_pages(path)
print("Pages:", len(pages))
print("Size of page 1:", pages[0].shape)
cv2.imwrite("output/page1.png", pages[0])