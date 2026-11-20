# Changelog

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
