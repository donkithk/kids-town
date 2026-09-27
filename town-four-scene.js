/* Four-scene kid build loop on /kids/ town home.
   Spends only through the existing place / upgrade APIs. Cancel never spends.
   Pad picks use iso math so a back diamond wins under a front sprite. */
(function () {
  var COLS = 8;
  var ROWS = 8;
  var ASSET = "mocks/town-building-proof/assets/";
  var MOTION_KEY = "ktTownMotion";
  var MARK_VALID = ASSET + "cell-valid.svg";

  var ASSET_ID = {
    "圖書館": "library",
    "健身室": "gym",
    "農場": "farm",
    "商店": "shop",
    "醫院": "hospital",
    "探險公會": "expedition-guild",
    "工坊": "workshop",
    "燈塔": "lighthouse",
    "競技場": "arena",
    "天文台": "observatory"
  };

  var FN = {
    "圖書館": ["借書", "還書"],
    "健身室": ["鍛鍊", "休息一下"],
    "農場": ["收成", "澆水"],
    "商店": ["買賣", "睇貨架"],
    "醫院": ["睇醫生", "休息"],
    "探險公會": ["接任務", "出發"],
    "工坊": ["整道具", "修理"],
    "燈塔": ["望海", "開燈"],
    "競技場": ["練習", "比試"],
    "天文台": ["觀星", "記錄"]
  };

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

  var pads = [];
  var built = false;
  var placeSeq = 0;
  var motionOn = true;
  var state = {
    scene: 1,
    sheet: false,
    sheetDef: null,
    listOpen: false,
    pad: null,
    defId: null,
    unstoreId: null,
    note: ""
  };

  function $(id) { return document.getElementById(id); }

  function reducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function readMotion() {
    var raw = null;
    try { raw = localStorage.getItem(MOTION_KEY); } catch (e) { raw = null; }
    if (raw === "on") return true;
    if (raw === "off") return false;
    return !reducedMotion();
  }

  function readTown() {
    if (typeof ktReadTown === "function") return ktReadTown();
    return { buildings: [], inventory: [], points: 0, defs: [], kidId: null };
  }

  function buildings() {
    return readTown().buildings || [];
  }

  function defs() {
    return readTown().defs || [];
  }

  function parseMats(def) {
    var raw = def && def.materials;
    if (!raw) return {};
    if (typeof raw === "string") {
      try { return JSON.parse(raw) || {}; } catch (e) { return {}; }
    }
    return raw;
  }

  function sameCell(a, b) {
    return !!(a && b && a.c === b.c && a.r === b.r);
  }

  function occAt(c, r) {
    var list = buildings();
    for (var i = 0; i < list.length; i += 1) {
      var b = list[i];
      if ((b.stored | 0) === 1) continue;
      if ((b.cell_x | 0) === c && (b.cell_y | 0) === r) return b;
    }
    return null;
  }

  function defById(id) {
    var list = defs();
    for (var i = 0; i < list.length; i += 1) {
      if (String(list[i].id) === String(id)) return list[i];
    }
    return null;
  }

  function placedDef(defId) {
    var list = buildings();
    for (var i = 0; i < list.length; i += 1) {
      var b = list[i];
      if ((b.stored | 0) === 1) continue;
      if (String(b.def_id) === String(defId)) return b;
    }
    return null;
  }

  function storedRows() {
    var town = readTown();
    return town.storedBuildings || town.stored_buildings || [];
  }

  /* Owned but warehoused. Not a map 「已起」, and not a new-build sale. */
  function storedDef(defId) {
    var list = storedRows().slice();
    var owned = buildings();
    for (var i = 0; i < owned.length; i += 1) {
      if ((owned[i].stored | 0) === 1) list.push(owned[i]);
    }
    for (var j = 0; j < list.length; j += 1) {
      if (String(list[j].def_id) === String(defId)) return list[j];
    }
    return null;
  }

  function originOf(row) {
    if (!row || row.cell_x == null || row.cell_y == null) return null;
    return { id: row.id, x: row.cell_x | 0, y: row.cell_y | 0 };
  }

  /* unstored rejects a 2×2 whose cells hold another building origin or a tile. */
  function footprintFree(c, r, ignoreId) {
    if (c < 0 || r < 0 || c > COLS - 2 || r > ROWS - 2) return false;
    var blocks = buildings().concat(storedRows());
    var tiles = (typeof townData !== "undefined" && townData && townData.tiles) || [];
    for (var dy = 0; dy < 2; dy += 1) {
      for (var dx = 0; dx < 2; dx += 1) {
        var cx = c + dx;
        var cy = r + dy;
        for (var i = 0; i < blocks.length; i += 1) {
          var origin = originOf(blocks[i]);
          if (!origin) continue;
          if (ignoreId != null && String(origin.id) === String(ignoreId)) continue;
          if (origin.x === cx && origin.y === cy) return false;
        }
        for (var t = 0; t < tiles.length; t += 1) {
          var tile = tiles[t];
          if ((tile.cell_x | 0) === cx && (tile.cell_y | 0) === cy) return false;
        }
      }
    }
    return true;
  }

  function firstUnstorePad(ignoreId) {
    for (var r = 0; r < ROWS; r += 1) {
      for (var c = 0; c < COLS; c += 1) {
        if (occAt(c, r)) continue;
        if (footprintFree(c, r, ignoreId)) return { c: c, r: r };
      }
    }
    return null;
  }

  /* 建築清單放返 stays on the four-scene pad. The 存倉 tab still uses startUnstoreBuilding. */
  function placeFromStore(row) {
    if (!row) return;
    state.defId = row.def_id;
    state.unstoreId = row.id;
    state.sheet = false;
    state.listOpen = false;
    var padOk = state.pad
      && !occAt(state.pad.c, state.pad.r)
      && footprintFree(state.pad.c, state.pad.r, row.id);
    if (!padOk) state.pad = firstUnstorePad(row.id);
    state.scene = 3;
    render();
  }

  function readyToUnstore() {
    if (!state.unstoreId || !state.pad) return false;
    if (occAt(state.pad.c, state.pad.r)) return false;
    return footprintFree(state.pad.c, state.pad.r, state.unstoreId);
  }

  function assetSrc(name) {
    var id = ASSET_ID[name] || "shop";
    var still = motionOn ? "" : "-still";
    return ASSET + "bldg-" + id + "-iso" + still + ".svg";
  }

  function show(el, on) {
    if (!el) return;
    el.hidden = !on;
  }

  function readyToPreview() {
    if (!state.pad || state.defId == null) return false;
    if (occAt(state.pad.c, state.pad.r)) return false;
    if (placedDef(state.defId)) return false;
    if (storedDef(state.defId)) return false;
    return true;
  }

  function buildGrid() {
    var village = $("village");
    if (!village || built) return;
    built = true;
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
        shadow.setAttribute("data-contact-shadow", "");
        shadow.hidden = true;
        shadow.setAttribute("aria-hidden", "true");
        var mark = document.createElement("img");
        mark.className = "mark";
        mark.alt = "";
        mark.hidden = true;
        mark.src = MARK_VALID;
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
        var cap = document.createElement("p");
        cap.className = "cap";
        cap.hidden = true;
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
        pad.appendChild(btn);
        village.appendChild(pad);
        pads.push({
          c: c, r: r, el: pad, btn: btn, mark: mark, shadow: shadow,
          sprite: sprite, ghost: ghost, cap: cap, badge: badge
        });
      }
    }
  }

  function localPoint(el, clientX, clientY) {
    var rect = el.getBoundingClientRect();
    var scaleX = rect.width / el.offsetWidth || 1;
    var scaleY = rect.height / el.offsetHeight || 1;
    return {
      x: (clientX - rect.left) / scaleX + el.scrollLeft,
      y: (clientY - rect.top) / scaleY + el.scrollTop
    };
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

  function cellAt(clientX, clientY) {
    var village = $("village");
    if (!village || !pads.length) return null;
    var rect = village.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    var scaleX = rect.width / village.offsetWidth;
    var inside = (clientX - rect.left) / scaleX;
    if (inside < 0 || inside > village.clientWidth) return null;
    var point = localPoint(village, clientX, clientY);
    var metrics = gridMetrics();
    if (!metrics.stepX || !metrics.stepY) return null;
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

  function cellBy(c, r) {
    for (var i = 0; i < pads.length; i += 1) {
      if (pads[i].c === c && pads[i].r === r) return pads[i];
    }
    return null;
  }

  function renderCell(cell) {
    var occ = occAt(cell.c, cell.r);
    var picked = sameCell(state.pad, cell);
    var ghostDef = state.defId != null ? defById(state.defId) : null;
    var showGhost = state.scene === 3 && picked && !!ghostDef && !state.sheet;
    var hot = state.scene === 2 && !occ && !state.sheet;
    var kind = "quiet";
    if (state.scene === 2 && !occ && !state.sheet) kind = picked ? "chosen" : "empty";
    if (state.scene === 3 && !state.sheet && occ) kind = "illegal";
    else if (state.scene === 3 && !state.sheet && !occ) kind = picked ? "preview" : "valid";
    cell.el.className = "pad is-" + kind + (hot ? " is-empty-hot" : "");

    if (showGhost) {
      cell.ghost.hidden = false;
      var gsrc = assetSrc(ghostDef.name);
      if (cell.ghost.getAttribute("src") !== gsrc) cell.ghost.src = gsrc;
      cell.ghost.alt = "";
    } else {
      cell.ghost.hidden = true;
    }

    cell.shadow.hidden = !(occ || showGhost);

    if (occ) {
      cell.sprite.hidden = false;
      var ssrc = assetSrc(occ.name);
      if (cell.sprite.getAttribute("src") !== ssrc) cell.sprite.src = ssrc;
      cell.sprite.alt = occ.name || "";
      cell.cap.hidden = false;
      cell.cap.textContent = occ.name || "";
    } else {
      cell.sprite.hidden = true;
      cell.sprite.alt = "";
      cell.cap.hidden = true;
      cell.cap.textContent = "";
    }

    var showMark = !state.sheet && (kind === "empty" || kind === "valid" || kind === "chosen" || kind === "preview" || kind === "illegal");
    cell.mark.hidden = !showMark;
    if (showMark && cell.mark.getAttribute("src") !== MARK_VALID) cell.mark.src = MARK_VALID;
    cell.badge.hidden = !(kind === "chosen" || kind === "preview");
    if (kind === "chosen") cell.badge.textContent = "呢格";
    if (kind === "preview") cell.badge.textContent = "預覽";

    var label = "第 " + (cell.c + 1) + " 欄第 " + (cell.r + 1) + " 行";
    if (occ && state.scene === 1) label += "，" + occ.name;
    else if (occ && state.scene === 3 && !state.sheet) label += "，" + occ.name + "，已經有屋，唔可以放";
    else if (occ) label += "，" + occ.name + "，已起";
    else if (state.scene === 1) label += "，空地";
    else if (state.scene === 2) label += picked ? "，已揀呢格" : "，空地，撳一下就揀";
    else if (kind === "preview") label += "，擺放預覽";
    else if (kind === "valid") label += "，可以放，撳一下就搬去呢格";
    else label += "，空地";
    cell.btn.setAttribute("aria-label", label);
  }

  function renderPalette() {
    var grid = $("paletteGrid");
    if (!grid) return;
    var list = defs();
    grid.textContent = "";
    var placedN = 0;
    list.forEach(function (def) {
      var placed = placedDef(def.id);
      var warehoused = placed ? null : storedDef(def.id);
      if (placed) placedN += 1;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pal-btn" + (placed ? " is-placed" : "") + (warehoused ? " is-stored" : "");
      var img = document.createElement("img");
      img.alt = "";
      img.src = assetSrc(def.name);
      var copy = document.createElement("span");
      var name = document.createElement("span");
      name.className = "pal-name";
      name.textContent = def.name;
      var cost = document.createElement("span");
      cost.className = "pal-cost";
      cost.textContent = placed ? "已起" : (warehoused ? "存倉" : ("💰" + (def.cost_gold || 0)));
      copy.appendChild(name);
      copy.appendChild(cost);
      btn.appendChild(img);
      btn.appendChild(copy);
      btn.setAttribute("aria-pressed", (!placed && !warehoused && String(state.defId) === String(def.id)) ? "true" : "false");
      btn.setAttribute("aria-label", placed
        ? (def.name + "，已起")
        : (warehoused ? (def.name + "，放返") : (def.name + "，未起")));
      btn.addEventListener("click", function () { onPalette(def.id); });
      grid.appendChild(btn);
    });
    var count = $("placedCount");
    if (count) count.textContent = "已起 " + placedN;
  }

  function renderBars() {
    var sheetOn = state.sheet;
    show($("btnBuild"), state.scene === 1 && !sheetOn && !state.placeBeat);
    show($("listLauncher"), state.scene === 2 && !state.listOpen && !sheetOn);
    show($("palette"), state.scene === 2 && state.listOpen && !sheetOn);
    show($("readyBar"), state.scene === 2 && !sheetOn);
    show($("uxPlaceBar"), state.scene === 3 && !sheetOn);
    var placingStore = !!state.unstoreId;
    var canConfirm = placingStore ? readyToUnstore() : readyToPreview();
    var go = $("btnToScene3");
    if (go) go.disabled = !canConfirm;
    var confirm = $("btnUxConfirm");
    if (confirm) confirm.disabled = !canConfirm;
    var placeStatus = $("placeStatus");
    if (placeStatus) {
      if (placingStore) {
        var storedDefRow = defById(state.defId);
        var storedName = (storedDefRow && storedDefRow.name) || "呢座屋";
        placeStatus.textContent = "放返存倉「" + storedName + "」，唔使扣金幣同材料。取消唔會扣。";
      } else {
        placeStatus.textContent = "確定先至扣資源。取消唔會扣。";
      }
    }
    var status = $("readyStatus");
    if (status && state.scene === 2) {
      var def = defById(state.defId);
      if (readyToPreview()) status.textContent = "已揀「" + def.name + "」同呢格空地。";
      else if (def && storedDef(def.id)) status.textContent = "「" + def.name + "」喺存倉。用存倉放返，唔使再扣資源。";
      else if (state.pad && !def) status.textContent = "已揀空地。打開清單，揀一座未起嘅屋。";
      else if (def && !placedDef(def.id) && !state.pad) status.textContent = "已揀「" + def.name + "」。再點一塊金色空地。";
      else status.textContent = "點金色空地，或者打開清單揀一座未起嘅屋。";
    }
    var map = $("townMap");
    if (map) {
      map.className = "map is-scene-" + state.scene + (state.listOpen && state.scene === 2 ? " is-list-open" : "") + (sheetOn ? " is-sheet" : "");
      map.setAttribute("aria-label", sheetOn ? "場景 4 · 升級" : ("場景 " + state.scene));
    }
  }

  function renderSheet() {
    var sheet = $("actionSheet");
    if (!sheet) return;
    show(sheet, state.sheet);
    if (!state.sheet) return;
    var def = defById(state.sheetDef) || {};
    var placed = placedDef(state.sheetDef);
    var title = $("sheetTitle");
    if (title) title.textContent = def.name || "升級或打開功能";
    var level = $("sheetLevel");
    if (level) level.textContent = "Lv." + ((placed && placed.level) || 1);
    var note = $("sheetNote");
    if (note) note.textContent = state.note || "可以升級，或者試下面嘅功能。";
    var art = $("sheetArt");
    if (art && def.name) {
      var src = assetSrc(def.name);
      if (art.getAttribute("src") !== src) art.src = src;
      art.alt = "";
    }
    var fns = $("sheetFns");
    if (!fns) return;
    var keep = fns.querySelectorAll(".fx-burst");
    fns.textContent = "";
    keep.forEach(function (node) { fns.appendChild(node); });
    (FN[def.name] || ["睇一看"]).forEach(function (label) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "fn";
      btn.textContent = label;
      btn.addEventListener("click", function () { onFn(label); });
      fns.appendChild(btn);
    });
  }

  function renderMotion() {
    var btn = $("btnMotion");
    if (!btn) return;
    btn.setAttribute("aria-pressed", motionOn ? "true" : "false");
    btn.textContent = motionOn ? "動畫 開" : "動畫 關";
  }

  function render() {
    if (!built) buildGrid();
    pads.forEach(renderCell);
    renderPalette();
    renderBars();
    renderSheet();
    renderMotion();
  }

  function onPalette(id) {
    if (placedDef(id)) {
      openSheet(id);
      return;
    }
    var warehoused = storedDef(id);
    if (warehoused) {
      placeFromStore(warehoused);
      return;
    }
    state.unstoreId = null;
    state.defId = String(state.defId) === String(id) ? null : id;
    state.listOpen = true;
    render();
  }

  function onCell(c, r) {
    var occ = occAt(c, r);
    if (state.sheet) {
      if (occ) openSheet(occ.def_id);
      return;
    }
    if (state.scene === 1) {
      if (occ) openSheet(occ.def_id);
      else if (typeof showToast === "function") showToast("想喺呢度起屋？先撳「我要起屋」。");
      return;
    }
    if (state.scene === 2) {
      if (occ) {
        openSheet(occ.def_id);
        return;
      }
      state.pad = sameCell(state.pad, { c: c, r: r }) ? null : { c: c, r: r };
      render();
      return;
    }
    if (state.scene === 3) {
      if (occ) {
        if (typeof showToast === "function") showToast("呢度已經有" + occ.name + "，唔可以放。");
        return;
      }
      state.pad = { c: c, r: r };
      render();
    }
  }

  function openSheet(defId) {
    state.sheetDef = defId;
    state.sheet = true;
    state.note = "";
    render();
  }

  function closeSheet() {
    state.sheet = false;
    render();
  }

  function cancelPreview() {
    state.scene = 2;
    state.sheet = false;
    state.unstoreId = null;
    if (typeof showToast === "function") showToast("已取消，資源未扣除");
    render();
  }

  function celebrate(kind, cellPos) {
    var sheet = $("actionSheet");
    var village = $("village");
    var host = kind === "upgrade" ? sheet : village;
    if (!host) return;
    var point = { x: 80, y: 80 };
    if (kind === "upgrade") {
      point = { x: Math.max(48, host.clientWidth * 0.28), y: Math.max(36, host.clientHeight * 0.42) };
    } else if (cellPos) {
      var cell = cellBy(cellPos.c, cellPos.r);
      var sprite = cell && cell.sprite && !cell.sprite.hidden ? cell.sprite : null;
      if (sprite) {
        var box = sprite.getBoundingClientRect();
        point = localPoint(village, box.left + box.width / 2, box.top + box.height * 0.38);
      }
    }
    var node = document.createElement("div");
    node.className = "fx-burst is-" + kind;
    node.setAttribute("data-town-fx", kind);
    node.setAttribute("aria-hidden", "true");
    node.style.left = point.x + "px";
    node.style.top = point.y + "px";
    var count = kind === "place" ? 12 : 14;
    for (var i = 0; i < count; i += 1) {
      var bit = document.createElement("span");
      bit.className = "fx-bit " + (i % 2 === 0 ? "is-star" : "is-coin");
      var angle = (Math.PI * 2 * i) / count - Math.PI / 2;
      var dist = kind === "place" ? 54 : 70;
      bit.style.setProperty("--dx", (Math.cos(angle) * dist).toFixed(1) + "px");
      bit.style.setProperty("--dy", (Math.sin(angle) * dist * 0.7).toFixed(1) + "px");
      node.appendChild(bit);
    }
    host.appendChild(node);
    setTimeout(function () {
      if (node.parentNode) node.parentNode.removeChild(node);
    }, kind === "upgrade" ? 2200 : 2000);
  }

  function rememberUnstore(placed) {
    if (typeof townData === "undefined" || !townData || !placed) return;
    var stored = townData.stored_buildings || [];
    townData.stored_buildings = stored.filter(function (row) {
      return String(row.id) !== String(placed.id);
    });
    var list = (townData.buildings || []).filter(function (row) {
      return String(row.id) !== String(placed.id);
    });
    list.push(placed);
    townData.buildings = list;
  }

  async function confirmUnstore() {
    if (!readyToUnstore()) return;
    var rowId = state.unstoreId;
    var cell = { c: state.pad.c, r: state.pad.r };
    var def = defById(state.defId);
    var name = (def && def.name) || "建築";
    var confirm = $("btnUxConfirm");
    if (confirm) confirm.disabled = true;
    try {
      var placed = await fetchAPI("/api/kids/" + readTown().kidId + "/buildings/" + rowId + "/unstored", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cell_x: cell.c, cell_y: cell.r })
      });
      rememberUnstore(placed);
      state.scene = 1;
      state.sheet = false;
      state.pad = null;
      state.defId = null;
      state.unstoreId = null;
      state.listOpen = false;
      render();
      if (typeof showToast === "function") showToast("放好「" + name + "」。");
      celebrate("place", cell);
      await loadTown();
    } catch (e) {
      if (typeof showToast === "function") showToast(e.message || "放唔返", "error");
      render();
    }
  }

  async function onConfirm() {
    if (state.unstoreId) {
      await confirmUnstore();
      return;
    }
    var warehoused = storedDef(state.defId);
    if (warehoused) {
      placeFromStore(warehoused);
      return;
    }
    if (!readyToPreview()) return;
    var def = defById(state.defId);
    var cell = { c: state.pad.c, r: state.pad.r };
    var confirm = $("btnUxConfirm");
    if (confirm) confirm.disabled = true;
    try {
      await fetchAPI("/api/kids/" + readTown().kidId + "/buildings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ def_id: def.id, cell_x: cell.c, cell_y: cell.r })
      });
      state.scene = 1;
      state.sheet = false;
      state.pad = null;
      state.defId = null;
      state.listOpen = false;
      state.placeBeat = true;
      state.sheetDef = def.id;
      await loadTown();
      if (typeof showToast === "function") showToast("起好「" + def.name + "」。");
      celebrate("place", cell);
      var token = ++placeSeq;
      setTimeout(function () {
        if (token !== placeSeq) return;
        state.placeBeat = false;
        openSheet(def.id);
      }, 420);
    } catch (e) {
      if (typeof showToast === "function") showToast(e.message || "起唔到", "error");
      render();
    }
  }

  async function onUpgrade() {
    var placed = placedDef(state.sheetDef);
    if (!placed) return;
    try {
      await fetchAPI("/api/kids/" + readTown().kidId + "/buildings/" + placed.id + "/upgrade", {
        method: "POST"
      });
      state.note = "";
      await loadTown();
      state.sheet = true;
      render();
      celebrate("upgrade");
      if (typeof showToast === "function") {
        var now = placedDef(state.sheetDef);
        showToast((now && now.name ? now.name : "建築") + " 升到 Lv." + ((now && now.level) || "") );
      }
    } catch (e) {
      if (typeof showToast === "function") showToast(e.message || "升級唔到", "error");
    }
  }

  function onFn(label) {
    var def = defById(state.sheetDef);
    var name = def && def.name ? def.name : "建築";
    state.note = name + "：" + (FN_COPY[label] || label);
    renderSheet();
    if (typeof showToast === "function") showToast(state.note);
  }

  function wire() {
    var map = $("townMap");
    if (!map || map.dataset.wired === "1") return;
    map.dataset.wired = "1";
    map.addEventListener("click", function (event) {
      var btn = event.target.closest && event.target.closest("button");
      if (btn && !btn.classList.contains("cell-btn")) return;
      var hit = cellAt(event.clientX, event.clientY);
      if (!hit) return;
      onCell(hit.c, hit.r);
    }, true);
    $("btnBuild").addEventListener("click", function () {
      state.scene = 2;
      state.sheet = false;
      state.listOpen = false;
      render();
    });
    $("listLauncher").addEventListener("click", function () {
      state.listOpen = true;
      render();
    });
    $("btnToScene3").addEventListener("click", function () {
      if (state.unstoreId) {
        if (!readyToUnstore()) return;
        state.scene = 3;
        state.listOpen = false;
        state.sheet = false;
        render();
        return;
      }
      if (!readyToPreview()) return;
      state.scene = 3;
      state.listOpen = false;
      state.sheet = false;
      render();
    });
    $("btnUxCancel").addEventListener("click", cancelPreview);
    $("btnUxConfirm").addEventListener("click", function () { onConfirm(); });
    $("btnUpgrade").addEventListener("click", function () { onUpgrade(); });
    $("btnCloseSheet").addEventListener("click", closeSheet);
    $("btnMotion").addEventListener("click", function () {
      motionOn = !motionOn;
      try { localStorage.setItem(MOTION_KEY, motionOn ? "on" : "off"); } catch (e) {}
      render();
    });
  }

  function townUxSync() {
    if (!$("townMap")) return;
    buildGrid();
    wire();
    render();
  }

  motionOn = readMotion();
  window.townUxSync = townUxSync;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", townUxSync);
  } else {
    townUxSync();
  }
})();
