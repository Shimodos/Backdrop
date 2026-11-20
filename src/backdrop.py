"""
Backdrop for 3ds Max  (a0.003)

Floating Qt panel that puts a finished render behind the active viewport, so
client corrections can be done right on top of the approved picture:
  - pick the folder with the delivered images (remembered per scene file)
  - the image is chosen by name: the file name of the render output
    (Render Setup > Common > Render Output, the field Pulze Scene Manager
    "Render Output - Common" writes to when a setup is activated) is matched
    against the image names in the folder
  - follows the scene live: activating another setup swaps the picture
  - any image can also be shown by hand with a click in the list
  - follows the 3ds Max UI theme (dark / light)

3ds Max has no callback for a render output change, so a cheap poll of the
path covers it.

Works with PySide2 (3ds Max 2021 - 2024) and PySide6 (3ds Max 2025+).
"""

# python.ExecuteFile runs every script in the one shared __main__ namespace.
# Another panel started later (Layer Manager has its own make_icon, ICONS, T)
# would replace this panel's functions under it. So when run that way this
# file loads itself again as a module of its own and hands __main__ back as
# it found it -- see the end of the file.
_SHARED = dict(globals()) if __name__ == "__main__" else None
MODULE_NAME = "adtools_backdrop"

import datetime
import hashlib
import json
import os
import re
import threading

try:                                     # 3ds Max 2025+
    from PySide6 import QtCore, QtGui, QtWidgets, QtSvg
except ImportError:                         # 3ds Max 2021 - 2024
    from PySide2 import QtCore, QtGui, QtWidgets, QtSvg

import qtmax
from pymxs import runtime as rt

VERSION = "a0.003"
OBJECT_NAME = "ADToolsBackdrop"
OVERLAY_NAME = "ADToolsBackdropOverlay"
TEXT_SIZES = (("Small", 13), ("Medium", 18), ("Large", 24), ("Extra large", 32))
POLL_INTERVAL_MS = 400
IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".tga")
COMMENTS_SUFFIX = " Dropbox File Comments"  # "<image name> Dropbox File Comments.txt"
COMMENTS_EVERY = 5                          # polls between looks for a comments file

Qt = QtCore.Qt


# ---------------------------------------------------------------------------
# Themes (shared look of the AD Tools panels, see Layer Manager)
# ---------------------------------------------------------------------------
DARK = {
    "window": "#1f2125", "titlebar": "#17181b", "surface": "#262930",
    "hover": "#2f333b", "border": "#363a42", "text": "#e7e9ec",
    "text_dim": "#a3a9b3", "text_faint": "#6c727d", "icon_off": "#4d535d",
    "accent": "#2cc6ea", "accent_hover": "#55d4f2", "accent_pressed": "#1fa7c8",
    "accent_text": "#04222b", "select": "#1d4250", "pill": "#343841",
    "button": "#2d3138", "button_hover": "#383d46", "frozen": "#6cb6ff",
    "warn": "#f5a524", "danger": "#e5484d", "scroll": "#444a54", "ok": "#3ecf8e",
}
LIGHT = {
    "window": "#f3f4f6", "titlebar": "#e6e8eb", "surface": "#ffffff",
    "hover": "#eef1f4", "border": "#d8dbe0", "text": "#1d2126",
    "text_dim": "#555c68", "text_faint": "#959ca7", "icon_off": "#c2c7ce",
    "accent": "#0aa3c6", "accent_hover": "#0cb3d9", "accent_pressed": "#0889a6",
    "accent_text": "#ffffff", "select": "#d3f1f8", "pill": "#eaecef",
    "button": "#ffffff", "button_hover": "#eef1f4", "frozen": "#2f7fe0",
    "warn": "#b86e00", "danger": "#d13438", "scroll": "#c5cad1", "ok": "#1f9d63",
}
T = dict(DARK)                              # active theme, see apply_theme()


def max_is_dark():
    """True when the 3ds Max UI uses a dark colour scheme."""
    try:
        c = rt.colorMan.getColor(rt.name("background"))
        return (c.x + c.y + c.z) / 3.0 < 0.5
    except Exception:
        return True


def themed(css):
    """Replace @token@ placeholders with colours of the active theme."""
    for key, value in T.items():
        css = css.replace("@" + key + "@", value)
    return css


STYLESHEET = """
QWidget#root { background-color: @window@; }
QLabel { color: @text@; font: 12px "Segoe UI"; background: transparent; }
QLabel#status { color: @text_faint@; font: 11px "Segoe UI"; }
QLabel#caption { color: @text_faint@; font: 11px "Segoe UI"; }
QLabel#value { color: @text@; font: 600 12px "Segoe UI"; }
QFrame#card {
    background-color: @surface@; border: 1px solid @border@; border-radius: 8px;
}
QLineEdit {
    background-color: @surface@; color: @text@;
    border: 1px solid @border@; border-radius: 7px;
    padding: 5px 8px; min-height: 18px; font: 12px "Segoe UI";
    selection-background-color: @accent@; selection-color: @accent_text@;
}
QLineEdit:hover { border: 1px solid @text_faint@; }
QLineEdit:focus { border: 1px solid @accent@; }
QListWidget {
    background-color: @surface@; border: 1px solid @border@;
    border-radius: 8px; padding: 3px; color: @text@;
    font: 12px "Segoe UI"; outline: none;
}
QListWidget::item { border: none; border-radius: 5px; padding: 5px 6px; }
QListWidget::item:hover { background-color: @hover@; }
QListWidget::item:selected { background-color: @select@; color: @text@; }
QListWidget#thumbs, QListWidget#notes { background: transparent; border: none; padding: 0; }
QListWidget#thumbs::item, QListWidget#notes::item { padding: 0; background: transparent; }
QLabel#setup { color: @text@; font: 600 13px "Segoe UI"; }
QLabel#heading { color: @text@; font: 600 12px "Segoe UI"; }
QPushButton#flat {
    border: none; background: transparent; border-radius: 6px; padding: 0;
    min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
}
QPushButton#flat:hover { background-color: @hover@; border: none; }
QPushButton#seg {
    background-color: @pill@; color: @text_dim@; border: 2px solid @pill@;
    border-radius: 0; padding: 3px 10px; font: 11px "Segoe UI";
}
QPushButton#seg:hover { color: @text@; border: 2px solid @pill@; }
QPushButton#seg:checked {
    background-color: @accent@; color: @accent_text@; border-radius: 6px;
    font: 600 11px "Segoe UI";
}
QPushButton#seg[side="left"] { border-top-left-radius: 7px; border-bottom-left-radius: 7px; }
QPushButton#seg[side="right"] { border-top-right-radius: 7px; border-bottom-right-radius: 7px; }
QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: @pill@; }
QSlider::sub-page:horizontal { height: 4px; border-radius: 2px; background: @accent@; }
QSlider::handle:horizontal {
    width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; background: @text@;
}
QListWidget::indicator {
    width: 12px; height: 12px; border-radius: 4px;
    border: 1px solid @text_faint@; background-color: @surface@;
}
QListWidget::indicator:checked { border: 1px solid @accent@; background-color: @accent@; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @scroll@; border-radius: 3px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: @text_faint@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QPushButton {
    background-color: @button@; color: @text@;
    border: 1px solid @border@; border-radius: 7px;
    padding: 6px 12px; font: 12px "Segoe UI";
}
QPushButton:hover { background-color: @button_hover@; border: 1px solid @text_faint@; }
QPushButton:pressed { background-color: @hover@; }
QPushButton#accent:checked {
    background-color: @accent@; border: 1px solid @accent@;
    color: @accent_text@; font: 600 12px "Segoe UI";
}
QPushButton#accent:checked:hover { background-color: @accent_hover@; border: 1px solid @accent_hover@; }
QPushButton#tool { padding: 0; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; }
QPushButton#tool:checked { border: 1px solid @accent@; color: @accent@; font: 600 11px "Segoe UI"; }
"""

MENU_STYLE = """
QMenu {
    background-color: @surface@; color: @text@;
    border: 1px solid @border@; border-radius: 8px;
    padding: 5px; font: 12px "Segoe UI";
}
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 5px; }
QMenu::item:selected { background-color: @select@; color: @text@; }
QMenu::item:checked { color: @accent@; }
QMenu::indicator { width: 0; }
QMenu::separator { height: 1px; background: @border@; margin: 5px 6px; }
"""

TITLEBAR_STYLE = """
QWidget#titlebar { background-color: @titlebar@; }
QLabel#title { color: @text@; font: 600 12px "Segoe UI"; background: transparent; }
QLabel#version { color: @text_faint@; font: 11px "Segoe UI"; background: transparent; }
QPushButton { border: none; background: transparent; border-radius: 5px; }
QPushButton:hover { background-color: @hover@; }
QPushButton#close:hover { background-color: @danger@; }
"""


# ---------------------------------------------------------------------------
# Vector icons (24x24 stroke icons, drawn with QtSvg so they stay sharp)
# ---------------------------------------------------------------------------
ICONS = {
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/>'
             '<circle cx="9" cy="10" r="1.600"/><path d="M21 16l-5-5-8 9"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5'
              'a2 2 0 0 1-2-2V7z"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/>'
           '<circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M3 3l18 18"/>'
               '<path d="M10.600 5.100c.500-.100.900-.100 1.400-.100 6.400 0 10 7 10 7s-1.100 2.200-3.200 4.100"/>'
               '<path d="M6.600 6.600C3.600 8.500 2 12 2 12s3.600 7 10 7c1.700 0 3.200-.500 4.500-1.200"/>'
               '<path d="M9.900 9.900a3 3 0 0 0 4.200 4.200"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1"/>'
            '<path d="M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1"/>',
    "check": '<path d="M5 12.500l4.500 4.500L19 7.500"/>',
    "sliders": '<path d="M4 6h8M16 6h4M4 12h2M10 12h10M4 18h10M18 18h2"/>'
               '<circle cx="14" cy="6" r="2"/><circle cx="8" cy="12" r="2"/>'
               '<circle cx="16" cy="18" r="2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.300-4.300L4 8.500"/><path d="M4 4v4.500h4.500"/>'
               '<path d="M4 13a8 8 0 0 0 14.300 4.300L20 15.500"/><path d="M20 20v-4.500h-4.500"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2'
           'M4.900 4.900l1.400 1.400M17.700 17.700l1.400 1.400M19.100 4.900l-1.400 1.400'
           'M6.300 17.700l-1.400 1.400"/>',
    "moon": '<path d="M21 12.800A9 9 0 1 1 11.200 3a7 7 0 0 0 9.800 9.800z"/>',
}
SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)
_renderers = {}


def svg_renderer(name, color, width=2.0):
    key = (name, color, width)
    renderer = _renderers.get(key)
    if renderer is None:
        data = SVG_TEMPLATE.format(color=color, width=width, body=ICONS[name])
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(data.encode("utf-8")))
        _renderers[key] = renderer
    return renderer


def make_icon(name, color, size=16):
    """QIcon for buttons; rendered oversized so it stays crisp on HiDPI."""
    scale = 4
    pixmap = QtGui.QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    try:
        svg_renderer(name, color).render(
            painter, QtCore.QRectF(0, 0, size * scale, size * scale))
    finally:
        painter.end()
    return QtGui.QIcon(pixmap)


# ---------------------------------------------------------------------------
# Matching a setup to an image, and the viewport background itself
# ---------------------------------------------------------------------------
def _norm(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def setup_key():
    """Name of the active setup: the render output file name without folder
    and extension ('' when no output file is set)."""
    try:
        path = rt.rendOutputFilename or ""
    except Exception:
        path = ""
    return os.path.splitext(os.path.basename(str(path).replace("/", "\\")))[0]


def list_images(folder):
    """[(name without extension, full path)] of the images right in the folder."""
    images = []
    try:
        names = sorted(os.listdir(folder), key=lambda n: n.lower())
    except OSError:
        return images
    for name in names:
        stem, ext = os.path.splitext(name)
        path = os.path.join(folder, name)
        if ext.lower() in IMAGE_TYPES and os.path.isfile(path):
            images.append((stem, path))
    return images


def match_image(key, images):
    """Path of the image that belongs to the setup, or None.

    An exact name match wins. Otherwise the longest name that starts the key
    or is started by it, which covers suffixes on either side (a frame number
    or a pass name after the setup name)."""
    wanted = _norm(key)
    if not wanted:
        return None
    best = None
    for stem, path in images:
        name = _norm(stem)
        if name == wanted:
            return path
        if name and (wanted.startswith(name) or name.startswith(wanted)):
            if best is None or len(name) > best[0]:
                best = (len(name), path)
    return best[1] if best else None


def show_background(path):
    """Put the image behind the active viewport, fitted to the render frame.

    backgroundImageFileName, setBkgImageAspect #output and
    InvalidateAllBackgrounds are the MAXScript 'Viewport Background Images'
    calls; viewport.DispBkgImage switches the display for the active view."""
    rt.backgroundImageFileName = path
    rt.setBkgImageAspect(rt.name("output"))
    rt.setBkgImageAnimate(False)
    rt.execute("viewport.DispBkgImage = true")
    rt.InvalidateAllBackgrounds()
    rt.completeRedraw()


def hide_background():
    rt.execute("viewport.DispBkgImage = false")
    rt.InvalidateAllBackgrounds()
    rt.completeRedraw()


# ---------------------------------------------------------------------------
# Dropbox comments: the file "Download comments" saves, drawn over the viewport
# ---------------------------------------------------------------------------
def comment_folders(image_folder, override=""):
    """Where a downloaded comments file is looked for: the folder chosen for
    comments, else next to the images and in the browser's Downloads."""
    if override:
        return [override]
    # BACKDROP_DOWNLOADS: the tests point this away from the user's folder.
    downloads = os.environ.get("BACKDROP_DOWNLOADS") or os.path.join(
        os.path.expanduser("~"), "Downloads")
    return [image_folder, downloads]


def find_comments_file(image_path, folders):
    """Newest '<image name> Dropbox File Comments*.txt' (a repeated download
    gets ' (1)' added by the browser), or None."""
    return index_comment_files(folders).get(os.path.basename(image_path).lower())


def index_comment_files(folders):
    """{image file name in lower case: its newest comments file} for every
    comments file in the folders."""
    suffix = COMMENTS_SUFFIX.lower()
    best = {}
    for folder in folders:
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            low = name.lower()
            cut = low.find(suffix)
            if cut <= 0 or not low.endswith(".txt"):
                continue
            path = os.path.join(folder, name)
            try:
                stamp = os.path.getmtime(path)
            except OSError:
                continue
            image = low[:cut]
            if image not in best or stamp > best[image][0]:
                best[image] = (stamp, path)
    return dict((image, found[1]) for image, found in best.items())


MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def local_time(stamp):
    """'2026-11-20T13:43:39.000Z' -> '20 Nov 15:43' in this computer's time."""
    try:
        moment = datetime.datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")
        moment = moment.replace(tzinfo=datetime.timezone.utc).astimezone()
        # Not strftime("%b"): that follows the Windows locale, the panel is in English.
        return "{:02d} {} {:02d}:{:02d}".format(
            moment.day, MONTHS[moment.month - 1], moment.hour, moment.minute)
    except ValueError:
        return ""


def short_name(stem):
    """'SK100-30_FC-2840BB_Angle01' -> 'SK100-30 · Angle01' for the
    narrow caption under a thumbnail."""
    parts = [p for p in stem.split("_") if p]
    return "{} · {}".format(parts[0], parts[-1]) if len(parts) > 2 else stem


def is_cloud_only(path):
    """A Dropbox / OneDrive placeholder: reading it would download the file."""
    try:
        attributes = os.stat(path).st_file_attributes
    except (OSError, AttributeError):
        return False
    return bool(attributes & (0x00400000 | 0x00001000))    # RECALL_ON_DATA_ACCESS | OFFLINE


def load_thumbnail(path, size=QtCore.QSize(240, 180)):
    """Small preview of an image, or None (placeholder, unreadable file).
    The reader scales while decoding, so a large JPEG stays cheap."""
    if is_cloud_only(path):
        return None
    reader = QtGui.QImageReader(path)
    full = reader.size()
    if full.isValid():
        reader.setScaledSize(full.scaled(size, Qt.KeepAspectRatioByExpanding))
    image = reader.read()
    return None if image.isNull() else QtGui.QPixmap.fromImage(image)


def parse_comments(text):
    """Comments of a Dropbox export as dicts: label, author, text and region
    (x, y, width, height as fractions of the image, origin top left; None for
    a comment that is not attached to a place)."""
    notes = []
    for block in re.split(r"(?m)^=+\s*$", text):
        content = re.search(r"(?ms)^Content:[ \t]?(.*?)(?=^Timestamp:|\Z)", block)
        if content is None:
            continue
        region, label = None, None
        start = block.find("Annotation:")
        brace = block.find("{", start) if start >= 0 else -1
        if brace >= 0:
            try:
                data = json.JSONDecoder().raw_decode(block[brace:])[0]
                r = data.get("region") or {}
                region = tuple(float(r[k]) for k in ("x", "y", "width", "height"))
                label = data.get("label")
            except (ValueError, KeyError, TypeError):
                region = None
        author = re.search(r"(?m)^Author:[ \t]?(.*)$", block)
        stamp = re.search(r"(?m)^Timestamp:[ \t]?(\S+)", block)
        notes.append({
            "label": str(label if label is not None else len(notes) + 1),
            "author": author.group(1).strip() if author else "",
            "time": local_time(stamp.group(1)) if stamp else "",
            "text": " ".join(content.group(1).split()),
            "region": region,
        })
    return notes


def load_comments(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return parse_comments(f.read())
    except OSError:
        return []


# The frames are drawn by MAXScript in a viewport redraw callback: with
# Nitrous the gw methods only work there ("Viewport Drawing Methods" and
# "Viewport Redraw Callback Mechanism" in the MAXScript help). bd_fit is the
# render frame inside a viewport of the given size -- the same area a
# background with the "Match Rendering Output" aspect covers.
rt.execute("""
global bd_notes, bd_color, bd_draw
if bd_notes == undefined do bd_notes = #()
if bd_color == undefined do bd_color = color 44 198 234
unRegisterRedrawViewsCallback bd_draw
fn bd_fit vw vh =
(
    local a = (renderWidth * renderPixelAspect) / (renderHeight as float)
    local w = vw as float, h = vh as float
    if (w / h) > a then w = h * a else h = w / a
    #((vw - w) / 2.0, (vh - h) / 2.0, w, h)
)
-- gw does no clipping and drawing outside the window can crash Max.
fn bd_px v hi = (amax 1 (amin (hi - 2) (v as integer)))
fn bd_draw =
(
    if bd_notes.count > 0 do
    (
        local vw = gw.getWinSizeX(), vh = gw.getWinSizeY()
        local f = bd_fit vw vh
        local px = bd_px
        gw.setTransform (matrix3 1)
        gw.setColor #line bd_color
        for n in bd_notes do
        (
            local x0 = px (f[1] + n[1] * f[3]) vw
            local y0 = px (f[2] + n[2] * f[4]) vh
            local x1 = px (f[1] + (n[1] + n[3]) * f[3]) vw
            local y1 = px (f[2] + (n[2] + n[4]) * f[4]) vh
            gw.wPolyline #([x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]) true
            gw.wPolyline #([x0 + 1, y0 + 1, 0], [x1 - 1, y0 + 1, 0], [x1 - 1, y1 - 1, 0], [x0 + 1, y1 - 1, 0]) true
            gw.wText [x0 + 4, y0 + 3, 0] n[5] color:bd_color
        )
        gw.enlargeUpdateRect #whole
        gw.updateScreen()
    )
)
""")


def shown_text(note):
    """The comment as it is displayed: its translation when that is on."""
    return note.get("shown") or note["text"]


def caption_of(note):
    return "{}  {}".format(note["label"], shown_text(note))[:60]


# ---------------------------------------------------------------------------
# Translation of the comments with DeepL (the user's own API key)
# ---------------------------------------------------------------------------
def needs_translation(text):
    """Latin letters and no Cyrillic: worth sending to the translator."""
    return bool(re.search(r"[A-Za-z]", text)) and not re.search(r"[Ѐ-ӿ]", text)


def deepl_request(key, texts, target="RU"):
    """(url, headers, body) of a DeepL /v2/translate call. Keys of the free
    plan end with ':fx' and have a host of their own; the key travels in the
    Authorization header (developers.deepl.com: auth, translate)."""
    host = "api-free.deepl.com" if key.strip().endswith(":fx") else "api.deepl.com"
    body = json.dumps({"text": list(texts), "target_lang": target}).encode("utf-8")
    headers = {"Authorization": "DeepL-Auth-Key " + key.strip(),
               "Content-Type": "application/json"}
    return "https://{}/v2/translate".format(host), headers, body


DEEPL_ERRORS = {403: "DeepL: the key was not accepted.",
                429: "DeepL: too many requests, try again later.",
                456: "DeepL: the character quota of this key is used up."}


def cert_not_after(der):
    """Expiry of a DER-encoded X.509 certificate as a naive UTC datetime, or
    None when it cannot be read. Walks the ASN.1 by hand down to
    tbsCertificate.validity.notAfter (RFC 5280, 4.1): the ssl module has no
    public call that decodes a certificate it did not receive from a peer."""
    def item(pos):
        tag = der[pos]
        length = der[pos + 1]
        pos += 2
        if length & 0x80:
            count = length & 0x7F
            length = int.from_bytes(der[pos:pos + count], "big")
            pos += count
        return tag, pos, pos + length

    try:
        _tag, start, _end = item(0)                 # Certificate
        _tag, start, _end = item(start)             # tbsCertificate
        tag, _body, end = item(start)
        if tag == 0xA0:                             # [0] version, optional
            tag, _body, end = item(end)
        pos = end                                   # after serialNumber
        for _ in range(2):                          # signature, issuer
            _tag, _body, pos = item(pos)
        _tag, start, _end = item(pos)               # validity
        _tag, _body, end = item(start)              # notBefore
        tag, body, end = item(end)                  # notAfter
        text = bytes(der[body:end]).decode("ascii")
        if tag == 0x17:                             # UTCTime YYMMDDHHMMSSZ
            year = int(text[:2])
            text = str(2000 + year if year < 50 else 1900 + year) + text[2:]
        return datetime.datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]),
                                 int(text[8:10]), int(text[10:12]), int(text[12:14]))
    except Exception:
        return None


_tls_context = None


def tls_context():
    """SSL context with the Windows certificate stores minus the expired
    certificates, or None (the Python default) where that is not possible.

    The default context loads every certificate of the stores; an expired
    one on the way to the root makes OpenSSL give up with 'certificate has
    expired' although a valid chain exists (seen with api-free.deepl.com in
    3ds Max 2024 and 2026)."""
    global _tls_context
    if _tls_context is None:
        try:
            import ssl
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)   # verifies host and chain
            now = datetime.datetime.utcnow()
            loaded = 0
            for store in ("ROOT", "CA"):
                for der, encoding, trust in ssl.enum_certificates(store):
                    if encoding != "x509_asn":
                        continue
                    if trust is not True and "1.3.6.1.5.5.7.3.1" not in trust:
                        continue                    # not trusted for server authentication
                    expires = cert_not_after(der)
                    if expires is not None and expires < now:
                        continue
                    try:
                        context.load_verify_locations(cadata=der)
                        loaded += 1
                    except Exception:
                        pass
            _tls_context = context if loaded else False
        except Exception:
            _tls_context = False
    return _tls_context or None


def _deepl_call(url, headers, body=None):
    """JSON answer of a DeepL call; raises RuntimeError with a message for
    the status line."""
    import urllib.error
    import urllib.request
    try:
        request = urllib.request.Request(url, data=body, headers=headers,
                                         method="POST" if body is not None else "GET")
        with urllib.request.urlopen(request, timeout=20, context=tls_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(DEEPL_ERRORS.get(e.code, "DeepL: error {}.".format(e.code)))
    except Exception as e:
        raise RuntimeError("DeepL: no answer ({}).".format(e))


def deepl_translate(key, texts):
    """Translations in the order of the texts."""
    data = _deepl_call(*deepl_request(key, texts))
    return [item["text"] for item in data["translations"]]


def deepl_usage_request(key):
    """(url, headers) of GET /v2/usage: what the key has used and may use."""
    url, headers, _body = deepl_request(key, [])
    return url.replace("/v2/translate", "/v2/usage"), {"Authorization": headers["Authorization"]}


def deepl_usage(key):
    """(characters used, character limit) of the key's billing period; the
    cheapest call that tells whether DeepL accepts the key."""
    data = _deepl_call(*deepl_usage_request(key))
    return int(data.get("character_count", 0)), int(data.get("character_limit", 0))


def cache_path():
    """Translations are kept on this computer, not next to the comments:
    that folder may be shared with the client."""
    custom = os.environ.get("BACKDROP_CACHE")       # the tests use their own
    if custom:
        return custom
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "AD Tools", "Backdrop", "translations.json")


def load_cache():
    try:
        with open(cache_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    try:
        path = cache_path()
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    except OSError as e:
        print("Backdrop: could not save the translations ({})".format(e))


class Translator(QtCore.QObject):
    """Runs the DeepL call off the UI thread; only plain Python happens
    there, the result comes back to the panel through a queued signal."""
    done = QtCore.Signal(object, object, str)       # texts, translations, error

    def start(self, key, texts):
        thread = threading.Thread(target=self._run, args=(key, list(texts)))
        thread.daemon = True
        thread.start()

    def _run(self, key, texts):
        try:
            self.done.emit(texts, deepl_translate(key, texts), "")
        except Exception as e:
            self.done.emit(texts, [], str(e))

    checked = QtCore.Signal(object, str)            # (used, limit) or None, error

    def check(self, key):
        """Ask DeepL whether it accepts the key."""
        thread = threading.Thread(target=self._check, args=(key,))
        thread.daemon = True
        thread.start()

    def _check(self, key):
        try:
            self.checked.emit(deepl_usage(key), "")
        except Exception as e:
            self.checked.emit(None, str(e))


def fit_frame(width, height):
    """Render frame inside a viewport of the given size: (left, top, w, h)."""
    try:
        aspect = float(rt.renderWidth) * float(rt.renderPixelAspect) / float(rt.renderHeight)
    except Exception:
        aspect = 4.0 / 3.0
    w, h = float(width), float(height)
    if h <= 0 or aspect <= 0:
        return (0.0, 0.0, w, h)
    if w / h > aspect:
        w = h * aspect
    else:
        h = w / aspect
    return ((width - w) / 2.0, (height - h) / 2.0, w, h)


def viewport_rect(main_window):
    """Screen rectangle of the active viewport as a QRect, or None."""
    try:
        hwnd = int(rt.viewport.getHWnd())
    except Exception:
        return None
    if not hwnd:
        return None
    try:
        widget = QtWidgets.QWidget.find(hwnd)
    except Exception:
        widget = None
    if widget is not None:
        return QtCore.QRect(widget.mapToGlobal(QtCore.QPoint(0, 0)), widget.size())
    import ctypes
    from ctypes import wintypes
    r = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r)):
        return None
    ratio = main_window.devicePixelRatioF() or 1.0     # native pixels -> Qt units
    return QtCore.QRect(int(r.left / ratio), int(r.top / ratio),
                        int((r.right - r.left) / ratio), int((r.bottom - r.top) / ratio))


class CommentOverlay(QtWidgets.QWidget):
    """Transparent, click-through window kept over the active viewport; it
    paints the comment frames and captions with Qt, so the text size and the
    colours can be chosen (the gw viewport text has one fixed font)."""

    def __init__(self, main_window):
        super(CommentOverlay, self).__init__(main_window)
        self.setObjectName(OVERLAY_NAME)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint
                            | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._main = main_window
        self.notes = []
        self.selected = None                # label of the comment picked in the panel
        self.done = set()                   # labels ticked off: drawn dimmed
        self.opacity = 1.0
        self.text_size = 18
        self.frame_color = QtGui.QColor("#2cc6ea")
        self.text_color = QtGui.QColor("#04222b")
        self._frame = (0.0, 0.0, 1.0, 1.0)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self.follow_viewport)

    def set_notes(self, notes):
        self.notes = list(notes)
        if self.notes:
            self.follow_viewport()
            self._timer.start()
        else:
            self._timer.stop()
            self.hide()
        self.update()

    def follow_viewport(self):
        """Stay exactly over the active viewport as it moves or changes."""
        rect = viewport_rect(self._main)
        if rect is None or rect.width() < 4 or rect.height() < 4 \
                or not self._main.isVisible() or self._main.isMinimized():
            self.hide()
            return
        frame = fit_frame(rect.width(), rect.height())
        if rect != self.geometry():
            self.setGeometry(rect)
        if frame != self._frame:
            self._frame = frame
            self.update()
        if not self.isVisible():
            self.show()

    def note_rects(self):
        """[(QRectF of the frame, note)] in widget coordinates."""
        left, top, w, h = self._frame
        rects = []
        for note in self.notes:
            x, y, nw, nh = note["region"]
            rects.append((QtCore.QRectF(left + x * w, top + y * h, nw * w, nh * h), note))
        return rects

    def paintEvent(self, event):
        """Every comment is a frame with a numbered pin; the one picked in the
        panel is drawn in the accent colour with its text next to the pin."""
        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setOpacity(self.opacity)
            radius = max(10.0, self.text_size * 0.62)
            pin_font = QtGui.QFont("Segoe UI")
            pin_font.setPixelSize(int(radius * 1.1))
            pin_font.setBold(True)
            text_font = QtGui.QFont("Segoe UI")
            text_font.setPixelSize(self.text_size)
            text_font.setBold(True)
            grey = QtGui.QColor("#8a909a")
            shadow = QtGui.QColor(0, 0, 0, 95)
            picked = None
            for rect, note in self.note_rects():
                label = note["label"]
                done = label in self.done
                selected = label == self.selected
                if selected:
                    color, width = self.frame_color, 3.0
                    picked = (rect, note)
                else:
                    color, width = (grey if done else QtGui.QColor("#ffffff")), 1.4
                # A dark edge keeps a light frame readable on a light render.
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QtGui.QPen(shadow, width + 2.0))
                painter.drawRoundedRect(rect, 4, 4)
                painter.setPen(QtGui.QPen(color, width))
                painter.drawRoundedRect(rect, 4, 4)

                center = self._pin_center(rect, radius)
                painter.setPen(QtGui.QPen(shadow, 2.0))
                painter.setBrush(QtGui.QColor("#4d535d") if done else self.frame_color)
                painter.drawEllipse(center, radius, radius)
                painter.setFont(pin_font)
                painter.setPen(QtGui.QColor("#c9cdd3") if done else self.text_color)
                painter.drawText(QtCore.QRectF(center.x() - radius, center.y() - radius,
                                               2 * radius, 2 * radius),
                                 int(Qt.AlignCenter), label)
            if picked is not None:                  # on top of every frame
                rect, note = picked
                center = self._pin_center(rect, radius)
                text = shown_text(note)
                if len(text) > 90:
                    text = text[:89] + "…"
                metrics = QtGui.QFontMetrics(text_font)
                bubble = QtCore.QRectF(center.x() + radius + 5, center.y() - radius - 2,
                                       metrics.horizontalAdvance(text) + 22,
                                       2 * radius + 4)
                if bubble.right() > self.width() - 2:       # keep it on screen
                    bubble.moveRight(self.width() - 2)
                    bubble.moveTop(center.y() + radius + 4)
                if bubble.left() < 2:
                    bubble.moveLeft(2)
                painter.setPen(QtGui.QPen(self.frame_color, 1.4))
                painter.setBrush(QtGui.QColor(23, 24, 27, 240))
                painter.drawRoundedRect(bubble, 8, 8)
                painter.setFont(text_font)
                painter.setPen(QtGui.QColor("#e7e9ec"))
                painter.drawText(bubble.adjusted(11, 0, -11, 0),
                                 int(Qt.AlignVCenter | Qt.AlignLeft), text)
        finally:
            painter.end()

    def _pin_center(self, rect, radius):
        """The pin sits on the top left corner of its frame, inside the window."""
        x = min(max(rect.left(), radius + 2), self.width() - radius - 2)
        y = min(max(rect.top(), radius + 2), self.height() - radius - 2)
        return QtCore.QPointF(x, y)


def draw_comments(notes, color=None):
    """Fallback drawing with the gw viewport methods (fixed font): frames
    with their captions over the active viewport; [] removes them."""
    if color is not None:
        rt.bd_color = rt.Color(color.red(), color.green(), color.blue())
    rows = []
    for note in notes:
        if note["region"]:
            x, y, w, h = note["region"]
            rows.append(rt.Array(x, y, w, h, caption_of(note)))
    rt.bd_notes = rt.Array(*rows)
    rt.execute("unRegisterRedrawViewsCallback bd_draw")
    if rows:
        rt.execute("registerRedrawViewsCallback bd_draw")
    rt.completeRedraw()


# ---------------------------------------------------------------------------
# Panel pieces: thumbnail grid, comment cards
# ---------------------------------------------------------------------------
ROLE_PATH = Qt.UserRole
ROLE_COUNT = Qt.UserRole + 1                # comments still open on that image
ROLE_MATCH = Qt.UserRole + 2                # image of the active setup


def ui_font(size, bold=False, strike=False):
    font = QtGui.QFont("Segoe UI")
    font.setPixelSize(size)
    font.setWeight(QtGui.QFont.DemiBold if bold else QtGui.QFont.Normal)
    font.setStrikeOut(strike)
    return font


class ElidedLabel(QtWidgets.QLabel):
    """Label that shortens its text to fit, so a long text never widens the
    panel; .full and text() keep it all, the tooltip shows it."""

    def __init__(self, parent=None, mode=Qt.ElideMiddle):
        super(ElidedLabel, self).__init__(parent)
        self.full = ""
        self._mode = mode
        self.setMinimumWidth(20)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)

    def setText(self, text):
        self.full = text
        self.setToolTip(text)
        self._fit()

    def resizeEvent(self, event):
        super(ElidedLabel, self).resizeEvent(event)
        self._fit()

    def text(self):
        return self.full

    def _fit(self):
        shown = self.fontMetrics().elidedText(self.full, self._mode, max(10, self.width()))
        super(ElidedLabel, self).setText(shown)


class ThumbList(QtWidgets.QListWidget):
    """Grid of image previews, three in a row at the default panel width."""
    GAP = 6
    CAPTION = 18

    def __init__(self, parent=None):
        super(ThumbList, self).__init__(parent)
        self.setObjectName("thumbs")
        self.setViewMode(QtWidgets.QListView.IconMode)
        self.setFlow(QtWidgets.QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setMovement(QtWidgets.QListView.Static)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.pixmaps = {}                   # path -> QPixmap or None
        self.setItemDelegate(ThumbDelegate(self))
        self._fit_grid()

    def resizeEvent(self, event):
        self._fit_grid()
        super(ThumbList, self).resizeEvent(event)

    def _fit_grid(self):
        # From the width of the list itself, with room for the scroll bar
        # whether it is shown or not: sized from the viewport, the cells
        # stopped fitting the moment the scroll bar appeared and a column
        # dropped off.
        bar = self.verticalScrollBar().sizeHint().width()
        width = max(120, self.width() - bar - 2 * self.frameWidth() - 4)
        columns = max(2, int(round(width / 104.0)))
        cell = width // columns
        self.setGridSize(QtCore.QSize(cell, int((cell - self.GAP) * 0.75) + self.CAPTION + self.GAP))


class ThumbDelegate(QtWidgets.QStyledItemDelegate):
    """Preview with rounded corners, the short name under it, a badge with
    the number of open comments, an outline on the image that is shown."""

    def __init__(self, view):
        super(ThumbDelegate, self).__init__(view)
        self.view = view

    def sizeHint(self, option, index):
        return self.view.gridSize()

    def paint(self, painter, option, index):
        path = index.data(ROLE_PATH)
        count = index.data(ROLE_COUNT) or 0
        current = index == self.view.currentIndex()
        hover = bool(option.state & QtWidgets.QStyle.State_MouseOver)
        gap = ThumbList.GAP
        cell = QtCore.QRectF(option.rect)
        picture = QtCore.QRectF(cell.left() + gap / 2.0, cell.top() + gap / 2.0,
                                cell.width() - gap,
                                cell.height() - gap - ThumbList.CAPTION)
        painter.save()
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            clip = QtGui.QPainterPath()
            clip.addRoundedRect(picture, 7, 7)
            pixmap = self.view.pixmaps.get(path)
            painter.save()
            painter.setClipPath(clip)
            if pixmap is not None:
                source = QtCore.QRectF(pixmap.rect())
                want = picture.width() / picture.height()
                if source.width() / source.height() > want:
                    cut = source.width() - source.height() * want
                    source.adjust(cut / 2, 0, -cut / 2, 0)
                else:
                    cut = source.height() - source.width() / want
                    source.adjust(0, cut / 2, 0, -cut / 2)
                painter.drawPixmap(picture, pixmap, source)
            else:                           # not loaded yet, or only in the cloud
                painter.fillRect(picture, QtGui.QColor(T["pill"]))
                icon = QtCore.QRectF(0, 0, 22, 22)
                icon.moveCenter(picture.center())
                svg_renderer("image", T["text_faint"], 1.6).render(painter, icon)
            painter.restore()

            painter.setBrush(Qt.NoBrush)
            if current:
                painter.setPen(QtGui.QPen(QtGui.QColor(T["accent"]), 2.0))
                painter.drawRoundedRect(picture.adjusted(-1, -1, 1, 1), 8, 8)
            elif hover:
                painter.setPen(QtGui.QPen(QtGui.QColor(T["text_faint"]), 1.0))
                painter.drawRoundedRect(picture, 7, 7)

            if index.data(ROLE_MATCH):      # the image of the active setup
                dot = QtCore.QPointF(picture.left() + 11, picture.top() + 11)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QtGui.QColor(T["ok"]))
                painter.drawEllipse(dot, 5, 5)
            if count:
                center = QtCore.QPointF(picture.right() - 12, picture.top() + 12)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QtGui.QColor(T["accent"]))
                painter.drawEllipse(center, 9, 9)
                painter.setFont(ui_font(10, True))
                painter.setPen(QtGui.QColor(T["accent_text"]))
                painter.drawText(QtCore.QRectF(center.x() - 9, center.y() - 9, 18, 18),
                                 int(Qt.AlignCenter), str(count))

            font = ui_font(10, current)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(T["text"] if current else T["text_dim"]))
            caption = QtCore.QRectF(cell.left() + 2, picture.bottom() + 2,
                                    cell.width() - 4, ThumbList.CAPTION)
            name = short_name(os.path.splitext(os.path.basename(path or ""))[0])
            name = QtGui.QFontMetrics(font).elidedText(name, Qt.ElideMiddle, int(caption.width()))
            painter.drawText(caption, int(Qt.AlignHCenter | Qt.AlignVCenter), name)
        finally:
            painter.restore()


class NoteList(QtWidgets.QListWidget):
    """Comment cards. The panel fills .notes in the order of the rows and
    .unseen with the labels whose frames are switched off."""
    eyeClicked = QtCore.Signal(str)         # label of the card whose eye was clicked

    def __init__(self, parent=None):
        super(NoteList, self).__init__(parent)
        self.setObjectName("notes")
        self.notes = []
        self.unseen = set()
        self.pin_clicked = False
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setItemDelegate(NoteDelegate(self))

    def resizeEvent(self, event):
        super(NoteList, self).resizeEvent(event)
        self.scheduleDelayedItemsLayout()           # card heights depend on the width


class NoteDelegate(QtWidgets.QStyledItemDelegate):
    """One comment as a card: numbered pin (a tick once dealt with), the text,
    the original under a translation, author and time, and an eye that takes
    its frame off the viewport."""
    PIN = 40                                # width of the pin column, also its click area
    EYE = 34                                # the same for the eye, on the right

    def __init__(self, view):
        super(NoteDelegate, self).__init__(view)
        self.view = view

    def _note(self, index):
        row = index.row()
        return self.view.notes[row] if 0 <= row < len(self.view.notes) else None

    def _text_width(self):
        return max(60, self.view.viewport().width() - self.PIN - self.EYE - 4)

    def _text_height(self, note):
        metrics = QtGui.QFontMetrics(ui_font(12, True))
        rect = metrics.boundingRect(QtCore.QRect(0, 0, self._text_width(), 1000),
                                    int(Qt.TextWordWrap), shown_text(note))
        return min(rect.height(), metrics.lineSpacing() * 4)

    def sizeHint(self, option, index):
        note = self._note(index)
        if note is None:
            return QtCore.QSize(100, 46)
        height = 9 + self._text_height(note) + 2 + 16 + 9
        if note.get("shown"):
            height += 16
        return QtCore.QSize(100, max(46, height) + 6)

    def editorEvent(self, event, model, option, index):
        """A click on the pin ticks the comment off or on again; a click on
        the eye hides or shows its frame on the viewport."""
        if event.type() != QtCore.QEvent.MouseButtonRelease or event.button() != Qt.LeftButton:
            return False
        if event.pos().x() - option.rect.left() <= self.PIN:
            self.view.pin_clicked = True            # the click is not a pick, see _note_clicked
            self.toggle(index)
            return True
        if option.rect.right() - event.pos().x() <= self.EYE:
            self.view.pin_clicked = True
            self.toggle_eye(index)
            return True
        return False

    def toggle_eye(self, index):
        note = self._note(index)
        if note is not None:
            self.view.eyeClicked.emit(note["label"])

    def is_done(self, index):
        """Ticked off. Asked from the item: the raw role value is an int in
        PySide2 and an enum in PySide6."""
        item = self.view.item(index.row())
        return item is not None and item.checkState() != Qt.Checked

    def toggle(self, index):
        item = self.view.item(index.row())
        if item is not None:
            item.setCheckState(Qt.Checked if self.is_done(index) else Qt.Unchecked)

    def paint(self, painter, option, index):
        note = self._note(index)
        if note is None:
            return
        done = self.is_done(index)
        selected = bool(option.state & QtWidgets.QStyle.State_Selected)
        hover = bool(option.state & QtWidgets.QStyle.State_MouseOver)
        card = QtCore.QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -6.5)
        painter.save()
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            fill = T["select"] if selected else (T["hover"] if hover else T["surface"])
            painter.setPen(QtGui.QPen(QtGui.QColor(T["accent"] if selected else T["border"]),
                                      1.5 if selected else 1.0))
            painter.setBrush(QtGui.QColor(fill))
            painter.drawRoundedRect(card, 8, 8)

            center = QtCore.QPointF(card.left() + 21, card.top() + 21)
            painter.setPen(Qt.NoPen)
            if done:
                painter.setBrush(QtGui.QColor(T["pill"]))
                painter.drawEllipse(center, 10, 10)
                svg_renderer("check", T["text_faint"]).render(
                    painter, QtCore.QRectF(center.x() - 7, center.y() - 7, 14, 14))
            else:
                painter.setBrush(QtGui.QColor(T["accent"]))
                painter.drawEllipse(center, 10, 10)
                painter.setFont(ui_font(11, True))
                painter.setPen(QtGui.QColor(T["accent_text"]))
                painter.drawText(QtCore.QRectF(center.x() - 10, center.y() - 10, 20, 20),
                                 int(Qt.AlignCenter), note["label"])

            unseen = note["label"] in self.view.unseen
            svg_renderer("eye_off" if unseen else "eye",
                         T["icon_off"] if unseen else T["text_dim"], 1.8).render(
                painter, QtCore.QRectF(card.right() - 26, card.top() + 13, 16, 16))

            x = card.left() + self.PIN
            width = self._text_width()
            y = card.top() + 9
            height = self._text_height(note)
            painter.setFont(ui_font(12, True, strike=done))
            painter.setPen(QtGui.QColor(T["text_faint"] if done else T["text"]))
            painter.drawText(QtCore.QRectF(x, y, width, height),
                             int(Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop), shown_text(note))
            y += height + 2
            small = ui_font(11)
            metrics = QtGui.QFontMetrics(small)
            painter.setFont(small)
            if note.get("shown"):           # the original under its translation
                painter.setPen(QtGui.QColor(T["text_faint"]))
                painter.drawText(QtCore.QRectF(x, y, width, 16), int(Qt.AlignVCenter),
                                 metrics.elidedText(note["text"], Qt.ElideRight, int(width)))
                y += 16
            meta = "  ·  ".join(part for part in (note["author"], note.get("time")) if part)
            painter.setPen(QtGui.QColor(T["text_dim"]))
            painter.drawText(QtCore.QRectF(x, y, width, 16), int(Qt.AlignVCenter),
                             metrics.elidedText(meta, Qt.ElideRight, int(width)))
        finally:
            painter.restore()


# ---------------------------------------------------------------------------
# Custom title bar
# ---------------------------------------------------------------------------
class CustomDockWidgetTitleBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(CustomDockWidgetTitleBar, self).__init__(parent)
        self.setObjectName("titlebar")
        self.setFixedHeight(32)
        self.setAutoFillBackground(True)
        # A plain QWidget subclass ignores stylesheet backgrounds without this.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._collapsed = False

        self.logo = QtWidgets.QLabel()
        self.logo.setFixedSize(16, 16)
        self.logo.setScaledContents(True)

        self.titleLabel = QtWidgets.QLabel("Backdrop")
        self.titleLabel.setObjectName("title")
        self.versionLabel = QtWidgets.QLabel(VERSION)
        self.versionLabel.setObjectName("version")

        self.theme_button = self._button(self.parentWidget().toggle_theme)
        self.minimize_button = self._button(self.parentWidget().toggle_collapsed)
        self.close_button = self._button(self.parentWidget().close)
        self.close_button.setObjectName("close")
        self.close_button.setToolTip("Close")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 4, 0)
        layout.setSpacing(6)
        layout.addWidget(self.logo)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.versionLabel)
        layout.addStretch()
        layout.addWidget(self.theme_button)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.close_button)

        self.apply_theme()

    def _button(self, slot):
        button = QtWidgets.QPushButton()
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(26, 24)
        button.setIconSize(QtCore.QSize(14, 14))
        button.clicked.connect(slot)
        return button

    def apply_theme(self):
        self.setStyleSheet(themed(TITLEBAR_STYLE))
        self.logo.setPixmap(make_icon("image", T["accent"]).pixmap(64, 64))
        self.close_button.setIcon(make_icon("close", T["text_dim"]))
        # The button shows the theme a click switches to.
        dark = T["window"] == DARK["window"]
        self.theme_button.setIcon(make_icon("sun" if dark else "moon", T["text_dim"]))
        self.theme_button.setToolTip(
            "Switch to the light theme" if dark else "Switch to the dark theme")
        self.set_collapsed(self._collapsed)

    def set_collapsed(self, collapsed):
        """Flip the minimize glyph between roll-up and roll-down."""
        self._collapsed = collapsed
        self.minimize_button.setIcon(
            make_icon("plus" if collapsed else "minus", T["text_dim"]))
        self.minimize_button.setToolTip("Expand panel" if collapsed else "Collapse panel")


# ---------------------------------------------------------------------------
# Main dock widget
# ---------------------------------------------------------------------------
class BackdropDockWidget(QtWidgets.QDockWidget):
    def __init__(self, parent=None):
        super(BackdropDockWidget, self).__init__(parent)
        self.setWindowFlags(Qt.Tool)
        self.setWindowTitle("Backdrop {}".format(VERSION))
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._folder = ""
        self._images = []                   # [(stem, path)]
        self._key = None                    # last seen setup name
        self._scene = None                  # last seen scene file
        self._shown = None                  # path on the viewport right now
        self._matched = None                # image of the active setup
        self._notes_folder = ""             # own folder for comment files, '' = auto
        self._notes = []                    # comments of the shown image
        self._notes_file = None             # (path, mtime) they were read from
        self._hidden = set()                # labels ticked off as dealt with
        self._unseen = set()                # labels whose frame is off the viewport
        self._selected = None               # label of the comment picked in the list
        self._just_selected = False         # see _note_clicked
        self._parsed = {}                   # comments file -> (mtime, notes)
        self._thumb_stamps = {}             # image -> mtime its preview was made from
        self._thumb_queue = []              # previews still to load
        self._dot_state = "off"
        self._key_note = ""                 # last answer of the DeepL key check
        self._ticks = 0
        self._cache = load_cache()          # original text -> translation
        self._asked = set()                 # texts already sent to DeepL
        self._translator = Translator(self)
        self._translator.done.connect(self._translated)
        self._translator.checked.connect(self._key_checked)
        # Frames are painted by a Qt overlay; the gw drawing stays as the
        # fallback for a Max where the overlay cannot be created.
        self._use_gw = False
        try:
            self.overlay = CommentOverlay(parent)
            self.overlay.text_size = load_int("text_size", 18)
            self.overlay.frame_color = load_color("frame_color", "#2cc6ea")
            self.overlay.text_color = load_color("text_color", "#04222b")
            self.overlay.opacity = min(100, max(20, load_int("opacity", 100))) / 100.0
        except Exception as e:
            print("Backdrop: no overlay, drawing with gw ({})".format(e))
            self.overlay = None
            self._use_gw = True
        self._dark = None                   # last seen 3ds Max colour scheme
        # "auto" follows the 3ds Max colour scheme; the title bar button
        # switches to an explicit "dark" / "light" and that choice is kept.
        self._theme_mode = load_theme_mode()

        # Roll-up state (Qt::Tool windows have no real minimize -- see toggle_collapsed)
        self._collapsed = False
        self._expanded_size = QtCore.QSize(340, 664)
        self._expanded_pos = None
        self._saved_min_height = 0
        self._saved_max_height = 16777215

        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)

        self.initUI()
        self.setTitleBarWidget(CustomDockWidgetTitleBar(self))
        self.apply_theme()
        watch_saves(True)
        self._poll()
        self._poll_timer.start()

    # -- UI -----------------------------------------------------------------
    def initUI(self):
        root = QtWidgets.QWidget()
        root.setObjectName("root")
        self._root = root

        main_layout = QtWidgets.QVBoxLayout(root)
        main_layout.setContentsMargins(10, 10, 10, 8)
        main_layout.setSpacing(8)

        # --- Active setup card: state dot, setup and camera, panel buttons ---
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        card_row = QtWidgets.QHBoxLayout(card)
        card_row.setContentsMargins(12, 8, 6, 8)
        card_row.setSpacing(8)
        self.dot = QtWidgets.QLabel()
        self.dot.setFixedSize(8, 8)
        card_row.addWidget(self.dot)
        names = QtWidgets.QVBoxLayout()
        names.setSpacing(1)
        self.setup_label = ElidedLabel()
        self.setup_label.setObjectName("setup")
        self.camera_label = ElidedLabel()
        self.camera_label.setObjectName("caption")
        names.addWidget(self.setup_label)
        names.addWidget(self.camera_label)
        card_row.addLayout(names, 1)
        self.follow_btn = self._flat_button(
            "Follow the scene: swap the image when another setup is activated", None)
        self.follow_btn.setCheckable(True)
        self.follow_btn.setChecked(_settings().value("follow", "true") != "false")
        self.follow_btn.toggled.connect(self._follow_toggled)
        self.folder_btn = self._flat_button(
            "Folders with the images and the comment files", self.open_folder_menu)
        self.style_btn = self._flat_button(
            "Text size and colours of the frames, DeepL key", self.open_style_menu)
        for btn in (self.follow_btn, self.folder_btn, self.style_btn):
            card_row.addWidget(btn)
        main_layout.addWidget(card)

        # --- Thumbnails of the images ---
        self.list = ThumbList(self)
        self.list.itemClicked.connect(self._item_clicked)
        main_layout.addWidget(self.list, 3)

        # --- Comments: heading, what is left, Original | RU ---
        notes_row = QtWidgets.QHBoxLayout()
        notes_row.setSpacing(8)
        self.notes_label = QtWidgets.QLabel("Comments")
        self.notes_label.setObjectName("heading")
        notes_row.addWidget(self.notes_label)
        self.notes_count = ElidedLabel()
        self.notes_count.setObjectName("caption")
        notes_row.addWidget(self.notes_count, 1)
        language = QtWidgets.QHBoxLayout()
        language.setSpacing(0)
        self.orig_btn = self._segment("Original", "left", "Show the comments as they were written")
        self.translate_btn = self._segment(
            "RU", "right", "Show the comments translated into Russian (DeepL, your API key)")
        self._language = QtWidgets.QButtonGroup(self)
        self._language.setExclusive(True)
        for btn in (self.orig_btn, self.translate_btn):
            self._language.addButton(btn)
            language.addWidget(btn)
        translate = _settings().value("translate", "false") == "true"
        (self.translate_btn if translate else self.orig_btn).setChecked(True)
        self.translate_btn.toggled.connect(self._translate_toggled)
        notes_row.addLayout(language)
        main_layout.addLayout(notes_row)

        self.notes_list = NoteList(self)
        self.notes_list.itemChanged.connect(self._note_checked)
        self.notes_list.eyeClicked.connect(self.toggle_note_visible)
        self.notes_list.itemSelectionChanged.connect(self._note_selection_changed)
        self.notes_list.itemClicked.connect(self._note_clicked)
        main_layout.addWidget(self.notes_list, 4)

        # --- What is on the viewport ---
        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(6)
        self.show_btn = self._toggle_button(
            "Image", "Show or hide the image behind the active viewport")
        self.show_btn.setChecked(True)
        self.show_btn.toggled.connect(self._show_toggled)
        action_row.addWidget(self.show_btn)
        self.notes_btn = self._toggle_button(
            "Frames", "Show or hide the comment frames over the viewport")
        self.notes_btn.setChecked(_settings().value("comments", "true") != "false")
        self.notes_btn.toggled.connect(self._notes_toggled)
        action_row.addWidget(self.notes_btn)
        opacity_label = QtWidgets.QLabel("Opacity")
        opacity_label.setObjectName("caption")
        action_row.addSpacing(6)
        action_row.addWidget(opacity_label)
        self.opacity_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(min(100, max(20, load_int("opacity", 100))))
        self.opacity_slider.setToolTip("Opacity of the comment frames")
        self.opacity_slider.valueChanged.connect(self._opacity_changed)
        action_row.addWidget(self.opacity_slider, 1)
        main_layout.addLayout(action_row)

        # --- Status ---
        # Elided: a long message (a network error) must not stretch the window.
        self.status_label = ElidedLabel(mode=Qt.ElideRight)
        self.status_label.setObjectName("status")
        main_layout.addWidget(self.status_label)

        self.setWidget(root)
        self.setMinimumSize(300, 420)
        self.resize(340, 664)

    def _flat_button(self, tooltip, slot):
        btn = self._tool_button(tooltip, slot)
        btn.setObjectName("flat")
        return btn

    def _segment(self, text, side, tooltip):
        btn = QtWidgets.QPushButton(text)
        btn.setObjectName("seg")
        btn.setProperty("side", side)
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _tool_button(self, tooltip, slot):
        btn = QtWidgets.QPushButton()
        btn.setObjectName("tool")
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setIconSize(QtCore.QSize(16, 16))
        if slot is not None:
            btn.clicked.connect(slot)
        return btn

    def _toggle_button(self, text, tooltip):
        btn = QtWidgets.QPushButton(text)
        btn.setObjectName("accent")
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def apply_theme(self):
        """Pick the palette (the user's choice, else the one matching the
        3ds Max UI) and restyle everything."""
        if self._theme_mode in ("dark", "light"):
            dark = self._theme_mode == "dark"
        else:
            dark = max_is_dark()
        T.clear()
        T.update(DARK if dark else LIGHT)
        self.setStyleSheet(themed("QDockWidget { background-color: @window@; }"))
        self._root.setStyleSheet(themed(STYLESHEET))
        self.folder_btn.setIcon(make_icon("folder", T["text_dim"]))
        self.style_btn.setIcon(make_icon("sliders", T["text_dim"]))
        self._button_icons()
        self._set_dot(self._dot_state)
        title_bar = self.titleBarWidget()
        if title_bar is not None:
            title_bar.apply_theme()
        self.list.viewport().update()
        self.notes_list.viewport().update()

    def _button_icons(self):
        for btn, icon in ((self.show_btn, "image"), (self.notes_btn, "eye")):
            btn.setIcon(make_icon(
                icon, T["accent_text"] if btn.isChecked() else T["text"]))
        self.follow_btn.setIcon(make_icon(
            "link", T["accent"] if self.follow_btn.isChecked() else T["icon_off"]))

    def _set_dot(self, state):
        """State of the active setup: 'ok' image shown, 'warn' nothing to
        show for it, 'off' no setup or no folder yet."""
        self._dot_state = state
        color = {"ok": T["ok"], "warn": T["warn"]}.get(state, T["icon_off"])
        self.dot.setStyleSheet("background-color: {}; border-radius: 4px;".format(color))

    def toggle_theme(self):
        """Title bar button: switch between the dark and the light palette."""
        dark_now = T["window"] == DARK["window"]
        self._theme_mode = "light" if dark_now else "dark"
        save_theme_mode(self._theme_mode)
        self.apply_theme()

    def showEvent(self, event):
        super(BackdropDockWidget, self).showEvent(event)
        round_window_corners(self)

    def toggle_collapsed(self):
        """Roll the panel up into its title bar and back.

        A floating QDockWidget is a Qt::Tool window, which has no real minimize
        button, so collapsing to the title bar is the workable equivalent.
        """
        body = self.widget()
        if body is None:
            return
        title_bar = self.titleBarWidget()
        bar_height = title_bar.height() if title_bar is not None else 32

        if self._collapsed:
            body.show()
            self.setMinimumHeight(self._saved_min_height)
            self.setMaximumHeight(self._saved_max_height)
            self.resize(self._expanded_size)
            if self._expanded_pos is not None:
                self.move(self._expanded_pos)
            self._collapsed = False
        else:
            self._expanded_size = self.size()
            self._expanded_pos = self.pos()
            self._saved_min_height = self.minimumHeight()
            self._saved_max_height = self.maximumHeight()
            body.hide()
            # Fixing both bounds forces the window to shrink to the bar itself.
            self.setMinimumHeight(bar_height)
            self.setMaximumHeight(bar_height)
            self.resize(self.width(), bar_height)
            self._snap_to_main_bottom()
            self._collapsed = True

        if title_bar is not None:
            title_bar.set_collapsed(self._collapsed)

    def _snap_to_main_bottom(self):
        """Park the collapsed bar on the bottom edge of the Max main window."""
        main_win = self.parentWidget()
        if main_win is None:
            return
        area = main_win.frameGeometry()
        frame = self.frameGeometry()
        y = area.bottom() - frame.height() + 1
        right_limit = max(area.left(), area.right() - frame.width() + 1)
        x = min(max(self.x(), area.left()), right_limit)
        self.move(x, y)

    # -- Folder -------------------------------------------------------------
    def browse_folder(self):
        start = self._folder if os.path.isdir(self._folder) else last_folder()
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Folder with the delivered images", start if os.path.isdir(start) else "")
        if folder:
            self.set_folder(folder)

    def set_folder(self, folder, remember=True):
        self._folder = os.path.normpath(folder) if folder else ""
        if remember:
            save_folder(scene_path(), self._folder)
        self.rescan()

    def rescan(self):
        """Re-read the folder and show the image of the active setup."""
        self._images = list_images(self._folder) if self._folder else []
        self._sync(force=True)

    def folder_menu(self):
        """Menu of the folder button. A path is shortened in the middle to a
        fixed width (the whole of it is in the tooltip): two long paths made
        the menu wider than the panel."""
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(themed(MENU_STYLE))
        menu.setToolTipsVisible(True)
        metrics = QtGui.QFontMetrics(ui_font(12))

        def path_line(caption, path, fallback):
            shown = metrics.elidedText(path, Qt.ElideMiddle, 250) if path else fallback
            action = menu.addAction("{}: {}".format(caption, shown))
            action.setEnabled(False)
            action.setToolTip(path or fallback)

        path_line("Images", self._folder, "not chosen")
        menu.addAction("Choose the image folder...").triggered.connect(
            lambda _checked=False: self.browse_folder())
        menu.addSeparator()
        path_line("Comments", self._notes_folder, "next to the images")
        menu.addAction("Choose the comments folder...").triggered.connect(
            lambda _checked=False: self.browse_notes_folder())
        if self._notes_folder:
            menu.addAction("Look next to the images again").triggered.connect(
                lambda _checked=False: self.set_notes_folder(""))
        menu.addSeparator()
        menu.addAction("Re-read the folders").triggered.connect(
            lambda _checked=False: self.rescan())
        clear = menu.addAction("Clear the folders of this scene")
        clear.setEnabled(bool(self._folder or self._notes_folder))
        clear.triggered.connect(lambda _checked=False: self.clear_folders())
        return menu

    def clear_folders(self):
        """Forget the image and the comments folder of the open scene; the
        image and the frames leave the viewport with them."""
        self._notes_folder = ""
        save_folder(scene_path(), "", "comments")
        self.set_folder("")

    def open_folder_menu(self):
        menu = self.folder_menu()
        runner = getattr(menu, "exec", None) or getattr(menu, "exec_")
        # Opened under the button, its right edge on the button's: the menu
        # stays over the panel instead of running off to the right.
        corner = self.folder_btn.mapToGlobal(
            QtCore.QPoint(self.folder_btn.width(), self.folder_btn.height() + 2))
        runner(QtCore.QPoint(corner.x() - menu.sizeHint().width(), corner.y()))

    # -- Following the scene --------------------------------------------------
    def _poll(self):
        scene = scene_path()
        saved = scene_was_saved()
        if scene != self._scene:
            renamed = saved and self._scene is not None and scene \
                and stored_folder(scene) is None
            self._scene = scene
            if renamed:
                # Save As: the same scene under a new name keeps its folders.
                save_folder(scene, self._folder)
                save_folder(scene, self._notes_folder, "comments")
            else:
                # Another scene: its own folders, or none for one never set up.
                self._notes_folder = load_folder(scene, "comments")
                self.set_folder(load_folder(scene), remember=False)
            return
        if self._theme_mode == "auto":
            dark = max_is_dark()
            if dark != self._dark:
                self._dark = dark
                self.apply_theme()
        self._sync()
        self._ticks += 1
        if self._ticks % COMMENTS_EVERY == 0:
            self._load_notes()              # a comments file downloaded meanwhile
            self._update_counts()

    def _sync(self, force=False):
        key = setup_key()
        try:
            camera = rt.viewport.getCamera()
            camera_name = camera.name if camera is not None else "no camera in the viewport"
        except Exception:
            camera_name = ""
        if camera_name != self.camera_label.full:
            self.camera_label.setText(camera_name)
        if key == self._key and not force:
            return
        if key != self._key and self._key is not None and not self._images_match(key):
            # A setup rendered after the folder was read: look again.
            self._images = list_images(self._folder) if self._folder else []
        self._key = key
        self.setup_label.setText(key or "No setup")
        match = match_image(key, self._images)
        self._matched = match
        if self.follow_btn.isChecked() or force:
            self._display(match)
        self._fill_list()
        if not self._folder:
            self._set_dot("off")
            self.set_status("Choose the folder with the images: the folder button.")
        elif not os.path.isdir(self._folder):
            self._set_dot("warn")
            self.set_status("Folder not found.", warn=True)
        elif not key:
            self._set_dot("off")
            self.set_status("No render output file set in this scene.", warn=True)
        elif match is None:
            self._set_dot("warn")
            self.set_status("No image named like this setup.", warn=True)
        else:
            self._set_dot("ok")
            self.set_status("{} images".format(len(self._images)))

    def _images_match(self, key):
        return match_image(key, self._images) is not None

    def _display(self, path):
        """Show the image (None: nothing to show) if the display is on."""
        self._shown = path
        try:
            if path and self.show_btn.isChecked():
                show_background(path)
            else:
                hide_background()
        except Exception as e:
            self.set_status("Viewport background failed: {}".format(e), warn=True)
        self._load_notes(force=True)

    # -- Comments -------------------------------------------------------------
    def browse_notes_folder(self):
        start = self._notes_folder or self._folder
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Folder with the downloaded comment files",
            start if os.path.isdir(start) else "")
        if folder:
            self.set_notes_folder(folder)

    def set_notes_folder(self, folder):
        """Own folder for the comment files of this scene; '' = look next to
        the images (and in Downloads)."""
        self._notes_folder = os.path.normpath(folder) if folder else ""
        save_folder(scene_path(), self._notes_folder, "comments")
        self._load_notes(force=True)
        self._update_counts()

    def _read_notes(self, path):
        """Comments of a file, parsed once per version of the file."""
        try:
            stamp = os.path.getmtime(path)
        except OSError:
            return []
        cached = self._parsed.get(path)
        if cached is None or cached[0] != stamp:
            cached = (stamp, load_comments(path))
            self._parsed[path] = cached
        return cached[1]

    def _update_counts(self):
        """Badge on every thumbnail: comments of that image not ticked off."""
        index = index_comment_files(comment_folders(self._folder, self._notes_folder))
        for row in range(self.list.count()):
            item = self.list.item(row)
            path = item.data(ROLE_PATH)
            found = index.get(os.path.basename(path).lower())
            count = 0
            if found:
                hidden = self._hidden if (self._notes_file and found == self._notes_file[0]) \
                    else load_hidden(found)
                count = sum(1 for n in self._read_notes(found) if n["label"] not in hidden)
            if item.data(ROLE_COUNT) != count:
                item.setData(ROLE_COUNT, count)

    def _load_notes(self, force=False):
        """Read the comments file of the shown image, if it is new or changed."""
        found = None
        if self._shown:
            path = find_comments_file(
                self._shown, comment_folders(self._folder, self._notes_folder))
            if path:
                try:
                    found = (path, os.path.getmtime(path))
                except OSError:
                    found = None
        if found == self._notes_file and not force:
            return
        if (found[0] if found else None) != (self._notes_file[0] if self._notes_file else None):
            self._selected = None           # another image: nothing picked yet
        self._notes_file = found
        self._notes = self._read_notes(found[0]) if found else []
        self._hidden = load_hidden(found[0]) if found else set()
        self._unseen = load_hidden(found[0], "unseen") if found else set()
        self.notes_list.unseen = self._unseen
        self._apply_language()
        self._fill_notes()
        self._draw_notes()

    def _fill_notes(self):
        self.notes_list.blockSignals(True)
        self.notes_list.clear()
        self.notes_list.notes = self._notes
        picked = None
        for note in self._notes:
            text = "{}  {}".format(note["label"], shown_text(note))
            if note["author"]:
                text += "  -  " + note["author"]
            item = QtWidgets.QListWidgetItem(text)
            item.setData(Qt.UserRole, note["label"])
            # Ticked: still to do. A click on the pin ticks a comment off.
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if note["label"] in self._hidden
                               else Qt.Checked)
            item.setToolTip(note["text"])
            self.notes_list.addItem(item)
            if note["label"] == self._selected:
                picked = item
        if picked is not None:
            self.notes_list.setCurrentItem(picked)
        else:
            self._selected = None
        self.notes_list.blockSignals(False)
        self._show_left()

    def _show_left(self):
        """'2 of 3 left' next to the heading, or why there is nothing."""
        if not self._shown:
            text = ""
        elif self._notes_folder and not os.path.isdir(self._notes_folder):
            text = "folder not found"
        elif self._notes_file is None:
            text = "no file for this image"
        elif not self._notes:
            text = "none"
        else:
            left = sum(1 for n in self._notes if n["label"] not in self._hidden)
            text = "all done" if left == 0 else "{} of {} left".format(left, len(self._notes))
        self.notes_count.setText(text)

    def _note_selection_changed(self):
        items = self.notes_list.selectedItems()
        self._selected = items[0].data(Qt.UserRole) if items else None
        self._just_selected = bool(items)
        self._draw_notes()

    def _note_clicked(self, item):
        """A click on the picked card lets go of it again."""
        if self.notes_list.pin_clicked or self._just_selected:
            self.notes_list.pin_clicked = False
            self._just_selected = False
            return
        self.notes_list.clearSelection()
        self.notes_list.setCurrentItem(None)

    def select_note(self, label):
        """Pick a comment (None: none): its frame is highlighted on the viewport."""
        self.notes_list.clearSelection()
        for row in range(self.notes_list.count()):
            item = self.notes_list.item(row)
            if label is not None and item.data(Qt.UserRole) == label:
                self.notes_list.setCurrentItem(item)
        self._just_selected = False

    def set_translate(self, on):
        (self.translate_btn if on else self.orig_btn).setChecked(True)

    def _opacity_changed(self, value):
        _settings().setValue("opacity", int(value))
        if self.overlay is not None:
            self.overlay.opacity = value / 100.0
            self.overlay.update()

    # -- Translation ------------------------------------------------------------
    def _apply_language(self):
        """Set what each comment shows; ask DeepL for the missing translations."""
        on = self.translate_btn.isChecked()
        missing = []
        for note in self._notes:
            text = note["text"]
            note["shown"] = self._cache.get(text) if on else None
            if on and not note["shown"] and needs_translation(text) \
                    and text not in self._asked and text not in missing:
                missing.append(text)
        if not missing:
            return
        key = load_key()
        if not key:
            self.set_status("Translation needs a DeepL key: the sliders button.", warn=True)
            return
        self._asked.update(missing)
        self.set_status("Translating {} comments...".format(len(missing)))
        self._translator.start(key, missing)

    def _translated(self, texts, translations, error):
        if error:
            self._asked.difference_update(texts)        # may be tried again
            self.set_status(error, warn=True)
            return
        self._cache.update(zip(texts, translations))
        save_cache(self._cache)
        self.set_status("Translated {} comments.".format(len(texts)))
        self._apply_language()
        self._fill_notes()
        self._draw_notes()

    def _translate_toggled(self, on):
        _settings().setValue("translate", "true" if on else "false")
        self._apply_language()
        self._fill_notes()
        self._draw_notes()

    def ask_key(self):
        """The user types their own DeepL API key; it is kept in the settings
        of this Windows account."""
        key, ok = QtWidgets.QInputDialog.getText(
            self, "DeepL API key",
            "Your DeepL API key: deepl.com/your-account/keys\n"
            "(the free API plan is enough). Empty: remove the saved key.",
            QtWidgets.QLineEdit.Password, load_key())
        if ok:
            self.set_key(key)

    def set_key(self, key):
        key = key.strip()
        _settings().setValue("deepl_key", key)
        self._asked.clear()
        self._key_note = ""
        if key:
            self.set_status("Checking the DeepL key...")
            self._translator.check(key)
        self._translate_toggled(self.translate_btn.isChecked())

    def _key_checked(self, usage, error):
        """Answer of the key check: accepted with its quota, or why not."""
        if error:
            self._key_note = error
            self.set_status(error, warn=True)
            return
        used, limit = usage
        self._key_note = "DeepL key accepted: {:,} of {:,} characters used.".format(
            used, limit).replace(",", " ")
        self.set_status(self._key_note)

    def visible_notes(self):
        """Comments whose frames are drawn right now."""
        if not (self.notes_btn.isChecked() and self.show_btn.isChecked()):
            return []
        return [n for n in self._notes if n["region"] and n["label"] not in self._unseen]

    def toggle_note_visible(self, label):
        """The eye on a card: take this comment's frame off the viewport, or
        put it back. Apart from ticking it off, and kept per comments file."""
        if label in self._unseen:
            self._unseen.discard(label)
        else:
            self._unseen.add(label)
        if self._notes_file:
            save_hidden(self._notes_file[0], self._unseen, "unseen")
        self.notes_list.unseen = self._unseen
        self.notes_list.viewport().update()
        self._draw_notes()

    def _draw_notes(self):
        notes = self.visible_notes()
        try:
            if self._use_gw or self.overlay is None:
                color = self.overlay.frame_color if self.overlay else None
                draw_comments([n for n in notes if n["label"] not in self._hidden], color)
            else:
                draw_comments([])
                self.overlay.done = set(self._hidden)
                self.overlay.selected = self._selected
                self.overlay.set_notes(notes)
        except Exception as e:
            self.set_status("Comment frames failed: {}".format(e), warn=True)

    def _note_checked(self, item):
        """Ticked off (dealt with) or back on: the pin goes grey, the badge
        on the thumbnail counts what is left."""
        label = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self._hidden.discard(label)
        else:
            self._hidden.add(label)
        if self._notes_file:
            save_hidden(self._notes_file[0], self._hidden)
        self._show_left()
        self._draw_notes()
        self._update_counts()

    # -- Look of the frames ---------------------------------------------------
    def open_style_menu(self):
        if self.overlay is None:
            return
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(themed(MENU_STYLE))
        for name, size in TEXT_SIZES:
            action = menu.addAction("Text: {}".format(name))
            action.setCheckable(True)
            action.setChecked(size == self.overlay.text_size)
            action.triggered.connect(lambda _checked=False, s=size: self.set_text_size(s))
        menu.addSeparator()
        menu.addAction("Frame colour...").triggered.connect(
            lambda _checked=False: self.pick_color("frame_color", "Frame colour"))
        menu.addAction("Text colour...").triggered.connect(
            lambda _checked=False: self.pick_color("text_color", "Text colour"))
        menu.addSeparator()
        menu.addAction("DeepL API key..." if not load_key() else "DeepL API key (saved)...") \
            .triggered.connect(lambda _checked=False: self.ask_key())
        runner = getattr(menu, "exec", None) or getattr(menu, "exec_")
        runner(self.style_btn.mapToGlobal(QtCore.QPoint(0, self.style_btn.height() + 2)))

    def set_text_size(self, size):
        self.overlay.text_size = int(size)
        _settings().setValue("text_size", int(size))
        self.overlay.update()

    def set_color(self, key, color):
        """key: 'frame_color' or 'text_color'."""
        setattr(self.overlay, key, QtGui.QColor(color))
        _settings().setValue(key, QtGui.QColor(color).name())
        self.overlay.update()
        self._draw_notes()

    def pick_color(self, key, title):
        color = QtWidgets.QColorDialog.getColor(getattr(self.overlay, key), self, title)
        if color.isValid():
            self.set_color(key, color)

    def _notes_toggled(self, on):
        _settings().setValue("comments", "true" if on else "false")
        self._button_icons()
        self._draw_notes()

    def _fill_list(self):
        """Thumbnails of the folder; previews are loaded one per event-loop
        turn so a folder of large renders does not freeze the panel."""
        self.list.blockSignals(True)
        self.list.clear()
        self.list.setCurrentItem(None)
        queue = []
        for stem, path in self._images:
            item = QtWidgets.QListWidgetItem(os.path.basename(path))
            item.setData(ROLE_PATH, path)
            item.setData(ROLE_MATCH, path == self._matched)
            item.setToolTip(os.path.basename(path))
            self.list.addItem(item)
            if path == self._shown:
                self.list.setCurrentItem(item)
            try:
                stamp = os.path.getmtime(path)
            except OSError:
                stamp = None
            # Also retried: a placeholder (the file may have come down since).
            if self._thumb_stamps.get(path) != stamp or self.list.pixmaps.get(path) is None:
                self._thumb_stamps[path] = stamp
                self.list.pixmaps.pop(path, None)
                queue.append(path)
        self.list.blockSignals(False)
        self._update_counts()
        start = not self._thumb_queue
        self._thumb_queue = queue
        if queue and start:
            QtCore.QTimer.singleShot(0, self._load_next_thumb)

    def _load_next_thumb(self):
        if not self._thumb_queue:
            return
        path = self._thumb_queue.pop(0)
        try:
            self.list.pixmaps[path] = load_thumbnail(path)
        except Exception:
            self.list.pixmaps[path] = None
        self.list.viewport().update()
        if self._thumb_queue:
            QtCore.QTimer.singleShot(0, self._load_next_thumb)

    def _item_clicked(self, item):
        """Show an image by hand; it stays until another setup is activated."""
        self._display(item.data(Qt.UserRole))

    def _follow_toggled(self, on):
        _settings().setValue("follow", "true" if on else "false")
        self._button_icons()
        if on:
            self._sync(force=True)

    def _show_toggled(self, on):
        self._button_icons()
        self._display(self._shown)

    # -- Helpers ------------------------------------------------------------
    def set_status(self, text, warn=False):
        self.status_label.setStyleSheet(
            "color: {};".format(T["warn"] if warn else T["text_faint"]))
        self.status_label.setText(text)

    def closeEvent(self, event):
        self._poll_timer.stop()
        self._thumb_queue = []
        try:
            watch_saves(False)
            draw_comments([])               # leave no callback behind
        except Exception:
            pass
        if self.overlay is not None:
            self.overlay.set_notes([])
            self.overlay.deleteLater()
        save_geometry(self)
        super(BackdropDockWidget, self).closeEvent(event)


# ---------------------------------------------------------------------------
# Settings kept between sessions: window position, theme, folder per scene
# ---------------------------------------------------------------------------
def _settings():
    # BACKDROP_SETTINGS lets the tests use a store of their own instead of
    # overwriting the user's.
    return QtCore.QSettings("AD Tools", os.environ.get("BACKDROP_SETTINGS", "Backdrop"))


def scene_path():
    try:
        return os.path.join(str(rt.maxFilePath), str(rt.maxFileName)).lower()
    except Exception:
        return ""


def _scene_id(scene, kind):
    return kind + "/" + hashlib.md5(scene.encode("utf-8")).hexdigest()


def stored_folder(scene, kind="folders"):
    """Folder kept for this scene file ("folders": images, "comments":
    comment files), or None when nothing was ever chosen for it."""
    try:
        value = _settings().value(_scene_id(scene, kind)) if scene else None
        return None if value is None else str(value)
    except Exception:
        return None


def load_folder(scene, kind="folders"):
    """Folder of this scene file. Folders belong to the scene they were
    chosen in: a scene without its own (a new one too) starts empty."""
    return stored_folder(scene, kind) or ""


def save_folder(scene, folder, kind="folders"):
    try:
        settings = _settings()
        if kind == "folders" and folder:
            settings.setValue("last_folder", folder)    # where "Choose..." opens
        if scene:
            settings.setValue(_scene_id(scene, kind), folder)
    except Exception as e:
        print("Backdrop: could not save the folder ({})".format(e))


def last_folder():
    try:
        return str(_settings().value("last_folder") or "")
    except Exception:
        return ""


# Set by a #filePostSave callback while the panel is open: tells "the scene got
# a new name by Save As" (its folders go with it) from "another scene was
# opened" (it has folders of its own, or none). A MAXScript global, so the
# callback needs nothing from Python.
SAVE_CALLBACK = "adtools_backdrop_saved"


def watch_saves(on):
    rt.execute("global bd_saved = false")
    rt.execute("callbacks.removeScripts id:#{}".format(SAVE_CALLBACK))
    if on:
        rt.execute("callbacks.addScript #filePostSave \"bd_saved = true\" id:#{}".format(
            SAVE_CALLBACK))


def scene_was_saved():
    """True once after a save of the scene; resets the flag."""
    try:
        saved = bool(rt.execute("bd_saved == true"))
        rt.execute("bd_saved = false")
        return saved
    except Exception:
        return False


def load_key():
    try:
        return str(_settings().value("deepl_key") or "")
    except Exception:
        return ""


def load_int(key, default):
    try:
        return int(_settings().value(key, default))
    except Exception:
        return default


def load_color(key, default):
    try:
        color = QtGui.QColor(str(_settings().value(key, default)))
    except Exception:
        color = QtGui.QColor()
    return color if color.isValid() else QtGui.QColor(default)


def _hidden_id(path, kind="hidden"):
    return kind + "/" + hashlib.md5(path.lower().encode("utf-8")).hexdigest()


def load_hidden(path, kind="hidden"):
    """Labels marked in this comments file: kind "hidden" = ticked off in the
    checklist, "unseen" = frame switched off on the viewport."""
    try:
        return set(x for x in str(_settings().value(_hidden_id(path, kind)) or "").split("|")
                   if x)
    except Exception:
        return set()


def save_hidden(path, labels, kind="hidden"):
    try:
        _settings().setValue(_hidden_id(path, kind), "|".join(sorted(labels)))
    except Exception as e:
        print("Backdrop: could not save the checklist ({})".format(e))


def load_theme_mode():
    try:
        mode = _settings().value("theme")
    except Exception:
        mode = None
    return mode if mode in ("dark", "light") else "auto"


def save_theme_mode(mode):
    try:
        _settings().setValue("theme", mode)
    except Exception as e:
        print("Backdrop: could not save the theme ({})".format(e))


def round_window_corners(widget):
    """Ask Windows 11 to round the corners of the floating panel
    (DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2)."""
    try:
        import ctypes
        preference = ctypes.c_int(2)
        return ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(int(widget.window().winId())), 33,
            ctypes.byref(preference), ctypes.sizeof(preference))
    except Exception:
        return None


def save_geometry(widget):
    try:
        collapsed = widget._collapsed
        size = widget._expanded_size if collapsed else widget.size()
        pos = widget._expanded_pos if collapsed and widget._expanded_pos else widget.pos()
        settings = _settings()
        settings.setValue("size", size)
        settings.setValue("pos", pos)
    except Exception as e:
        print("Backdrop: could not save window position ({})".format(e))


def restore_geometry(widget):
    try:
        settings = _settings()
        size = settings.value("size")
        pos = settings.value("pos")
        if isinstance(size, QtCore.QSize) and size.isValid():
            widget.resize(size)
        if isinstance(pos, QtCore.QPoint):
            target = QtCore.QRect(pos, widget.size())
            for screen in QtGui.QGuiApplication.screens():
                if screen.availableGeometry().intersects(target):
                    widget.move(pos)
                    break
    except Exception as e:
        print("Backdrop: could not restore window position ({})".format(e))


backdrop = None


def main():
    global backdrop
    try:
        main_window = qtmax.GetQMaxMainWindow()
        # Running the script again re-creates the module globals, so look the
        # previous panel up in Qt instead of trusting a Python variable.
        for old in main_window.findChildren(QtWidgets.QDockWidget, OBJECT_NAME):
            try:
                old.close()
            except Exception:
                pass
        for old in main_window.findChildren(QtWidgets.QWidget, OVERLAY_NAME):
            try:
                old.hide()
                old.deleteLater()
            except Exception:
                pass

        backdrop =BackdropDockWidget(parent=main_window)
        backdrop.setObjectName(OBJECT_NAME)
        backdrop.setFloating(True)
        restore_geometry(backdrop)
        backdrop.show()
        print("Backdrop {} loaded".format(VERSION))
    except Exception:
        import traceback
        print("Backdrop failed to start:\n{}".format(traceback.format_exc()))


def _run_isolated(path):
    """Load this file as the module MODULE_NAME and open the panel from it."""
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location(MODULE_NAME, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    module.main()


def _restore_shared(shared, namespace):
    """Put __main__ back: drop the names this file added, restore the ones it
    replaced (they may belong to another panel that is open)."""
    for name in list(namespace):
        if name in shared:
            namespace[name] = shared[name]
        elif not name.startswith("__"):
            del namespace[name]


if __name__ == '__main__':
    try:
        # Not __file__: under python.ExecuteFile it can still name the script
        # that was run before this one. The code object knows its own file.
        _run_isolated(_run_isolated.__code__.co_filename)
    except Exception:
        import traceback
        print("Backdrop failed to start:\n{}".format(traceback.format_exc()))
    finally:
        _restore_shared(_SHARED, globals())
