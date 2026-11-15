# Locked A–C art preview

Review toggle only. Does not change the live 8×8, the expansion ring, footprint edges, hitboxes, placement, `--s` shadow scale, navigation, or the daily battle win limit. Default is off, so existing town screens stay as they are until `?art=abc` or the menu control 「開啟美術預覽」.

| ID | What |
| --- | --- |
| TC-ART-ABC-01 | Locked JPEG SHA-256. Frame center is transparent and the wood rail is opaque. Guild crop corners are transparent and no opaque pixel is still the cream field. |
| TC-ART-ABC-02 | Re-running the derive functions matches the committed cutout pixels. |
| TC-ART-ABC-03 | `COLS`/`ROWS` stay 8. Overlap stays half-open (`<=`). Plaza file is not a map background. Guild footprint stays 2. Daily win sentence stays. |
| TC-ART-ABC-04 | `/kids/` serves the cutout PNG and the original JPEG. Python source stays 404. |
| TC-FE-ART-ABC-01 | `/kids/` without `?art=abc` does not show the frame. The menu has 「開啟美術預覽」. |
| TC-FE-ART-ABC-02 | With `?art=abc`, stage offset is 1280×720, scale is uniform, pads stay 64 buildable + 36 locked, pad width matches art-off, a locked click toasts the locked sentence, an empty click toasts the scene-1 sentence, and the footer tab is still the click target. |
| TC-FE-ART-ABC-03 | With `?art=abc`, 探險公會 uses the cutout, the image corner alpha is 0, the DOM name is 「探險公會」, and the contact-shadow node is still there. A non-guild building stays on the SVG. |
| TC-ART-ABC-05 | Preview port stays 9123 unless `--port` or `ART_PREVIEW_PORT` is set. `--port` wins. Isolated 9124 serves `/kids/` from a temp DB and does not change `kids_town.db`. |
