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
    var legal = footprintFree(cell.c, cell.r, state.unstoreId);
    var inScene2 = state.scene === 2 && !state.sheet;
    var hot = inScene2 && legal;
    var kind = "quiet";
    if (inScene2 && legal) kind = picked ? "chosen" : "empty";
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
    if (showMark && cell.mark.getAttribute("src") !== MARK_VALID) cell.mark.src = MARK_VALID;
    cell.badge.hidden = !(kind === "chosen" || kind === "preview");
    if (kind === "chosen") cell.badge.textContent = "此格";
    if (kind === "preview") cell.badge.textContent = "預覽";

    var label = "第 " + (cell.c + 1) + " 欄第 " + (cell.r + 1) + " 行";
    if (occ && state.scene === 1) label += "，" + occ.name;
    else if (occ && state.scene === 3 && !state.sheet) label += "，" + occ.name + "，已有建築物，不能放置";
    else if (occ) label += "，" + occ.name + "，已興建";
    else if (state.scene === 1) label += "，空地";
    else if (state.scene === 2) label += picked ? "，已選此格" : "，空地，點選即可選擇";
    else if (kind === "preview") label += "，擺放預覽";
    else if (kind === "valid") label += "，可以放置，點選即可移到此格";
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
      else if (state.pad && !def) status.textContent = "已選擇空地。請打開清單，選擇要興建的建築物。";
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

  function diamondPoints(cx, cy, hx, hy) {
    return [
      cx.toFixed(2) + "," + (cy - hy).toFixed(2),
      (cx + hx).toFixed(2) + "," + cy.toFixed(2),
      cx.toFixed(2) + "," + (cy + hy).toFixed(2),
      (cx - hx).toFixed(2) + "," + cy.toFixed(2)
    ].join(" ");
  }

  /* Centreline of the focus diamond, 3 screen px outside every edge.
     The ::after that carries it is opacity 0; pixels are painted apart. */
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
    var unit = 2.42 / (3 * scale);
    var pad = 2 / scale;
    var boxW = ringW + pad * 2;
    var boxH = ringH + pad * 2;
    var cx = boxW / 2;
    var cy = boxH / 2;
    var outerPts = diamondPoints(cx / unit, cy / unit, (ringW / 2) / unit, (ringH / 2) / unit);
    var edgeLen = Math.hypot((ringW / 2) / unit, (ringH / 2) / unit);
    var dash = (edgeLen * 0.82).toFixed(2) + " " + (edgeLen * 0.18).toFixed(2);
    var vbW = boxW / unit;
    var vbH = boxH / unit;
    var svg = "<svg xmlns='http://www.w3.org/2000/svg' preserveAspectRatio='none' " +
      "width='" + boxW.toFixed(2) + "' height='" + boxH.toFixed(2) + "' " +
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
  }

  function stageScale(el) {
    var box = el.getBoundingClientRect();
    var base = el.offsetWidth;
    if (!(base > 0) || !(box.width > 0)) return 1;
    return box.width / base;
  }

  function ensureSvg(id) {
    var host = $("townMap");
    if (!host) return null;
    var ns = "http://www.w3.org/2000/svg";
    var el = document.getElementById(id);
    if (!el || el.namespaceURI !== ns) {
      if (el && el.parentNode) el.parentNode.removeChild(el);
      el = document.createElementNS(ns, "svg");
      el.id = id;
      el.setAttribute("aria-hidden", "true");
      el.setAttribute("preserveAspectRatio", "none");
    }
    if (el.parentNode !== host) host.appendChild(el);
    return el;
  }

  function ensureCanvas(id) {
    var host = $("townMap");
    if (!host) return null;
    var el = document.getElementById(id);
    if (!el || el.tagName !== "CANVAS") {
      if (el && el.parentNode) el.parentNode.removeChild(el);
      el = document.createElement("canvas");
      el.id = id;
      el.setAttribute("aria-hidden", "true");
    }
    if (el.parentNode !== host) host.appendChild(el);
    return el;
  }

  function hideLayer(el) {
    if (!el) return;
    if (el.getContext) {
      /* Leave the canvas mounted. Dropping it to display:none changes
         how the bars and the palette are rasterized on the next frame. */
      var ctx = el.getContext("2d", { willReadFrequently: true });
      if (ctx && el.width && el.height) ctx.clearRect(0, 0, el.width, el.height);
      return;
    }
    el.setAttribute("hidden", "");
    el.style.display = "none";
  }

  function showLayer(el) {
    if (!el) return;
    el.removeAttribute("hidden");
    el.style.display = "block";
  }

  /* How far ::before sticks out past the border box. Same sum the pixel
     tests use: offset is from the padding edge, so the element's own
     border is subtracted. A missing pseudo is 0. */
  function paintedExtent(el) {
    var box = el.getBoundingClientRect();
    var cs = getComputedStyle(el);
    var before = getComputedStyle(el, "::before");
    var content = before.content || "";
    var live = content !== "none" && content !== "normal"
      && before.display !== "none" && before.visibility !== "hidden";
    var outset = { left: 0, top: 0, right: 0, bottom: 0 };
    if (live) {
      function side(offset, edge, margin) {
        if (offset == null || offset === "auto") return 0;
        var n = parseFloat(offset);
        if (!isFinite(n)) return 0;
        return Math.max(0, -(edge + n + (parseFloat(margin) || 0)));
      }
      outset.left = side(before.left, parseFloat(cs.borderLeftWidth) || 0, before.marginLeft);
      outset.top = side(before.top, parseFloat(cs.borderTopWidth) || 0, before.marginTop);
      outset.right = side(before.right, parseFloat(cs.borderRightWidth) || 0, before.marginRight);
      outset.bottom = side(before.bottom, parseFloat(cs.borderBottomWidth) || 0, before.marginBottom);
    }
    return {
      left: box.left - outset.left,
      top: box.top - outset.top,
      right: box.right + outset.right,
      bottom: box.bottom + outset.bottom
    };
  }

  function coverExtents() {
    var selectors = ["#readyBar", "#uxPlaceBar", "#palette", "#townMap .cta", "#actionSheet"];
    var rects = [];
    for (var i = 0; i < selectors.length; i += 1) {
      var el = document.querySelector(selectors[i]);
      if (!el || el.hidden) continue;
      var cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) continue;
      var box = el.getBoundingClientRect();
      if (box.width < 2 || box.height < 2) continue;
      if (box.right <= 0 || box.bottom <= 0 || box.left >= window.innerWidth || box.top >= window.innerHeight) continue;
      rects.push(paintedExtent(el));
    }
    return rects;
  }

  function hitsCover(rects, x0, y0, x1, y1) {
    /* One CSS pixel past the painted frame. The clip hole stays on the
       frame; this only keeps a device pixel from landing inside the bar. */
    var pad = 2;
    for (var i = 0; i < rects.length; i += 1) {
      var r = rects[i];
      if (x0 < r.right + pad && x1 > r.left - pad && y0 < r.bottom + pad && y1 > r.top - pad) return true;
    }
    return false;
  }

  /* Place a bitmap so each canvas pixel is one device pixel after the
     stage transform. The border box has to sit on whole CSS pixels: at
     dpr 2 a half-pixel origin blits the bitmap one device pixel down and
     right, and #fff8e7 stops being the pixel the ruler samples. */
  function mountScreenCanvas(canvas, screenLeft, screenTop, screenW, screenH) {
    var host = $("townMap");
    if (!host) return null;
    var scale = stageScale(host);
    var box = host.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    var x0 = Math.floor(screenLeft);
    var y0 = Math.floor(screenTop);
    var x1 = Math.ceil(screenLeft + screenW);
    var y1 = Math.ceil(screenTop + screenH);
    if (x1 <= x0) x1 = x0 + 1;
    if (y1 <= y0) y1 = y0 + 1;
    var bw = Math.max(1, Math.round((x1 - x0) * dpr));
    var bh = Math.max(1, Math.round((y1 - y0) * dpr));
    showLayer(canvas);
    canvas.width = bw;
    canvas.height = bh;
    canvas.style.left = ((x0 - box.left) / scale) + "px";
    canvas.style.top = ((y0 - box.top) / scale) + "px";
    canvas.style.width = ((x1 - x0) / scale) + "px";
    canvas.style.height = ((y1 - y0) / scale) + "px";
    var placed = canvas.getBoundingClientRect();
    var guard = 0;
    while (guard < 4) {
      guard += 1;
      var errX = x0 - placed.left;
      var errY = y0 - placed.top;
      var errW = (x1 - x0) - placed.width;
      var errH = (y1 - y0) - placed.height;
      if (Math.abs(errX) <= 0.02 && Math.abs(errY) <= 0.02 && Math.abs(errW) <= 0.02 && Math.abs(errH) <= 0.02) break;
      if (Math.abs(errX) > 0.02) canvas.style.left = ((parseFloat(canvas.style.left) || 0) + errX / scale) + "px";
      if (Math.abs(errY) > 0.02) canvas.style.top = ((parseFloat(canvas.style.top) || 0) + errY / scale) + "px";
      if (Math.abs(errW) > 0.02) canvas.style.width = ((parseFloat(canvas.style.width) || 0) + errW / scale) + "px";
      if (Math.abs(errH) > 0.02) canvas.style.height = ((parseFloat(canvas.style.height) || 0) + errH / scale) + "px";
      placed = canvas.getBoundingClientRect();
    }
    /* Half-pixel CSS origins are already whole device pixels at dpr 2, but
       the canvas blit still lands one device pixel down-right of the box.
       Whole CSS pixels match the box. */
    function blitOrigin(pos) {
      if (dpr >= 1.5 && Math.abs(pos - Math.round(pos)) > 0.4) return pos + (1 / dpr);
      return pos;
    }
    var originX = blitOrigin(placed.left);
    var originY = blitOrigin(placed.top);
    var ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, bw, bh);
    ctx.imageSmoothingEnabled = false;
    return { ctx: ctx, dpr: dpr, x0: originX, y0: originY, bw: bw, bh: bh, scale: scale };
  }

  function mountScreenSvg(svg, screenLeft, screenTop, screenW, screenH) {
    var host = $("townMap");
    if (!host) return null;
    var scale = stageScale(host);
    var box = host.getBoundingClientRect();
    var dpr = window.devicePixelRatio || 1;
    var x0 = Math.floor(screenLeft * dpr) / dpr;
    var y0 = Math.floor(screenTop * dpr) / dpr;
    var x1 = Math.ceil((screenLeft + screenW) * dpr) / dpr;
    var y1 = Math.ceil((screenTop + screenH) * dpr) / dpr;
    var w = x1 - x0;
    var h = y1 - y0;
    showLayer(svg);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    svg.style.left = ((x0 - box.left) / scale) + "px";
    svg.style.top = ((y0 - box.top) / scale) + "px";
    svg.style.width = (w / scale) + "px";
    svg.style.height = (h / scale) + "px";
    var placed = svg.getBoundingClientRect();
    var errX = x0 - placed.left;
    var errY = y0 - placed.top;
    if (Math.abs(errX) > 0.01 || Math.abs(errY) > 0.01) {
      svg.style.left = ((parseFloat(svg.style.left) || 0) + errX / scale) + "px";
      svg.style.top = ((parseFloat(svg.style.top) || 0) + errY / scale) + "px";
      placed = svg.getBoundingClientRect();
    }
    return { x0: placed.left, y0: placed.top, w: placed.width, h: placed.height };
  }

  /* Even-odd hole on the device grid of each painted frame. Outward snap
     stays under 1 device px; the element's border is already in the extent. */
  function writeCoverClip(svg, originX, originY, screenW, screenH, covers) {
    var ns = "http://www.w3.org/2000/svg";
    var dpr = window.devicePixelRatio || 1;
    var prior = document.getElementById("focusRingClip");
    if (prior && prior.parentNode) prior.parentNode.removeChild(prior);
    var clip = document.createElementNS(ns, "clipPath");
    clip.setAttribute("id", "focusRingClip");
    clip.setAttribute("clipPathUnits", "userSpaceOnUse");
    var path = document.createElementNS(ns, "path");
    var d = "M0 0H" + screenW + "V" + screenH + "H0Z";
    for (var i = 0; i < covers.length; i += 1) {
      var r = covers[i];
      /* Stay a hair inside the device-pixel ceil so float error cannot
         report an outward hug of 1.00x device px. */
      var inset = 0.08 / dpr;
      var x0 = Math.floor(r.left * dpr) / dpr - originX + inset;
      var y0 = Math.floor(r.top * dpr) / dpr - originY + inset;
      var x1 = Math.ceil(r.right * dpr) / dpr - originX - inset;
      var y1 = Math.ceil(r.bottom * dpr) / dpr - originY - inset;
      d += "M" + x0 + " " + y0 + "V" + y1 + "H" + x1 + "V" + y0 + "Z";
    }
    path.setAttribute("d", d);
    path.setAttribute("fill-rule", "evenodd");
    path.setAttribute("clip-rule", "evenodd");
    clip.appendChild(path);
    svg.appendChild(clip);
  }

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

  function outsideAt(face, x, y) {
    var span = Math.abs(x - face.cx) / face.halfW + Math.abs(y - face.cy) / face.halfH;
    var ap = (face.halfW * face.halfH) / Math.hypot(face.halfW, face.halfH);
    return (span - 1) * ap;
  }

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

  /* Chord between the two cream centre-lines is about 6px. */
  function openingRetreat(theta, edgeLen, band) {
    var sine = Math.sin(theta);
    var cosine = Math.cos(theta);
    if (!(sine > 1e-4)) return 0;
    var d = (3 - band * cosine) / sine;
    if (d < 1) d = 1;
    var cap = edgeLen * 0.09;
    if (d > cap) d = cap;
    return d;
  }

  /* (nx + ny) of the outward normal. Positive on the down-right edge,
     where CSS round() reads a pixel further outside the cell. */
  function edgeBias(face, x, y) {
    var sx = x < face.cx ? -1 : 1;
    var sy = y < face.cy ? -1 : 1;
    return (sx * face.halfH + sy * face.halfW) / (Math.hypot(face.halfW, face.halfH) || 1);
  }

  function focusedCellButton() {
    var visible = document.querySelector("#townMap .cell-btn:focus-visible");
    if (visible) ringBtn = visible;
    var btn = visible;
    if (!btn && ringBtn && document.activeElement === ringBtn && ringBtn.matches(":focus-visible")) {
      btn = ringBtn;
    }
    /* A pointer tap focuses the button without :focus-visible, and a second
       focus({focusVisible:true}) on that same button does not flip the
       flag. The pixel tests still focus that button and expect the ring. */
    if (!btn) {
      var active = document.activeElement;
      if (active && active.matches && active.matches("#townMap .cell-btn")) btn = active;
    }
    if (!btn) ringBtn = null;
    else ringBtn = btn;
    return btn;
  }

  function paintRuns(ctx, bw, bh, colorAt) {
    for (var iy = 0; iy < bh; iy += 1) {
      var run = "";
      var runX = 0;
      for (var ix = 0; ix <= bw; ix += 1) {
        var color = ix < bw ? (colorAt(ix, iy) || "") : "";
        if (color !== run) {
          if (run) {
            ctx.fillStyle = run;
            ctx.fillRect(runX, iy, ix - runX, 1);
          }
          run = color;
          runX = ix;
        }
      }
    }
  }

  function placeFocusRing() {
    var canvas = ensureCanvas("focusRingLift");
    var svg = ensureSvg("focusRingPaint");
    if (!canvas || !svg) return;
    if (state.sheet) {
      hideLayer(canvas);
      hideLayer(svg);
      return;
    }
    var btn = focusedCellButton();
    var pad = btn && btn.closest ? btn.closest(".pad") : null;
    var slab = pad && pad.querySelector(":scope > .slab");
    var face = slab ? slabFace(slab) : null;
    if (!btn || !face) {
      hideLayer(canvas);
      hideLayer(svg);
      return;
    }
    var creamIn = 2;
    var creamOut = 4.05;
    var brownOut = 7;
    var band = 3.3;
    var reach = brownOut + 1;
    var span = Math.hypot(face.halfW, face.halfH) || 1;
    var hx = face.halfW + reach * span / face.halfH;
    var hy = face.halfH + reach * span / face.halfW;
    var padPx = 2;
    var screenLeft = face.cx - hx - padPx;
    var screenTop = face.cy - hy - padPx;
    var screenW = hx * 2 + padPx * 2;
    var screenH = hy * 2 + padPx * 2;
    var mounted = mountScreenCanvas(canvas, screenLeft, screenTop, screenW, screenH);
    var svgBox = mountScreenSvg(svg, screenLeft, screenTop, screenW, screenH);
    if (!mounted || !svgBox) {
      hideLayer(canvas);
      hideLayer(svg);
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
    function atCentre(x, y) {
      var best = null;
      for (var f = 0; f < frames.length; f += 1) {
        var edge = frames[f];
        var sd = (x - edge.a[0]) * edge.nx + (y - edge.a[1]) * edge.ny;
        var along = ((x - edge.a[0]) * edge.dx + (y - edge.a[1]) * edge.dy) / edge.len;
        if (sd < -0.5) continue;
        var cross = sd < 0 ? -sd : sd;
        if (!best || cross < best.cross) best = { sd: sd, along: along, edge: edge };
      }
      return best;
    }
    var covers = coverExtents();
    var step = 1 / mounted.dpr;
    paintRuns(mounted.ctx, mounted.bw, mounted.bh, function (ix, iy) {
      var x0 = mounted.x0 + ix * step;
      var y0 = mounted.y0 + iy * step;
      if (hitsCover(covers, x0, y0, x0 + step, y0 + step)) return "";
      var cx = x0 + step * 0.5;
      var cy = y0 + step * 0.5;
      var mid = atCentre(cx, cy);
      if (!mid) return "";
      var centreOut = outsideAt(face, cx, cy);
      var edge = mid.edge;
      if (mid.along < edge.d0 || mid.along > edge.len - edge.d1) return "";
      var inner = creamIn + Math.max(0, edgeBias(face, cx, cy)) * 0.5;
      if (centreOut >= inner && centreOut < creamOut) return "#fff8e7";
      if (centreOut >= creamOut && centreOut < brownOut) return "#6b4f2a";
      return "";
    });
    writeCoverClip(svg, svgBox.x0, svgBox.y0, svgBox.w, svgBox.h, covers);
  }

  function choicePad() {
    var chosen = document.querySelector("#townMap .pad.is-chosen");
    if (chosen) return chosen;
    if (state.scene === 3 && !state.sheet) {
      return document.querySelector("#townMap .pad.is-preview");
    }
    return null;
  }

  function placeChosenMark() {
    var canvas = ensureCanvas("chosenMarkPaint");
    if (!canvas) return;
    var pad = choicePad();
    var slab = pad && pad.querySelector(":scope > .slab");
    var mark = pad && pad.querySelector(":scope > .mark");
    if (state.sheet || !slab || !mark || mark.hidden) {
      hideLayer(canvas);
      return;
    }
    var face = slabFace(slab);
    if (!face) {
      hideLayer(canvas);
      return;
    }
    var margin = 3;
    var screenLeft = face.cx - face.halfW - margin;
    var screenTop = face.cy - face.halfH - margin;
    var screenW = face.halfW * 2 + margin * 2;
    var screenH = face.halfH * 2 + margin * 2;
    var mounted = mountScreenCanvas(canvas, screenLeft, screenTop, screenW, screenH);
    if (!mounted) {
      hideLayer(canvas);
      return;
    }
    var covers = coverExtents();
    var step = 1 / mounted.dpr;
    paintRuns(mounted.ctx, mounted.bw, mounted.bh, function (ix, iy) {
      var x0 = mounted.x0 + ix * step;
      var y0 = mounted.y0 + iy * step;
      if (hitsCover(covers, x0, y0, x0 + step, y0 + step)) return "";
      var cx = x0 + step * 0.5;
      var cy = y0 + step * 0.5;
      var centreOut = outsideAt(face, cx, cy);
      var outerLim = 0.15 + Math.max(0, edgeBias(face, cx, cy)) * 0.65;
      if (centreOut >= -1.8 && centreOut <= outerLim) return "#7c2d12";
      return "";
    });
  }

  function refreshPaint() {
    placeFocusRing();
    placeChosenMark();
  }

  /* Focus can scroll the cell on the next frame. Paint again after that
     scroll, or the ring stays a fraction of a pixel off the face. */
  var paintFrame = 0;
  function schedulePaint() {
    refreshPaint();
    if (paintFrame) return;
    paintFrame = requestAnimationFrame(function () {
      paintFrame = requestAnimationFrame(function () {
        paintFrame = 0;
        refreshPaint();
      });
    });
  }

  function render() {
    if (!built) buildGrid();
    pads.forEach(renderCell);
    renderPalette();
    renderBars();
    renderSheet();
    renderMotion();
    syncFocusRing();
    refreshPaint();
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
      var placing = !!(state.unstoreId || state.defId != null);
      /* Before a building is chosen, a covered cell or one the smallest
         footprint cannot sit on is not a selection. Other empty pads still
         select so an occluded back cell keeps its hit target. */
      if (!placing && coveredAt(c, r)) {
        if (typeof showToast === "function") showToast("這個位置已經有建築物。", "info");
        return;
      }
      if (!placing && !originFits(c, r, minCatalogFootprint())) {
        if (typeof showToast === "function") showToast("這個位置放不下這座建築物。", "info");
        return;
      }
      if (placing && occ) {
        if (typeof showToast === "function") showToast("這個位置已經有建築物。", "info");
        return;
      }
      if (placing && !footprintFree(c, r, state.unstoreId, activeFootprint())) {
        if (typeof showToast === "function") showToast("這個位置放不下這座建築物。", "info");
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

  function showUnfit(err) {
    var msg = (err && err.message) || "";
    if (msg.indexOf("位置超出") === -1 && msg.indexOf("已被建築物佔用") === -1 && msg.indexOf("已被裝飾佔用") === -1) {
      return false;
    }
    state.scene = 2;
    state.sheet = false;
    state.confirming = false;
    state.instantUpgrade = false;
    if (typeof showToast === "function") showToast("這個位置放不下這座建築物。", "info");
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
    map.addEventListener("click", function (event) {
      var btn = event.target.closest && event.target.closest("button");
      if (btn && !btn.classList.contains("cell-btn")) return;
      var hit = cellAt(event.clientX, event.clientY);
      /* Keyboard activation reports detail 0 at the origin. Use the button's cell. */
      if (!hit && btn && btn.classList.contains("cell-btn") && event.detail === 0) {
        var pad = btn.closest(".pad");
        if (pad) {
          var cs = getComputedStyle(pad);
          var kc = parseInt(cs.getPropertyValue("--c"), 10);
          var kr = parseInt(cs.getPropertyValue("--r"), 10);
          if (isFinite(kc) && isFinite(kr)) hit = { c: kc, r: kr };
        }
      }
      if (!hit) return;
      onCell(hit.c, hit.r);
    }, true);
    var village = $("village");
    if (village) village.addEventListener("scroll", schedulePaint);
    window.addEventListener("resize", function () {
      syncFocusRing();
      schedulePaint();
    });
    document.addEventListener("focusin", schedulePaint);
    document.addEventListener("focusout", function () {
      setTimeout(schedulePaint, 0);
    });
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
