# Locked A–C art preview

Review toggle only. The 8×8, expansion ring, footprint edges, and daily battle win limit stay. Default is off, so `--s` stays 0.85 until `?art=abc`. With the preview on, `--s` shrinks so the ring fits the opening, and the contact shadow shrinks with it.

| ID | What |
| --- | --- |
| TC-ART-ABC-01 | Locked JPEG SHA-256. Frame center is transparent and the wood rail is opaque. Guild crop corners are transparent and no opaque pixel is still the cream field. |
| TC-ART-ABC-02 | Re-running the derive functions matches the committed cutout pixels. |
| TC-ART-ABC-03 | `COLS`/`ROWS` stay 8. Overlap stays half-open (`<=`). Plaza file is not a map background. Guild footprint stays 2. Daily win sentence stays. |
| TC-ART-ABC-04 | `/kids/` serves the cutout PNG and the original JPEG. Python source stays 404. |
| TC-FE-ART-ABC-01 | `/kids/` without `?art=abc` does not show the frame. The menu has 「開啟美術預覽」. |
| TC-FE-ART-ABC-02 | With `?art=abc`, the stage stays 1280×720 and letterboxes. The frame is zoomed (thinner rim). `--s` drops below 0.85 so the 8×8 plus the locked ring fit with no scrollbar. Clicks still hit the locked ring and an empty cell. |
| TC-FE-ART-ABC-03 | With `?art=abc`, 探險公會 uses the cutout, the image corner alpha is 0, the DOM name is 「探險公會」, and the contact-shadow node is still there. A non-guild building stays on the SVG. |
| TC-FE-ART-ABC-04 | The main menu stays inside the stage with preview on or off. Footer 「公會大廳」 still switches tabs while the menu is open, and the backdrop does not remain. |
| TC-ART-ABC-05 | Preview port stays 9123 unless `--port` or `ART_PREVIEW_PORT` is set. `--port` wins. Isolated 9124 serves `/kids/` from a temp DB and does not change `kids_town.db`. |
