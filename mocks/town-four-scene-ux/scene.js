/* Four-scene kid loop. Demo state only — no API.
   Spend happens only when the kid confirms a place or an upgrade.
   Cancel never touches the purse. Building art stays in the locked proof pack. */
(function () {
  var COLS = 6;
  var ROWS = 5;
  var ASSET = "../town-building-proof/assets/";
  var START = { gold: 6000, wood: 240, brick: 180, glass: 12, gear: 90 };
  var SEED = { "0,2": "shop", "2,1": "library", "4,0": "farm" };

  var DEFS = [
    { id: "library", name: "圖書館", cost: { gold: 100, wood: 5 }, fns: ["借書", "還書"] },
    { id: "gym", name: "健身室", cost: { gold: 200, wood: 10, brick: 5 }, fns: ["鍛鍊", "休息一下"] },
    { id: "farm", name: "農場", cost: { gold: 300, wood: 15, brick: 10 }, fns: ["收成", "澆水"] },
    { id: "shop", name: "商店", cost: { gold: 500, wood: 20, brick: 15, gear: 5 }, fns: ["買賣", "睇貨架"] },
    { id: "hospital", name: "醫院", cost: { gold: 400, wood: 15, brick: 20 }, fns: ["睇醫生", "休息"] },
    { id: "expedition-guild", name: "探險公會", cost: { gold: 150, wood: 10, brick: 5 }, fns: ["接任務", "出發"] },
    { id: "workshop", name: "工坊", cost: { gold: 350, wood: 20, gear: 5 }, fns: ["整道具", "修理"] },
    { id: "lighthouse", name: "燈塔", cost: { gold: 800, wood: 30, brick: 25, gear: 15 }, fns: ["望海", "開燈"] },
    { id: "arena", name: "競技場", cost: { gold: 1000, wood: 40, brick: 30, gear: 20 }, fns: ["練習", "比試"] },
    { id: "observatory", name: "天文台", cost: { gold: 1500, wood: 50, brick: 40, gear: 25, glass: 3 }, fns: ["觀星", "記錄"] }
  ];

  var defById = {};
  DEFS.forEach(function (def) { defById[def.id] = def; });

  var UPGRADE_COST = { gold: 50, wood: 2 };
  var FN_COPY = {
    "借書": "借咗一本故事書",
    "還書": "書還好咗",
    "鍛鍊": "做完一輪鍛鍊",
    "休息一下": "休息好咗",
    "收成": "收成一籃菜",
    "澆水": "澆完水",
    "買賣": "買賣完成",
    "睇貨架": "睇完貨架",
    "睇醫生": "睇完醫生",
    "休息": "休息好咗",
    "接任務": "接咗一個任務",
    "出發": "準備出發",
    "整道具": "整好一件道具",
    "修理": "修理好咗",
    "望海": "望咗一望海",
    "開燈": "燈亮咗",
    "練習": "練習完一輪",
    "比試": "比試完一場",
    "觀星": "觀完星",
    "記錄": "寫低記錄"
  };

  var grid = clone(SEED);
  var res = clone(START);
  var levels = {};
  var fnMsg = {};
  var pads = [];
  var palBtns = {};
  var toastTimer = 0;
  var placeSeq = 0;
  var motionOn = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var state = {
    scene: 1,
    sheet: false,
    sheetId: "library",
    listOpen: false,
    pad: null,
    bldg: null,
    hover: null,
    fnsOpen: false,
    lastFn: null,
    placeBeat: false,
    confirm: false
  };

  var map = document.getElementById("townMap");
  var village = document.getElementById("village");
  var palette = document.getElementById("palette");
  var paletteGrid = document.getElementById("paletteGrid");
  var placeBar = document.getElementById("placeBar");
  var readyBar = document.getElementById("readyBar");
  var sheet = document.getElementById("actionSheet");
  var toast = document.getElementById("toast");

  function clone(obj) {
    var next = {};
    Object.keys(obj).forEach(function (key) { next[key] = obj[key]; });
    return next;
  }

  function keyOf(c, r) { return c + "," + r; }

  function findPos(id) {
    var found = null;
    Object.keys(grid).forEach(function (key) {
      if (grid[key] === id) {
        var bits = key.split(",");
        found = { c: Number(bits[0]), r: Number(bits[1]) };
      }
    });
    return found;
  }

  function costText(def) {
    var cost = def.cost;
    var parts = ["💰" + cost.gold];
    if (cost.wood) parts.push("🪵" + cost.wood);
    if (cost.brick) parts.push("🧱" + cost.brick);
    if (cost.gear) parts.push("⚙️" + cost.gear);
    if (cost.glass) parts.push("🪟" + cost.glass);
    return parts.join(" ");
  }

  function upgradeCostText() {
    return "💰" + UPGRADE_COST.gold + " 🪵" + UPGRADE_COST.wood;
  }

  function asset(id) {
    return ASSET + "bldg-" + id + "-iso" + (motionOn ? "" : "-still") + ".svg";
  }

  function showToast(message) {
    toast.hidden = false;
    toast.textContent = message;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.hidden = true; }, 2800);
  }

  function sameCell(a, b) {
    return !!(a && b && a.c === b.c && a.r === b.r);
  }

  function readyToPreview() {
    return !!(state.pad && state.bldg && !grid[keyOf(state.pad.c, state.pad.r)] && !findPos(state.bldg));
  }

  function canAfford(cost) {
    var names = Object.keys(cost);
    for (var i = 0; i < names.length; i += 1) {
      if ((res[names[i]] || 0) < cost[names[i]]) return false;
    }
    return true;
  }

  function spend(cost) {
    Object.keys(cost).forEach(function (name) {
      res[name] = (res[name] || 0) - cost[name];
    });
  }

  function levelOf(id) {
    return levels[id] || 1;
  }

  function sceneLabel() {
    if (state.sheet) return "場景 4 · 升級";
    if (state.scene === 2) return "場景 2 · 揀空地";
    if (state.scene === 3) return "場景 3 · 擺位置";
    return "場景 1 · 睇地圖";
  }

  function goScene(next) {
    if (next === 3 && !readyToPreview()) {
      showToast("先揀一塊空地，同一座未起嘅屋。");
      state.scene = 2;
      state.sheet = false;
      state.confirm = false;
      render();
      return;
    }
    state.sheet = false;
    state.confirm = false;
    state.scene = next;
    state.hover = null;
    if (next === 1) {
      state.listOpen = false;
      state.pad = null;
      state.bldg = null;
    }
    if (next === 3) state.listOpen = false;
    render();
  }

  function openSheet(id) {
    if (id && defById[id]) {
      if (id !== state.sheetId) {
        state.fnsOpen = false;
        state.lastFn = null;
      }
      state.sheetId = id;
    }
    state.sheet = true;
    render();
    var title = document.getElementById("sheetTitle");
    if (title) title.focus();
  }

  function closeSheet() {
    state.sheet = false;
    state.confirm = false;
    render();
  }

  function cancelPreview() {
    state.scene = 2;
    state.hover = null;
    showToast("已取消，資源未扣除（💰" + res.gold + "）");
    render();
  }

  function onPalette(id) {
    var def = defById[id];
    if (findPos(id)) {
      openSheet(id);
      return;
    }
    if (state.bldg === id) {
      state.bldg = null;
      render();
      return;
    }
    state.bldg = id;
    state.listOpen = true;
    render();
  }

  function onCell(c, r) {
    var occ = grid[keyOf(c, r)] || null;
    if (state.sheet) {
      if (occ) openSheet(occ);
      return;
    }
    if (state.scene === 1) {
      if (occ) openSheet(occ);
      else {
        var cta = document.getElementById("btnBuild");
        cta.classList.add("is-nudge");
        showToast("想喺呢度起屋？先撳「我要起屋」。");
        setTimeout(function () { cta.classList.remove("is-nudge"); }, 800);
      }
      return;
    }
    if (state.scene === 2) {
      if (occ) {
        openSheet(occ);
        return;
      }
      state.pad = sameCell(state.pad, { c: c, r: r }) ? null : { c: c, r: r };
      if (state.pad) state.listOpen = true;
      render();
      return;
    }
    if (state.scene === 3) {
      var moving = defById[state.bldg];
      if (occ) {
        showToast("呢度已經有" + defById[occ].name + "，唔可以放。");
        return;
      }
      if (sameCell(state.pad, { c: c, r: r })) {
        showToast("就係呢格。撳「確定放置」先至扣資源。");
        return;
      }
      state.pad = { c: c, r: r };
      showToast("「" + (moving ? moving.name : "屋") + "」搬去第 " + (c + 1) + " 欄第 " + (r + 1) + " 行。");
      render();
    }
  }

  function onConfirm() {
    if (!readyToPreview()) {
      showToast("呢格唔可以放。揀一塊空地。");
      render();
      return;
    }
    var def = defById[state.bldg];
    if (!canAfford(def.cost)) {
      showToast("資源唔夠起「" + def.name + "」。取消唔會扣。");
      render();
      return;
    }
    spend(def.cost);
    var id = state.bldg;
    var placed = { c: state.pad.c, r: state.pad.r };
    grid[keyOf(placed.c, placed.r)] = id;
    levels[id] = 1;
    state.pad = null;
    state.bldg = null;
    state.scene = 1;
    state.listOpen = false;
    state.hover = null;
    showToast("起好「" + def.name + "」。已扣 " + costText(def) + "。");
    state.placeBeat = true;
    render();
    celebrate("place", placed);
    var token = ++placeSeq;
    setTimeout(function () {
      if (token !== placeSeq) return;
      state.placeBeat = false;
      if (grid[keyOf(placed.c, placed.r)] === id) openSheet(id);
      else render();
    }, 680);
  }

  function onUpgrade() {
    var def = defById[state.sheetId];
    if (!def || !findPos(def.id)) {
      showToast("未起好，未可以升級。");
      return;
    }
    if (!canAfford(UPGRADE_COST)) {
      showToast("資源唔夠升級「" + def.name + "」。");
      render();
      return;
    }
    state.confirm = true;
    render();
  }

  function closeConfirm() {
    if (!state.confirm) return;
    state.confirm = false;
    showToast("已取消，未升級，資源未扣除。");
    render();
    var upgradeBtn = document.getElementById("btnUpgrade");
    if (upgradeBtn) upgradeBtn.focus();
  }

  function onUpgradeConfirm() {
    var def = defById[state.sheetId];
    if (!state.confirm || !def || !findPos(def.id)) return;
    if (!canAfford(UPGRADE_COST)) {
      state.confirm = false;
      showToast("資源唔夠升級「" + def.name + "」。");
      render();
      return;
    }
    state.confirm = false;
    spend(UPGRADE_COST);
    levels[def.id] = levelOf(def.id) + 1;
    showToast(def.name + " 升到 Lv." + levels[def.id] + "（示範）。");
    render();
    celebrate("upgrade", findPos(def.id));
    var upgradeBtn = document.getElementById("btnUpgrade");
    if (upgradeBtn) upgradeBtn.focus();
  }

  function cellBy(c, r) {
    for (var i = 0; i < pads.length; i += 1) {
      if (pads[i].c === c && pads[i].r === r) return pads[i];
    }
    return null;
  }

  function motionReduced() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function localPoint(host, clientX, clientY) {
    var hostRect = host.getBoundingClientRect();
    if (hostRect.width < 1) return null;
    return {
      x: (clientX - hostRect.left) * (host.offsetWidth / hostRect.width),
      y: (clientY - hostRect.top) * (host.offsetHeight / hostRect.height)
    };
  }

  /* Absolute left/top is the padding edge, not the border edge. */
  function pointInBox(host, clientX, clientY) {
    var rect = host.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    var style = window.getComputedStyle(host);
    var borderX = parseFloat(style.borderLeftWidth) || 0;
    var borderY = parseFloat(style.borderTopWidth) || 0;
    return {
      x: (clientX - rect.left) * (host.offsetWidth / rect.width) - borderX,
      y: (clientY - rect.top) * (host.offsetHeight / rect.height) - borderY
    };
  }

  /* Place plays on the new building while the sheet is still closed.
     Upgrade is the last child of the sheet, centered on the sheet art,
     so the wood panel paints underneath the gold. The confirm popup
     closes before this runs, so the burst is not covered. Reduced
     motion keeps one ring. */
  function celebrate(kind, cellPos) {
    var cell = cellPos ? cellBy(cellPos.c, cellPos.r) : null;
    var sheetOpen = !!(state.sheet && sheet && !sheet.hidden);
    var host = map;
    var point = null;
    if (!sheetOpen) {
      var sprite = cell && cell.sprite && !cell.sprite.hidden ? cell.sprite : null;
      if (!sprite) return;
      var spriteBox = sprite.getBoundingClientRect();
      point = localPoint(map, spriteBox.left + spriteBox.width / 2, spriteBox.top + spriteBox.height * 0.38);
    } else {
      var art = document.getElementById("sheetArt");
      var artBox = art.getBoundingClientRect();
      if (artBox.width < 1) return;
      host = sheet;
      point = pointInBox(sheet, artBox.left + artBox.width / 2, artBox.top + artBox.height * 0.55);
    }
    if (!point || !host) return;

    var reduced = motionReduced();
    var node = document.createElement("div");
    node.className = "fx-burst is-" + kind + (host === sheet ? " is-front" : "") + (reduced ? " is-quiet" : "");
    node.setAttribute("aria-hidden", "true");
    node.style.left = point.x + "px";
    node.style.top = point.y + "px";

    var ring = document.createElement("span");
    ring.className = "fx-ring";
    node.appendChild(ring);
    if (!reduced && kind === "upgrade") {
      var flash = document.createElement("span");
      flash.className = "fx-flash";
      node.appendChild(flash);
    }

    if (!reduced) {
      var count = kind === "place" ? 12 : 14;
      for (var i = 0; i < count; i += 1) {
        var bit = document.createElement("span");
        var shape = "is-coin";
        if (kind === "upgrade") shape = i % 2 === 0 ? "is-star" : "is-coin";
        else if (i % 3 === 0) shape = "is-star";
        else if (i % 3 === 1) shape = "is-leaf";
        bit.className = "fx-bit " + shape;
        var angle = (Math.PI * 2 * i) / count - Math.PI / 2;
        var dist = (kind === "place" ? 62 : 78) + (i % 3) * 16;
        var squash = kind === "place" ? 0.62 : 0.82;
        bit.style.setProperty("--dx", (Math.cos(angle) * dist).toFixed(1) + "px");
        bit.style.setProperty("--dy", (Math.sin(angle) * dist * squash).toFixed(1) + "px");
        bit.style.setProperty("--rot", (i * 36) + "deg");
        bit.style.animationDelay = ((i % 4) * 18) + "ms";
        node.appendChild(bit);
      }
      if (cell) {
        cell.el.classList.add("is-celebrating");
        setTimeout(function () { cell.el.classList.remove("is-celebrating"); }, 1150);
      }
    }

    host.appendChild(node);
    var removed = false;
    function cleanup() {
      if (removed) return;
      removed = true;
      if (node.parentNode) node.parentNode.removeChild(node);
    }
    setTimeout(cleanup, kind === "upgrade" ? 1400 : 1250);
  }

  function onOpenFn() {
    var def = defById[state.sheetId];
    if (!def || !findPos(def.id)) {
      showToast("未起好，未可以打開功能。");
      return;
    }
    state.fnsOpen = true;
    showToast("打開咗「" + def.name + "」嘅功能。揀一個掣試吓。");
    render();
    var first = document.querySelector("#sheetFns .fn");
    if (first) first.focus();
  }

  function onFn(label) {
    var def = defById[state.sheetId];
    if (!def || !findPos(def.id)) {
      showToast("未起好，未可以做呢個功能。");
      return;
    }
    state.fnsOpen = true;
    fnMsg[def.id] = def.name + "：" + (FN_COPY[label] || label) + "（示範）";
    state.lastFn = def.id + ":" + label;
    showToast(fnMsg[def.id]);
    render();
  }

  function buildPalette() {
    DEFS.forEach(function (def) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pal-btn";
      var img = document.createElement("img");
      img.alt = "";
      img.src = asset(def.id);
      var copy = document.createElement("span");
      var name = document.createElement("span");
      name.className = "pal-name";
      name.textContent = def.name;
      var cost = document.createElement("span");
      cost.className = "pal-cost";
      copy.appendChild(name);
      copy.appendChild(cost);
      btn.appendChild(img);
      btn.appendChild(copy);
      btn.addEventListener("click", function () { onPalette(def.id); });
      paletteGrid.appendChild(btn);
      palBtns[def.id] = btn;
    });
  }

  function buildGround() {
    var layer = document.createElement("div");
    layer.className = "ground";
    layer.setAttribute("aria-hidden", "true");
    village.appendChild(layer);
    for (var r = -1; r <= ROWS; r += 1) {
      for (var c = 0; c < COLS; c += 1) {
        if (r >= 0 && r < ROWS) continue;
        var diff = c - r;
        if (diff < -4 || diff > 5) continue;
        var tile = document.createElement("div");
        tile.className = "ground-tile";
        tile.style.setProperty("--c", String(c));
        tile.style.setProperty("--r", String(r));
        var img = document.createElement("img");
        img.alt = "";
        img.className = "slab";
        if (r >= ROWS) img.src = ASSET + "ground-path.svg";
        else if (r < 0) {
          img.src = ASSET + "ground-step.svg";
          tile.classList.add("is-raised");
        } else if ((c + r) % 2) img.src = ASSET + "ground-tile-alt.svg";
        else img.src = ASSET + "ground-tile.svg";
        tile.appendChild(img);
        layer.appendChild(tile);
      }
    }
  }

  function buildGrid() {
    buildGround();
    for (var r = 0; r < ROWS; r += 1) {
      for (var c = 0; c < COLS; c += 1) {
        var pad = document.createElement("div");
        pad.className = "pad";
        pad.style.setProperty("--c", String(c));
        pad.style.setProperty("--r", String(r));
        var slab = document.createElement("img");
        slab.className = "slab";
        slab.alt = "";
        slab.src = ASSET + "ground-plot.svg";
        var shadow = document.createElement("div");
        shadow.className = "shadow";
        shadow.hidden = true;
        shadow.setAttribute("aria-hidden", "true");
        var mark = document.createElement("img");
        mark.className = "mark";
        mark.alt = "";
        mark.hidden = true;
        var cap = document.createElement("p");
        cap.className = "cap";
        cap.hidden = true;
        var sprite = document.createElement("img");
        sprite.className = "sprite";
        sprite.alt = "";
        sprite.hidden = true;
        var ghost = document.createElement("img");
        ghost.className = "ghost";
        ghost.alt = "";
        ghost.hidden = true;
        var badge = document.createElement("span");
        badge.className = "badge";
        badge.hidden = true;
        var ring = document.createElement("span");
        ring.className = "focus-ring";
        ring.setAttribute("aria-hidden", "true");
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "cell-btn";
        pad.appendChild(slab);
        pad.appendChild(shadow);
        pad.appendChild(mark);
        pad.appendChild(sprite);
        pad.appendChild(ghost);
        pad.appendChild(badge);
        pad.appendChild(cap);
        pad.appendChild(ring);
        pad.appendChild(btn);
        village.appendChild(pad);
        var cell = {
          c: c, r: r, el: pad, btn: btn, mark: mark, shadow: shadow,
          sprite: sprite, ghost: ghost, cap: cap, badge: badge
        };
        pads.push(cell);
        (function (cell) {
          btn.addEventListener("click", function (event) {
            if (event.detail !== 0) return;
            onCell(cell.c, cell.r);
          });
        })(cell);
      }
    }
  }

  function gridMetrics() {
    var pad = pads[0].el;
    var s = pad.offsetWidth / 160;
    return {
      stepX: 84 * s,
      stepY: 50 * s,
      origin: { x: pad.offsetLeft + 80 * s, y: pad.offsetTop + 121 * s }
    };
  }

  function localPoint(el, clientX, clientY) {
    var rect = el.getBoundingClientRect();
    var scaleX = rect.width / el.offsetWidth;
    var scaleY = rect.height / el.offsetHeight;
    return {
      x: (clientX - rect.left) / scaleX + el.scrollLeft,
      y: (clientY - rect.top) / scaleY + el.scrollTop
    };
  }

  function cellAt(clientX, clientY) {
    var rect = village.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    var scaleX = rect.width / village.offsetWidth;
    var inside = (clientX - rect.left) / scaleX;
    if (inside < 0 || inside > village.clientWidth) return null;
    var point = localPoint(village, clientX, clientY);
    var metrics = gridMetrics();
    var dx = point.x - metrics.origin.x;
    var dy = point.y - metrics.origin.y;
    var cf = 0.5 * (dx / metrics.stepX + dy / metrics.stepY);
    var rf = 0.5 * (dy / metrics.stepY - dx / metrics.stepX);
    var c = Math.round(cf);
    var r = Math.round(rf);
    if (Math.abs(cf - c) > 0.501 || Math.abs(rf - r) > 0.501) return null;
    if (c < 0 || r < 0 || c >= COLS || r >= ROWS) return null;
    return { c: c, r: r };
  }

  function renderCell(cell) {
    var occ = grid[keyOf(cell.c, cell.r)] || null;
    var picked = sameCell(state.pad, cell);
    var showGhost = state.scene === 3 && picked && !!state.bldg;
    var hot = state.scene === 2 && !occ;
    var kind = "quiet";
    if (state.scene === 2 && !occ) kind = picked ? "chosen" : "empty";
    if (state.scene === 3 && occ) kind = "illegal";
    else if (state.scene === 3 && !occ) kind = picked ? "preview" : "valid";

    cell.el.className = "pad is-" + kind + (hot ? " is-empty-hot" : "");

    if (showGhost) {
      cell.ghost.hidden = false;
      var ghostSrc = asset(state.bldg);
      if (cell.ghost.getAttribute("src") !== ghostSrc) cell.ghost.src = ghostSrc;
    } else {
      cell.ghost.hidden = true;
    }

    cell.shadow.hidden = !(occ || showGhost);

    if (occ) {
      cell.sprite.hidden = false;
      var spriteSrc = asset(occ);
      if (cell.sprite.getAttribute("src") !== spriteSrc) cell.sprite.src = spriteSrc;
      cell.cap.hidden = false;
      cell.cap.textContent = defById[occ].name;
    } else {
      cell.sprite.hidden = true;
      cell.cap.hidden = true;
    }

    if (kind === "empty" || kind === "valid") {
      cell.mark.hidden = false;
      cell.mark.src = ASSET + "cell-valid.svg";
      cell.badge.hidden = true;
    } else if (kind === "chosen" || kind === "preview") {
      cell.mark.hidden = false;
      cell.mark.src = ASSET + "cell-valid.svg";
      cell.badge.hidden = false;
      cell.badge.textContent = kind === "preview" ? "預覽" : "呢格";
      cell.badge.className = "badge is-pick";
    } else if (kind === "illegal") {
      cell.mark.hidden = false;
      cell.mark.src = ASSET + "cell-illegal.svg";
      cell.badge.hidden = false;
      cell.badge.textContent = "唔得";
      cell.badge.className = "badge is-bad";
    } else {
      cell.mark.hidden = true;
      cell.badge.hidden = true;
    }

    var label = "第 " + (cell.c + 1) + " 欄第 " + (cell.r + 1) + " 行";
    if (occ && state.scene === 1) label = defById[occ].name + "，撳一下睇升級同功能";
    else if (occ) label = defById[occ].name + "，已起";
    else if (state.scene === 1) label += "，空地。想起屋要先去場景 2";
    else if (state.scene === 2) label += picked ? "，已揀呢格" : "，空地，撳一下就揀";
    else if (kind === "illegal") label += "，已經有屋，唔可以放";
    else if (kind === "preview") label += "，擺放預覽";
    else if (kind === "valid") label += "，可以放，撳一下就搬去呢格";
    cell.btn.setAttribute("aria-label", label);
  }

  function renderPalette() {
    DEFS.forEach(function (def) {
      var btn = palBtns[def.id];
      var placed = findPos(def.id);
      var pressed = state.bldg === def.id && !placed;
      btn.setAttribute("aria-pressed", pressed ? "true" : "false");
      btn.classList.toggle("is-placed", !!placed);
      btn.querySelector(".pal-cost").textContent = placed ? "已起 · 可睇升級" : costText(def);
      var img = btn.querySelector("img");
      var next = asset(def.id);
      if (img.getAttribute("src") !== next) img.src = next;
      btn.setAttribute("aria-label", placed
        ? def.name + "，已起，撳一下打開升級面板"
        : def.name + "，" + costText(def) + "，撳一下就揀來起");
    });
    document.getElementById("placedCount").textContent = "已起 " + Object.keys(grid).length + "/10";
  }

  function renderResources() {
    ["gold", "wood", "brick", "glass", "gear"].forEach(function (name) {
      document.getElementById("res-" + name).textContent = String(res[name]);
    });
  }

  function renderRail() {
    var current = state.sheet ? 4 : state.scene;
    document.getElementById("sceneChip").textContent = sceneLabel();
    document.querySelectorAll(".step").forEach(function (btn) {
      var n = Number(btn.getAttribute("data-scene"));
      if (n === current) btn.setAttribute("aria-current", "step");
      else btn.removeAttribute("aria-current");
    });
  }

  function renderBars() {
    var showReady = state.scene === 2 && !state.sheet;
    var showPlace = state.scene === 3 && !state.sheet;
    readyBar.hidden = !showReady;
    placeBar.hidden = !showPlace;
    document.getElementById("btnBuild").hidden = state.scene !== 1 || state.sheet || state.placeBeat;
    document.getElementById("listLauncher").hidden = !(state.scene === 2 && !state.listOpen && !state.sheet);
    palette.hidden = !(state.scene === 2 && state.listOpen && !state.sheet);
    document.getElementById("hint").hidden = state.sheet || state.scene === 3 || (state.scene === 2 && state.listOpen);

    if (showReady) {
      var status = document.getElementById("readyStatus");
      var go = document.getElementById("btnToScene3");
      go.disabled = !readyToPreview();
      if (readyToPreview()) {
        status.textContent = "已揀「" + defById[state.bldg].name + "」同呢格空地。去場景 3 睇預覽。確定先至扣資源。";
      } else if (state.pad && !state.bldg) {
        status.textContent = "已揀空地。打開清單，揀一座未起嘅屋。";
      } else if (state.bldg && !state.pad) {
        status.textContent = "已揀「" + defById[state.bldg].name + "」。再點一塊金色空地。";
      } else {
        status.textContent = "點金色空地，或者打開清單揀一座未起嘅屋。";
      }
    }

    if (showPlace) {
      var def = defById[state.bldg];
      var placeOk = readyToPreview();
      var afford = !!(def && canAfford(def.cost));
      var confirm = document.getElementById("btnConfirm");
      confirm.disabled = !(placeOk && afford);
      confirm.textContent = "確定放置";
      if (placeOk && afford) {
        document.getElementById("placeStatus").textContent =
          "預覽「" + def.name + "」· " + costText(def) + "。點其他金色格可以搬位。確定先至扣資源，取消保持 💰" + res.gold + "。";
      } else if (placeOk) {
        document.getElementById("placeStatus").textContent =
          "資源唔夠起「" + def.name + "」（要 " + costText(def) + "）。取消唔會扣。";
      } else {
        document.getElementById("placeStatus").textContent = "呢格唔可以放。揀一塊金色空地。取消唔會扣。";
      }
    }

    var hint = document.getElementById("hint");
    if (state.scene === 1) hint.textContent = "圖書館、農場、商店已經起好。周圍睇吓，或者撳「我要起屋」。";
    else if (state.scene === 2) hint.textContent = "金色格係空地。點一格，或者打開建築清單。";
  }

  function renderSheet() {
    sheet.hidden = !state.sheet;
    if (!state.sheet) return;
    var def = defById[state.sheetId] || defById.library;
    state.sheetId = def.id;
    var placedHere = !!findPos(def.id);
    var upgradeBtn = document.getElementById("btnUpgrade");
    var openBtn = document.getElementById("btnOpenFn");
    document.getElementById("sheetTitle").textContent = def.name;
    document.getElementById("sheetLevel").textContent = "Lv." + levelOf(def.id) + " · 示範";
    document.getElementById("sheetNote").textContent = fnMsg[def.id]
      ? fnMsg[def.id]
      : (placedHere
        ? (state.fnsOpen
          ? "功能打開咗。揀下面一個掣試吓，呢度只係示範。"
          : "可以升級，或者打開功能。撳「升級」會彈出確認窗，確定先至扣。")
        : "放好之後先至可以升級同打開功能。");
    document.getElementById("sheetCost").textContent = placedHere
      ? ("升級要 " + upgradeCostText())
      : "未起好，未有升級費用";
    var art = document.getElementById("sheetArt");
    var next = asset(def.id);
    if (art.getAttribute("src") !== next) art.src = next;
    upgradeBtn.disabled = !placedHere || !canAfford(UPGRADE_COST);
    upgradeBtn.textContent = placedHere ? "升級" : "未起好，未可以升級";
    upgradeBtn.setAttribute("aria-expanded", state.confirm ? "true" : "false");
    openBtn.disabled = !placedHere;
    openBtn.textContent = "打開功能";
    openBtn.setAttribute("aria-pressed", state.fnsOpen ? "true" : "false");

    var picks = document.getElementById("sheetPicks");
    picks.textContent = "";
    Object.keys(grid).forEach(function (key) {
      var id = grid[key];
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = defById[id].name;
      btn.setAttribute("aria-pressed", id === def.id ? "true" : "false");
      btn.addEventListener("click", function () { openSheet(id); });
      picks.appendChild(btn);
    });

    var fns = document.getElementById("sheetFns");
    fns.textContent = "";
    fns.classList.toggle("is-open", !!state.fnsOpen && placedHere);
    def.fns.forEach(function (label) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "fn";
      btn.disabled = !placedHere;
      btn.textContent = label;
      btn.setAttribute("aria-pressed", state.lastFn === def.id + ":" + label ? "true" : "false");
      btn.addEventListener("click", function () { onFn(label); });
      fns.appendChild(btn);
    });
  }

  function renderConfirm() {
    var modal = document.getElementById("upgradeConfirm");
    var opening = state.confirm && modal.hidden;
    modal.hidden = !state.confirm;
    if (!state.confirm) return;
    var def = defById[state.sheetId] || defById.library;
    document.getElementById("upgradeConfirmCopy").textContent =
      "「" + def.name + "」而家 Lv." + levelOf(def.id) +
      "，升級到 Lv." + (levelOf(def.id) + 1) +
      " 會扣 " + upgradeCostText() + "。確定先至扣，取消只關呢個視窗。";
    if (opening) modal.focus();
  }

  function renderMotion() {
    var btn = document.getElementById("btnMotion");
    btn.setAttribute("aria-pressed", motionOn ? "true" : "false");
    btn.textContent = motionOn ? "動畫 開" : "動畫 關";
  }

  function render() {
    var current = state.sheet ? 4 : state.scene;
    map.className = "map is-scene-" + state.scene
      + (state.listOpen && state.scene === 2 && !state.sheet ? " is-list-open" : " is-list-closed")
      + (state.sheet ? " is-sheet" : "");
    map.setAttribute("aria-label", sceneLabel());
    document.getElementById("btnListToggle").textContent = "收起清單";
    pads.forEach(renderCell);
    renderPalette();
    renderResources();
    renderRail();
    renderBars();
    renderSheet();
    renderConfirm();
    renderMotion();
    document.getElementById("townMap").dataset.scene = String(current);
  }

  function bootFromUrl() {
    var q = new URLSearchParams(location.search);
    var scene = Number(q.get("scene") || "1");
    var pad = q.get("pad");
    var bldg = q.get("bldg");
    if (pad) {
      var bits = pad.split(",");
      var c = Number(bits[0]);
      var r = Number(bits[1]);
      if (c >= 0 && r >= 0 && c < COLS && r < ROWS && !grid[keyOf(c, r)]) state.pad = { c: c, r: r };
    }
    if (bldg && defById[bldg] && !findPos(bldg)) state.bldg = bldg;
    if (q.get("list") === "1") state.listOpen = true;
    if (scene === 4) {
      state.scene = 1;
      state.sheet = true;
      if (bldg && defById[bldg]) state.sheetId = bldg;
      state.confirm = q.get("confirm") === "1" && !!findPos(state.sheetId);
    } else if (scene === 3) {
      if (!state.pad) state.pad = { c: 1, r: 0 };
      if (!state.bldg) state.bldg = "gym";
      if (readyToPreview()) {
        state.scene = 3;
        state.listOpen = false;
      } else state.scene = 2;
    } else if (scene === 2) {
      state.scene = 2;
    } else {
      state.scene = 1;
      state.listOpen = false;
    }
  }

  function fit() {
    var stage = document.querySelector(".stage");
    if (!stage) return;
    var params = new URLSearchParams(location.search);
    if (params.has("native")) {
      document.body.classList.add("is-native");
      stage.style.transform = "none";
      return;
    }
    var vv = window.visualViewport;
    if (vv && vv.scale > 1.02) return;
    document.body.classList.remove("is-native");
    var scale = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
    stage.style.transform = "translate(-50%, -50%) scale(" + scale + ")";
  }

  function onReset() {
    grid = clone(SEED);
    res = clone(START);
    levels = {};
    fnMsg = {};
    state.scene = 1;
    state.sheet = false;
    state.sheetId = "library";
    state.listOpen = false;
    state.pad = null;
    state.bldg = null;
    state.hover = null;
    state.fnsOpen = false;
    state.lastFn = null;
    state.placeBeat = false;
    state.confirm = false;
    placeSeq += 1;
    showToast("示範已重置。資源返到 💰6000。");
    render();
  }

  buildPalette();
  buildGrid();
  bootFromUrl();
  render();
  fit();
  window.addEventListener("resize", fit);
  if (window.visualViewport) window.visualViewport.addEventListener("resize", fit);

  document.getElementById("btnBuild").addEventListener("click", function () { goScene(2); });
  document.getElementById("listLauncher").addEventListener("click", function () {
    state.listOpen = true;
    render();
    var first = paletteGrid.querySelector("button");
    if (first) first.focus();
  });
  document.getElementById("btnListToggle").addEventListener("click", function () {
    state.listOpen = false;
    render();
    document.getElementById("listLauncher").focus();
  });
  document.getElementById("btnBack").addEventListener("click", function () { goScene(1); });
  document.getElementById("btnToScene3").addEventListener("click", function () { goScene(3); });
  document.getElementById("btnCancel").addEventListener("click", cancelPreview);
  document.getElementById("btnConfirm").addEventListener("click", onConfirm);
  document.getElementById("btnUpgrade").addEventListener("click", onUpgrade);
  document.getElementById("btnUpgradeConfirm").addEventListener("click", onUpgradeConfirm);
  document.getElementById("btnUpgradeCancel").addEventListener("click", closeConfirm);
  document.getElementById("upgradeConfirm").addEventListener("click", function (event) {
    if (event.target === document.getElementById("upgradeConfirm")) closeConfirm();
  });
  document.getElementById("btnOpenFn").addEventListener("click", onOpenFn);
  document.getElementById("btnCloseSheet").addEventListener("click", closeSheet);
  document.getElementById("btnReset").addEventListener("click", onReset);
  document.getElementById("btnMotion").addEventListener("click", function () {
    motionOn = !motionOn;
    render();
  });

  document.querySelectorAll(".step").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var n = Number(btn.getAttribute("data-scene"));
      if (n === 4) openSheet(state.sheetId);
      else goScene(n);
    });
  });

  village.addEventListener("click", function (event) {
    if (event.target.closest(".cell-btn")) return;
    var hit = cellAt(event.clientX, event.clientY);
    if (hit) onCell(hit.c, hit.r);
    else if (state.scene === 2 && !state.sheet) showToast("點金色格先至係空地。");
  });

  document.addEventListener("keydown", function (event) {
    if (state.confirm) {
      var modal = document.getElementById("upgradeConfirm");
      if (event.key === "Escape") {
        event.preventDefault();
        closeConfirm();
        return;
      }
      if (event.key === "Tab" && modal) {
        var items = Array.prototype.filter.call(
          modal.querySelectorAll("button, [href], [tabindex]:not([tabindex='-1'])"),
          function (el) { return !el.disabled; }
        );
        if (!items.length) return;
        var first = items[0];
        var last = items[items.length - 1];
        var active = document.activeElement;
        if (event.shiftKey && (active === first || active === modal || !modal.contains(active))) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && (active === last || !modal.contains(active))) {
          event.preventDefault();
          first.focus();
        }
      }
      return;
    }
    if (event.key !== "Escape") return;
    if (state.sheet) closeSheet();
    else if (state.scene === 3) cancelPreview();
    else if (state.scene === 2) goScene(1);
  });

  var menu = document.querySelector(".mb");
  if (menu) menu.addEventListener("click", function () { showToast("四場景稿未接主目錄"); });
  document.querySelectorAll(".footer-tab:not([aria-current='page'])").forEach(function (tab) {
    tab.addEventListener("click", function () { showToast("四場景稿只示範城鎮首頁"); });
  });
})();
