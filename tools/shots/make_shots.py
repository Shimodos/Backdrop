"""Screenshots of the panel for the README, rendered inside 3ds Max.

Run through tools/make_shots.ps1 (3dsmaxbatch, nothing is shown). The photos
of tools/shots/images stand in for renders (see CREDITS.md there). Writes
docs/shots/panel-dark.png, panel-light.png (the panel itself, at 2x) and
viewport.png (the comment frames over the image, as on the viewport).
"""
import os
import shutil
import sys
import time
import traceback

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

from pymxs import runtime as rt

ROOT = os.environ["BD_ROOT"]
SRC = os.path.join(ROOT, "src", "backdrop.py")
PHOTOS = os.path.join(ROOT, "tools", "shots", "images")
OUT = os.path.join(ROOT, "docs", "shots")
WORK = os.path.join(ROOT, "tests", "out", "shots")
NAMES = ["SK100-30_FC-2840BB_Angle01", "SK100-30_FC-2840BB_Angle02",
         "SK100-30_FC-2840BB_Angle03", "SK200-32_FC-2840BB_Angle01",
         "SK200-32_FC-2840BB_Angle02", "SK200-32_FC-2840BB_Angle03"]

BLOCK = """
Timestamp: {time}
Annotation: {{
  "type": "image",
  "region": {{ "height": {h}, "page": 1, "width": {w}, "x": {x}, "y": {y} }},
  "label": {label},
  "regionType": "rectangle"
}}

Head Comment:
Timestamp: {time}
Author: {author}
Content: {text}

========================
"""
# Comments on the first photo (a cup and a phone on a table by a window).
FIRST = [
    (0.555, 0.545, 0.200, 0.290, "Emily R.", "Move the cup closer to the edge of the table"),
    (0.300, 0.770, 0.170, 0.150, "Emily R.", "Remove the phone"),
    (0.560, 0.030, 0.300, 0.380, "Marc D.", "Too bright outside the window"),
]
FOURTH = [
    (0.380, 0.400, 0.150, 0.220, "Emily R.", "Warmer white on the walls"),
    (0.620, 0.450, 0.200, 0.200, "Emily R.", "More contrast here"),
]


def pump(ms=0):
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    app.processEvents()
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def write_comments(name, notes):
    text = ""
    for i, (x, y, w, h, author, body) in enumerate(notes):
        text += BLOCK.format(x=x, y=y, w=w, h=h, label=i + 1, author=author, text=body,
                             time="2026-11-18T1{}:2{}:00.000Z".format(i, i))
    with open(os.path.join(WORK, name + ".jpg Dropbox File Comments.txt"),
              "w", encoding="utf-8") as f:
        f.write(text)


def grab(widget, path, scale=2):
    """The widget as it paints itself, at twice the size for sharp text."""
    pixmap = QtGui.QPixmap(widget.size() * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(QtCore.Qt.transparent)
    widget.render(pixmap, QtCore.QPoint(0, 0))
    pixmap.save(path)


def run():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(os.path.join(WORK, "none"))
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for i, name in enumerate(NAMES):
        shutil.copy(os.path.join(PHOTOS, "0{}.jpg".format(i + 1)),
                    os.path.join(WORK, name + ".jpg"))
    write_comments(NAMES[0], FIRST)
    write_comments(NAMES[3], FOURTH)

    # Nothing of the user's is read or written: own settings, no Downloads, own cache.
    os.environ["BACKDROP_SETTINGS"] = "BackdropShots"
    os.environ["BACKDROP_DOWNLOADS"] = os.path.join(WORK, "none")
    os.environ["BACKDROP_CACHE"] = os.path.join(WORK, "none", "translations.json")
    QtCore.QSettings("AD Tools", "BackdropShots").clear()

    rt.resetMaxFile(rt.name("noPrompt"))
    rt.renderWidth, rt.renderHeight, rt.renderPixelAspect = 1200, 900, 1.0
    rt.rendOutputFilename = "D:\\Project\\04_EXR\\" + NAMES[0] + ".exr"
    try:
        rt.viewport.setCamera(rt.Freecamera(name="Cam_Kitchen_Top_01"))
    except Exception:
        pass

    rt.python.ExecuteFile(SRC)
    mod = sys.modules["adtools_backdrop"]
    panel = mod.backdrop
    panel.set_folder(WORK)
    pump(1500)                              # previews load one per event-loop turn
    panel.notes_list.itemDelegate().toggle(panel.notes_list.model().index(2, 0))
    panel.select_note("1")
    pump(200)

    for mode in ("dark", "light"):
        panel._theme_mode = mode
        panel.apply_theme()
        pump(200)
        grab(panel, os.path.join(OUT, "panel-{}.png".format(mode)))

    # The frames as they sit over the viewport: the image, then the overlay on it.
    overlay = panel.overlay
    overlay._timer.stop()
    overlay.resize(1200, 900)
    overlay._frame = (0.0, 0.0, 1200.0, 900.0)
    picture = QtGui.QImage(os.path.join(WORK, NAMES[0] + ".jpg")).convertToFormat(
        QtGui.QImage.Format_ARGB32)
    overlay.render(picture, QtCore.QPoint(0, 0), QtGui.QRegion(),
                   QtWidgets.QWidget.RenderFlags(QtWidgets.QWidget.DrawChildren))
    picture.save(os.path.join(OUT, "viewport.png"))

    panel.close()
    pump(100)
    QtCore.QSettings("AD Tools", "BackdropShots").clear()
    rt.execute("viewport.DispBkgImage = false")


log = os.path.join(ROOT, "tests", "out", "make_shots.log")
try:
    run()
    result = "ok"
except Exception:
    result = traceback.format_exc()
with open(log, "w") as f:
    f.write(result)
