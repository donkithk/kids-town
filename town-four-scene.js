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
    note: "",
    confirming: false,
    instantUpgrade: false,
    upgrading: false,
    claiming: false,
    farmClaimed: false
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

  var MAT_ICON = { wood: "🪵", brick: "🧱", glass: "🪟", gear: "⚙️", gem: "💎" };
  var MAT_LABEL = { wood: "木材", brick: "磚頭", glass: "玻璃", gear: "齒輪", gem: "寶石" };

  function parseVals(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    if (typeof raw === "string") {
      try {
        var parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      } catch (e) { return []; }
    }
    return [];
  }

  function formatBuffValue(value) {
    var n = typeof value === "number" ? value : parseFloat(value);
    if (!isFinite(n)) return String(value);
    if (Math.abs(n - Math.round(n)) < 1e-9) return String(Math.round(n));
    return String(n);
  }

  /* Shop and farm still read buff_vals. Other sheets name the passive or
     skill the backend applies. Anything else is 「未開放」 with no number. */
  var UNAVAILABLE_LABEL = "未開放";
  var FARM_CLAIM_LABEL = "領取";
  var FARM_CLAIMED_LABEL = "✓ 今日已領";
  var DISCOUNT_FOLD = [
    [0.9, "九折"],
    [0.85, "八五折"],
    [0.8, "八折"],
    [0.75, "七五折"],
    [0.7, "七折"]
  ];

  function discountFold(value) {
    var n = typeof value === "number" ? value : parseFloat(value);
    if (!isFinite(n)) return "";
    for (var i = 0; i < DISCOUNT_FOLD.length; i += 1) {
      if (Math.abs(n - DISCOUNT_FOLD[i][0]) < 1e-6) return DISCOUNT_FOLD[i][1];
    }
    return "";
  }

  function passivePoints(level) {
    return 2 * level;
  }

  /* Name wins over the stored buff_type. The library has no task_bonus row. */
  function sheetEffectLabel(name, level, buffType, rawValue, valueText) {
    if (name === "圖書館") return "知識 +" + passivePoints(level);
    if (name === "健身室") return "臂力 +" + passivePoints(level);
    if (name === "工坊") return "創意 +" + passivePoints(level);
    if (name === "競技場") return "臂力 +" + passivePoints(level) + "、速度 +" + level;
    if (name === "探險公會") return "勇氣 +" + passivePoints(level);
    if (name === "天文台") return "技能：流星雨（魔法攻擊全體敵人）";
    if (name === "醫院") return "技能：繃帶（小回復）";
    if (name === "燈塔") return "技能：強光（魔法攻擊，之後 2 次怪物攻擊打唔中）";
    if (name === "銀行") return "技能：金錢砸（每次 10 金幣，傷害約普攻 3 倍）";
    if (name === "商店" || buffType === "discount") {
      var fold = discountFold(rawValue);
      return fold ? ("起屋／升級金幣" + fold) : "起屋／升級金幣";
    }
    if (name === "農場" || buffType === "daily_gold") {
      return "每日金幣 +" + valueText + "🪙";
    }
    return UNAVAILABLE_LABEL;
  }

  /* buff_vals[level-1] for shop and farm. Prefer the placed row. */
  function levelBuff(placed) {
    if (!placed) return null;
    var def = defById(placed.def_id) || {};
    var buffType = String(placed.buff_type || def.buff_type || "");
    var name = placed.name || def.name || "";
    var vals = parseVals(placed.buff_vals);
    if (!vals.length) vals = parseVals(def.buff_vals);
    if (!buffType && !name) return null;
    var level = parseInt(placed.level, 10);
    if (!isFinite(level) || level < 1) level = 1;
    var rawValue = null;
    var text = "";
    if (vals.length) {
      var idx = Math.max(0, Math.min(level - 1, vals.length - 1));
      rawValue = vals[idx];
      text = formatBuffValue(rawValue);
    }
    var label = sheetEffectLabel(name, level, buffType, rawValue, text);
    if (!label) return null;
    return { type: buffType, text: text, label: label };
  }

  function inventoryQty(key) {
    var inv = readTown().inventory || [];
    var total = 0;
    for (var i = 0; i < inv.length; i += 1) {
      if (inv[i].item_type !== key) continue;
      total += parseInt(inv[i].quantity, 10) || 0;
    }
    return total;
  }

  /* Highest placed shop. Same index as get_building_buff('discount'). */
  function shopDiscountFactor() {
    var bestLevel = -1;
    var bestVals = null;
    buildings().forEach(function (row) {
      if ((row.stored | 0) === 1) return;
      var def = defById(row.def_id) || {};
      var buff = row.buff_type || def.buff_type;
      if (buff !== "discount") return;
      var level = parseInt(row.level, 10) || 1;
      if (level <= bestLevel) return;
      var vals = parseVals(row.buff_vals);
      if (!vals.length) vals = parseVals(def.buff_vals);
      if (!vals.length) return;
      bestLevel = level;
      bestVals = vals;
    });
    if (!bestVals) return null;
    var idx = Math.max(0, Math.min(bestLevel - 1, bestVals.length - 1));
    var factor = parseFloat(bestVals[idx]);
    return isFinite(factor) ? factor : null;
  }

  function baseMatsFor(placed, def) {
    var raw = parseMats(placed);
    if (raw && Object.keys(raw).length) return raw;
    return parseMats(def);
  }

  /* gold = max(1, floor(level * 100 * shop discount)); no shop → level * 100.
     materials = each base mat × (level + 1). Matches upgrade_building. */
  function upgradeQuote(placed) {
    var def = defById(placed.def_id) || {};
    var name = placed.name || def.name || "建築";
    var level = parseInt(placed.level, 10);
    if (!isFinite(level) || level < 1) level = 1;
    var maxLevel = parseInt(placed.max_level != null ? placed.max_level : def.max_level, 10);
    if (!isFinite(maxLevel) || maxLevel < 1) maxLevel = 5;
    var baseGold = level * 100;
    var factor = shopDiscountFactor();
    var gold = factor == null ? baseGold : Math.max(1, Math.floor(baseGold * factor));
    var mats = {};
    var raw = baseMatsFor(placed, def);
    Object.keys(raw).forEach(function (key) {
      var qty = parseInt(raw[key], 10);
      if (!isFinite(qty) || qty <= 0) return;
      mats[key] = qty * (level + 1);
    });
    var gaps = [];
    var goldHave = parseInt(readTown().points, 10) || 0;
    if (goldHave < gold) gaps.push("金幣唔夠");
    Object.keys(mats).forEach(function (key) {
      if (inventoryQty(key) < mats[key]) gaps.push((MAT_LABEL[key] || key) + "唔夠");
    });
    var maxed = level >= maxLevel;
    return {
      name: name,
      level: level,
      gold: gold,
      mats: mats,
      maxed: maxed,
      afford: !maxed && gaps.length === 0,
      shortText: gaps.join("、")
    };
  }

  function costBits(quote) {
    var parts = ["💰" + quote.gold];
    Object.keys(quote.mats).forEach(function (key) {
      parts.push((MAT_ICON[key] || "") + quote.mats[key]);
    });
    return parts.join(" ");
  }

  function paintUpgrade(placed) {
    var btn = $("btnUpgrade");
    var box = $("upgradeConfirm");
    var copy = $("upgradeConfirmCopy");
    var ok = $("btnUpgradeConfirm");
    var quote = placed ? upgradeQuote(placed) : null;
    if (btn) {
      if (!quote) {
        btn.textContent = "升級";
        btn.disabled = true;
      } else if (quote.maxed) {
        btn.textContent = "已滿級";
        btn.disabled = true;
      } else {
        btn.textContent = "升級";
        btn.disabled = !quote.afford || state.upgrading;
      }
      btn.setAttribute("aria-disabled", btn.disabled ? "true" : "false");
    }
    var cost = $("sheetCost");
    if (cost) {
      if (quote && !quote.maxed) cost.textContent = "升級要 " + costBits(quote);
      else if (quote && quote.maxed) cost.textContent = "已滿級";
      else cost.textContent = "";
    }
    var showConfirm = !!(state.confirming && quote && !quote.maxed);
    var wasHidden = !!(box && box.hidden);
    if (box) show(box, showConfirm);
    if (btn) btn.setAttribute("aria-expanded", showConfirm ? "true" : "false");
    if (copy && quote) {
      copy.textContent = "「" + quote.name + "」而家 Lv." + quote.level
        + "，升級到 Lv." + (quote.level + 1)
        + " 會扣 " + costBits(quote) + "。確定先至扣，取消只關呢個視窗。";
    }
    if (showConfirm && wasHidden && box && typeof box.focus === "function") box.focus();
    if (ok) {
      ok.disabled = !(showConfirm && quote.afford) || state.upgrading;
      ok.setAttribute("aria-disabled", ok.disabled ? "true" : "false");
    }
    return quote;
  }

  function paintSheetBuff(placed) {
    var node = $("sheetBuff");
    if (!node) return;
    var buff = levelBuff(placed);
    if (!buff) {
      node.textContent = "";
      node.removeAttribute("aria-label");
      node.classList.remove("is-unwired");
      show(node, false);
      return;
    }
    node.textContent = buff.label;
    node.setAttribute("aria-label", buff.label);
    node.classList.toggle("is-unwired", buff.label === UNAVAILABLE_LABEL);
    show(node, true);
  }

  function farmClaimedNow() {
    return !!(state.farmClaimed || readTown().farmClaimedToday);
  }

  function paintFarmClaim(placed) {
    var btn = $("btnFarmClaim");
    if (!btn) return;
    var buff = levelBuff(placed);
    var isFarm = !!(buff && buff.type === "daily_gold");
    show(btn, isFarm);
    if (!isFarm) return;
    var claimed = farmClaimedNow();
    btn.classList.toggle("is-claimed", claimed);
    if (claimed) {
      btn.textContent = FARM_CLAIMED_LABEL;
      btn.setAttribute("aria-label", FARM_CLAIMED_LABEL);
      btn.disabled = true;
    } else {
      btn.textContent = FARM_CLAIM_LABEL;
      btn.setAttribute("aria-label", FARM_CLAIM_LABEL);
      btn.disabled = !!state.claiming;
    }
    btn.setAttribute("aria-disabled", btn.disabled ? "true" : "false");
  }

  function markFarmClaimed(points) {
    state.farmClaimed = true;
    state.claiming = false;
    state.note = "今日已領";
    if (typeof townData !== "undefined" && townData) {
      townData.farm_claimed_today = true;
      if (points != null && townData.kid) townData.kid.points = points;
    }
    render();
    if (typeof updateHeader === "function") updateHeader();
  }

  async function onFarmClaim() {
    if (state.claiming || farmClaimedNow()) return;
    var buff = levelBuff(placedDef(state.sheetDef));
    if (!buff || buff.type !== "daily_gold") return;
    var town = readTown();
    if (!town.kidId || typeof fetchAPI !== "function") return;
    state.claiming = true;
    render();
    try {
      var data = await fetchAPI("/api/kids/" + town.kidId + "/farm/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}"
      });
      markFarmClaimed(data && data.points);
    } catch (e) {
      if (e && e.message === "already_claimed_today") {
        markFarmClaimed(null);
        return;
      }
      if (typeof showToast === "function") showToast("領唔到", "error");
    } finally {
      state.claiming = false;
      render();
    }
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
    if (!state.sheet) {
      state.confirming = false;
      paintUpgrade(null);
      paintSheetBuff(null);
      paintFarmClaim(null);
      return;
    }
    var def = defById(state.sheetDef) || {};
    var placed = placedDef(state.sheetDef);
    var title = $("sheetTitle");
    if (title) title.textContent = def.name || "升級或打開功能";
    var level = $("sheetLevel");
    if (level) level.textContent = "Lv." + ((placed && placed.level) || 1);
    var quote = paintUpgrade(placed);
    var note = $("sheetNote");
    if (note) {
      if (state.note) note.textContent = state.note;
      else if (quote && quote.maxed) note.textContent = "已經最高等級。";
      else if (quote && !quote.afford) note.textContent = quote.shortText + "。未可以升級。";
      else if (quote) note.textContent = "可以升級。撳「升級」會彈出確認窗，確定先至扣。";
      else note.textContent = "可以升級。";
    }
    paintSheetBuff(placed);
    paintFarmClaim(placed);
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

  function openSheet(defId, opts) {
    state.sheetDef = defId;
    state.sheet = true;
    state.note = "";
    state.confirming = false;
    state.instantUpgrade = !!(opts && opts.instant);
    render();
  }

  function closeSheet() {
    state.sheet = false;
    state.confirming = false;
    state.instantUpgrade = false;
    render();
  }

  function cancelPreview() {
    state.scene = 2;
    state.sheet = false;
    state.confirming = false;
    state.instantUpgrade = false;
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
        openSheet(def.id, { instant: true });
      }, 420);
    } catch (e) {
      if (typeof showToast === "function") showToast(e.message || "起唔到", "error");
      render();
    }
  }

  async function postUpgrade() {
    if (state.upgrading) return;
    var placed = placedDef(state.sheetDef);
    if (!placed) return;
    var quote = upgradeQuote(placed);
    if (!quote || quote.maxed || !quote.afford) return;
    state.upgrading = true;
    render();
    try {
      await fetchAPI("/api/kids/" + readTown().kidId + "/buildings/" + placed.id + "/upgrade", {
        method: "POST"
      });
      state.confirming = false;
      state.instantUpgrade = false;
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
      render();
    } finally {
      state.upgrading = false;
      render();
    }
  }

  function onUpgrade() {
    var placed = placedDef(state.sheetDef);
    if (!placed || state.upgrading) return;
    var quote = upgradeQuote(placed);
    if (!quote || quote.maxed || !quote.afford) return;
    /* Sheet that auto-opens right after a new place stays one click,
       so the existing scene-4 upgrade check still spends on that tap.
       Tapping a building already on the map only opens confirmation. */
    if (state.instantUpgrade) {
      state.instantUpgrade = false;
      postUpgrade();
      return;
    }
    if (!state.confirming) {
      state.confirming = true;
      render();
    }
  }

  function onUpgradeConfirm() {
    if (!state.confirming || state.upgrading) return;
    postUpgrade();
  }

  function onUpgradeCancel() {
    if (state.upgrading) return;
    state.confirming = false;
    render();
  }

  /* Buff chip is the scene-4 feature. Tapping it restates the live bonus in
     the note. It does not toast an FN stub or spend resources. */
  function onSheetBuff() {
    var buff = levelBuff(placedDef(state.sheetDef));
    if (!buff) return;
    state.note = "而家等級加成 " + buff.label;
    renderSheet();
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
    var upgradeConfirm = $("btnUpgradeConfirm");
    if (upgradeConfirm) upgradeConfirm.addEventListener("click", function () { onUpgradeConfirm(); });
    var upgradeCancel = $("btnUpgradeCancel");
    if (upgradeCancel) upgradeCancel.addEventListener("click", function () { onUpgradeCancel(); });
    var upgradeModal = $("upgradeConfirm");
    if (upgradeModal) {
      upgradeModal.addEventListener("click", function (event) {
        if (event.target === upgradeModal) onUpgradeCancel();
      });
    }
    var sheetBuff = $("sheetBuff");
    if (sheetBuff) sheetBuff.addEventListener("click", function () { onSheetBuff(); });
    var farmClaim = $("btnFarmClaim");
    if (farmClaim) farmClaim.addEventListener("click", function () { onFarmClaim(); });
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
