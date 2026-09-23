# Kids Town shared footer — builder specification

**Status:** user-approved fixed 5-tab layout from the guild board mock  
**Stage:** 1280×720 fixed landscape  
**Implementation owner:** builder, as the shared component in **PR #20**

## 1. Product contract

- Render this **same footer component on every page**. Page navigation changes only the selected tab; it must never swap to a different footer design or tab order.
- The five tabs, in fixed order, are:

  | Order | ID | Traditional Chinese label | Icon |
  |---:|---|---|---|
  | 1 | `town-home` | 城鎮首頁 | house |
  | 2 | `guild-hall` | 公會大廳 | people/group; may show an optional red notification badge |
  | 3 | `quest-board` | 任務板 | scroll/map |
  | 4 | `shop` | 商店 | market stall |
  | 5 | `backpack` | 背包 | satchel/backpack |

- 「查看所有公會任務」is a **page-contextual CTA on the `quest-board` screen**, never a footer item, label, or badge.
- Use Traditional Chinese labels exactly as listed. IDs, asset names, and ARIA references remain English.

## 2. Placement and geometry

- The footer occupies the bottom safe zone, approximately **y=624–720** on the 1280×720 stage. Target a visual height of **72–96px**; do not cover content above that reserved zone.
- The component is full stage width (or `width: 100%` inside the stage), bottom aligned, and visually attached to the stage edge.
- Use five equal-width tabs (`20%` each at the reference width). Every button has a minimum **44×44px** hit target; a practical reference tab is 256×80px.
- The bar is a warm cream/parchment surface with subtle wood/gold edging. Keep the tab contents centered and allow labels to remain legible when zoomed.
- The component may scale with the stage, but preserve the 5:1 structure and the minimum touch target in the rendered viewport.

## 3. Visual tokens

```css
:root {
  --footer-wood: #8b5e3c;
  --footer-wood-mid: #a67c52;
  --footer-gold: #d4a017;
  --footer-gold-bright: #f0c14b;
  --footer-cream: #faf6ef;
  --footer-ink: #3b2a1a;
  --footer-icon: #7a5b43;
  --footer-muted: #806b58;
  --footer-badge: #b52b2b;
  --footer-focus: #c45c26;
  --footer-disabled: #b9aa98;
}
```

- **Unselected:** `--footer-cream` bar/tab fill, soft brown icon and label (`--footer-icon` / `--footer-muted`).
- **Selected:** a clearly warmer/highlighted fill plus a golden frame or equivalent golden CSS chrome (`--footer-gold` / `--footer-gold-bright`). The selected state must be visually distinct without relying on color alone: add `aria-current="page"` and a frame/underline/highlight.
- Keep contrast readable against cream. Do not use neon, cold blue, or a dark full-width wood footer in place of the approved cream footer.

## 4. States

### Default / unselected

Show the cream/parchment tab surface, warm-brown icon, and warm-brown label. Use a restrained shadow or separator; do not make inactive tabs look disabled.

### Selected

Only the tab representing the current page receives selected chrome: warmer fill, gold frame/outline or inset border, and a slightly stronger icon/label. Keep its footprint and hit target identical to the other tabs so selection does not move the layout. The other four tabs stay unselected.

### Notification badge

`guild-hall` may include an optional small red badge for unread activity. The badge is an overlay inside the tab, near the icon's upper-right, with a short numeric value or accessible text supplied by the app. It must not change tab width or push the label. Omit it when there are no notifications. The badge is not a sixth tab.

```html
<span class="tab-badge" aria-label="3 則新通知">3</span>
```

### Focus

Keyboard focus must be visible with `:focus-visible`, for example:

```css
.footer-tab:focus-visible {
  outline: 3px solid var(--footer-focus);
  outline-offset: 3px;
  z-index: 2;
}
```

Do not remove the browser focus indicator without replacing it. Focus styling must work in both selected and unselected states.

### Disabled

A disabled tab is exceptional and should remain in the fixed order. Keep its 44px+ hit geometry, reduce icon/label opacity using `--footer-disabled`, remove hover/press affordances, and expose `disabled` to assistive technology. Never silently omit a tab or replace it with a different footer.

## 5. Icon assets

All icons are real transparent SVGs with a `64 64` viewBox, warm-brown stroke/fill, rounded joins/caps, and simple hand-drawn-ish cottagecore RPG shapes. They contain no text and no opaque background.

| File | Meaning | Suggested alt treatment |
|---|---|---|
| [`icon-town-home.svg`](./icon-town-home.svg) | house / town home | decorative when the button label is present |
| [`icon-guild-hall.svg`](./icon-guild-hall.svg) | two people / group | decorative; badge supplies notification text |
| [`icon-quest-board.svg`](./icon-quest-board.svg) | scroll/map quest board | decorative |
| [`icon-shop.svg`](./icon-shop.svg) | market stall | decorative |
| [`icon-backpack.svg`](./icon-backpack.svg) | satchel/backpack | decorative |

Use `<img alt="">` or an inline SVG with `aria-hidden="true"` when the visible Traditional Chinese label already names the destination. Do not bake labels into the SVGs.

## 6. Suggested HTML structure

The production builder should render one shared component and drive `selectedId` from the current route. The following is a structure sketch, not a second footer design:

```html
<nav class="shared-footer" aria-label="主要導覽">
  <ul class="footer-tabs">
    <li>
      <button class="footer-tab" type="button" data-tab-id="town-home">
        <img src="ui/icon-town-home.svg" alt="">
        <span>城鎮首頁</span>
      </button>
    </li>
    <li>
      <button class="footer-tab" type="button" data-tab-id="guild-hall">
        <span class="tab-icon-wrap">
          <img src="ui/icon-guild-hall.svg" alt="">
          <span class="tab-badge" aria-label="3 則新通知">3</span>
        </span>
        <span>公會大廳</span>
      </button>
    </li>
    <li>
      <button class="footer-tab" type="button" data-tab-id="quest-board" aria-current="page">
        <img src="ui/icon-quest-board.svg" alt="">
        <span>任務板</span>
      </button>
    </li>
    <li>
      <button class="footer-tab" type="button" data-tab-id="shop">
        <img src="ui/icon-shop.svg" alt="">
        <span>商店</span>
      </button>
    </li>
    <li>
      <button class="footer-tab" type="button" data-tab-id="backpack">
        <img src="ui/icon-backpack.svg" alt="">
        <span>背包</span>
      </button>
    </li>
  </ul>
</nav>
```

Prefer a real `<button>` for route-changing tabs (or an accessible link if routing requires links), never a non-semantic clickable `<div>`. Use `aria-current="page"` on exactly the selected destination and keep DOM order equal to the fixed order above.

## 7. CSS token suggestions

```css
.shared-footer {
  position: absolute;
  inset: auto 0 0;
  min-height: 72px;
  max-height: 96px;
  padding: 6px 12px 8px;
  background: var(--footer-cream);
  border-top: 3px solid var(--footer-wood-mid);
  border-radius: 18px 18px 0 0;
  box-shadow: 0 -5px 16px rgb(59 42 26 / 14%);
}
.footer-tabs { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; height: 100%; margin: 0; padding: 0; list-style: none; }
.footer-tab {
  position: relative;
  min-width: 44px;
  min-height: 44px;
  border: 2px solid transparent;
  border-radius: 14px;
  color: var(--footer-muted);
  background: transparent;
  font: inherit;
  cursor: pointer;
}
.footer-tab[aria-current="page"] {
  color: var(--footer-ink);
  background: #fff0c7;
  border-color: var(--footer-gold);
  box-shadow: inset 0 0 0 2px rgb(240 193 75 / 45%);
}
.footer-tab img { width: 40px; height: 40px; display: block; margin: 0 auto 2px; }
.footer-tab:disabled { color: var(--footer-disabled); cursor: not-allowed; }
```

A selected frame may be implemented as this pure CSS border/inset chrome; no separate frame image is required. If a future design exports a frame asset, it must not replace the cream bar or alter tab geometry.

## 8. Do / don't

**Do**

- Keep this exact order, IDs, labels, and shared appearance on every page.
- Keep labels in DOM for localization and accessibility; keep SVGs text-free.
- Preserve 44×44px minimum targets, visible keyboard focus, and zoom-friendly sizing.
- Keep the guild notification badge optional and visually attached to `guild-hall`.
- Test selected, unselected, badge, focus, disabled, keyboard, and reduced-motion behavior.

**Don't**

- Don't create page-specific footer variants, reorder tabs, or change the selected tab into a different component.
- Don't put 「查看所有公會任務」 in the footer; it belongs to the quest-board page content.
- Don't use icons alone, tiny targets, hidden focus, or color-only selection.
- Don't bake Traditional Chinese text, notification counts, or route state into SVG assets.
- Don't animate essential navigation. Respect `prefers-reduced-motion: reduce` by disabling nonessential transitions.

## 9. Builder handoff

Implement this as the shared footer component in **PR #20**. The static [`footer-strip.html`](./footer-strip.html) is a visual reference only: it demonstrates the identical five-tab footer twice, once with `quest-board` selected and once with `shop` selected. Production routing, notification data, and disabled-state logic remain in the builder's component.
