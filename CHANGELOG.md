# Changelog

## Unreleased

### Added
- Scenes without Pulze Scene Manager: when no image is named like the render output, the
  image is looked for by the output file of a Batch Render view of the viewed camera, then
  by the name of that camera. The status line says what it was found by, and lists the
  names tried when nothing fits.
- A click on a preview puts the camera of that image in the viewport: the one with a Batch
  Render view saving to that name, or the one named like the image.
- In a scene with setups of Pulze Scene Manager 2 that click takes the camera, the frame,
  the shown and hidden layers, the render output file and the resolution of the setup
  named like the image, read from the saved scene file; the picked setup is the active one in the panel until another is activated
  in Scene Manager or the camera is changed. The rest of the setup is not applied.

## a0.006

### Added
- Comments of Google Drive by a link: *folder button → Google Drive link…* takes the link
  of a folder or of one image, the browser opens Google's sign-in, and the comments of
  every image are fetched with their frames. Needs an OAuth client of your own, chosen
  with *Google client file…*; the link is kept per scene. Guide: `docs/google-drive.md`.
  It opens from the panel: *folder button → How to connect Google Drive…*
- *Comments from: Dropbox files / Google Drive* in the folder menu: a scene shows the
  comments of one service at a time. A fetch switches to Drive, removing the link or
  signing out of Google switches back to the Dropbox files.
- The answer of the Drive API method `comments.list`, saved by hand as
  `<image name> Google Drive Comments.json`, is read like a Dropbox file.

## a0.005

### Added
- Right click on a comment card: copy its text (the translation or the original), open a
  web address from the comment in the browser or copy it.

### Changed
- The text of the picked comment on the viewport is a block wrapped to several lines and
  shown in full, placed above its frame or under it. Before, it was one line cut at 90
  characters.

### Fixed
- Entries without text in a Dropbox export (author *Unknown*, no annotation) were shown as
  empty cards. They are left out, as in Dropbox itself.

## a0.004

### Added
- An eye on every comment card hides that comment on the viewport without ticking it off.
- *Clear the folders of this scene* in the folder menu.

### Changed
- The image and the comment frames are shown only on a viewport that looks through a
  camera: the active one if it is a camera view, else the first camera view of the layout.
  With no camera view nothing is shown. Before, the image went on whatever view was active
  and the frames followed it.
- Folders are kept strictly per scene: a new or another scene starts without folders
  instead of taking over the last ones. *Save As* keeps the folders of the scene.

## a0.003

### Fixed
- The preview grid lost a column as soon as its scroll bar appeared.
- The month in the time of a comment followed the Windows locale; it is in English now,
  like the rest of the panel.

## a0.002

First public version.

### Added
- The delivered image of the active setup behind the viewport. The image is found by name:
  the file name of the render output (Render Setup > Common > Render Output, the field
  Pulze Scene Manager writes when a setup is activated) against the images of a folder.
  Activating another setup swaps the picture.
- Grid of image previews; a click shows any image by hand. The folder is remembered per
  scene file. Files that exist only in the cloud are shown as placeholders, not downloaded.
- Dropbox comments: the file "Download comments" saves for an image is picked up by its
  name, next to the images, in Downloads or in a folder of its own.
- Comment frames over the viewport, drawn by a click-through overlay: a numbered pin on
  every frame, the comment picked in the panel highlighted with its text. Text size,
  colours and opacity can be set.
- Comments as cards with author and time; a click on the pin ticks a comment off, the
  badge on the thumbnail counts what is left.
- Translation of the comments into Russian with DeepL and the user's own API key. The key
  is checked when entered; translations are cached on the computer.
- Dark and light palettes, picked from the 3ds Max colour scheme or with the title bar button.
- Toolbar icon.

### Fixed
- Requests to DeepL failed with "certificate has expired": Python loads the expired
  certificates of the Windows stores too. They are now left out.
- Another script with functions of the same name could replace the panel's own (3ds Max
  runs every Python script in one shared namespace). The panel runs as a module of its own.
