"""Screenshots of the panel for the README, rendered inside 3ds Max.

Run through tools/make_shots.ps1 (3dsmaxbatch, nothing is shown). The renders
of tools/shots/images are the delivered images (see CREDITS.md there). Writes
docs/shots/panel-dark.png, panel-light.png (the panel itself, at 2x),
viewport.png (the comment frames over the image, as on the viewport),
drive-menu.png (the folder menu with Google Drive set up) and the frames of
sources.gif (switching between the comments of Dropbox and of Google Drive).
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

# The scene is reset: never in a 3ds Max someone is working in.
# maxOps.isInNonInteractiveMode() is true under 3dsmaxbatch (2024 and 2026).
if not rt.maxOps.isInNonInteractiveMode():
    raise RuntimeError("make_shots.py resets the scene: run it with tools/make_shots.ps1, "
                       "not in an open 3ds Max")

ROOT = os.environ["BD_ROOT"]
SRC = os.path.join(ROOT, "src", "backdrop.py")
PHOTOS = os.path.join(ROOT, "tools", "shots", "images")
OUT = os.path.join(ROOT, "docs", "shots")
WORK = os.path.join(ROOT, "tests", "out", "shots")
NAMES = ["Living_Cam01", "Living_Cam02", "Living_Cam03",
         "Dining_Cam01", "Kitchen_Cam01", "Kitchen_Cam02"]

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
# Comments on the first render (living room: TV wall, plant in a pot, armchair).
FIRST = [
    (0.515, 0.395, 0.160, 0.185, "Emily R.",
     "Lower the TV a little and centre it on the wall panel, as in the reference"),
    (0.735, 0.500, 0.170, 0.300, "Emily R.", "Move the plant closer to the wall"),
    (0.225, 0.490, 0.120, 0.170, "Marc D.", "Warmer fabric on the armchair"),
]
# ...and on the fourth (dining room: chandelier, plant by the window).
FOURTH = [
    (0.430, 0.270, 0.140, 0.150, "Emily R.", "A simpler chandelier"),
    (0.640, 0.420, 0.120, 0.210, "Emily R.", "A taller plant"),
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


VIEW_W, VIEW_H = 640, 480                   # the "viewport" of the animation
# What the same client wrote in Google Drive: (x1, y1, x2, y2, author, text).
FIRST_DRIVE = [
    (0.36, 0.60, 0.66, 0.80, "Emily R.", "A lower coffee table, in dark wood"),
    (0.02, 0.30, 0.20, 0.72, "Emily R.", "Lighter curtains, let more daylight in"),
    (0.54, 0.56, 0.70, 0.68, "Marc D.", "Hide the cables under the TV"),
]
FOURTH_DRIVE = [
    (0.30, 0.50, 0.70, 0.80, "Emily R.", "Six chairs instead of four"),
    (0.60, 0.20, 0.80, 0.50, "Emily R.", "Remove the picture"),
]


def write_drive_comments(folder, name, notes):
    """An answer of the Drive API method comments.list, as the panel saves it."""
    import json
    comments = []
    for i, (x1, y1, x2, y2, author, body) in enumerate(notes):
        comments.append({
            "kind": "drive#comment", "content": body, "deleted": False,
            "createdTime": "2026-11-19T1{}:1{}:00.000Z".format(i, i),
            "author": {"kind": "drive#user", "displayName": author},
            "anchor": json.dumps([None, [None, [x1, y1, x2, y2]], None, "revision"])})
    with open(os.path.join(folder, name + ".jpg Google Drive Comments.json"),
              "w", encoding="utf-8") as f:
        json.dump({"kind": "drive#commentList", "comments": comments}, f)


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
    os.environ["BACKDROP_DRIVE"] = os.path.join(WORK, "none")
    QtCore.QSettings("AD Tools", "BackdropShots").clear()

    rt.resetMaxFile(rt.name("noPrompt"))
    rt.renderWidth, rt.renderHeight, rt.renderPixelAspect = 1200, 900, 1.0
    rt.rendOutputFilename = "D:\\Project\\04_EXR\\" + NAMES[0] + ".exr"
    try:
        rt.viewport.setCamera(rt.Freecamera(name="Cam_Living_01"))
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

    # Google Drive set up (docs/google-drive.md): made-up link, client and
    # sign-in, all in the settings of the shots; the "fetched" comments are
    # files written here, Google is not called.
    panel._theme_mode = "dark"
    panel.apply_theme()
    link = "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz"
    settings = QtCore.QSettings("AD Tools", "BackdropShots")
    settings.setValue("drive_client_id", "demo")
    settings.setValue("drive_refresh", "demo")
    fetched = mod.drive_folder(link)
    os.makedirs(fetched)
    write_drive_comments(fetched, NAMES[0], FIRST_DRIVE)
    write_drive_comments(fetched, NAMES[3], FOURTH_DRIVE)
    panel._drive_link = link

    # Frames of docs/shots/sources.gif (joined by make_shots.ps1): the scene
    # goes from the Dropbox files to Google Drive and back through the menu.
    frames = os.path.join(WORK, "frames")
    os.makedirs(frames)
    overlay.resize(VIEW_W, VIEW_H)
    overlay._frame = (0.0, 0.0, float(VIEW_W), float(VIEW_H))
    photo = QtGui.QImage(os.path.join(WORK, NAMES[0] + ".jpg")).scaled(
        VIEW_W, VIEW_H, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
    steps = []                              # (file name, seconds on screen)

    def frame(seconds, pick=None):
        """The viewport with its frames and the panel next to it; with the
        folder menu open on the item `pick` when there is one."""
        pump(150)
        canvas = QtGui.QImage(VIEW_W + panel.width() + 48, panel.height() + 32,
                              QtGui.QImage.Format_ARGB32)
        canvas.fill(QtGui.QColor("#15171b"))
        painter = QtGui.QPainter(canvas)
        try:
            top = 16 + (panel.height() - VIEW_H) // 2
            painter.drawImage(16, top, photo)
            overlay.render(painter, QtCore.QPoint(16, top), QtGui.QRegion(),
                           QtWidgets.QWidget.RenderFlags(QtWidgets.QWidget.DrawChildren))
            left = VIEW_W + 32
            panel.render(painter, QtCore.QPoint(left, 16))
            if pick:
                menu = panel.folder_menu()
                menu.ensurePolished()
                menu.resize(menu.sizeHint())
                for action in menu.actions():
                    if action.text() == pick:
                        menu.setActiveAction(action)
                corner = panel.folder_btn.mapTo(panel, QtCore.QPoint(
                    panel.folder_btn.width(), panel.folder_btn.height() + 2))
                menu.render(painter, QtCore.QPoint(left + corner.x() - menu.width(),
                                                   16 + corner.y()))
                menu.deleteLater()
        finally:
            painter.end()
        name = "{:02d}.png".format(len(steps))
        canvas.save(os.path.join(frames, name))
        steps.append((name, seconds))

    panel._folder = "D:\\Project\\05_JPG\\Living_room"      # what the menu shows
    panel.set_status("6 images")
    frame(2.2)
    frame(1.6, "Comments from: Google Drive")
    panel._folder = WORK
    panel.set_source("drive", fetch=False)
    panel.select_note("1")
    panel.set_status("Google Drive: 5 comments on 2 images.")
    panel._folder = "D:\\Project\\05_JPG\\Living_room"
    frame(2.6)
    frame(1.6, "Comments from: Dropbox files")
    with open(os.path.join(frames, "frames.txt"), "w") as f:    # ffmpeg concat list
        for name, seconds in steps + steps[-1:]:
            f.write("file '{}'\nduration {}\n".format(name, seconds))

    # The folder menu alone, with Google Drive chosen.
    menu = panel.folder_menu()
    menu.ensurePolished()
    menu.resize(menu.sizeHint())
    grab(menu, os.path.join(OUT, "drive-menu.png"))
    menu.deleteLater()

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
