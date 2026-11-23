# Roadmap

What is planned, roughly in this order. Nothing here is promised or dated.

## Comments from more than Dropbox

Today the panel reads one format: the text file Dropbox saves with "Download comments".
The goal is to read review comments from other clouds that let a client mark a place on
an image, starting with Google Drive.

- **Sources as plug-ins.** One small reader per service, each turning its export or API
  answer into the same list the panel already draws: text, author, time and a region as
  fractions of the image. The cards, the pins and the translation stay as they are.
- **Google Drive** first. To find out before any code: whether its API or an export gives
  the region of a comment on an image, not only the text.
- **Other services** with region comments on images, picked by what users of the panel
  actually deliver through.
- **Choosing the source**: by the file found next to the image where the format tells,
  otherwise a setting per scene.

## Fetching comments without a manual download

- **Dropbox.** The public API has no comments endpoint. An undocumented route
  (`comments2/list_comments`) still answers; whether it works with an app token and
  returns regions is not known yet. `tools/test_dropbox_comments.ps1` asks it.
- For services with a documented comments API: sign in once, then refresh from the panel.

## Translation

- Target language as a setting (Russian is fixed today).
- A second translator next to DeepL if its quality on short review notes is not enough.

## Pulze Scene Manager 3

Waits for Scene Manager 3 to leave beta. Scene Manager 2 has no call to activate a setup,
so today the link works one way: a setup activated there changes the image here.

- **A click on a preview activates its setup** in Scene Manager, through the local API of
  version 3.
- **The active setup asked from Scene Manager** instead of read from the file name of the
  render output, which stays as the fallback for scenes without it.

## Panel

- Website with screenshots and a demo, like the one of Layer Manager.
