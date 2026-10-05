/* Four-scene kid build loop on /kids/ town home.
   Spends only through the existing place / upgrade APIs. Cancel never spends.
   Pad picks use iso math so a back diamond wins under a front sprite. */
(function () {
  var COLS = 8;
  var ROWS = 8;
  var ASSET = "mocks/town-building-proof/assets/";
  var MOTION_KEY = "ktTownMotion";
  var MARK_VALID = ASSET + "cell-valid.svg";
  var MARK_CHOSEN = "data:image/svg+xml," + encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'></svg>"
  );

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
  var ringGeom = null;
  var ringBtn = null;
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

  /* Name wins over the stored buff_type. The library has no task_bonus row.
     Passive sheets use passive_line from the town payload (live ability and
     battle-stat diffs). The bracket words live with that formatter. */
  function sheetEffectLabel(name, level, buffType, rawValue, valueText, placed) {
    if (name === "圖書館" || name === "健身室" || name === "工坊" || name === "競技場" || name === "探險公會") {
      return (placed && placed.passive_line) || "";
    }
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
    var label = sheetEffectLabel(name, level, buffType, rawValue, text, placed);
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

  /* Owned but warehoused. Not a map building, and not a new-build sale. */
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

  /* Catalog square side. A missing footprint stays 2. */
  function footprintOf(def) {
    var n = parseInt(def && def.footprint, 10);
    if (!isFinite(n) || n < 1) return 2;
    return n;
  }

  function defByName(name) {
    var list = defs();
    for (var i = 0; i < list.length; i += 1) {
      if (list[i].name === name) return list[i];
    }
    return null;
  }

  function placedSize(row) {
    if (!row) return footprintOf(null);
    return footprintOf(defById(row.def_id) || defByName(row.name));
  }

  function minCatalogFootprint() {
    var list = defs();
    var min = 0;
    for (var i = 0; i < list.length; i += 1) {
      var n = footprintOf(list[i]);
      if (!min || n < min) min = n;
    }
    return min || footprintOf(null);
  }

  function unstoreRow() {
    if (!state.unstoreId) return null;
    var owned = buildings().concat(storedRows());
    for (var i = 0; i < owned.length; i += 1) {
      if (String(owned[i].id) === String(state.unstoreId)) return owned[i];
    }
    return null;
  }

  /* Chosen building, else the smallest catalog footprint. */
  function activeFootprint() {
    if (state.unstoreId) return placedSize(unstoreRow());
    if (state.defId != null) return footprintOf(defById(state.defId));
    return minCatalogFootprint();
  }

  function footprintsOverlap(ax, ay, aSize, bx, by, bSize) {
    return !(ax + aSize <= bx || bx + bSize <= ax || ay + aSize <= by || by + bSize <= ay);
  }

  function originFits(c, r, size) {
    return c >= 0 && r >= 0 && c + size <= COLS && r + size <= ROWS;
  }

  /* True when a placed building's whole footprint covers this cell. */
  function coveredAt(c, r) {
    var list = buildings();
    for (var i = 0; i < list.length; i += 1) {
      var row = list[i];
      if ((row.stored | 0) === 1) continue;
      if (row.cell_x == null || row.cell_y == null) continue;
      var size = placedSize(row);
      var ox = row.cell_x | 0;
      var oy = row.cell_y | 0;
      if (c >= ox && c < ox + size && r >= oy && r < oy + size) return row;
    }
    return null;
  }

  /* Placed buildings only. stored=1 does not occupy a cell. */
  function footprintFree(c, r, ignoreId, size) {
    var fp = size || activeFootprint();
    if (!originFits(c, r, fp)) return false;
    var blocks = buildings();
    for (var i = 0; i < blocks.length; i += 1) {
      var row = blocks[i];
      if ((row.stored | 0) === 1) continue;
      if (row.cell_x == null || row.cell_y == null) continue;
      if (ignoreId != null && String(row.id) === String(ignoreId)) continue;
      if (footprintsOverlap(c, r, fp, row.cell_x | 0, row.cell_y | 0, placedSize(row))) return false;
    }
    var tiles = (typeof townData !== "undefined" && townData && townData.tiles) || [];
    for (var dy = 0; dy < fp; dy += 1) {
      for (var dx = 0; dx < fp; dx += 1) {
        var cx = c + dx;
        var cy = r + dy;
        for (var t = 0; t < tiles.length; t += 1) {
          var tile = tiles[t];
          if ((tile.cell_x | 0) === cx && (tile.cell_y | 0) === cy) return false;
        }
      }
    }
    return true;
  }

  function hasLegalOrigin(ignoreId, size) {
    var fp = size || activeFootprint();
    var last = ROWS - fp;
    for (var r = 0; r <= last; r += 1) {
      for (var c = 0; c <= COLS - fp; c += 1) {
        if (footprintFree(c, r, ignoreId, fp)) return true;
      }
    }
    return false;
  }

  function firstUnstorePad(ignoreId, size) {
    var fp = size || activeFootprint();
    for (var r = 0; r < ROWS; r += 1) {
      for (var c = 0; c < COLS; c += 1) {
        if (occAt(c, r)) continue;
        if (footprintFree(c, r, ignoreId, fp)) return { c: c, r: r };
      }
    }
    return null;
  }

  /* 存倉「取出」and the building list share this path. A full map stays put. */
  function beginWarehousePlace(row) {
    if (!row) return false;
    if (!hasLegalOrigin(row.id, placedSize(row))) {
      if (typeof showToast === "function") {
        showToast("城鎮沒有空位，請先收起或移動其他建築。", "info");
      }
      return false;
    }
    state.defId = row.def_id;
    state.unstoreId = row.id;
    state.sheet = false;
    state.listOpen = false;
    state.pad = null;
    state.confirming = false;
    state.placeBeat = false;
    state.scene = 2;
    render();
    return true;
  }

  /* Confirm fallback when a stored row is chosen without the take-out scene. */
  function placeFromStore(row) {
    if (!row) return;
    state.defId = row.def_id;
    state.unstoreId = row.id;
    state.sheet = false;
    state.listOpen = false;
    var padOk = state.pad
      && !occAt(state.pad.c, state.pad.r)
      && footprintFree(state.pad.c, state.pad.r, row.id, placedSize(row));
    if (!padOk) state.pad = firstUnstorePad(row.id, placedSize(row));
    state.scene = 3;
    render();
  }

  function readyToUnstore() {
    if (!state.unstoreId || !state.pad) return false;
    if (occAt(state.pad.c, state.pad.r)) return false;
    return footprintFree(state.pad.c, state.pad.r, state.unstoreId);
  }

  function assetSrc(name, cutout) {
    var id = ASSET_ID[name] || "shop";
    var still = (cutout || !motionOn) ? "-still" : "";
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
        /* Gold stays on a chosen cell. The .mark swaps to the brown stroke
           for the document, and that image is not the paint on screen. */
        var fill = document.createElement("img");
        fill.className = "cell-fill";
        fill.alt = "";
        fill.setAttribute("aria-hidden", "true");
        fill.src = MARK_VALID;
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
        pad.appendChild(fill);
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

  function clientContentBox(el) {
    var box = el.getBoundingClientRect();
    var cs = getComputedStyle(el);
    return {
      left: box.left + (parseFloat(cs.borderLeftWidth) || 0),
      top: box.top + (parseFloat(cs.borderTopWidth) || 0),
      right: box.right - (parseFloat(cs.borderRightWidth) || 0),
      bottom: box.bottom - (parseFloat(cs.borderBottomWidth) || 0)
    };
  }

  function intersectRect(a, b) {
    if (!a || !b) return null;
    var left = Math.max(a.left, b.left);
    var top = Math.max(a.top, b.top);
    var right = Math.min(a.right, b.right);
    var bottom = Math.min(a.bottom, b.bottom);
    if (right - left < 1 || bottom - top < 1) return null;
    return { left: left, top: top, right: right, bottom: bottom };
  }

  function pointInRect(x, y, rect) {
    return !!rect && x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  }

  function layoutFrame() {
    var root = document.documentElement;
    return { left: 0, top: 0, right: root.clientWidth, bottom: root.clientHeight };
  }

  /* Tightest overflow ancestor of a pad: the layer that actually clips cells.
     Every side is that layer's border box, then the on-screen frame. */
  function cellClipRect() {
    var pad = document.querySelector("#townMap .pad");
    var clip = null;
    for (var node = pad ? pad.parentElement : $("village"); node && node !== document.body; node = node.parentElement) {
      var cs = getComputedStyle(node);
      var box = node.getBoundingClientRect();
      var clipsX = cs.overflowX === "hidden" || cs.overflowX === "auto" || cs.overflowX === "scroll" || cs.overflowX === "clip";
      var clipsY = cs.overflowY === "hidden" || cs.overflowY === "auto" || cs.overflowY === "scroll" || cs.overflowY === "clip";
      if (!clipsX && !clipsY) continue;
      var next = {
        left: clipsX ? box.left : -1e9,
        top: clipsY ? box.top : -1e9,
        right: clipsX ? box.right : 1e9,
        bottom: clipsY ? box.bottom : 1e9
      };
      clip = clip ? {
        left: Math.max(clip.left, next.left),
        top: Math.max(clip.top, next.top),
        right: Math.min(clip.right, next.right),
        bottom: Math.min(clip.bottom, next.bottom)
      } : next;
    }
    return clip;
  }

  function visibleMapClip() {
    return intersectRect(layoutFrame(), cellClipRect());
  }

  /* The message sits above the margin around the scrollport. It must not
     turn that margin into a cell, and it must not eat a tap on the scrollport. */
  function marginUnderToast(x, y) {
    var toast = document.getElementById("toast");
    if (!toast || toast.style.display !== "block") return false;
    var box = toast.getBoundingClientRect();
    if (x < box.left || x > box.right || y < box.top || y > box.bottom) return false;
    var village = $("village");
    if (!village) return true;
    return !pointInRect(x, y, clientContentBox(village));
  }

  var SOLID_UI = [
    "#palette", "#listLauncher", "#readyBar", "#uxPlaceBar", "#actionSheet",
    "#app .gh", "#ktFooter", "#upgradeConfirm", "#modalOverlay", "#btnBuild",
    "#townMap .tools", "#dr", "#dov"
  ];

  function rectsOverlap(a, b) {
    return a.right >= b.left && a.left <= b.right && a.bottom >= b.top && a.top <= b.bottom;
  }

  function elementConcealed(el) {
    for (var node = el; node && node !== document.documentElement; node = node.parentElement) {
      if (node.inert) return true;
      var cs = getComputedStyle(node);
      if (cs.display === "none" || cs.visibility === "hidden") return true;
      if (Number(cs.opacity) === 0) return true;
    }
    return false;
  }

  /* Open and painted. Inert, hidden, fully transparent, or off-screen does not count. */
  function solidUiOpen(el) {
    if (!el || elementConcealed(el)) return false;
    var box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) return false;
    if (!rectsOverlap(box, layoutFrame())) return false;
    return true;
  }

  /* The control the event landed on, including its border. */
  function solidUiFromTarget(target) {
    if (!target || !target.closest) return false;
    for (var i = 0; i < SOLID_UI.length; i += 1) {
      var hit = target.closest(SOLID_UI[i]);
      if (hit && solidUiOpen(hit)) return true;
    }
    return false;
  }

  /* Open, visible solid UI. The element's own border box is inclusive. */
  function solidUiCovers(x, y) {
    var map = $("townMap");
    if (!map) return false;
    var mapBox = map.getBoundingClientRect();
    for (var i = 0; i < SOLID_UI.length; i += 1) {
      var nodes = document.querySelectorAll(SOLID_UI[i]);
      for (var n = 0; n < nodes.length; n += 1) {
        var el = nodes[n];
        if (!solidUiOpen(el)) continue;
        var box = el.getBoundingClientRect();
        if (!rectsOverlap(box, mapBox)) continue;
        if (x >= box.left && x <= box.right && y >= box.top && y <= box.bottom) return true;
      }
    }
    return false;
  }

  function activationPoint(event, el) {
    var x = event.clientX;
    var y = event.clientY;
    if (event.detail === 0 && x === 0 && y === 0 && el) {
      var box = el.getBoundingClientRect();
      if (box.width > 0 && box.height > 0) {
        return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
      }
    }
    return { x: x, y: y };
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
    var clip = visibleMapClip();
    if (!pointInRect(clientX, clientY, clip)) return null;
    if (solidUiCovers(clientX, clientY)) return null;
    if (marginUnderToast(clientX, clientY)) return null;
    var rect = village.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
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
    var covered = coveredAt(cell.c, cell.r);
    var free = footprintFree(cell.c, cell.r, state.unstoreId);
    /* Gold, the chosen pad, and a successful tap are the cells the footprint can occupy. */
    var selectable = free;
    var legal = free;
    var inScene2 = state.scene === 2 && !state.sheet;
    var hot = inScene2 && legal;
    var kind = "quiet";
    if (inScene2 && picked && selectable) kind = "chosen";
    else if (inScene2 && legal) kind = "empty";
    if (state.scene === 3 && !state.sheet && occ) kind = "illegal";
    else if (state.scene === 3 && !state.sheet && picked) kind = "preview";
    else if (state.scene === 3 && !state.sheet && !occ) kind = "valid";
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

    var showMark = !state.sheet && (kind === "empty" || kind === "chosen" || kind === "preview");
    cell.mark.hidden = !showMark;
    var markSrc = kind === "chosen" ? MARK_CHOSEN : MARK_VALID;
    if (showMark && cell.mark.getAttribute("src") !== markSrc) cell.mark.src = markSrc;
    cell.badge.hidden = !(kind === "chosen" || kind === "preview");
    if (kind === "chosen") cell.badge.textContent = "此格";
    if (kind === "preview") cell.badge.textContent = "預覽";

    var label = "第 " + (cell.c + 1) + " 欄第 " + (cell.r + 1) + " 行";
    if (state.scene === 2) {
      /* Same sentences the tap toasts. Covered includes non-anchor cells. */
      if (covered) label += "，這個位置已經有建築物。";
      else if (picked && selectable) label += "，已選此格";
      else if (legal) label += "，空地，點選即可選擇";
      else label += "，這個位置放不下這座建築物。";
    } else if (occ && state.scene === 1) label += "，" + occ.name;
    else if (occ && state.scene === 3 && !state.sheet) label += "，" + occ.name + "，已有建築物，不能放置";
    else if (occ) label += "，" + occ.name + "，已興建";
    else if (state.scene === 1) label += "，空地";
    else if (kind === "preview") label += "，擺放預覽";
    else if (kind === "valid") label += "，可以放置，點選即可移到此格";
    else label += "，空地";
    cell.btn.setAttribute("aria-label", label);
  }

  /* Stored, then not-yet-built, then already built. Each group keeps catalog order. */
  function paletteOrder(list) {
    var stored = [];
    var unbuilt = [];
    var built = [];
    list.forEach(function (def) {
      if (placedDef(def.id)) built.push(def);
      else if (storedDef(def.id)) stored.push(def);
      else unbuilt.push(def);
    });
    return stored.concat(unbuilt, built);
  }

  function renderPalette() {
    var grid = $("paletteGrid");
    if (!grid) return;
    var list = paletteOrder(defs());
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
      img.src = assetSrc(def.name, true);
      var copy = document.createElement("span");
      var name = document.createElement("span");
      name.className = "pal-name";
      name.textContent = def.name;
      var cost = document.createElement("span");
      cost.className = "pal-cost";
      cost.textContent = placed ? "已興建" : (warehoused ? "存倉" : ("💰" + (def.cost_gold || 0)));
      copy.appendChild(name);
      copy.appendChild(cost);
      btn.appendChild(img);
      btn.appendChild(copy);
      btn.setAttribute("aria-pressed", (!placed && !warehoused && String(state.defId) === String(def.id)) ? "true" : "false");
      btn.setAttribute("aria-label", placed
        ? (def.name + "，已興建")
        : (warehoused ? (def.name + "，放回") : (def.name + "，未興建")));
      btn.addEventListener("click", function () { onPalette(def.id); });
      grid.appendChild(btn);
    });
    var count = $("placedCount");
    if (count) count.textContent = "已興建 " + placedN;
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
        var storedName = (storedDefRow && storedDefRow.name) || "這座建築";
        placeStatus.textContent = "放回「" + storedName + "」。不扣除金幣和材料。";
      } else {
        placeStatus.textContent = "按「確定放置」後才扣除資源；取消不會扣除。";
      }
    }
    var status = $("readyStatus");
    if (status && state.scene === 2) {
      var def = defById(state.defId);
      if (state.unstoreId) {
        var takeName = (def && def.name) || "這座建築";
        status.textContent = "請點選空地，放回「" + takeName + "」。不扣除金幣和材料。";
      } else if (readyToPreview()) status.textContent = "已選擇「" + def.name + "」和這個位置。";
      else if (state.pad && !def && footprintFree(state.pad.c, state.pad.r, null)) {
        status.textContent = "已選擇空地。請打開清單，選擇要興建的建築物。";
      }
      else if (def && !placedDef(def.id) && !state.pad) status.textContent = "請點選金色空地，興建「" + def.name + "」。";
      else status.textContent = "請點選金色空地，或打開清單選擇要興建的建築物。";
    }
    var map = $("townMap");
    if (map) {
      map.className = "map is-scene-" + state.scene + (state.listOpen && state.scene === 2 ? " is-list-open" : "") + (sheetOn ? " is-sheet" : "");
      var sceneLabel = "場景 " + state.scene;
      if (sheetOn) sceneLabel = "場景 4 · 升級";
      else if (state.scene === 1) sceneLabel = "場景 1 · 查看地圖";
      map.setAttribute("aria-label", sceneLabel);
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
      var src = assetSrc(def.name, true);
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

  function diamondPoints(cx, cy, hx, hy) {
    return [
      cx.toFixed(2) + "," + (cy - hy).toFixed(2),
      (cx + hx).toFixed(2) + "," + cy.toFixed(2),
      cx.toFixed(2) + "," + (cy + hy).toFixed(2),
      (cx - hx).toFixed(2) + "," + cy.toFixed(2)
    ].join(" ");
  }

  /* Chosen outline: 3px stroke, fill none. The path is inset by half that
     stroke, taken from the slab's painted diamond, so the outer edge meets
     the cell and the centre stays clear for the badge. */
  function syncChosenMark() {
    var slab = document.querySelector("#townMap .pad > .slab");
    if (!slab || slab.offsetWidth < 2 || slab.offsetHeight < 2) return;
    var painted = slab.getBoundingClientRect();
    var scaleX = painted.width / slab.offsetWidth;
    var scaleY = painted.height / slab.offsetHeight;
    if (!(scaleX > 0) || !(scaleY > 0) || !(painted.width > 1)) return;
    var faceH = painted.height * (50 / 120);
    var hx = (painted.width / 2) / scaleX;
    var hy = faceH / scaleY;
    var ap = (painted.width / 2) * faceH /
      Math.sqrt((painted.width / 2) * (painted.width / 2) + faceH * faceH);
    var scale = Math.min(scaleX, scaleY);
    var inset = 1.5 * scale;
    if (!(ap > inset) || !(hx > 0) || !(hy > 0)) return;
    var k = 1 - inset / ap;
    var pts = diamondPoints(hx, hy, hx * k, hy * k);
    var svg = "<svg xmlns='http://www.w3.org/2000/svg' " +
      "viewBox='0 0 " + slab.offsetWidth.toFixed(2) + " " + slab.offsetHeight.toFixed(2) + "'>" +
      "<polygon points='" + pts + "' fill='none' stroke='#7c2d12' stroke-width='3' " +
      "stroke-linejoin='round'/></svg>";
    var next = "data:image/svg+xml," + encodeURIComponent(svg);
    if (next === MARK_CHOSEN) return;
    MARK_CHOSEN = next;
    var nodes = document.querySelectorAll("#townMap .pad.is-chosen > .mark");
    for (var i = 0; i < nodes.length; i += 1) {
      if (nodes[i].getAttribute("src") !== next) nodes[i].src = next;
    }
  }

  /* Focus ring: the face diamond pushed out by the same gap on every edge,
     so the aspect stays. Dashed strokes only, outside the solid chosen line. */
  function syncFocusRing() {
    var map = $("townMap");
    var slab = document.querySelector("#townMap .pad > .slab");
    var btn = document.querySelector("#townMap .cell-btn");
    if (!map || !slab || !btn || slab.offsetWidth < 2 || btn.offsetWidth < 2) return;
    var painted = slab.getBoundingClientRect();
    var halfW = slab.offsetWidth / 2;
    var halfH = slab.offsetHeight * (50 / 120);
    var halfWp = painted.width / 2;
    var halfHp = painted.height * (50 / 120);
    var ap = (halfWp * halfHp) / Math.sqrt(halfWp * halfWp + halfHp * halfHp);
    if (!(ap > 0) || !(halfW > 0)) return;
    var scale = halfWp / halfW;
    var gap = 3;
    var k = 1 + gap / ap;
    var ringW = 2 * k * halfW;
    var ringH = 2 * k * halfH;
    /* Width 3 in this viewBox is about 2.4px on screen. The path sits 3px
       outside the cell, so the inner edge lands about 2px outside and the
       dash still covers the centreline. */
    var unit = 2.42 / (3 * scale);
    var pad = 2 / scale;
    var boxW = ringW + pad * 2;
    var boxH = ringH + pad * 2;
    var cx = boxW / 2;
    var cy = boxH / 2;
    var outerPts = diamondPoints(cx / unit, cy / unit, (ringW / 2) / unit, (ringH / 2) / unit);
    /* One dash per edge, in viewBox units, with a short gap at the corner.
       pathLength would put that gap on a different part of the stroke. */
    var edgeLen = Math.hypot((ringW / 2) / unit, (ringH / 2) / unit);
    var dash = (edgeLen * 0.82).toFixed(2) + " " + (edgeLen * 0.18).toFixed(2);
    var vbW = boxW / unit;
    var vbH = boxH / unit;
    ringGeom = { vbW: vbW, vbH: vbH, points: outerPts, dash: dash };
    var svg = "<svg xmlns='http://www.w3.org/2000/svg' preserveAspectRatio='none' " +
      "shape-rendering='geometricPrecision' width='" + boxW.toFixed(2) + "' height='" + boxH.toFixed(2) + "' " +
      "viewBox='0 0 " + vbW.toFixed(2) + " " + vbH.toFixed(2) + "'>" +
      "<polygon fill='none' stroke='#6b4f2a' stroke-width='2' " +
      "stroke-linejoin='round' stroke-dasharray='" + dash + "' points='" + outerPts + "'/>" +
      "<polygon fill='none' stroke='#fff8e7' stroke-width='3' " +
      "stroke-linejoin='round' stroke-dasharray='" + dash + "' points='" + outerPts + "'/>" +
      "</svg>";
    map.style.setProperty("--ring-x", (btn.offsetWidth / 2 - boxW / 2).toFixed(3) + "px");
    map.style.setProperty("--ring-y", (btn.offsetHeight / 2 - boxH / 2).toFixed(3) + "px");
    map.style.setProperty("--ring-w", boxW.toFixed(3) + "px");
    map.style.setProperty("--ring-h", boxH.toFixed(3) + "px");
    map.style.setProperty("--ring-image", "url(\"data:image/svg+xml," + encodeURIComponent(svg) + "\")");
    placeFocusRing();
  }

  function paintVillage() {
    return $("village");
  }

  function screenScale(el) {
    var box = el.getBoundingClientRect();
    var base = el.offsetWidth;
    if (!(base > 0) || !(box.width > 0)) return 1;
    return box.width / base;
  }

  /* Content position inside the scrolling map for a screen-pixel box. */
  function layoutBox(village, screenLeft, screenTop, screenW, screenH) {
    var box = village.getBoundingClientRect();
    var scale = screenScale(village);
    return {
      scale: scale,
      left: village.scrollLeft + (screenLeft - box.left) / scale,
      top: village.scrollTop + (screenTop - box.top) / scale,
      width: screenW / scale,
      height: screenH / scale
    };
  }

  function ensurePaintSvg(id, host) {
    if (!host) return null;
    var ns = "http://www.w3.org/2000/svg";
    var paint = document.getElementById(id);
    if (!paint || paint.namespaceURI !== ns) {
      if (paint && paint.parentNode) paint.parentNode.removeChild(paint);
      paint = document.createElementNS(ns, "svg");
      paint.id = id;
      paint.setAttribute("aria-hidden", "true");
      paint.setAttribute("preserveAspectRatio", "none");
    }
    if (paint.parentNode !== host) host.appendChild(paint);
    return paint;
  }

  /* The ring sits on the map, under the palette and every bar, so the
     scrollport does not cut a stroke that is still on the map. Device
     pixels are SVG rects: a bitmap inside the stage scale is resampled
     and the cream moves onto the wrong device pixel. */
  function ensureRingPaint() {
    return ensurePaintSvg("focusRingPaint", $("townMap"));
  }

  function ensureChosenPaint() {
    return ensurePaintSvg("chosenMarkPaint", paintVillage());
  }

  function hidePaint(paint) {
    if (!paint) return;
    while (paint.firstChild) paint.removeChild(paint.firstChild);
    paint.setAttribute("hidden", "");
    paint.style.display = "none";
  }

  function hideRing(ring) {
    hidePaint(ring || document.getElementById("focusRingPaint"));
  }

  function hideLine(paint) {
    hidePaint(paint || document.getElementById("chosenMarkPaint"));
  }

  /* Scene 2 and scene 3 each show one bar, and the palette may be open.
     The box is the live border of whatever is actually showing. */
  function shownBoxes(selector) {
    var nodes = document.querySelectorAll(selector);
    var rects = [];
    for (var i = 0; i < nodes.length; i += 1) {
      var el = nodes[i];
      if (!el || el.hidden) continue;
      var cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      var box = el.getBoundingClientRect();
      if (box.width < 2 || box.height < 2) continue;
      rects.push({
        el: el,
        left: box.left,
        top: box.top,
        right: box.right,
        bottom: box.bottom
      });
    }
    return rects;
  }

  /* Bars, the palette, and the scene-1 button. Each border box grows out
     to the device-pixel grid so a fractional edge cannot cut a pixel in
     half and blend the band into a rounded corner. */
  function coverRects() {
    var dpr = window.devicePixelRatio || 1;
    var rects = shownBoxes("#townMap .place-bar")
      .concat(shownBoxes("#townMap .palette"))
      .concat(shownBoxes("#townMap .cta"));
    var snapped = [];
    for (var i = 0; i < rects.length; i += 1) {
      var r = rects[i];
      snapped.push({
        el: r.el,
        left: Math.floor(r.left * dpr + 1e-4) / dpr,
        top: Math.floor(r.top * dpr + 1e-4) / dpr,
        right: Math.ceil(r.right * dpr - 1e-4) / dpr,
        bottom: Math.ceil(r.bottom * dpr - 1e-4) / dpr
      });
    }
    return snapped;
  }

  function hitsCover(rects, x0, y0, x1, y1) {
    for (var i = 0; i < rects.length; i += 1) {
      var r = rects[i];
      if (x0 < r.right && x1 > r.left && y0 < r.bottom && y1 > r.top) return true;
    }
    return false;
  }

  /* Cell-sized SVG. ViewBox units are screen px, so one device pixel is
     1/dpr wide after the stage scale. The chosen line snaps its layout
     position and undoes that in the viewBox. The ring's paint origin snaps
     a half CSS pixel onto a whole CSS pixel, so at scale 1 that half pixel
     is carried in the viewBox instead of in the element's screen origin. */
  function mountDeviceSvg(paint, village, screenLeft, screenTop, screenW, screenH, deviceOrigin) {
    var scale = screenScale(village);
    var box = village.getBoundingClientRect();
    if (!(scale > 0) || !(box.width > 2)) return null;
    var cs = getComputedStyle(village);
    var borderLeft = parseFloat(cs.borderLeftWidth) || 0;
    var borderTop = parseFloat(cs.borderTopWidth) || 0;
    var targetLeft = screenLeft;
    var targetTop = screenTop;
    if (deviceOrigin && Math.abs(scale - 1) < 0.02) {
      var fracX = screenLeft - Math.floor(screenLeft);
      var fracY = screenTop - Math.floor(screenTop);
      if (Math.abs(fracX - 0.5) < 0.05) targetLeft = Math.floor(screenLeft);
      if (Math.abs(fracY - 0.5) < 0.05) targetTop = Math.floor(screenTop);
    }
    var rawLeft = village.scrollLeft + (targetLeft - box.left) / scale - borderLeft;
    var rawTop = village.scrollTop + (targetTop - box.top) / scale - borderTop;
    var leftPx = deviceOrigin ? rawLeft : Math.round(village.scrollLeft + (screenLeft - box.left) / scale - borderLeft);
    var topPx = deviceOrigin ? rawTop : Math.round(village.scrollTop + (screenTop - box.top) / scale - borderTop);
    while (paint.firstChild) paint.removeChild(paint.firstChild);
    paint.removeAttribute("hidden");
    paint.style.display = "block";
    paint.setAttribute("viewBox", "0 0 " + screenW + " " + screenH);
    paint.style.width = (screenW / scale) + "px";
    paint.style.height = (screenH / scale) + "px";
    paint.style.left = leftPx + "px";
    paint.style.top = topPx + "px";
    var shiftX = deviceOrigin ? (targetLeft - screenLeft) : (leftPx - (village.scrollLeft + (screenLeft - box.left) / scale - borderLeft)) * scale;
    var shiftY = deviceOrigin ? (targetTop - screenTop) : (topPx - (village.scrollTop + (screenTop - box.top) / scale - borderTop)) * scale;
    if (deviceOrigin) {
      var placed = paint.getBoundingClientRect();
      var errX = targetLeft - placed.left;
      var errY = targetTop - placed.top;
      if (Math.abs(errX) > 1e-3 || Math.abs(errY) > 1e-3) {
        leftPx += errX / scale;
        topPx += errY / scale;
        paint.style.left = leftPx + "px";
        paint.style.top = topPx + "px";
        placed = paint.getBoundingClientRect();
      }
      shiftX = placed.left - screenLeft;
      shiftY = placed.top - screenTop;
    }
    return {
      ns: "http://www.w3.org/2000/svg",
      shiftX: shiftX,
      shiftY: shiftY,
      scale: scale
    };
  }

  /* Clip definitions live beside the map, not inside the line svg, so the
     line's own shapes stay the stroked rects. The clip is applied to the
     group of those rects, in the same user space as the viewBox. */
  function clipDefsHost() {
    var map = $("townMap");
    if (!map) return null;
    var ns = "http://www.w3.org/2000/svg";
    var host = document.getElementById("paintClipDefs");
    if (!host || host.namespaceURI !== ns) {
      if (host && host.parentNode) host.parentNode.removeChild(host);
      host = document.createElementNS(ns, "svg");
      host.id = "paintClipDefs";
      host.setAttribute("aria-hidden", "true");
      host.setAttribute("width", "0");
      host.setAttribute("height", "0");
      host.style.position = "absolute";
      host.style.width = "0";
      host.style.height = "0";
      host.style.overflow = "hidden";
      host.style.pointerEvents = "none";
    }
    if (host.parentNode !== map) map.appendChild(host);
    return host;
  }

  /* Even-odd clip: the cell box minus each showing bar, the palette, and
     the scene-1 button. Each hole is that border box grown out to the
     device-pixel grid, in the same user space as the stroked rects. */
  function clipPaintToCovers(svg, covers, screenLeft, screenTop, shiftX, shiftY, screenW, screenH, clipId) {
    var ns = "http://www.w3.org/2000/svg";
    var defs = clipDefsHost();
    if (!defs) return;
    var prior = document.getElementById(clipId);
    if (prior && prior.parentNode) prior.parentNode.removeChild(prior);
    var clip = document.createElementNS(ns, "clipPath");
    clip.setAttribute("id", clipId);
    clip.setAttribute("clipPathUnits", "userSpaceOnUse");
    var path = document.createElementNS(ns, "path");
    var dpr = window.devicePixelRatio || 1;
    var originX = screenLeft + shiftX;
    var originY = screenTop + shiftY;
    var d = "M0 0H" + screenW + "V" + screenH + "H0Z";
    for (var i = 0; i < covers.length; i += 1) {
      var r = covers[i];
      var x0 = Math.floor(r.left * dpr + 1e-4) / dpr - originX;
      var y0 = Math.floor(r.top * dpr + 1e-4) / dpr - originY;
      var x1 = Math.ceil(r.right * dpr - 1e-4) / dpr - originX;
      var y1 = Math.ceil(r.bottom * dpr - 1e-4) / dpr - originY;
      d += "M" + x0 + " " + y0 + "V" + y1 + "H" + x1 + "V" + y0 + "Z";
    }
    path.setAttribute("d", d);
    path.setAttribute("fill-rule", "evenodd");
    path.setAttribute("clip-rule", "evenodd");
    path.setAttribute("shape-rendering", "crispEdges");
    clip.appendChild(path);
    defs.appendChild(clip);
    var group = document.createElementNS(ns, "g");
    while (svg.firstChild) group.appendChild(svg.firstChild);
    group.setAttribute("clip-path", "url(#" + clipId + ")");
    group.setAttribute("clip-rule", "evenodd");
    group.setAttribute("shape-rendering", "crispEdges");
    svg.appendChild(group);
    svg.removeAttribute("clip-path");
  }

  function paintRun(svg, ns, screenLeft, screenTop, shiftX, shiftY, x, y, w, h, color) {
    var rect = document.createElementNS(ns, "rect");
    rect.setAttribute("x", (x - screenLeft - shiftX).toFixed(3));
    rect.setAttribute("y", (y - screenTop - shiftY).toFixed(3));
    rect.setAttribute("width", w.toFixed(3));
    rect.setAttribute("height", h.toFixed(3));
    rect.setAttribute("fill", color);
    rect.setAttribute("shape-rendering", "crispEdges");
    svg.appendChild(rect);
  }

  /* Scene 3 keeps the line on the current choice while the confirm bar waits. */
  function lineHeldForConfirm() {
    if (state.scene !== 3 || state.sheet || !state.pad) return false;
    var bar = document.getElementById("uxPlaceBar");
    if (!bar) return false;
    var cs = getComputedStyle(bar);
    return cs.display !== "none" && cs.visibility !== "hidden";
  }

  function clearMarks(part, force) {
    var dropRing = part !== "line";
    var dropLine = part !== "ring";
    if (dropLine && !force && lineHeldForConfirm()) dropLine = false;
    if (dropRing) {
      ringBtn = null;
      hideRing();
    }
    if (dropLine) hideLine();
  }

  function choicePad() {
    var chosen = document.querySelector("#townMap .pad.is-chosen");
    if (chosen) return chosen;
    if (state.scene === 3 && !state.sheet) {
      return document.querySelector("#townMap .pad.is-preview");
    }
    return null;
  }

  /* Screen-pixel diamond of the slab's top face. Same rect the chosen
     stroke uses, so the ring and the line share one edge. */
  function slabFace(slab) {
    var box = slab.getBoundingClientRect();
    if (!(box.width > 2) || !(box.height > 2)) return null;
    var lift = 10 * (box.width / 168);
    var halfW = box.width / 2;
    var halfH = box.height * (50 / 120);
    if (!(halfW > 2) || !(halfH > 2)) return null;
    return {
      cx: box.left + halfW,
      cy: box.top + box.height / 2 - lift,
      halfW: halfW,
      halfH: halfH
    };
  }

  /* Half the interior angle at a diamond tip, from the two live edges. */
  function tipHalfAngle(tips, index) {
    var v = tips[index];
    var prev = tips[(index + 3) % 4];
    var next = tips[(index + 1) % 4];
    var ax = prev[0] - v[0];
    var ay = prev[1] - v[1];
    var bx = next[0] - v[0];
    var by = next[1] - v[1];
    var la = Math.hypot(ax, ay) || 1;
    var lb = Math.hypot(bx, by) || 1;
    var cos = (ax * bx + ay * by) / (la * lb);
    if (cos > 1) cos = 1;
    if (cos < -1) cos = -1;
    return Math.acos(cos) / 2;
  }

  /* Retreat along one edge so the chord between the cream bands is about 6px.
     The bands already sit outside the cell, so the chord is
     2 * (d * sin(theta) + band * cos(theta)). d = 0 when that offset
     alone is wide enough. A short edge uses the same 6px chord: a 4.5px
     target leaves the blunt tip under 4px once the band is included. */
  function openingRetreat(theta, edgeLen, band) {
    var sine = Math.sin(theta);
    var cosine = Math.cos(theta);
    if (!(sine > 1e-4)) return 0;
    var d = (3 - band * cosine) / sine;
    /* Acute tips already clear 6px from the band offset, but a zero retreat
       snaps the two opposite tips a pixel apart. Keep a short shared retreat. */
    if (d < 1) d = 1;
    var cap = edgeLen * 0.09;
    if (d > cap) d = cap;
    return d;
  }

  /* Dashes live on the map, in a box around the focused cell.
     Each rect is one device pixel of a solid band: inner cream 3px,
     outer brown 2px, between the two corner openings of that edge. */
  function placeFocusRing() {
    var ring = ensureRingPaint();
    var map = $("townMap");
    if (!ring || !map) return;
    if (state.sheet) {
      hideRing(ring);
      return;
    }
    var visible = document.querySelector("#townMap .cell-btn:focus-visible");
    if (visible) ringBtn = visible;
    var btn = visible;
    if (!btn && ringBtn && document.activeElement === ringBtn && ringBtn.matches(":focus-visible")) {
      btn = ringBtn;
    }
    if (!btn) ringBtn = null;
    var pad = btn && btn.closest ? btn.closest(".pad") : null;
    var slab = pad && pad.querySelector(":scope > .slab");
    var face = slab ? slabFace(slab) : null;
    if (!btn || !face) {
      hideRing(ring);
      return;
    }
    /* Inner cream is 3px, starting 2px outside the cell. Outer brown is
       2px. A device pixel takes the colour of the band its centre sits on. */
    var cream = 3;
    var brown = 2;
    var minOut = 2;
    var band = minOut + cream * 0.5;
    var reach = minOut + cream + brown + 1;
    var span = Math.hypot(face.halfW, face.halfH) || 1;
    var hx = face.halfW + reach * span / face.halfH;
    var hy = face.halfH + reach * span / face.halfW;
    var dpr = window.devicePixelRatio || 1;
    var padPx = 2;
    var screenLeft = Math.floor((face.cx - hx - padPx) * dpr) / dpr;
    var screenTop = Math.floor((face.cy - hy - padPx) * dpr) / dpr;
    var screenRight = Math.ceil((face.cx + hx + padPx) * dpr) / dpr;
    var screenBottom = Math.ceil((face.cy + hy + padPx) * dpr) / dpr;
    var screenW = screenRight - screenLeft;
    var screenH = screenBottom - screenTop;
    var mounted = mountDeviceSvg(ring, map, screenLeft, screenTop, screenW, screenH, true);
    if (!mounted) {
      hideRing(ring);
      return;
    }
    var tips = [
      [face.cx, face.cy - face.halfH],
      [face.cx + face.halfW, face.cy],
      [face.cx, face.cy + face.halfH],
      [face.cx - face.halfW, face.cy]
    ];
    var frames = [];
    var thetas = [];
    for (var t = 0; t < 4; t += 1) thetas.push(tipHalfAngle(tips, t));
    for (var i = 0; i < 4; i += 1) {
      var a = tips[i];
      var b = tips[(i + 1) % 4];
      var dx = b[0] - a[0];
      var dy = b[1] - a[1];
      var len = Math.hypot(dx, dy) || 1;
      var nx = -dy / len;
      var ny = dx / len;
      var mx = (a[0] + b[0]) / 2;
      var my = (a[1] + b[1]) / 2;
      var out = (mx + nx - face.cx) * (mx + nx - face.cx) + (my + ny - face.cy) * (my + ny - face.cy);
      var inn = (mx - nx - face.cx) * (mx - nx - face.cx) + (my - ny - face.cy) * (my - ny - face.cy);
      if (out < inn) { nx = -nx; ny = -ny; }
      frames.push({
        a: a, nx: nx, ny: ny, dx: dx, dy: dy, len: len,
        d0: openingRetreat(thetas[i], len, band),
        d1: openingRetreat(thetas[(i + 1) % 4], len, band)
      });
    }
    /* Closest edge to the device-pixel centre. The far side of a convex
       diamond is a larger line distance, so the maximum would pick it.
       The outer part of the band stops a pixel short of the opening, so
       its corner cannot become the only cream at the tip. */
    function atCentre(x, y) {
      var best = null;
      for (var f = 0; f < frames.length; f += 1) {
        var edge = frames[f];
        var sd = (x - edge.a[0]) * edge.nx + (y - edge.a[1]) * edge.ny;
        var along = ((x - edge.a[0]) * edge.dx + (y - edge.a[1]) * edge.dy) / edge.len;
        if (sd < -0.5) continue;
        var cross = sd < 0 ? -sd : sd;
        if (!best || cross < best.cross) best = { sd: sd, cross: cross, along: along, edge: edge };
      }
      return best;
    }
    var ap = (face.halfW * face.halfH) / Math.hypot(face.halfW, face.halfH);
    function outsideAt(x, y) {
      var span = Math.abs(x - face.cx) / face.halfW + Math.abs(y - face.cy) / face.halfH;
      return (span - 1) * ap;
    }
    var covers = coverRects();
    var mapBox = map.getBoundingClientRect();
    var mapSlack = 2;
    var step = 1 / dpr;
    var bw = Math.round(screenW * dpr);
    var bh = Math.round(screenH * dpr);
    for (var iy = 0; iy < bh; iy += 1) {
      var y0 = screenTop + iy * step;
      var runColor = "";
      var runX = 0;
      for (var ix = 0; ix <= bw; ix += 1) {
        var color = "";
        var x0 = screenLeft + ix * step;
        if (ix < bw
          && x0 < mapBox.right + mapSlack && x0 + step > mapBox.left - mapSlack
          && y0 < mapBox.bottom + mapSlack && y0 + step > mapBox.top - mapSlack
          && !hitsCover(covers, x0, y0, x0 + step, y0 + step)) {
          var cx = x0 + step * 0.5;
          var cy = y0 + step * 0.5;
          var mid = atCentre(cx, cy);
          var centreOut = outsideAt(cx, cy);
          /* A down-right normal runs with the pixel grid, so a pixel whose
             centre is just past 2px still covers the point 1px closer to
             the cell. Keep that edge back until the centre clears it. Near
             an opening the same inset leaves the last cream pixel empty,
             so it eases off along the last quarter of the edge. */
          var slant = mid ? Math.max(0, mid.edge.nx + mid.edge.ny) : 0;
          var fromEnd = mid ? Math.min(mid.along, mid.edge.len - mid.along) : 0;
          var inset = mid && fromEnd < mid.edge.len * 0.25 ? 0.34 : 0.45;
          var innerLimit = minOut + slant * inset;
          if (mid && centreOut >= innerLimit && centreOut < minOut + cream + brown) {
            /* Brown stops short of the opening so it cannot be the only ink at the tip. */
            var tipRetreat = centreOut >= minOut + cream - 1 ? 1.5 : 0;
            var edge = mid.edge;
            if (mid.along >= edge.d0 + tipRetreat && mid.along <= edge.len - edge.d1 - tipRetreat) {
              color = centreOut < minOut + cream ? "#fff8e7" : "#6b4f2a";
            }
          }
        }
        if (color !== runColor) {
          if (runColor) {
            paintRun(
              ring, mounted.ns, screenLeft, screenTop, mounted.shiftX, mounted.shiftY,
              screenLeft + runX * step, y0, (ix - runX) * step, step, runColor
            );
          }
          runColor = color;
          runX = ix;
        }
      }
    }
    clipPaintToCovers(
      ring, covers, screenLeft, screenTop, mounted.shiftX, mounted.shiftY,
      screenW, screenH, "focusRingClip"
    );
    trimPaintBox(
      ring, screenLeft + mounted.shiftX, screenTop + mounted.shiftY,
      screenW, screenH, mounted.scale, covers
    );
  }

  /* The ring's border box must stay off the bars, the palette, and the
     scene-1 button. An overlapping box changes how their rounded corners
     are rasterized, even where the band itself is not drawn. */
  function trimPaintBox(paint, originX, originY, screenW, screenH, scale, covers) {
    if (!(scale > 0)) return;
    var left = originX;
    var top = originY;
    var right = originX + screenW;
    var bottom = originY + screenH;
    var guard = 0;
    while (guard < 8) {
      guard += 1;
      var best = null;
      for (var i = 0; i < covers.length; i += 1) {
        var c = covers[i];
        if (right <= c.left || left >= c.right || bottom <= c.top || top >= c.bottom) continue;
        var options = [
          { edge: "bottom", at: c.top, loss: bottom - c.top },
          { edge: "top", at: c.bottom, loss: c.bottom - top },
          { edge: "right", at: c.left, loss: right - c.left },
          { edge: "left", at: c.right, loss: c.right - left }
        ];
        for (var k = 0; k < options.length; k += 1) {
          var opt = options[k];
          if (!(opt.loss > 0.05)) continue;
          var width = right - left;
          var height = bottom - top;
          if (opt.edge === "left" || opt.edge === "right") width -= opt.loss;
          else height -= opt.loss;
          if (width < 2 || height < 2) continue;
          if (!best || opt.loss < best.loss) best = opt;
        }
      }
      if (!best) break;
      if (best.edge === "bottom") bottom = best.at;
      else if (best.edge === "top") top = best.at;
      else if (best.edge === "right") right = best.at;
      else left = best.at;
    }
    var cutL = left - originX;
    var cutT = top - originY;
    var viewW = right - left;
    var viewH = bottom - top;
    if (cutL < 0.05 && cutT < 0.05 && Math.abs(viewW - screenW) < 0.05 && Math.abs(viewH - screenH) < 0.05) return;
    paint.setAttribute("viewBox", cutL + " " + cutT + " " + viewW + " " + viewH);
    paint.style.left = ((parseFloat(paint.style.left) || 0) + cutL / scale) + "px";
    paint.style.top = ((parseFloat(paint.style.top) || 0) + cutT / scale) + "px";
    paint.style.width = (viewW / scale) + "px";
    paint.style.height = (viewH / scale) + "px";
  }

  /* Chosen line: whole device pixels of #7c2d12. The cell-aligned sample
     of each pixel sits on the stroke, and no corner sticks out past it. */
  function placeChosenMark() {
    var paint = ensureChosenPaint();
    var village = paintVillage();
    if (!paint || !village) return;
    var pad = choicePad();
    var slab = pad && pad.querySelector(":scope > .slab");
    var mark = pad && pad.querySelector(":scope > .mark");
    if (state.sheet || !slab || !mark || mark.hidden) {
      hideLine(paint);
      return;
    }
    var face = slabFace(slab);
    if (!face) {
      hideLine(paint);
      return;
    }
    var dpr = window.devicePixelRatio || 1;
    var margin = 4;
    var screenLeft = Math.floor((face.cx - face.halfW - margin) * dpr) / dpr;
    var screenTop = Math.floor((face.cy - face.halfH - margin) * dpr) / dpr;
    var screenRight = Math.ceil((face.cx + face.halfW + margin) * dpr) / dpr;
    var screenBottom = Math.ceil((face.cy + face.halfH + margin) * dpr) / dpr;
    var mounted = mountDeviceSvg(
      paint, village, screenLeft, screenTop,
      screenRight - screenLeft, screenBottom - screenTop
    );
    if (!mounted) {
      hideLine(paint);
      return;
    }
    var ap = (face.halfW * face.halfH) / Math.hypot(face.halfW, face.halfH);
    function outsideAt(x, y) {
      var span = Math.abs(x - face.cx) / face.halfW + Math.abs(y - face.cy) / face.halfH;
      return (span - 1) * ap;
    }
    var covers = coverRects();
    var boundX = face.cx - face.halfW;
    var boundY = face.cy - face.halfH;
    var cssOffX = (boundX - Math.floor(boundX) + 0.5) % 1;
    var cssOffY = (boundY - Math.floor(boundY) + 0.5) % 1;
    if (cssOffX < 0) cssOffX += 1;
    if (cssOffY < 0) cssOffY += 1;
    var screenW = screenRight - screenLeft;
    var screenH = screenBottom - screenTop;
    var bw = Math.round(screenW * dpr);
    var bh = Math.round(screenH * dpr);
    var step = 1 / dpr;
    for (var iy = 0; iy < bh; iy += 1) {
      var y0 = screenTop + iy * step;
      var y1 = y0 + step;
      var runX = -1;
      for (var ix = 0; ix <= bw; ix += 1) {
        var on = false;
        if (ix < bw) {
          var x0 = screenLeft + ix * step;
          var x1 = x0 + step;
          if (!hitsCover(covers, x0, y0, x1, y1)) {
            var maxO = outsideAt(x0, y0);
            var c1 = outsideAt(x1, y0);
            var c2 = outsideAt(x0, y1);
            var c3 = outsideAt(x1, y1);
            if (c1 > maxO) maxO = c1;
            if (c2 > maxO) maxO = c2;
            if (c3 > maxO) maxO = c3;
            /* The sample aligned with the cell decides the stroke. A corner
               past the outer limit would show up beyond the cell edge. */
            var cssOut = outsideAt(x0 + cssOffX, y0 + cssOffY);
            on = cssOut <= 0.55 && cssOut >= -1.4 && maxO <= 1.4;
          }
        }
        if (on) {
          if (runX < 0) runX = ix;
        } else if (runX >= 0) {
          paintRun(
            paint, mounted.ns, screenLeft, screenTop, mounted.shiftX, mounted.shiftY,
            screenLeft + runX * step, y0, (ix - runX) * step, step, "#7c2d12"
          );
          runX = -1;
        }
      }
    }
    clipPaintToCovers(
      paint, covers, screenLeft, screenTop, mounted.shiftX, mounted.shiftY,
      screenW, screenH, "chosenMarkClip"
    );
  }

  function render() {
    if (!built) buildGrid();
    syncChosenMark();
    pads.forEach(renderCell);
    renderPalette();
    renderBars();
    renderSheet();
    renderMotion();
    syncFocusRing();
    placeChosenMark();
  }

  function onPalette(id) {
    if (placedDef(id)) {
      openSheet(id);
      return;
    }
    var warehoused = storedDef(id);
    if (warehoused) {
      beginWarehousePlace(warehoused);
      return;
    }
    state.unstoreId = null;
    state.defId = String(state.defId) === String(id) ? null : id;
    state.listOpen = true;
    if (state.defId != null && state.pad && !footprintFree(state.pad.c, state.pad.r, null, footprintOf(defById(state.defId)))) {
      state.pad = null;
      if (typeof showToast === "function") showToast("這個位置放不下這座建築物。", "info");
    }
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
      else if (typeof showToast === "function") showToast("想在這裏興建？請先按「我要起屋」。");
      return;
    }
    if (state.scene === 2) {
      var coveredNow = coveredAt(c, r);
      var freeNow = footprintFree(c, r, state.unstoreId, activeFootprint());
      if (!freeNow) {
        if (typeof showToast === "function") {
          showToast(coveredNow ? "這個位置已經有建築物。" : "這個位置放不下這座建築物。", "info");
        }
        return;
      }
      if (state.unstoreId) {
        state.pad = { c: c, r: r };
        state.scene = 3;
        state.listOpen = false;
        state.sheet = false;
        render();
        return;
      }
      state.pad = sameCell(state.pad, { c: c, r: r }) ? null : { c: c, r: r };
      render();
      return;
    }
    if (state.scene === 3) {
      if (occ) {
        if (typeof showToast === "function") showToast("這裏已有「" + occ.name + "」，不能放置。", "info");
        return;
      }
      if (!footprintFree(c, r, state.unstoreId)) {
        if (typeof showToast === "function") showToast("這個位置放不下這座建築物。", "info");
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
    var keepUnstore = state.unstoreId;
    state.scene = 2;
    state.sheet = false;
    state.confirming = false;
    state.instantUpgrade = false;
    state.pad = null;
    state.unstoreId = keepUnstore;
    if (typeof showToast === "function") showToast("已取消，資源未扣除", "info");
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
      if (typeof showToast === "function") showToast("已放好「" + name + "」。");
      celebrate("place", cell);
      await loadTown();
    } catch (e) {
      if (!showUnfit(e)) {
        if (typeof showToast === "function") showToast(e.message || "未能放回", "error");
        render();
      }
    }
  }

  /* A child-facing sentence is written Chinese. English and JSON stay hidden. */
  function childFacing(err) {
    var msg = err && typeof err.message === "string" ? err.message.trim() : "";
    /* A fragment such as a range or occupancy note is not a sentence for the child. */
    if (msg && /[\u3400-\u9fff]/.test(msg) && /[。！？]$/.test(msg)) return msg;
    return "";
  }

  function showUnfit(err) {
    var status = err && err.status;
    if (!(status >= 400 && status < 500)) return false;
    state.scene = 2;
    state.pad = null;
    state.sheet = false;
    state.confirming = false;
    state.instantUpgrade = false;
    var sentence = childFacing(err) || "這個位置放不下這座建築物。";
    if (typeof showToast === "function") showToast(sentence, "info");
    render();
    return true;
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
      if (showUnfit(e)) return;
      var msg = e.message || "未能興建";
      if (typeof showToast === "function") {
        if (msg === "城鎮沒有空位，請先收起或移動其他建築。") showToast(msg, "info");
        else showToast(msg, "error");
      }
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

  function returnToMap() {
    state.scene = 1;
    state.sheet = false;
    state.listOpen = false;
    state.pad = null;
    state.defId = null;
    state.unstoreId = null;
    state.confirming = false;
    state.instantUpgrade = false;
    var bar = document.getElementById("placementBar");
    if (bar) bar.classList.remove("active");
    render();
  }

  function wire() {
    var map = $("townMap");
    if (!map || map.dataset.wired === "1") return;
    map.dataset.wired = "1";
    window.addEventListener("resize", function () {
      syncChosenMark();
      syncFocusRing();
      placeChosenMark();
    });
    document.addEventListener("focusin", function (event) {
      var t = event.target;
      if (t && t.classList && t.classList.contains("cell-btn") && t.matches(":focus-visible")) {
        ringBtn = t;
      }
      placeFocusRing();
    }, true);
    document.addEventListener("focusout", function (event) {
      var next = event.relatedTarget;
      if (next && next.classList && next.classList.contains("cell-btn") && next.matches(":focus-visible")) {
        ringBtn = next;
        return;
      }
      ringBtn = null;
      hideRing();
    }, true);
    document.addEventListener("scroll", function () {
      placeFocusRing();
      placeChosenMark();
    }, true);
    document.addEventListener("click", function (event) {
      var nav = event.target && event.target.closest && event.target.closest("[data-kt-nav]");
      if (!nav || nav.getAttribute("data-kt-nav") === "town") return;
      clearMarks("both", true);
    }, true);
    map.addEventListener("click", function (event) {
      var target = event.target;
      var btn = target.closest && target.closest("button");
      var cellBtn = btn && btn.classList.contains("cell-btn") ? btn : null;
      /* Enter and Space activate the focused cell button even when a bar
         covers that button. A pointer tap still has to miss solid UI. */
      var fromKey = event.detail === 0 && event.clientX === 0 && event.clientY === 0;
      /* A pointer tap focuses the button without focus-visible. Drop that
         focus so a later focus-visible call still emits focusin. */
      /* Blur in this turn, before the browser handles the next key.
         A deferred blur races a later Space on the same button. */
      if (cellBtn && !fromKey) cellBtn.blur();
      if (cellBtn && fromKey) {
        var keyPad = cellBtn.closest(".pad");
        if (keyPad) {
          var kc = parseInt(keyPad.style.getPropertyValue("--c"), 10);
          var kr = parseInt(keyPad.style.getPropertyValue("--r"), 10);
          if (isFinite(kc) && isFinite(kr)) {
            onCell(kc, kr);
            return;
          }
        }
      }
      if (solidUiFromTarget(target)) return;
      /* A tap whose target sits outside the village is not a cell, even when
         rounded coordinates fall inside the village border. */
      var village = $("village");
      if (!village || !village.contains(target)) return;
      var point = activationPoint(event, cellBtn);
      if (solidUiCovers(point.x, point.y)) {
        /* Rounded coordinates can name a control while the event still
           names the cell that was hit. A cell that is itself the element
           at those coordinates stays inside the control. */
        var atPoint = document.elementFromPoint(point.x, point.y);
        var atBtn = atPoint && atPoint.closest && atPoint.closest(".cell-btn");
        if (!cellBtn || atBtn === cellBtn) return;
      }
      if (!pointInRect(point.x, point.y, visibleMapClip())) return;
      if (marginUnderToast(point.x, point.y)) return;
      if (cellBtn) {
        var pad = cellBtn.closest(".pad");
        if (pad) {
          var pc = parseInt(pad.style.getPropertyValue("--c"), 10);
          var pr = parseInt(pad.style.getPropertyValue("--r"), 10);
          if (isFinite(pc) && isFinite(pr)) {
            onCell(pc, pr);
            return;
          }
        }
      }
      if (btn) return;
      var hit = cellAt(point.x, point.y);
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
    var back = $("btnUxBack");
    if (back) back.addEventListener("click", returnToMap);
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
  window.ktBeginWarehousePlace = beginWarehousePlace;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", townUxSync);
  } else {
    townUxSync();
  }
})();
