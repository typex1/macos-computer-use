# draw.io desktop (Electron)

`ax.py --app draw.io` exposes the full UI. The active document is
`AXFocusedWindow` of the app; several windows may be open.

## Anchors

- Menus: `PopUpButton 'File' | 'Edit' | 'View' | 'Arrange' | 'Extras' | 'Help'`.
- Shape search: `TextField 'Type / to search'` at the top of the left sidebar.
- Scratchpad and library shapes are `Button ''` elements containing
  `StaticText` labels (e.g. 'Rectangle', 'Ellipse', or cloud icons by name).
  Clicking a shape inserts it at the centre of the current view, selected.
- Page tabs along the bottom are buttons titled with the page names.
- Inserted shapes show up in `find` as `StaticText` with their label at the
  canvas position; use that to verify an insert without a screenshot.

## Verified

- `ax.py --app draw.io click "<shape label>" --role StaticText` inserted a
  Scratchpad shape into the open diagram; a second `find` showed the new label
  on the canvas.
