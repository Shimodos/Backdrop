"""Draws the Backdrop icons with Qt inside 3ds Max.

Run through tools/make_icons.ps1 (3dsmaxbatch). Writes the toolbar icons
installer/icons/Dark|Light/Backdrop_<24|30|36|48>.png (the sizes and folder
names 3ds Max looks for by iconName) and docs/icon-256.png, the app tile.

The picture: a render in a frame, with the pin of a client comment on it.
"""
import os
import traceback

try:
    from PySide6 import QtCore, QtGui, QtSvg
except ImportError:
    from PySide2 import QtCore, QtGui, QtSvg

Qt = QtCore.Qt
ROOT = os.environ["BD_ROOT"]

# 24x24 drawing: frame, horizon line of the render, comment pin top right.
GLYPH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M14.500 5H5.500A2.500 2.500 0 0 0 3 7.500v10A2.500 2.500 0 0 0 5.500 20h13'
    'a2.500 2.500 0 0 0 2.500-2.500V11.500" stroke="{frame}" stroke-width="{width}"/>'
    '<path d="M3.500 17l5-5.500 4 4 2.500-2.500 5.500 5" stroke="{frame}" stroke-width="{width}"/>'
    '<circle cx="19" cy="6" r="3.600" fill="{pin}" stroke="none"/>'
    '</svg>'
)


def render(svg, size):
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(0)
    painter = QtGui.QPainter(image)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8"))).render(
            painter, QtCore.QRectF(0, 0, size, size))
    finally:
        painter.end()
    return image


def toolbar_icons():
    # Dark UI gets the light drawing and the other way round.
    looks = {"Dark": ("#d9dde3", "#2cc6ea"), "Light": ("#3c434d", "#0aa3c6")}
    for theme, (frame, pin) in looks.items():
        folder = os.path.join(ROOT, "installer", "icons", theme)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        for size in (24, 30, 36, 48):
            svg = GLYPH.format(frame=frame, pin=pin, width=1.9)
            render(svg, size).save(os.path.join(folder, "Backdrop_{}.png".format(size)))


def tile(size=256):
    """Rounded accent tile with the white drawing: site, releases, shortcuts."""
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(0)
    painter = QtGui.QPainter(image)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        gradient = QtGui.QLinearGradient(0, 0, size, size)
        gradient.setColorAt(0.0, QtGui.QColor("#3ad3f5"))
        gradient.setColorAt(1.0, QtGui.QColor("#0c9cc0"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        box = QtCore.QRectF(size * 0.03, size * 0.03, size * 0.94, size * 0.94)
        painter.drawRoundedRect(box, size * 0.21, size * 0.21)
        svg = GLYPH.format(frame="#ffffff", pin="#04222b", width=1.7)
        inner = size * 0.60
        QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8"))).render(
            painter, QtCore.QRectF((size - inner) / 2, (size - inner) / 2, inner, inner))
    finally:
        painter.end()
    docs = os.path.join(ROOT, "docs")
    if not os.path.isdir(docs):
        os.makedirs(docs)
    image.save(os.path.join(docs, "icon-256.png"))


log = os.path.join(ROOT, "tests", "out", "make_icons.log")
try:
    toolbar_icons()
    tile()
    result = "ok"
except Exception:
    result = traceback.format_exc()
if not os.path.isdir(os.path.dirname(log)):
    os.makedirs(os.path.dirname(log))
with open(log, "w") as f:
    f.write(result)
