"""Design mock-ups of the Backdrop panel, painted with Qt inside 3ds Max.

Run through tools/make_mockups.ps1 (3dsmaxbatch). Nothing here is wired to
the scene: the pictures only show how the panel could look. Writes
docs/mockups/variant_a.png, variant_b.png, variant_c.png and overlay.png.
"""
import os
import traceback

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

from pymxs import runtime as rt

Qt = QtCore.Qt
SRC = os.environ["BD_SRC"]
OUT = os.environ["BD_MOCK_OUT"]
IMAGES = os.environ.get("BD_MOCK_IMAGES", "")
S = 2                                        # pixel scale of the pictures
W = 340

import sys
rt.python.ExecuteFile(SRC)
backdrop_module = sys.modules["adtools_backdrop"]
T = dict(backdrop_module.DARK)
svg = backdrop_module.svg_renderer
if getattr(backdrop_module, "backdrop", None) is not None:
    backdrop_module.backdrop.close()

FRAME = "#2cc6ea"
NOTES = [
    (1, "Подвинуть миску ближе к мойке", "Move the bowl closer to the sink", "Emily R.", "2 ч назад", False),
    (2, "Подсветить щётку, сейчас теряется", "Highlight the brush, it gets lost", "Emily R.", "2 ч назад", False),
    (3, "Ручки — матовый никель", "Handles: brushed nickel", "Aleksey D.", "вчера", True),
]
REGIONS = [(0.238, 0.207, 0.103, 0.113), (0.314, 0.391, 0.083, 0.116), (0.399, 0.862, 0.063, 0.138)]
NAMES = ["SK100-30 · Angle01", "SK100-30 · Angle02", "SK200-32 · Angle01",
         "SK200-32 · Angle02", "SK200-32 · Angle03", "SK200-32 · Angle05"]
COUNTS = [3, 0, 2, 0, 5, 1]


def load_thumbs():
    thumbs = []
    files = []
    if os.path.isdir(IMAGES):
        files = sorted(f for f in os.listdir(IMAGES) if f.lower().endswith(".jpg"))[:6]
    for i in range(6):
        image = QtGui.QImage()
        if i < len(files):
            reader = QtGui.QImageReader(os.path.join(IMAGES, files[i]))
            reader.setScaledSize(QtCore.QSize(1200, 900))
            image = reader.read()
        if image.isNull():
            image = QtGui.QImage(1200, 900, QtGui.QImage.Format_RGB32)
            image.fill(QtGui.QColor.fromHsv(200 + i * 8, 40, 90 + i * 12))
        thumbs.append(image)
    return thumbs


class P(object):
    """Small drawing helpers over a QPainter, in logical pixels."""

    def __init__(self, width, height):
        self.image = QtGui.QImage(width * S, height * S, QtGui.QImage.Format_ARGB32)
        self.image.fill(QtGui.QColor(T["window"]))
        self.p = QtGui.QPainter(self.image)
        self.p.scale(S, S)
        self.p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self.p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

    def save(self, name):
        self.p.end()
        self.image.save(os.path.join(OUT, name))

    def box(self, x, y, w, h, fill=None, border=None, radius=8, width=1.0):
        self.p.setPen(QtGui.QPen(QtGui.QColor(border), width) if border else Qt.NoPen)
        self.p.setBrush(QtGui.QColor(fill) if fill else Qt.NoBrush)
        self.p.drawRoundedRect(QtCore.QRectF(x + 0.5, y + 0.5, w - 1, h - 1), radius, radius)

    def text(self, x, y, w, h, value, color="text", size=12, bold=False,
             align=Qt.AlignLeft | Qt.AlignVCenter, strike=False, wrap=False):
        font = QtGui.QFont("Segoe UI")
        font.setPixelSize(size)
        font.setWeight(QtGui.QFont.DemiBold if bold else QtGui.QFont.Normal)
        font.setStrikeOut(strike)
        self.p.setFont(font)
        self.p.setPen(QtGui.QColor(T.get(color, color)))
        rect = QtCore.QRectF(x, y, w, h)
        if wrap:
            self.p.drawText(rect, int(align | Qt.TextWordWrap), value)
        else:
            metrics = QtGui.QFontMetrics(font)
            self.p.drawText(rect, int(align), metrics.elidedText(value, Qt.ElideRight, int(w)))

    def icon(self, name, x, y, size=16, color="text"):
        svg(name, T.get(color, color)).render(self.p, QtCore.QRectF(x, y, size, size))

    def picture(self, image, x, y, w, h, radius=6):
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(x, y, w, h), radius, radius)
        self.p.save()
        self.p.setClipPath(path)
        src = QtCore.QRectF(image.rect())
        want = w / float(h)
        if src.width() / src.height() > want:
            cut = src.width() - src.height() * want
            src.adjust(cut / 2, 0, -cut / 2, 0)
        else:
            cut = src.height() - src.width() / want
            src.adjust(0, cut / 2, 0, -cut / 2)
        self.p.drawImage(QtCore.QRectF(x, y, w, h), image, src)
        self.p.restore()

    def badge(self, cx, cy, value, fill=FRAME, color="#04222b", r=10, size=11):
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(QtGui.QColor(T.get(fill, fill)))
        self.p.drawEllipse(QtCore.QPointF(cx, cy), r, r)
        self.text(cx - r, cy - r, 2 * r, 2 * r, str(value), color, size, True, Qt.AlignCenter)

    # -- shared blocks --------------------------------------------------------
    def titlebar(self):
        self.p.fillRect(QtCore.QRectF(0, 0, W, 32), QtGui.QColor(T["titlebar"]))
        self.icon("image", 10, 8, 16, "accent")
        self.text(32, 0, 70, 32, "Backdrop", size=12, bold=True)
        self.text(92, 0, 60, 32, "a0.002", "text_faint", 11)
        for i, name in enumerate(("sun", "minus", "close")):
            self.icon(name, W - 86 + i * 28, 9, 14, "text_dim")

    def tool(self, x, y, name, on=False, size=30):
        self.box(x, y, size, size, T["select"] if on else T["button"],
                 T["accent"] if on else T["border"], 7)
        self.icon(name, x + (size - 16) / 2.0, y + (size - 16) / 2.0, 16,
                  "accent" if on else "text")

    def segmented(self, x, y, w, labels, active, h=26):
        self.box(x, y, w, h, T["pill"], None, 7)
        part = w / float(len(labels))
        for i, label in enumerate(labels):
            if i == active:
                self.box(x + i * part + 2, y + 2, part - 4, h - 4, T["accent"], None, 5)
            self.text(x + i * part, y, part, h, label,
                      "accent_text" if i == active else "text_dim", 11, i == active,
                      Qt.AlignCenter)

    def note_card(self, x, y, w, note, selected=False, translated=True):
        number, ru, en, author, when, done = note
        h = 62 if translated else 48
        self.box(x, y, w, h, T["select"] if selected else T["surface"],
                 T["accent"] if selected else T["border"], 8, 1.5 if selected else 1.0)
        if done:
            self.p.setPen(Qt.NoPen)
            self.p.setBrush(QtGui.QColor(T["pill"]))
            self.p.drawEllipse(QtCore.QPointF(x + 21, y + 21), 10, 10)
            self.icon("check", x + 14, y + 14, 14, "text_faint")
        else:
            self.badge(x + 21, y + 21, number)
        tx = x + 40
        self.text(tx, y + 8, w - 50, 18, ru if translated else en,
                  "text_faint" if done else "text", 12, True, strike=done)
        line = y + 27
        if translated:
            self.text(tx, line, w - 50, 15, en, "text_faint", 11)
            line += 16
        self.text(tx, line, w - 50, 15, "{}  ·  {}".format(author, when), "text_dim", 11)
        return h + 6


def variant_a(thumbs):
    """Today's layout, comments as cards."""
    c = P(W, 664)
    c.titlebar()
    c.box(10, 42, 252, 30, T["surface"], T["border"], 7)
    c.text(19, 42, 236, 30, "…04_JPG\\SK200-32_SK100-30_Scene_3", "text", 12)
    c.tool(268, 42, "folder")
    c.tool(300, 42, "refresh")

    c.box(10, 80, 320, 66, T["surface"], T["border"], 8)
    for i, (key, value) in enumerate((("Setup", "SK100-30_FC-2840BB_Angle01"),
                                      ("Camera", "Angle_Key14_Top_Under_Big_205_"),
                                      ("Image", "SK100-30_FC-2840BB_Angle01.jpg"))):
        c.text(20, 88 + i * 17, 50, 16, key, "text_faint", 11)
        c.text(70, 88 + i * 17, 250, 16, value, "text", 12, True)

    c.box(10, 154, 320, 122, T["surface"], T["border"], 8)
    for i in range(4):
        y = 158 + i * 29
        if i == 0:
            c.box(13, y, 314, 27, T["select"], None, 5)
            c.icon("check", 20, y + 6, 14, "accent")
        c.text(42, y, 250, 27, NAMES[i].replace(" · ", "_FC-2840BB_") + ".jpg", "text", 12)
        if COUNTS[i]:
            c.box(292, y + 5, 28, 17, T["pill"], None, 8)
            c.text(292, y + 5, 28, 17, str(COUNTS[i]), "text_dim", 11, True, Qt.AlignCenter)

    c.text(12, 286, 110, 30, "Comments", "text", 12, True)
    c.text(78, 286, 60, 30, "2 of 3 left", "text_faint", 11)
    c.segmented(150, 288, 110, ("Original", "RU"), 1)
    c.tool(268, 286, "eye", True)
    c.tool(300, 286, "sliders")

    y = 324
    for i, note in enumerate(NOTES):
        y += c.note_card(10, y, 320, note, selected=(i == 0))

    c.box(10, 620, 157, 30, T["accent"], None, 7)
    c.icon("link", 46, 627, 16, "accent_text")
    c.text(66, 620, 100, 30, "Follow Setup", "accent_text", 12, True)
    c.box(173, 620, 157, 30, T["accent"], None, 7)
    c.icon("eye", 196, 627, 16, "accent_text")
    c.text(216, 620, 110, 30, "Show in Viewport", "accent_text", 12, True)
    c.save("variant_a.png")


def variant_b(thumbs):
    """Thumbnails instead of file names, folders behind the gear."""
    c = P(W, 664)
    c.titlebar()
    c.box(10, 42, 320, 46, T["surface"], T["border"], 8)
    c.p.setPen(Qt.NoPen)
    c.p.setBrush(QtGui.QColor("#3ecf8e"))
    c.p.drawEllipse(QtCore.QPointF(24, 65), 4, 4)
    c.text(36, 47, 220, 18, "SK100-30 · Angle01", "text", 13, True)
    c.text(36, 65, 220, 16, "Angle_Key14_Top_Under_Big_205_", "text_faint", 11)
    c.icon("folder", 276, 57, 16, "text_dim")
    c.icon("sliders", 302, 57, 16, "text_dim")

    for i in range(6):
        x = 10 + (i % 3) * 108
        y = 98 + (i // 3) * 104
        c.picture(thumbs[i], x, y, 104, 78, 7)
        if i == 0:
            c.box(x - 1, y - 1, 106, 80, None, T["accent"], 8, 2.0)
        if COUNTS[i]:
            c.badge(x + 92, y + 12, COUNTS[i], r=9, size=10)
        c.text(x, y + 80, 104, 18, NAMES[i], "text" if i == 0 else "text_dim", 10,
               i == 0, Qt.AlignCenter)

    c.text(12, 308, 110, 30, "Comments", "text", 12, True)
    c.text(78, 308, 60, 30, "2 of 3 left", "text_faint", 11)
    c.segmented(220, 310, 110, ("Original", "RU"), 1)

    y = 344
    for i, note in enumerate(NOTES):
        y += c.note_card(10, y, 320, note, selected=(i == 0))

    c.segmented(10, 622, 150, ("Image", "Frames"), 0, 28)
    c.text(172, 622, 50, 28, "Opacity", "text_faint", 11)
    c.box(222, 634, 108, 4, T["pill"], None, 2)
    c.box(222, 634, 76, 4, T["accent"], None, 2)
    c.p.setBrush(QtGui.QColor(T["text"]))
    c.p.setPen(Qt.NoPen)
    c.p.drawEllipse(QtCore.QPointF(298, 636), 6, 6)
    c.save("variant_b.png")


def variant_c(thumbs):
    """One big preview with numbered pins, comments underneath."""
    c = P(W, 664)
    c.titlebar()
    c.picture(thumbs[0], 10, 42, 320, 240, 8)
    for i, (x, y, w, h) in enumerate(REGIONS):
        selected = i == 0
        rx, ry, rw, rh = 10 + x * 320, 42 + y * 240, w * 320, h * 240
        c.box(rx, ry, rw, rh, None, FRAME if selected else "#ffffff", 3, 2.0 if selected else 1.0)
        c.badge(rx, ry, i + 1, FRAME if not NOTES[i][5] else T["pill"],
                "#04222b" if not NOTES[i][5] else T["text_dim"], 9, 10)

    c.tool(10, 290, "chev_left", size=28)
    c.text(44, 288, 252, 18, "SK100-30 · Angle01", "text", 12, True, Qt.AlignCenter)
    c.text(44, 305, 252, 14, "1 / 9", "text_faint", 10, False, Qt.AlignCenter)
    c.tool(302, 290, "chev_right", size=28)

    c.text(12, 326, 110, 30, "Comments", "text", 12, True)
    c.text(78, 326, 60, 30, "2 of 3 left", "text_faint", 11)
    c.segmented(220, 328, 110, ("Original", "RU"), 1)

    y = 362
    for i, note in enumerate(NOTES):
        y += c.note_card(10, y, 320, note, selected=(i == 0))

    c.p.fillRect(QtCore.QRectF(0, 620, W, 44), QtGui.QColor(T["titlebar"]))
    for i, (name, on) in enumerate((("link", True), ("image", True), ("eye", True),
                                    ("folder", False), ("sliders", False))):
        c.tool(10 + i * 36, 627, name, on)
    c.text(200, 627, 130, 30, "9 images · 3 comments", "text_faint", 11, False,
           Qt.AlignRight | Qt.AlignVCenter)
    c.save("variant_c.png")


def overlay(thumbs):
    """The frames over the viewport: captions always on, or pins + one caption."""
    width, height = 1000, 420
    c = P(width, height)
    c.p.fillRect(QtCore.QRectF(0, 0, width, height), QtGui.QColor("#15161a"))
    for side, title in enumerate(("Now: every caption shown",
                                  "Pins; the caption only for the selected comment")):
        ox = 14 + side * 493
        c.text(ox, 6, 470, 22, title, "text_dim", 12, True)
        pw, ph = 479, 359
        c.picture(thumbs[0], ox, 34, pw, ph, 6)
        for i, (x, y, w, h) in enumerate(REGIONS):
            rx, ry, rw, rh = ox + x * pw, 34 + y * ph, w * pw, h * ph
            done = NOTES[i][5]
            if side == 0:
                c.box(rx, ry, rw, rh, None, FRAME, 0, 2.0)
                label = "{}  {}".format(i + 1, NOTES[i][1])
                c.box(rx - 1, ry - 22, 16 + len(label) * 7.6, 22, FRAME, None, 3)
                c.text(rx + 6, ry - 22, 400, 22, label, "#04222b", 14, True)
            else:
                selected = i == 0
                color = FRAME if selected else ("#8a909a" if done else "#ffffff")
                c.box(rx, ry, rw, rh, None, color, 4, 2.5 if selected else 1.2)
                c.badge(rx, ry, i + 1, FRAME if not done else "#4d535d",
                        "#04222b" if not done else "#c9cdd3", 11, 12)
                if selected:
                    label = NOTES[i][1]
                    c.box(rx + 16, ry - 14, 22 + len(label) * 7.4, 28, "#17181b", FRAME, 8, 1.2)
                    c.text(rx + 27, ry - 14, 400, 28, label, "#e7e9ec", 14, True)
    c.save("overlay.png")


try:
    backdrop_module.ICONS["chev_left"] = '<path d="M15 6l-6 6 6 6"/>'
    backdrop_module.ICONS["chev_right"] = '<path d="M9 6l6 6-6 6"/>'
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    pictures = load_thumbs()
    for make in (variant_a, variant_b, variant_c, overlay):
        make(pictures)
    with open(os.path.join(OUT, "done.txt"), "w") as f:
        f.write("ok")
except Exception:
    with open(os.path.join(OUT, "error.txt"), "w") as f:
        f.write(traceback.format_exc())
