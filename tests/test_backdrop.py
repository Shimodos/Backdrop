"""Headless checks for backdrop.py.

Run inside 3ds Max through tests/run_tests.ps1 (3dsmaxbatch). Makes a folder
of small images, opens the panel and switches the render output the way
activating a Scene Manager setup does, writing a report to
%BD_OUT%\\report_<max year>.txt and a screenshot of the panel next to it.
"""
import datetime
import json
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

# The checks reset and load scenes: never in a 3ds Max someone is working in.
# maxOps.isInNonInteractiveMode() is true under 3dsmaxbatch (2024 and 2026).
if not rt.maxOps.isInNonInteractiveMode():
    raise RuntimeError("test_backdrop.py resets the scene: run it with tests/run_tests.ps1, "
                       "not in an open 3ds Max")

SRC = os.environ["BD_SRC"]
OUT = os.environ["BD_OUT"]
YEAR = int(list(rt.maxVersion())[7])
REPORT = os.path.join(OUT, "report_{}.txt".format(YEAR))
IMAGES = os.path.join(OUT, "images_{}".format(YEAR))
NAMES = ["SK100-30_FC-2840BB_Angle01", "SK100-30_FC-2840BB_Angle02",
         "SK200-32_FC-2840BB_Angle01", "SK200-32_FC-2840BB_Angle02",
         "SK200-32_FC-2840BB_Angle03"]

failed = []
report = open(REPORT, "w", encoding="utf-8")


def log(*args):
    # Flushed line by line: if Max itself dies, the report shows how far we got.
    report.write(" ".join(str(a) for a in args) + "\n")
    report.flush()
    os.fsync(report.fileno())


def check(name, condition, detail=""):
    if condition:
        log("ok    ", name)
    else:
        failed.append(name)
        log("FAIL  ", name, detail)


def pump(ms=0):
    """Let Qt timers and queued events run."""
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    app.processEvents()
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def make_images():
    shutil.rmtree(IMAGES, ignore_errors=True)
    os.makedirs(os.path.join(IMAGES, "001"))
    # Stands in for the Downloads folder, so the user's own is not touched.
    os.environ["BACKDROP_DOWNLOADS"] = os.path.join(IMAGES, "001")
    os.makedirs(os.path.join(IMAGES, "002"))
    os.environ["BACKDROP_CACHE"] = os.path.join(IMAGES, "002", "cache", "translations.json")
    for i, name in enumerate(NAMES):
        image = QtGui.QImage(64, 48, QtGui.QImage.Format_RGB32)
        image.fill(QtGui.QColor.fromHsv(i * 60, 200, 220))
        image.save(os.path.join(IMAGES, name + ".jpg"))
    # Must be ignored: a subfolder with an older round, and a non-image.
    shutil.copy(os.path.join(IMAGES, NAMES[0] + ".jpg"),
                os.path.join(IMAGES, "001", "old.jpg"))
    with open(os.path.join(IMAGES, "notes.txt"), "w") as f:
        f.write("x")


def drawn(panel):
    """Number of comment frames on the viewport."""
    return len(panel.overlay.notes)


def thumb_count(panel, name):
    """Badge of open comments on the thumbnail of an image."""
    for i in range(panel.list.count()):
        item = panel.list.item(i)
        if item.text() == name + ".jpg":
            return item.data(QtCore.Qt.UserRole + 1) or 0
    return None


def callbacks():
    return str(rt.execute(
        "(local s = stringStream \"\"; showRegisteredRedrawViewsCallbacks to:s; s as string)"))


# The file Dropbox saves for "Download comments" on an image.
COMMENTS = """
Timestamp: 2026-11-20T13:43:39.000Z
Annotation: {
  "type": "image",
  "region": {
    "height": 0.112976454,
    "page": 1,
    "width": 0.102985054,
    "x": 0.23786907,
    "y": 0.20700033
  },
  "label": 1,
  "regionType": "rectangle"
}

Head Comment:
Timestamp: 2026-11-20T13:43:39.000Z
Author: Aleksey Demchenko
Content: Подвинуть

========================


Timestamp: 2026-11-20T13:43:58.000Z
Annotation: {
  "type": "image",
  "region": {
    "height": 0.116144024,
    "page": 1,
    "width": 0.083180234,
    "x": 0.31391957,
    "y": 0.39071906
  },
  "label": 2,
  "regionType": "rectangle"
}

Head Comment:
Timestamp: 2026-11-20T13:43:58.000Z
Author: Aleksey Demchenko
Content: Подсветитиь

========================


Timestamp: 2026-11-20T13:44:11.000Z
Annotation: {
  "type": "image",
  "region": {
    "height": 0.13836974,
    "page": 1,
    "width": 0.06258322,
    "x": 0.3986842,
    "y": 0.86163026
  },
  "label": 3,
  "regionType": "rectangle"
}

Head Comment:
Timestamp: 2026-11-20T13:44:11.000Z
Author: Aleksey Demchenko
Content: Ручки


========================
"""


def background():
    return os.path.basename(str(rt.backgroundImageFileName))


def shown():
    return bool(rt.execute("viewport.DispBkgImage"))


def shown_on():
    """Indexes of the viewports with the background image displayed."""
    active = int(rt.viewport.activeViewport)
    result = []
    for index in range(1, int(rt.viewport.numViews) + 1):
        rt.execute("viewport.activeViewport = {}".format(index))
        if shown():
            result.append(index)
    rt.execute("viewport.activeViewport = {}".format(active))
    return result


def activate(setup,folder="D:\\out\\04_EXR\\Scene_3", ext=".exr"):
    """What activating a Scene Manager setup does to Render Output - Common."""
    rt.rendOutputFilename = os.path.join(folder, setup + ext) if setup else ""
    pump(900)


def run():
    import __main__
    rt.resetMaxFile(rt.name("noPrompt"))
    start_camera = rt.Freecamera(name="Start_camera")
    rt.viewport.setCamera(start_camera)     # the image only goes on a camera view
    make_images()
    QtCore.QSettings("AD Tools", os.environ["BACKDROP_SETTINGS"]).clear()

    # Names another panel owns in the shared __main__ must survive the start.
    sentinel = object()
    __main__.make_icon = sentinel
    rt.python.ExecuteFile(SRC)
    mod = sys.modules.get("adtools_backdrop")
    panel = getattr(mod, "backdrop", None)
    check("panel created", panel is not None)
    if panel is None:
        return
    check("__main__ is handed back untouched", __main__.make_icon is sentinel
          and not hasattr(__main__, "BackdropDockWidget") and not hasattr(__main__, "ICONS"),
          [n for n in ("BackdropDockWidget", "ICONS", "T") if hasattr(__main__, n)])
    match = mod.match_image
    pump(50)

    # --- name matching ---
    images = mod.list_images(IMAGES)
    check("folder lists only its own images", [s for s, _ in images] == NAMES,
          [s for s, _ in images])
    check("exact name", os.path.basename(match(NAMES[2], images) or "") == NAMES[2] + ".jpg")
    check("case and separators ignored",
          os.path.basename(match("sk200 32_fc-2840bb-angle02", images) or "")
          == NAMES[3] + ".jpg")
    check("frame suffix on the output",
          os.path.basename(match(NAMES[4] + "_0014", images) or "") == NAMES[4] + ".jpg")
    check("unknown setup has no image", match("SK200-32_FC-2840BB_Angle04", images) is None)
    check("empty setup has no image", match("", images) is None)

    # --- no folder yet ---
    check("nothing shown without a folder", not shown())

    # --- folder + active setup ---
    activate(NAMES[2])
    panel.set_folder(IMAGES)
    pump(100)
    check("list shows the images", panel.list.count() == len(NAMES), panel.list.count())
    check("setup image is on the viewport", background() == NAMES[2] + ".jpg", background())
    check("background display is on", shown())
    check("aspect matches the render output",
          str(rt.getBkgImageAspect()) == "output", rt.getBkgImageAspect())
    check("setup name shown", panel.setup_label.full == NAMES[2], panel.setup_label.full)
    check("state dot: image found", panel._dot_state == "ok", panel._dot_state)
    pump(600)
    check("previews loaded for every image",
          sorted(os.path.basename(p) for p, pix in panel.list.pixmaps.items() if pix is not None)
          == sorted(n + ".jpg" for n in NAMES), list(panel.list.pixmaps))
    check("active setup marked on its thumbnail",
          [panel.list.item(i).data(mod.ROLE_MATCH) for i in range(panel.list.count())]
          == [n == NAMES[2] for n in NAMES])
    check("short thumbnail name", mod.short_name(NAMES[0]) == "SK100-30 · Angle01",
          mod.short_name(NAMES[0]))

    # --- another setup is activated ---
    activate(NAMES[0])
    check("image follows the setup", background() == NAMES[0] + ".jpg", background())
    current = panel.list.currentItem()
    check("list highlights it", current is not None and current.text() == NAMES[0] + ".jpg")

    # --- setup without an image ---
    activate("SK200-32_FC-2840BB_Angle04")
    check("no image: display is off", not shown())
    check("no image: says so", "No image" in panel.status_label.text()
          and panel._dot_state == "warn", panel.status_label.text())

    # --- image rendered after the folder was read ---
    late = QtGui.QImage(64, 48, QtGui.QImage.Format_RGB32)
    late.fill(QtGui.QColor("#808080"))
    late.save(os.path.join(IMAGES, "SK200-32_FC-2840BB_Angle05.jpg"))
    activate("SK200-32_FC-2840BB_Angle05")
    check("new file is picked up", background() == "SK200-32_FC-2840BB_Angle05.jpg",
          background())
    check("display is back on", shown())

    # --- show / hide ---
    panel.show_btn.setChecked(False)
    pump(50)
    check("hide switches the display off", not shown())
    panel.show_btn.setChecked(True)
    pump(50)
    check("show switches it back on", shown())

    # --- manual pick, then follow off ---
    panel._item_clicked(panel.list.item(1))
    pump(50)
    check("clicked image is shown", background() == NAMES[1] + ".jpg", background())
    panel.follow_btn.setChecked(False)
    activate(NAMES[3])
    check("follow off: image stays", background() == NAMES[1] + ".jpg", background())
    panel.follow_btn.setChecked(True)
    pump(50)
    check("follow on: image of the setup", background() == NAMES[3] + ".jpg", background())

    # --- Dropbox comments ---
    notes = mod.parse_comments(COMMENTS)
    check("three comments parsed", len(notes) == 3, len(notes))
    check("comment text", [n["text"] for n in notes] == ["Подвинуть", "Подсветитиь", "Ручки"],
          [n["text"] for n in notes])
    check("comment labels", [n["label"] for n in notes] == ["1", "2", "3"])
    check("comment author", notes[0]["author"] == "Aleksey Demchenko", notes[0]["author"])
    check("comment region", notes[0]["region"] is not None
          and abs(notes[0]["region"][0] - 0.23786907) < 1e-6
          and abs(notes[0]["region"][3] - 0.112976454) < 1e-6, notes[0]["region"])
    check("general comment has no region",
          mod.parse_comments("\nHead Comment:\nAuthor: A\nContent: all good\n")[0]["region"] is None)

    # --- entries without text (Dropbox does not show them either) ---
    empty = ("\nTimestamp: 2026-10-29T17:32:43.000Z\nAnnotation: No annotation\n\n"
             "Head Comment:\nTimestamp: 2026-10-29T17:32:43.000Z\nAuthor: Unknown\nContent: \n\n"
             "========================\n\n")
    linked = ("\nTimestamp: 2026-10-29T19:35:36.000Z\nAnnotation: {\n  \"type\": \"image\",\n"
              "  \"region\": { \"height\": 0.1, \"page\": 1, \"width\": 0.1, \"x\": 0.2, \"y\": 0.4 },\n"
              "  \"label\": 3,\n  \"regionType\": \"rectangle\"\n}\n\n"
              "Head Comment:\nTimestamp: 2026-10-29T19:35:36.000Z\nAuthor: Emily R.\n"
              "Content: make the dish matte\n\nuse the bottle from this scene:\n"
              "https://example.com/scl/fo/abc/Scene_D?dl=0&preview=Angle07.jpg&rlkey=xyz\n\n"
              "========================\n")
    notes = mod.parse_comments(empty + empty + linked)
    check("comments without text are left out", len(notes) == 1 and notes[0]["label"] == "3"
          and notes[0]["author"] == "Emily R.", [(n["label"], n["text"]) for n in notes])
    link = "https://example.com/scl/fo/abc/Scene_D?dl=0&preview=Angle07.jpg&rlkey=xyz"
    check("link found in a comment", mod.find_links(notes[0]["text"]) == [link],
          mod.find_links(notes[0]["text"]))
    check("links: sentence punctuation dropped, each once, none in plain text",
          mod.find_links("see (https://a.example/x), then http://b.example/y. and https://a.example/x")
          == ["https://a.example/x", "http://b.example/y"] and mod.find_links("no link here") == [],
          mod.find_links("see (https://a.example/x), then http://b.example/y. and https://a.example/x"))

    # --- Google Drive: the answer of comments.list saved as a file ---
    def drive_comment(text, created, corners=None, **more):
        anchor = json.dumps([None, [None, corners], None, "0Brevision"]) if corners else None
        comment = {"kind": "drive#comment", "content": text, "createdTime": created,
                   "deleted": False, "replies": [],
                   "author": {"displayName": "Emily R.", "kind": "drive#user"}}
        if anchor:
            comment["anchor"] = anchor
        comment.update(more)
        return comment

    drive = json.dumps({"kind": "drive#commentList", "comments": [
        drive_comment("Faucet", "2026-11-23T12:37:04.769Z", [0.476, 0.172, 0.598, 0.465]),
        drive_comment("gone", "2026-11-23T12:36:55.000Z", [0.1, 0.1, 0.2, 0.2], deleted=True),
        drive_comment("", "2026-11-23T12:36:50.000Z", [0.1, 0.1, 0.2, 0.2]),
        drive_comment("shift more left", "2026-11-23T12:36:49.824Z", [0.498, 0.442, 0.737, 0.618]),
        drive_comment("general note", "2026-11-23T12:36:30.000Z"),
        drive_comment("first one", "2026-11-23T12:36:23.252Z", [0.233, 0.182, 0.346, 0.331]),
    ]})
    from_drive = mod.parse_drive_comments(drive)
    check("drive: numbered by time, deleted and empty left out",
          [(n["label"], n["text"]) for n in from_drive]
          == [("1", "first one"), ("2", "general note"), ("3", "shift more left"), ("4", "Faucet")],
          [(n["label"], n["text"]) for n in from_drive])
    region = from_drive[3]["region"]
    check("drive: two corners become x, y, width, height",
          region is not None and abs(region[0] - 0.476) < 1e-9 and abs(region[1] - 0.172) < 1e-9
          and abs(region[2] - 0.122) < 1e-9 and abs(region[3] - 0.293) < 1e-9, region)
    check("drive: comment without an anchor has no region, author and time read",
          from_drive[1]["region"] is None and from_drive[0]["author"] == "Emily R."
          and from_drive[0]["time"] == mod.local_time("2026-11-23T12:36:23.252Z") != "",
          (from_drive[1]["region"], from_drive[0]["author"], from_drive[0]["time"]))
    odd = json.dumps({"comments": [drive_comment("odd anchor", "2026-11-23T12:00:00.000Z",
                                                 anchor='{"r":"head","a":[{"rect":{"x":1}}]}')]})
    check("drive: an anchor of another shape gives a comment without a place",
          [n["region"] for n in mod.parse_drive_comments(odd)] == [None])
    check("drive: not JSON, or not a comment list, is no comments",
          mod.parse_drive_comments("not json") == [] and mod.parse_drive_comments("[1, 2]") == []
          and mod.parse_drive_comments("{}") == [])
    drive_dir = os.path.join(OUT, "drive_{}".format(YEAR))
    shutil.rmtree(drive_dir, ignore_errors=True)
    os.makedirs(drive_dir)
    for name in ("Shot_A.jpg Google Drive Comments.json", "Shot_B google drive comments.json",
                 "other.json"):
        with open(os.path.join(drive_dir, name), "w", encoding="utf-8") as f:
            f.write(drive)
    index = mod.index_comment_files([drive_dir])
    check("drive: files are found by the name of the image",
          sorted(index) == ["shot_a.jpg", "shot_b"], sorted(index))
    found = mod.find_comments_file(os.path.join(drive_dir, "Shot_B.png"), [drive_dir])
    check("drive: the image extension may be left out of the file name, the file is read",
          os.path.basename(found or "") == "Shot_B google drive comments.json"
          and len(mod.load_comments(found)) == 4, found)

    # --- menu of a comment card: nothing really reaches the clipboard or a browser ---
    copied, opened = [], []
    real_copy, real_open = mod.copy_text, mod.open_link
    mod.copy_text, mod.open_link = copied.append, opened.append
    try:
        menu = panel.note_menu(notes[0])
        titles = [a.text() for a in menu.actions() if not a.isSeparator()]
        check("card menu: text and link actions", titles[0] == "Copy the text"
              and titles[2:] == ["Open the link", "Copy the link"], titles)
        for action in menu.actions():
            if action.isEnabled() and not action.isSeparator():
                action.trigger()
        check("card menu: copies the text and the link; the address line opens it too",
              copied == [notes[0]["text"], link] and opened == [link, link], (copied, opened))
        del copied[:]
        menu = panel.note_menu(dict(notes[0], shown="сделайте блюдце матовым"))
        titles = [a.text() for a in menu.actions() if not a.isSeparator()]
        check("card menu of a translated comment offers both texts",
              titles[:2] == ["Copy the translation", "Copy the original"], titles)
        menu.actions()[0].trigger()
        menu.actions()[1].trigger()
        check("translation and original are copied", copied == ["сделайте блюдце матовым",
                                                                notes[0]["text"]], copied)
        plain = panel.note_menu({"label": "1", "text": "all good", "author": "", "region": None})
        check("card menu without a link: only the text",
              [a.text() for a in plain.actions()] == ["Copy the text"])
    finally:
        mod.copy_text, mod.open_link = real_copy, real_open

    rt.renderWidth, rt.renderHeight, rt.renderPixelAspect = 3500, 2626, 1.0
    fit = list(rt.bd_fit(1000, 500))
    check("frame in a wide viewport", abs(fit[3] - 500) < 0.01
          and abs(fit[2] - 500 * 3500 / 2626.0) < 0.01
          and abs(fit[0] - (1000 - fit[2]) / 2) < 0.01 and abs(fit[1]) < 0.01, fit)
    fit = list(rt.bd_fit(500, 1000))
    check("frame in a tall viewport", abs(fit[2] - 500) < 0.01
          and abs(fit[1] - (1000 - 500 * 2626 / 3500.0) / 2) < 0.01, fit)

    check("no comments file: nothing to draw", drawn(panel) == 0)
    downloads = os.environ["BACKDROP_DOWNLOADS"]
    old = os.path.join(downloads, NAMES[3] + ".jpg Dropbox File Comments.txt")
    with open(old, "w", encoding="utf-8") as f:
        f.write(COMMENTS.split("========================")[0] + "========================\n")
    os.utime(old, (time.time() - 100, time.time() - 100))
    pump(2500)
    check("downloaded file is picked up", drawn(panel) == 1, rt.bd_notes.count)
    with open(os.path.join(downloads, NAMES[3] + ".jpg Dropbox File Comments (1).txt"),
              "w", encoding="utf-8") as f:
        f.write(COMMENTS)
    pump(2500)
    check("newer download replaces it", drawn(panel) == 3, rt.bd_notes.count)
    check("comments listed", panel.notes_list.count() == 3, panel.notes_list.count())
    check("what is left is counted", panel.notes_count.full == "3 of 3 left",
          panel.notes_count.full)
    local = datetime.datetime(2026, 11, 20, 13, 43, 39, tzinfo=datetime.timezone.utc).astimezone()
    check("comment time in local time, month in English",
          mod.local_time("2026-11-20T13:43:39.000Z")
          == "{:02d} Nov {:02d}:{:02d}".format(local.day, local.hour, local.minute)
          and panel._notes[0]["time"] != "", panel._notes[0]["time"])
    check("badge on the thumbnail", thumb_count(panel, NAMES[3]) == 3
          and thumb_count(panel, NAMES[0]) == 0, thumb_count(panel, NAMES[3]))
    hint = panel.notes_list.itemDelegate().sizeHint(None, panel.notes_list.model().index(0, 0))
    check("card has a height", hint.height() >= 46, hint.height())
    cards = panel.notes_list.itemDelegate()
    first = panel.notes_list.model().index(0, 0)
    check("card of an open comment is not drawn as done", not cards.is_done(first))
    cards.toggle(first)                     # what a click on the pin does
    pump(50)
    check("click on the pin ticks the comment off", cards.is_done(first)
          and panel.notes_list.item(0).checkState() == QtCore.Qt.Unchecked
          and panel.notes_count.full == "2 of 3 left", panel.notes_count.full)
    cards.toggle(first)
    pump(50)
    check("second click on the pin ticks it on again", not cards.is_done(first)
          and panel.notes_count.full == "3 of 3 left")
    grid = panel.list.gridSize()
    bar = panel.list.verticalScrollBar().sizeHint().width()
    check("three thumbnails in a row, with or without the scroll bar",
          grid.width() * 3 <= panel.list.width() - bar < grid.width() * 4,
          (grid.width(), panel.list.width(), bar))
    check("frame caption", mod.caption_of(panel.overlay.notes[1]) == "2  Подсветитиь")
    check("overlay draws, not gw", int(rt.bd_notes.count) == 0 and "bd_draw" not in callbacks())

    # --- the overlay picture ---
    overlay = panel.overlay
    overlay._timer.stop()                   # no viewport window in batch: place it by hand
    overlay.resize(1000, 500)
    overlay._frame = mod.fit_frame(1000, 500)
    rect = overlay.note_rects()[0][0]
    check("frame placed inside the render area",
          abs(rect.left() - (overlay._frame[0] + 0.23786907 * overlay._frame[2])) < 0.01
          and abs(rect.height() - 0.112976454 * 500) < 0.01, rect)
    panel.set_color("frame_color", "#ff0000")
    panel.set_color("text_color", "#ffffff")
    panel.set_text_size(32)
    check("nothing picked at first", overlay.selected is None)
    panel.select_note("1")
    pump(50)
    check("picked comment is highlighted on the viewport", overlay.selected == "1",
          overlay.selected)
    image = QtGui.QImage(1000, 500, QtGui.QImage.Format_ARGB32)
    image.fill(0)
    overlay.render(image, QtCore.QPoint(0, 0), QtGui.QRegion(),
                   QtWidgets.QWidget.RenderFlags(QtWidgets.QWidget.DrawChildren))
    image.save(os.path.join(OUT, "overlay_{}.png".format(YEAR)))
    edge = QtGui.QColor(image.pixel(int(rect.left()), int(rect.center().y())))
    check("frame painted in the chosen colour", edge.red() > 200 and edge.green() < 60,
          edge.name())
    check("outside the frames stays transparent",
          QtGui.QColor.fromRgba(image.pixel(990, 250)).alpha() == 0)
    check("text size and colours kept",
          mod.load_int("text_size", 0) == 32
          and mod.load_color("frame_color", "#000000").name() == "#ff0000"
          and mod.load_color("text_color", "#000000").name() == "#ffffff")

    # --- the text of the picked comment is a block, not one long line ---
    long_text = ("Make the soap dish more beige and not shiny or glossy. Use the bottle from "
                 "this scene: https://example.com/scl/fo/abc/Scene_D?dl=0&preview=Angle07.jpg"
                 "&rlkey=xyz&subfolder_nav_tracking=1")
    doc = overlay.bubble_document(long_text)
    line = QtGui.QFontMetrics(doc.defaultFont()).lineSpacing()
    check("long comment is wrapped into a block",
          doc.size().height() >= 3 * line and doc.size().width() <= 32 * 20 + 1,
          (doc.size().width(), doc.size().height(), line))
    short = overlay.bubble_document("ok")
    check("short comment keeps a small bubble",
          short.size().height() < 1.5 * line and short.size().width() < 100,
          (short.size().width(), short.size().height()))
    overlay.resize(300, 500)
    check("the block is never wider than the viewport",
          overlay.bubble_document(long_text).size().width() <= 300 - 22)
    overlay.resize(1000, 500)
    picked_note = [n for n in overlay.notes if n["label"] == "1"][0]
    picked_note["shown"] = long_text
    image.fill(0)
    overlay.render(image, QtCore.QPoint(0, 0), QtGui.QRegion(),
                   QtWidgets.QWidget.RenderFlags(QtWidgets.QWidget.DrawChildren))
    image.save(os.path.join(OUT, "bubble_{}.png".format(YEAR)))
    del picked_note["shown"]

    # --- checklist ---
    item = panel.notes_list.item(1)
    check("comments are ticked", item.checkState() == QtCore.Qt.Checked)
    item.setCheckState(QtCore.Qt.Unchecked)
    pump(50)
    check("ticked off: pin goes grey, frame stays",
          overlay.done == {"2"} and drawn(panel) == 3, overlay.done)
    check("ticked off: counted", panel.notes_count.full == "2 of 3 left"
          and thumb_count(panel, NAMES[3]) == 2, panel.notes_count.full)
    activate(NAMES[0])
    check("another image: nothing picked", overlay.selected is None and panel._selected is None)
    activate(NAMES[3])
    check("tick is remembered", overlay.done == {"2"}
          and panel.notes_list.item(1).checkState() == QtCore.Qt.Unchecked, overlay.done)
    panel.notes_list.item(1).setCheckState(QtCore.Qt.Checked)
    pump(50)
    check("ticked on again", overlay.done == set() and thumb_count(panel, NAMES[3]) == 3)

    # --- the eye on a card: one frame off the viewport, apart from ticking off ---
    cards.toggle_eye(panel.notes_list.model().index(0, 0))
    pump(50)
    check("eye off: that frame leaves the viewport",
          [n["label"] for n in overlay.notes] == ["2", "3"], [n["label"] for n in overlay.notes])
    check("eye off: the comment is still to do", panel.notes_count.full == "3 of 3 left"
          and panel.notes_list.item(0).checkState() == QtCore.Qt.Checked
          and thumb_count(panel, NAMES[3]) == 3, panel.notes_count.full)
    activate(NAMES[0])
    activate(NAMES[3])
    check("eye off is remembered", [n["label"] for n in overlay.notes] == ["2", "3"]
          and panel.notes_list.unseen == {"1"}, panel.notes_list.unseen)
    panel._use_gw = True
    panel._draw_notes()
    check("eye off holds for the gw fallback too", int(rt.bd_notes.count) == 2)
    panel._use_gw = False
    panel._draw_notes()
    cards.toggle_eye(panel.notes_list.model().index(0, 0))
    pump(50)
    check("eye on again: frame back", drawn(panel) == 3 and panel.notes_list.unseen == set())

    # --- picking a card, letting go of it, opacity ---
    panel.select_note("3")
    pump(50)
    check("card picked", overlay.selected == "3")
    panel._note_clicked(panel.notes_list.item(2))       # a second click on the same card
    pump(50)
    check("second click lets go", overlay.selected is None and panel._selected is None,
          overlay.selected)
    panel.opacity_slider.setValue(40)
    check("opacity of the frames", abs(overlay.opacity - 0.4) < 0.001
          and mod.load_int("opacity", 0) == 40, overlay.opacity)
    panel.opacity_slider.setValue(100)

    # --- translation (DeepL is replaced by a fake: no network in the tests) ---
    url, headers, body = mod.deepl_request(" abc:fx ", ["Hi", "Bye"])
    check("free key goes to the free host", url == "https://api-free.deepl.com/v2/translate", url)
    check("key travels in the header", headers["Authorization"] == "DeepL-Auth-Key abc:fx")
    check("request body", json.loads(body.decode("utf-8"))
          == {"text": ["Hi", "Bye"], "target_lang": "RU"}, body)
    check("pro key goes to the pro host",
          mod.deepl_request("abc", ["Hi"])[0] == "https://api.deepl.com/v2/translate")
    check("english needs translation", mod.needs_translation("Move the bowl"))
    check("russian and numbers do not", not mod.needs_translation("Ручки")
          and not mod.needs_translation("Подвинуть bowl") and not mod.needs_translation("12"))

    # Certificates: expiry read from the DER, checked against OpenSSL's own decoding.
    import ssl
    import tempfile
    compared = wrong = 0
    for der, encoding, _trust in list(ssl.enum_certificates("ROOT"))[:25]:
        if encoding != "x509_asn":
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
            f.write(ssl.DER_cert_to_PEM_cert(der))
        try:
            theirs = ssl.cert_time_to_seconds(ssl._ssl._test_decode_cert(f.name)["notAfter"])
        finally:
            os.unlink(f.name)
        ours = mod.cert_not_after(der)
        compared += 1
        if ours is None or abs((ours - datetime.datetime(1970, 1, 1)).total_seconds() - theirs) > 1:
            wrong += 1
    check("certificate expiry is read correctly", compared > 5 and wrong == 0, (compared, wrong))
    check("garbage is not a certificate", mod.cert_not_after(b"\x30\x03abc") is None)

    # The real DeepL server with a made-up key: it must get as far as DeepL
    # refusing the key. Before, Python stopped at an expired certificate of
    # the Windows store ("certificate has expired").
    try:
        mod.deepl_usage("00000000-0000-0000-0000-000000000000:fx")
        answer = "accepted"
    except RuntimeError as e:
        answer = str(e)
    if "no answer" in answer and "certificate" not in answer.lower():
        log("skip   no network for the DeepL check:", answer)
    else:
        check("connection to DeepL passes the certificate check",
              answer == "DeepL: the key was not accepted.", answer)

    # A long message must not stretch the window.
    width = panel.width()
    long_message = "DeepL: no answer (" + "certificate verify failed " * 20 + ")"
    panel.set_status(long_message, warn=True)
    pump(200)
    check("long status does not widen the panel", panel.width() == width
          and panel.status_label.text() == long_message
          and panel.status_label.toolTip() == long_message
          and panel.minimumSizeHint().width() < 400,
          (panel.width(), panel.minimumSizeHint().width()))

    calls = []

    def fake_deepl(key, texts):
        calls.append((key, list(texts)))
        return ["RU:" + t for t in texts]

    checks = []

    def fake_usage(key):
        checks.append(key)
        return 1200, 500000

    mod.deepl_usage = fake_usage
    usage_url, usage_headers = mod.deepl_usage_request("abc:fx")
    check("key check asks the usage endpoint",
          usage_url == "https://api-free.deepl.com/v2/usage"
          and usage_headers == {"Authorization": "DeepL-Auth-Key abc:fx"}, usage_url)
    mod.deepl_translate = fake_deepl
    english = COMMENTS.replace("Подвинуть", "Move the bowl").replace("Подсветитиь", "Highlight it")
    with open(os.path.join(downloads, NAMES[3] + ".jpg Dropbox File Comments (2).txt"),
              "w", encoding="utf-8") as f:
        f.write(english)
    pump(2500)
    check("original shown by default",
          mod.caption_of(overlay.notes[0]) == "1  Move the bowl",
          mod.caption_of(overlay.notes[0]))
    panel.set_translate(True)
    pump(300)
    check("no key: nothing is sent, and it says so",
          calls == [] and "key" in panel.status_label.text(), panel.status_label.text())
    panel.set_key("abc:fx")
    pump(800)
    check("entered key is checked with DeepL", checks == ["abc:fx"] and panel._key_note
          == "DeepL key accepted: 1 200 of 500 000 characters used.", panel._key_note)
    check("only the english comments are sent, once",
          calls == [("abc:fx", ["Move the bowl", "Highlight it"])], calls)
    check("frames show the translation",
          [mod.caption_of(n) for n in overlay.notes]
          == ["1  RU:Move the bowl", "2  RU:Highlight it", "3  Ручки"],
          [mod.caption_of(n) for n in overlay.notes])
    check("list shows the translation, the original in the tooltip",
          panel.notes_list.item(0).text().startswith("1  RU:Move the bowl")
          and panel.notes_list.item(0).toolTip() == "Move the bowl",
          panel.notes_list.item(0).text())
    with open(os.environ["BACKDROP_CACHE"], "r", encoding="utf-8") as f:
        check("translations are cached on disk", json.load(f).get("Highlight it") == "RU:Highlight it")
    activate(NAMES[0])
    activate(NAMES[3])
    check("cached: not sent again", len(calls) == 1
          and mod.caption_of(overlay.notes[0]) == "1  RU:Move the bowl", calls)

    def failing_deepl(key, texts):
        raise RuntimeError("DeepL: the key was not accepted.")

    mod.deepl_usage = lambda key: failing_deepl(key, [])
    panel._translator.check("bad")
    pump(500)
    check("rejected key: says so", panel._key_note == "DeepL: the key was not accepted.",
          panel._key_note)
    mod.deepl_translate = failing_deepl
    panel._cache.clear()
    panel._asked.clear()
    panel._translate_toggled(True)
    pump(800)
    check("error: message shown, original stays",
          panel.status_label.text() == "DeepL: the key was not accepted."
          and mod.caption_of(overlay.notes[0]) == "1  Move the bowl",
          panel.status_label.text())
    panel.set_translate(False)
    pump(100)
    check("translation off: original", mod.caption_of(overlay.notes[1]) == "2  Highlight it")

    # --- gw fallback ---
    panel._use_gw = True
    panel._draw_notes()
    check("gw fallback draws", int(rt.bd_notes.count) == 3 and "bd_draw" in callbacks())
    rt.execute("bd_draw()")                 # must not raise, with or without a window
    panel._use_gw = False
    panel._draw_notes()
    check("gw fallback off", int(rt.bd_notes.count) == 0 and "bd_draw" not in callbacks())

    panel.notes_btn.setChecked(False)
    pump(50)
    check("comments off: frames removed", drawn(panel) == 0
          and "bd_draw" not in callbacks())
    panel.notes_btn.setChecked(True)
    pump(50)
    check("comments on: frames back", drawn(panel) == 3)
    activate(NAMES[0])
    check("image without comments: no frames", drawn(panel) == 0
          and panel.notes_list.count() == 0)
    activate(NAMES[3])
    check("back to the commented image", drawn(panel) == 3)

    # --- own folder for the comment files ---
    own = os.path.join(IMAGES, "002")
    panel.set_notes_folder(own)
    pump(50)
    check("own folder: files elsewhere are ignored", drawn(panel) == 0
          and "no file" in panel.notes_count.full, panel.notes_count.full)
    with open(os.path.join(own, NAMES[3] + ".jpg Dropbox File Comments.txt"),
              "w", encoding="utf-8") as f:
        f.write("========================".join(COMMENTS.split("========================")[:2])
                + "========================\n")
    pump(2500)
    check("own folder: its file is used", drawn(panel) == 2, rt.bd_notes.count)
    # The test scene is untitled, so the per-scene store is checked by name.
    mod.save_folder("c:\\work\\a.max", own, "comments")
    check("own folder saved for the scene",
          mod.load_folder("c:\\work\\a.max", "comments") == own)
    check("another scene starts without one",
          mod.load_folder("c:\\work\\b.max", "comments") == "")

    # --- Google Drive: comments fetched by a link after a sign-in ---
    # Google itself is never called: drive_call is replaced. The listener the
    # browser is sent back to is the real one, on 127.0.0.1.
    import base64
    import hashlib
    import threading
    import urllib.error
    import urllib.parse
    import urllib.request
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def local_get(url):
        try:
            with direct.open(url, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as e:
            return e.code

    check("drive link: folder, file and open?id are read, other addresses are not",
          mod.drive_link_id("https://drive.google.com/drive/folders/1AbC_d-9?usp=sharing") == "1AbC_d-9"
          and mod.drive_link_id("https://drive.google.com/file/d/1xYz-0_k/view?usp=drive_link") == "1xYz-0_k"
          and mod.drive_link_id("https://drive.google.com/open?id=1Qq2") == "1Qq2"
          and mod.drive_link_id("https://example.com/drive/folders/1AbC") == ""
          and mod.drive_link_id("") == "")
    verifier, challenge = mod.pkce_pair()
    check("sign-in: the challenge is the hashed verifier",
          43 <= len(verifier) <= 128 and challenge == base64.urlsafe_b64encode(
              hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
          and mod.pkce_pair()[0] != verifier)
    asked = urllib.parse.parse_qs(urllib.parse.urlsplit(
        mod.drive_auth_url("ID.apps", "http://127.0.0.1:5000", "CH", "ST")).query)
    check("sign-in: the address of Google's page",
          asked == {"client_id": ["ID.apps"], "redirect_uri": ["http://127.0.0.1:5000"],
                    "response_type": ["code"], "scope": [mod.DRIVE_SCOPE],
                    "code_challenge": ["CH"], "code_challenge_method": ["S256"],
                    "state": ["ST"]}, asked)

    fetched_dir = os.path.join(OUT, "fetched_{}".format(YEAR))
    shutil.rmtree(fetched_dir, ignore_errors=True)
    os.makedirs(fetched_dir)
    os.environ["BACKDROP_DRIVE"] = fetched_dir
    client_file = os.path.join(fetched_dir, "client.json")
    with open(client_file, "w", encoding="utf-8") as f:
        json.dump({"installed": {"client_id": "ID.apps", "client_secret": "SEC",
                                 "redirect_uris": ["http://localhost"]}}, f)
    with open(os.path.join(fetched_dir, "other.json"), "w", encoding="utf-8") as f:
        f.write("{\"kind\": \"drive#commentList\"}")
    try:
        mod.read_drive_client(os.path.join(fetched_dir, "other.json"))
        refused = False
    except ValueError:
        refused = True
    check("client file: id and secret are read, another JSON is refused",
          mod.read_drive_client(client_file) == ("ID.apps", "SEC") and refused)

    waiting = mod.DriveSignIn("ID.apps")
    got = []
    waiter = threading.Thread(target=lambda: got.append(waiting.wait(10)))
    waiter.start()
    stray = local_get(waiting.redirect + "/favicon.ico")
    foreign = local_get(waiting.redirect + "/?state=other&code=EVIL")
    still_waiting = waiter.is_alive()
    answered = local_get(waiting.redirect + "/?state={}&code=CODE1".format(waiting.state))
    waiter.join(5)
    check("sign-in listener: only the answer with our state is taken",
          (stray, foreign, still_waiting, answered, got) == (404, 404, True, 200, ["CODE1"]),
          (stray, foreign, still_waiting, answered, got))
    refusing = mod.DriveSignIn("ID.apps")
    said = []

    def wait_refused():
        try:
            refusing.wait(10)
        except mod.DriveError as e:
            said.append(str(e))
    waiter = threading.Thread(target=wait_refused)
    waiter.start()
    local_get(refusing.redirect + "/?state={}&error=access_denied".format(refusing.state))
    waiter.join(5)
    check("sign-in listener: a refusal is told", said == [
        "Google: the sign-in was refused (access_denied)."], said)

    drive_calls = []
    drive_state = {"expired": False}
    image_name = NAMES[3] + ".jpg"

    def fake_drive(url, form=None, token=""):
        drive_calls.append((url, form, token))
        if url == mod.DRIVE_TOKEN_URL:
            if drive_state["expired"]:
                raise mod.DriveError("Google Drive: error 400 (invalid_grant)", 400,
                                     "invalid_grant")
            if form["grant_type"] == "authorization_code":
                return {"access_token": "AT1", "expires_in": 3599, "refresh_token": "RT"}
            return {"access_token": "AT2", "expires_in": 3599}
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parts.query)
        if parts.path.endswith("/comments"):
            file_id = parts.path.split("/")[-2]
            if file_id == "img1" and "pageToken" not in query:
                return {"nextPageToken": "c2", "comments": [
                    drive_comment("Faucet", "2026-11-23T12:37:04.769Z", [0.4, 0.1, 0.6, 0.4])]}
            if file_id == "img1":
                return {"comments": [
                    drive_comment("more left", "2026-11-23T12:36:49.824Z", [0.5, 0.4, 0.7, 0.6]),
                    drive_comment("first one", "2026-11-23T12:36:23.252Z", [0.2, 0.2, 0.3, 0.3])]}
            if file_id == "img3":
                return {"comments": [drive_comment("odd", "2026-11-23T12:00:00.000Z")]}
            return {"comments": []}
        if parts.path.endswith("/files/FOLDER1"):
            return {"id": "FOLDER1", "name": "renders", "mimeType": mod.DRIVE_FOLDER_TYPE}
        if parts.path.endswith("/files/img1"):
            return {"id": "img1", "name": image_name, "mimeType": "image/jpeg"}
        if parts.path.endswith("/files") and "pageToken" not in query:
            return {"nextPageToken": "f2", "files": [{"id": "img1", "name": image_name}]}
        if parts.path.endswith("/files"):
            return {"files": [{"id": "img2", "name": NAMES[0] + ".jpg"},
                              {"id": "img3", "name": "odd:name?.png"}]}
        raise mod.DriveError("Google Drive: nothing found", 404)

    real_drive, real_open = mod.drive_call, mod.open_link
    opened = []
    mod.drive_call, mod.open_link = fake_drive, opened.append
    folder_link = "https://drive.google.com/drive/folders/FOLDER1?usp=sharing"
    try:
        check("fetch: images of a folder over two pages, a file link is its one image",
              mod.drive_images("AT", "FOLDER1") == [("img1", image_name), ("img2", NAMES[0] + ".jpg"),
                                                    ("img3", "odd:name?.png")]
              and mod.drive_images("AT", "img1") == [("img1", image_name)])
        listing = urllib.parse.parse_qs(urllib.parse.urlsplit(drive_calls[1][0]).query)
        check("fetch: the folder is asked for its images, with the token",
              listing["q"] == ["'FOLDER1' in parents and trashed = false and "
                               "mimeType contains 'image/'"] and drive_calls[1][2] == "AT",
              listing)
        counted = mod.fetch_drive_comments("AT", folder_link)
        saved_to = mod.drive_folder(folder_link)
        saved = sorted(os.listdir(saved_to))
        check("fetch: a file per commented image, none for an image without comments",
              counted == (2, 4) and os.path.dirname(saved_to) == fetched_dir
              and saved == sorted([image_name + " Google Drive Comments.json",
                                   "odd_name_.png Google Drive Comments.json"]),
              (counted, saved))
        first_file = os.path.join(saved_to, image_name + " Google Drive Comments.json")
        check("fetch: the pages of comments are joined into one answer",
              [n["text"] for n in mod.load_comments(first_file)]
              == ["first one", "more left", "Faucet"])
        stamp = os.path.getmtime(first_file)
        time.sleep(1.1)
        mod.fetch_drive_comments("AT", folder_link)
        check("fetch: an unchanged file is not written again",
              os.path.getmtime(first_file) == stamp)
        shutil.rmtree(saved_to)

        # The panel: client file, link, sign-in in the "browser", fetch.
        panel.set_drive_link("https://example.com/folders/1")
        check("panel: another address is not taken as a link",
              panel._drive_link == "" and panel.status_label.text() == "Not a Google Drive link.")
        panel.set_drive_link(folder_link)
        check("panel: without a client file nothing is opened, the status says why",
              opened == [] and not panel._drive_busy
              and "client file" in panel.status_label.text(), panel.status_label.text())
        del drive_calls[:]
        panel.set_drive_client(client_file)
        check("panel: the client file starts the sign-in in the browser",
              mod.load_drive_client() == ("ID.apps", "SEC") and panel._drive_busy
              and len(opened) == 1 and opened[0].startswith(mod.DRIVE_AUTH_URL + "?")
              and "client_id=ID.apps" in opened[0]
              and panel.status_label.text() == "Sign in to Google in the browser...",
              (opened, panel.status_label.text()))
        sign_in = panel._drive_sign_in
        local_get(sign_in.redirect + "/?state={}&code=CODE2".format(sign_in.state))
        end = time.time() + 10
        while panel._drive_busy and time.time() < end:
            pump(50)
        token_form = drive_calls[0][1] if drive_calls else {}
        check("panel: the code is changed for tokens with the verifier of this sign-in",
              token_form == {"client_id": "ID.apps", "client_secret": "SEC", "code": "CODE2",
                             "code_verifier": sign_in.verifier,
                             "grant_type": "authorization_code",
                             "redirect_uri": sign_in.redirect}
              and mod.load_drive_refresh() == "RT" and drive_calls[1][2] == "AT1", token_form)
        check("panel: the fetched comments are on the viewport",
              drawn(panel) == 3 and not panel._drive_busy
              and panel.status_label.text() == "Google Drive: 4 comments on 2 images."
              and [n["text"] for n in panel._notes] == ["first one", "more left", "Faucet"],
              (drawn(panel), panel.status_label.text()))
        texts = [a.text() for a in panel.folder_menu().actions()]
        check("panel: the folder menu has the link, the fetch and the sign-out",
              "Google Drive link..." in texts and "Fetch the comments again" in texts
              and "Google client file (saved)..." in texts and "Sign out of Google" in texts,
              texts)
        del drive_calls[:]
        panel.fetch_drive()
        end = time.time() + 10
        while panel._drive_busy and time.time() < end:
            pump(50)
        check("panel: the next fetch signs in by itself, no browser",
              len(opened) == 1 and drive_calls[0][1] == {
                  "client_id": "ID.apps", "client_secret": "SEC",
                  "grant_type": "refresh_token", "refresh_token": "RT"}
              and drive_calls[1][2] == "AT2", drive_calls[:2])
        drive_state["expired"] = True
        panel.fetch_drive()
        end = time.time() + 10
        while panel._drive_busy and time.time() < end:
            pump(50)
        check("panel: a sign-in Google took back is forgotten and told",
              mod.load_drive_refresh() == ""
              and panel.status_label.text() == "Google: signed out. Fetch again to sign in.",
              panel.status_label.text())
        drive_state["expired"] = False
        mod.save_folder("c:\\work\\a.max", folder_link, "drive")
        check("panel: the link is kept per scene",
              mod.load_folder("c:\\work\\a.max", "drive") == folder_link
              and mod.load_folder("c:\\work\\b.max", "drive") == "")

        # Both a downloaded Dropbox file (2 comments) and the fetched Drive
        # file (3) are there for the shown image: the source is a choice.
        mod.save_drive_refresh("RT")
        after_fetch = (panel._source, drawn(panel))
        panel.set_source("dropbox")
        pump(50)
        dropbox_only = (drawn(panel), os.path.basename(panel._notes_file[0]))
        del drive_calls[:]
        panel.set_source("drive")
        end = time.time() + 10
        while panel._drive_busy and time.time() < end:
            pump(50)
        drive_only = (drawn(panel), os.path.basename(panel._notes_file[0]))
        check("source: a fetch shows Drive, the menu goes to the Dropbox files and back",
              after_fetch == ("drive", 3)
              and dropbox_only == (2, image_name + " Dropbox File Comments.txt")
              and drive_only == (3, image_name + " Google Drive Comments.json"),
              (after_fetch, dropbox_only, drive_only))
        check("source: going to Drive fetches its comments anew",
              len(drive_calls) > 1 and drive_calls[0][0] == mod.DRIVE_TOKEN_URL, drive_calls[:1])
        ticked = [a.text() for a in panel.folder_menu().actions() if a.isChecked()]
        check("source: the menu shows the choice", ticked == ["Comments from: Google Drive"],
              ticked)
        mod.save_folder("c:\\work\\a.max", "drive", "source")
        check("source: kept per scene", mod.load_folder("c:\\work\\a.max", "source") == "drive"
              and mod.load_folder("c:\\work\\b.max", "source") == "")
        panel.drive_sign_out()
        pump(50)
        check("source: signing out of Google goes back to the Dropbox files",
              panel._source == "dropbox" and drawn(panel) == 2
              and mod.load_drive_refresh() == ""
              and panel.status_label.text() == "Signed out of Google.",
              (panel._source, drawn(panel)))
        panel.set_source("drive", fetch=False)
        pump(50)
        panel.set_drive_link("")
        pump(50)
        check("panel: without the link the downloaded files are shown again",
              drawn(panel) == 2 and panel._drive_link == "" and panel._source == "dropbox",
              (drawn(panel), panel._source))
        del opened[:]
        guide = [a for a in panel.folder_menu().actions()
                 if a.text() == "How to connect Google Drive..."]
        if guide:
            guide[0].trigger()
        check("panel: the folder menu opens the guide", opened == [mod.GUIDE_URL], opened)
    finally:
        mod.drive_call, mod.open_link = real_drive, real_open

    # --- scenes without Scene Manager: Batch Render view, then the camera name ---
    viewed = mod.view_camera()
    camera_was = str(viewed.name)
    check("names: the render output comes first, the camera name last",
          mod.image_keys(viewed) == [("output", NAMES[3]), ("camera", camera_was)],
          mod.image_keys(viewed))
    count = len(panel._images)
    activate(NAMES[2])
    check("names: an image found by the render output says nothing more",
          panel._match_source == "output"
          and panel.status_label.text() == "{} images".format(count),
          (panel._match_source, panel.status_label.text()))
    activate("")
    check("names: no output and a camera named like no image: told what was tried",
          panel._matched is None and panel.status_label.text()
          == "No image named like the camera name '{}'.".format(camera_was),
          panel.status_label.text())
    batch_view = rt.batchRenderMgr.CreateView(viewed)
    batch_view.outputFilename = "F:\\Renderout\\EXR\\" + NAMES[1] + ".exr"
    elsewhere = rt.Freecamera(name="Elsewhere")
    rt.batchRenderMgr.CreateView(elsewhere).outputFilename = "F:\\Renderout\\" + NAMES[4] + ".exr"
    rt.batchRenderMgr.CreateView(rt.undefined).outputFilename = "F:\\Renderout\\" + NAMES[0] + ".exr"
    pump(900)
    check("names: the Batch Render view of the viewed camera gives the image",
          mod.batch_names(viewed) == [NAMES[1]] and panel._match_source == "batch"
          and background() == NAMES[1] + ".jpg" and panel.setup_label.full == NAMES[1]
          and panel.status_label.text()
          == "{} images, found by the Batch Render view".format(count),
          (mod.batch_names(viewed), panel._match_source, background(),
           panel.status_label.text()))
    batch_view.outputFilename = "F:\\Renderout\\EXR\\Unknown_view.exr"
    viewed.name = NAMES[2]
    pump(900)
    check("names: with no image for the view, the camera name gives it",
          panel._match_source == "camera" and background() == NAMES[2] + ".jpg"
          and panel.status_label.text()
          == "{} images, found by the camera name".format(count),
          (panel._match_source, background(), panel.status_label.text()))
    activate(NAMES[3])
    check("names: a render output with an image wins over the camera name",
          panel._match_source == "output" and background() == NAMES[3] + ".jpg",
          (panel._match_source, background()))
    activate("SK900-00_Nothing_Angle09")
    check("names: a render output without an image falls through to the camera",
          panel._match_source == "camera" and background() == NAMES[2] + ".jpg",
          (panel._match_source, background()))

    # A click on a preview goes to the camera of that image.
    def click(name):
        for row in range(panel.list.count()):
            item = panel.list.item(row)
            if os.path.basename(item.data(mod.ROLE_PATH)) == name + ".jpg":
                panel._item_clicked(item)
        pump(900)

    def looking_through():
        return str(mod.view_camera().name)

    click(NAMES[4])
    check("click: the camera with a Batch Render view of that name is put in the viewport",
          looking_through() == "Elsewhere" and background() == NAMES[4] + ".jpg"
          and panel._match_source == "batch" and panel.setup_label.full == NAMES[4],
          (looking_through(), background(), panel._match_source))
    named = rt.Freecamera(name=NAMES[0])
    click(NAMES[0])
    check("click: a camera named like the image is put in the viewport",
          looking_through() == NAMES[0] and background() == NAMES[0] + ".jpg"
          and panel._match_source == "camera", (looking_through(), background()))
    click(NAMES[1])
    check("click: an image no camera is named after is shown, the camera stays",
          looking_through() == NAMES[0] and background() == NAMES[1] + ".jpg",
          (looking_through(), background()))
    check("click: a camera is found by the exact name before a name that starts alike",
          str(mod.camera_for_image(NAMES[2]).name) == NAMES[2]
          and mod.camera_for_image("Nothing_like_a_camera") is None)
    rt.viewport.setCamera(viewed)
    rt.delete(named)
    viewed.name = camera_was
    batch_view.outputFilename = ""
    rt.delete(elsewhere)
    pump(900)
    check("names: nothing fits: every name tried is listed",
          panel._matched is None and panel.status_label.text()
          == "No image named like the render output 'SK900-00_Nothing_Angle09' "
             "or the camera name '{}'.".format(camera_was), panel.status_label.text())
    activate(NAMES[3])
    # --- folder menu with long paths ---
    deep = "D:\\Studio Dropbox\\Client_219_Kitchen_Sinks_Collection\\04_JPG\\" \
           "SK200-32_SK100-30_FC-2840BB_FC-2820SS_Scene_3"
    kept = (panel._folder, panel._notes_folder)
    panel._folder, panel._notes_folder = deep, deep + "\\Comments"
    menu = panel.folder_menu()
    lines = [a for a in menu.actions() if not a.isEnabled() and not a.isSeparator()]
    check("folder menu stays narrow with long paths", menu.sizeHint().width() <= 380,
          menu.sizeHint().width())
    check("folder menu: whole path in the tooltip",
          [a.toolTip() for a in lines] == [deep, deep + "\\Comments", "no link"]
          and all("…" in a.text() for a in lines[:2]), [a.text() for a in lines])
    panel._folder, panel._notes_folder = kept
    menu.deleteLater()

    panel.set_notes_folder(os.path.join(IMAGES, "missing"))
    pump(50)
    check("missing folder: says so", "not found" in panel.notes_count.full,
          panel.notes_count.full)
    panel.set_notes_folder("")
    pump(50)
    check("cleared: back to the automatic lookup", drawn(panel) == 3,
          rt.bd_notes.count)

    # --- folder is remembered ---
    check("untitled scene: the folder is not stored anywhere", mod.scene_path() == ""
          and mod.load_folder("") == "" and mod.last_folder() == os.path.normpath(IMAGES),
          mod.last_folder())

    # --- themes + screenshot ---
    for mode in ("light", "dark"):
        panel._theme_mode = mode
        panel.apply_theme()
        pump(50)
        pixmap = QtGui.QPixmap(panel.size())
        panel.render(pixmap, QtCore.QPoint(0, 0))
        pixmap.save(os.path.join(OUT, "panel_{}_{}.png".format(YEAR, mode)))
    check("theme switch keeps the list", panel.list.count() == len(NAMES) + 1)

    # --- another AD Tools panel started while this one is open ---
    # Layer Manager defines its own make_icon / ICONS / T in __main__; that
    # used to replace Backdrop's and break the next list refresh.
    layer_manager_src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(SRC))),
                                     "LayerManager", "src", "layer_manager.py")
    if os.path.isfile(layer_manager_src):
        os.environ["LAYER_MANAGER_SETTINGS"] = "LayerManagerTests"
        rt.python.ExecuteFile(layer_manager_src)
        pump(300)
        other = getattr(sys.modules.get("adtools_layer_manager"), "layer_manager", None)
        check("layer manager opened next to it", other is not None)
        try:
            panel._fill_list()
            activate(NAMES[1])
            check("still works with Layer Manager open",
                  background() == NAMES[1] + ".jpg" and panel.list.count() == len(NAMES) + 1,
                  background())
        except Exception:
            check("still works with Layer Manager open", False, traceback.format_exc())
        if other is not None:
            other.close()
            pump(100)
    else:
        log("skip   Layer Manager not found at", layer_manager_src)

    # --- frames and the image only on a viewport that looks through a camera ---
    activate(NAMES[1])
    check("camera view: the image is on it", shown_on() == [1], shown_on())
    rt.execute("viewport.setType #view_persp_user")
    rt.delete(start_camera)
    rt.execute("viewport.setLayout #layout_4")
    check("no camera view: nowhere to draw", mod.camera_viewport() is None,
          mod.camera_viewport())
    overlay.follow_viewport()
    check("no camera view: overlay hidden", not overlay.isVisible())
    pump(900)
    check("no camera view: no image anywhere", shown_on() == [], shown_on())
    shot = rt.Freecamera(name="Shot_camera")
    rt.execute("viewport.activeViewport = 2")
    rt.viewport.setCamera(shot)
    check("camera view active: frames go there", mod.camera_viewport() == 2,
          mod.camera_viewport())
    rt.execute("viewport.activeViewport = 1")       # the user clicks into the top view
    check("another view active: frames stay on the camera view",
          str(rt.viewport.getType()) == "view_top" and mod.camera_viewport() == 2,
          (str(rt.viewport.getType()), mod.camera_viewport()))
    pump(900)
    check("a camera view appeared: the image goes there, not on the active view",
          shown_on() == [2] and int(rt.viewport.activeViewport) == 1,
          (shown_on(), int(rt.viewport.activeViewport)))
    activate(NAMES[2])
    check("another setup from the top view: still only the camera view",
          shown_on() == [2] and background() == NAMES[2] + ".jpg"
          and int(rt.viewport.activeViewport) == 1, (shown_on(), background()))
    panel.show_btn.setChecked(False)
    pump(50)
    check("hide reaches the camera view from another one", shown_on() == [], shown_on())
    panel.show_btn.setChecked(True)
    pump(50)
    check("show from another view puts it back", shown_on() == [2], shown_on())
    rt.execute("viewport.activeViewport = 3")
    rt.viewport.setCamera(shot)                     # a second camera view, and active
    check("the active camera view wins", mod.camera_viewport() == 3, mod.camera_viewport())
    pump(900)
    check("the image moves to the active camera view", shown_on() == [3], shown_on())
    rt.execute("viewport.setLayout #layout_1")
    rt.delete(shot)

    # --- folders belong to the scene they were chosen in ---
    scenes = os.path.join(IMAGES, "002")
    first = os.path.join(scenes, "scene_a.max")
    second = os.path.join(scenes, "scene_b.max")
    images = os.path.normpath(IMAGES)
    panel.set_notes_folder(scenes)
    check("save callback registered", "bd_saved" in str(rt.execute(
        "(local s = stringStream \"\"; callbacks.show id:#adtools_backdrop_saved to:s; s as string)")))
    rt.saveMaxFile(first, quiet=True)       # the untitled scene gets a name
    pump(900)
    check("save as: the scene keeps its folders", panel._folder == images
          and panel.list.count() > 0, panel._folder)
    check("save as: they are stored for the new name",
          mod.stored_folder(mod.scene_path()) == images
          and mod.stored_folder(mod.scene_path(), "comments") == os.path.normpath(scenes),
          mod.stored_folder(mod.scene_path()))

    # --- setups of Scene Manager 2 in the scene file: a click takes camera and frame ---
    import base64
    key14 = rt.Freecamera(name="Angle_Key14_Top")
    key05 = rt.Freecamera(name="Angle_Key05_Top")
    check("pulze: a scene file without setups has none", mod.pulze_setups() == [],
          mod.pulze_setups())

    faucet_a = rt.LayerManager.newLayerFromName("Faucet_A")
    faucet_b = rt.LayerManager.newLayerFromName("Faucet_B")

    size_was = (int(rt.renderWidth), int(rt.renderHeight))
    out_file = "D:/out/04_EXR/Scene_3/" + NAMES[4] + ".exr"

    def setup(name, camera, handle, frame, frames_on=True, kind=0, layers=None, layers_on=True,
              output=None, size=None):
        return {"version": 7, "scenename": {"text": name},
                "output_Common": {"enabled": output is not None, "projectPath": "D:/out/",
                                  "finalPath": output, "exist": True, "preset": []},
                "resolution": {"enabled": size is not None,
                               "width": str(size[0]) if size else "640",
                               "height": str(size[1]) if size else "480",
                               "ratio": "1.333", "locked": True},
                "camera": {"enabled": camera is not None, "name": camera or "None",
                           "handle": handle, "locked": False, "props": []},
                "frames": {"enabled": frames_on, "type": kind, "single": str(frame),
                           "start": 0, "end": 100, "nth": 1, "list": "1,3,5-12"},
                "layers": {"enabled": layers_on, "set": [
                    {"name": layer, "handle": layer,
                     "props": [{"name": "on", "class": "BooleanClass", "value": on}]}
                    for layer, on in layers or []]}}

    def layers_shown():
        return bool(faucet_a.on), bool(faucet_b.on)

    saved = [setup(NAMES[0], "Angle_Key14_Top", int(key14.inode.handle), 14,
                   layers=[("Faucet_A", True), ("Faucet_B", False)]),
             setup(NAMES[1], "Angle_Key05_Top", 999999, 5,          # a handle of nothing
                   layers=[("Faucet_A", False), ("Faucet_B", True), ("Gone_layer", True)]),
             setup(NAMES[2], None, "None", 23,
                   layers=[("Faucet_A", True), ("Faucet_B", True)], layers_on=False),
             setup(NAMES[3], "Angle_Key14_Top", int(key14.inode.handle), 30, kind=1),
             # the same camera and frame as the first, other layers
             setup(NAMES[4], "Angle_Key14_Top", int(key14.inode.handle), 14,
                   layers=[("Faucet_A", False), ("Faucet_B", True)],
                   output=out_file, size=(3500, 2626))]
    wrote = rt.CustomFileStream.writeStream(
        first, mod.PULZE_STREAM, base64.b64encode(json.dumps(saved).encode("utf-8")).decode("ascii"))
    read = mod.pulze_setups()
    plain = {"output": "", "size": None}
    check("pulze: the setups of the scene file are read", wrote and read == [
        dict(plain, name=NAMES[0], camera="Angle_Key14_Top", handle=int(key14.inode.handle),
             frame=14, layers=[("Faucet_A", True), ("Faucet_B", False)]),
        dict(plain, name=NAMES[1], camera="Angle_Key05_Top", handle=999999, frame=5,
             layers=[("Faucet_A", False), ("Faucet_B", True), ("Gone_layer", True)]),
        dict(plain, name=NAMES[2], camera="", handle=None, frame=23, layers=[]),
        dict(plain, name=NAMES[3], camera="Angle_Key14_Top", handle=int(key14.inode.handle),
             frame=None, layers=[]),
        dict(name=NAMES[4], camera="Angle_Key14_Top", handle=int(key14.inode.handle),
             frame=14, layers=[("Faucet_A", False), ("Faucet_B", True)],
             output=out_file, size=(3500, 2626))], (wrote, read))
    rt.sliderTime = 0
    activate(NAMES[3])                          # the setup active in Scene Manager
    click(NAMES[0])
    check("pulze: a click takes the camera, the frame and the layers of the setup",
          looking_through() == "Angle_Key14_Top" and int(rt.sliderTime.frame) == 14
          and layers_shown() == (True, False)
          and background() == NAMES[0] + ".jpg" and panel.status_label.text()
          == "Camera, frame 14 and layers of the saved Scene Manager setup '{}'; the rest "
             "of it is not applied.".format(NAMES[0]),
          (looking_through(), int(rt.sliderTime.frame), layers_shown(), background(),
           panel.status_label.text()))
    click(NAMES[4])
    check("pulze: the same camera and frame with other layers: the layers change",
          looking_through() == "Angle_Key14_Top" and int(rt.sliderTime.frame) == 14
          and layers_shown() == (False, True) and panel.setup_label.full == NAMES[4]
          and background() == NAMES[4] + ".jpg",
          (looking_through(), layers_shown(), panel.setup_label.full, background()))
    check("pulze: the click sets the render output and the resolution of the setup",
          str(rt.rendOutputFilename) == out_file.replace("/", "\\")
          and mod.set_render_output(out_file, (3500, 2626)) == []
          and (int(rt.renderWidth), int(rt.renderHeight)) == (3500, 2626)
          and panel.status_label.text()
          == "Camera, frame 14, layers, render output and resolution of the saved Scene "
             "Manager setup '{}'; the rest of it is not applied.".format(NAMES[4]),
          (str(rt.rendOutputFilename), int(rt.renderWidth), int(rt.renderHeight),
           panel.status_label.text()))
    pump(1500)
    check("pulze: the render output of the picked setup keeps it the active one",
          panel.setup_label.full == NAMES[4] and background() == NAMES[4] + ".jpg",
          (panel.setup_label.full, background()))
    activate(NAMES[3])
    click(NAMES[0])
    check("pulze: a setup that sets no output or resolution leaves them alone",
          mod.setup_key() == NAMES[3]
          and (int(rt.renderWidth), int(rt.renderHeight)) == (3500, 2626),
          (mod.setup_key(), int(rt.renderWidth), int(rt.renderHeight)))
    pump(1500)
    check("pulze: the picked setup is the active one, not the render output's",
          mod.setup_key() == NAMES[3] and panel.setup_label.full == NAMES[0]
          and panel._match_source == "setup"
          and os.path.basename(panel._matched) == NAMES[0] + ".jpg",
          (mod.setup_key(), panel.setup_label.full, panel._match_source, panel._matched))
    rt.viewport.setCamera(key05)                # the camera changed elsewhere
    pump(900)
    check("pulze: another camera in the viewport gives the render output its say back",
          panel.setup_label.full == NAMES[3] and panel._match_source == "output"
          and background() == NAMES[3] + ".jpg",
          (panel.setup_label.full, panel._match_source, background()))
    click(NAMES[0])
    activate(NAMES[2])                          # Scene Manager activated a setup
    check("pulze: a setup activated in Scene Manager replaces the picked one",
          panel.setup_label.full == NAMES[2] and background() == NAMES[2] + ".jpg",
          (panel.setup_label.full, background()))
    activate(NAMES[3])
    click(NAMES[1])
    check("pulze: a camera whose handle is gone is found by its name",
          looking_through() == "Angle_Key05_Top" and int(rt.sliderTime.frame) == 5,
          (looking_through(), int(rt.sliderTime.frame)))
    check("pulze: a layer the scene no longer has is skipped, the others are set",
          layers_shown() == (False, True), layers_shown())
    click(NAMES[2])
    check("pulze: a setup without a camera and with layers off moves the frame only",
          looking_through() == "Angle_Key05_Top" and int(rt.sliderTime.frame) == 23
          and layers_shown() == (False, True)
          and panel.status_label.text().startswith("Frame 23 of the saved"),
          (looking_through(), int(rt.sliderTime.frame), layers_shown(),
           panel.status_label.text()))
    click(NAMES[3])
    check("pulze: a setup that renders a range leaves the time slider alone",
          looking_through() == "Angle_Key14_Top" and int(rt.sliderTime.frame) == 23
          and panel.status_label.text().startswith("Camera of the saved"),
          (looking_through(), int(rt.sliderTime.frame), panel.status_label.text()))
    rt.sliderTime = 0
    rt.renderWidth, rt.renderHeight = size_was
    rt.delete(key14)
    rt.delete(key05)
    rt.resetMaxFile(rt.name("noPrompt"))    # File > New
    pump(900)
    check("new scene starts with no folders", panel._folder == "" and panel._notes_folder == ""
          and panel.list.count() == 0, (panel._folder, panel.list.count()))
    check("new scene: says to choose a folder", "Choose the folder" in panel.status_label.text(),
          panel.status_label.text())
    rt.saveMaxFile(second, quiet=True)      # an empty scene saved: nothing to carry
    pump(900)
    check("scene saved without folders stays without", panel._folder == ""
          and mod.load_folder(mod.scene_path()) == "", panel._folder)
    rt.loadMaxFile(first, quiet=True)
    pump(900)
    check("opening a scene brings its own folders back", panel._folder == images
          and panel._notes_folder == os.path.normpath(scenes)
          and panel.list.count() > 0, (panel._folder, panel._notes_folder))
    rt.loadMaxFile(second, quiet=True)
    pump(900)
    check("opening the other scene: still none", panel._folder == "" and panel.list.count() == 0,
          panel._folder)
    clear = [a for a in panel.folder_menu().actions() if a.text().startswith("Clear the folders")]
    check("nothing to clear in a scene without folders", len(clear) == 1 and not clear[0].isEnabled())

    # --- clearing the folders of a scene ---
    rt.loadMaxFile(first, quiet=True)
    pump(900)
    clear = [a for a in panel.folder_menu().actions() if a.text().startswith("Clear the folders")]
    check("clear is offered when the scene has folders", clear[0].isEnabled())
    clear[0].trigger()
    pump(200)
    check("clear: both folders gone, list and viewport empty",
          panel._folder == "" and panel._notes_folder == "" and panel.list.count() == 0
          and panel.notes_list.count() == 0 and not shown() and drawn(panel) == 0,
          (panel._folder, panel._notes_folder))
    check("clear is remembered for the scene", mod.stored_folder(mod.scene_path()) == ""
          and mod.stored_folder(mod.scene_path(), "comments") == "")
    rt.loadMaxFile(second, quiet=True)
    pump(900)
    rt.loadMaxFile(first, quiet=True)
    pump(900)
    check("cleared scene stays empty when opened again", panel._folder == ""
          and panel._notes_folder == "", (panel._folder, panel._notes_folder))
    rt.resetMaxFile(rt.name("noPrompt"))
    pump(300)

    panel.close()
    pump(50)
    check("closing removes the redraw callback", "bd_draw" not in callbacks())
    check("closing removes the save callback", "bd_saved" not in str(rt.execute(
        "(local s = stringStream \"\"; callbacks.show id:#adtools_backdrop_saved to:s; s as string)")))
    rt.execute("viewport.DispBkgImage = false")


try:
    run()
except Exception:
    failed.append("exception")
    log(traceback.format_exc())
log("RESULT: PASSED" if not failed else "RESULT: FAILED ({})".format(", ".join(failed)))
report.close()
