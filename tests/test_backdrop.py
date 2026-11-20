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


def activate(setup, folder="D:\\out\\04_EXR\\Scene_3", ext=".exr"):
    """What activating a Scene Manager setup does to Render Output - Common."""
    rt.rendOutputFilename = os.path.join(folder, setup + ext) if setup else ""
    pump(900)


def run():
    import __main__
    rt.resetMaxFile(rt.name("noPrompt"))
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
          [a.toolTip() for a in lines] == [deep, deep + "\\Comments"]
          and all("…" in a.text() for a in lines), [a.text() for a in lines])
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
