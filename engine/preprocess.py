import cv2
import numpy as np

BLUR_THRESHOLD = 40
BLUR_WIDTH = 1000  # score at a fixed width so the source resolution doesn't matter

# second-derivative kernels along 0, 90, 45 and 135 degrees
DIRECTION_KERNELS = [
    np.array([[0, 0, 0], [1, -2, 1], [0, 0, 0]], dtype=np.float64),
    np.array([[0, 1, 0], [0, -2, 0], [0, 1, 0]], dtype=np.float64),
    np.array([[1, 0, 0], [0, -2, 0], [0, 0, 1]], dtype=np.float64),
    np.array([[0, 0, 1], [0, -2, 0], [1, 0, 0]], dtype=np.float64),
]

def blur_score(img):
    # sharpness in the worst direction, so one-way motion blur is caught too
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float64)
    h, w = gray.shape
    gray = cv2.resize(gray, (BLUR_WIDTH, round(h * BLUR_WIDTH / w)),
                      interpolation=cv2.INTER_AREA)
    return min(cv2.filter2D(gray, -1, k).var() for k in DIRECTION_KERNELS)

def deskew(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255,
                           cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(thresh)
    angle = cv2.minAreaRect(coords)[-1]
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(255, 255, 255)), angle

PAPER_MIN_AREA = 0.3   # paper must cover at least this share of the photo
PAPER_MAX_AREA = 0.95  # above this the page fills the image (a scan): nothing to cut out

def find_paper(img):
    # four corners of the sheet in a photo, or None if there is no separate sheet
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (5, 5), 0)
    bright = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    if not contours:
        return None
    sheet = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(sheet) / (small.shape[0] * small.shape[1])
    if not PAPER_MIN_AREA <= area <= PAPER_MAX_AREA:
        return None
    corners = cv2.approxPolyDP(sheet, 0.02 * cv2.arcLength(sheet, True), True)
    if len(corners) != 4:
        return None
    return corners.reshape(4, 2).astype(np.float32) * 4

def flatten(img, corners):
    # order corners top-left, top-right, bottom-right, bottom-left
    s, d = corners.sum(1), np.diff(corners, axis=1).ravel()
    tl, tr = corners[np.argmin(s)], corners[np.argmin(d)]
    br, bl = corners[np.argmax(s)], corners[np.argmax(d)]
    w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    M = cv2.getPerspectiveTransform(np.float32([tl, tr, br, bl]),
                                    np.float32([[0, 0], [w, 0], [w, h], [0, h]]))
    angle = np.degrees(np.arctan2(tr[1] - tl[1], tr[0] - tl[0]))  # tilt of the top edge
    return cv2.warpPerspective(img, M, (w, h)), angle

THUMB_SIZE = (170, 220)  # (width, height) used to compare pages with templates
MIN_LEAD = 1.5  # best turn must score this many times the runner-up, else don't turn
# (real photos score only ~0.2-0.3 even when upright, so an absolute cutoff fails)

# clockwise turn needed to fix the page, keyed by degrees
ROTATIONS = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}

def thumbnail(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, THUMB_SIZE,
                      interpolation=cv2.INTER_AREA).astype(np.float32)

def make_templates(pages):
    # blank form pages -> thumbnails that orient() compares against
    return [thumbnail(p) for p in pages]

def orient(img, templates):
    # try all four turns, keep the one that looks most like a blank page
    scores = {}
    for turn, code in ROTATIONS.items():
        thumb = thumbnail(img if code is None else cv2.rotate(img, code))
        scores[turn] = max(cv2.matchTemplate(thumb, t, cv2.TM_CCOEFF_NORMED)[0][0]
                           for t in templates)
    best_turn = max(scores, key=scores.get)
    best, second = sorted(scores.values(), reverse=True)[:2]
    if best <= 0 or best < MIN_LEAD * max(second, 0):
        return img, 0  # no turn clearly stands out
    code = ROTATIONS[best_turn]
    return (img if code is None else cv2.rotate(img, code)), best_turn

def enhance_contrast(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

def preprocess(img, templates=None):
    # straighten before orient: tilted thumbnails match templates poorly
    blur = blur_score(img)
    corners = find_paper(img)
    if corners is not None:
        straight, angle = flatten(img, corners)  # photo of a sheet on a background
    else:
        straight, angle = deskew(img)            # page fills the image (scan)
    rotation = 0
    if templates:
        straight, rotation = orient(straight, templates)
    return enhance_contrast(straight), blur, angle, rotation
