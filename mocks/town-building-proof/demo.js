/* Demo-only client state. No API. Costs mirror seed_building_defs()
   header chips (gold / wood / brick / glass / gear). Gems on lighthouse,
   arena, and observatory stay in the README — the locked header has no gem chip. */
(function () {
  var COLS = 6;
  var ROWS = 5;
  var START = { gold: 6000, wood: 240, brick: 180, glass: 12, gear: 90 };

  /* Order and ids follow backend_v2.seed_building_defs (bank id 11 is out of scope). */
  var DEFS = [
    { id: "library", seed: 1, name: "圖書館", cost: { gold: 100, wood: 5 } },
    { id: "gym", seed: 2, name: "健身室", cost: { gold: 200, wood: 10, brick: 5 } },
    { id: "farm", seed: 3, name: "農場", cost: { gold: 300, wood: 15, brick: 10 } },
    { id: "shop", seed: 4, name: "商店", cost: { gold: 500, wood: 20, brick: 15, gear: 5 } },
    { id: "hospital", seed: 5, name: "醫院", cost: { gold: 400, wood: 15, brick: 20 } },
    { id: "expedition-guild", seed: 6, name: "探險公會", cost: { gold: 150, wood: 10, brick: 5 } },
    { id: "workshop", seed: 7, name: "工坊", cost: { gold: 350, wood: 20, gear: 5 } },
    { id: "lighthouse", seed: 8, name: "燈塔", cost: { gold: 800, wood: 30, brick: 25, gear: 15 } },
    { id: "arena", seed: 9, name: "競技場", cost: { gold: 1000, wood: 40, brick: 30, gear: 20 } },
    { id: "observatory", seed: 10, name: "天文台", cost: { gold: 1500, wood: 50, brick: 40, gear: 25, glass: 3 } }
  ];

  var defById = {};
  DEFS.forEach(function (def) { defById[def.id] = def; });

  var grid = {};
  var res = clone(START);
  var mode = "idle";
  var selectedId = null;
  var from = null;
  var target = null;
  var hover = null;
  var pads = [];
  var palBtns = {};
  var toastTimer = 0;
  var oobTimer = 0;

  var map = document.getElementById("townMap");
  var village = document.getElementById("village");
  var paletteGrid = document.getElementById("paletteGrid");
  var placeBar = document.getElementById("placeBar");
  var placeStatus = document.getElementById("placeStatus");
  var btnConfirm = document.getElementById("btnConfirm");
  var btnCancel = document.getElementById("btnCancel");
  var emptyHint = document.getElementById("emptyHint");
  var oobMark = document.getElementById("oobMark");

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

  function canAfford(def) {
    var cost = def.cost;
    var names = ["gold", "wood", "brick", "glass", "gear"];
    for (var i = 0; i < names.length; i += 1) {
      if ((cost[names[i]] || 0) > res[names[i]]) return false;
    }
    return true;
  }

  function spend(def) {
    var cost = def.cost;
    ["gold", "wood", "brick", "glass", "gear"].forEach(function (name) {
      res[name] -= cost[name] || 0;
    });
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

  function cellKind(c, r) {
    var occ = grid[keyOf(c, r)] || null;
    var isSource = mode === "move" && from && from.c === c && from.r === r;
    if (mode === "idle") return occ ? "occupied" : "empty";
    if (isSource) return "source";
    if (occ) return "illegal";
    return "valid";
  }

  function endMode() {
    mode = "idle";
    selectedId = null;
    from = null;
    target = null;
    hover = null;
  }

  function showToast(message) {
    var toast = document.getElementById("toast");
    toast.hidden = false;
    toast.textContent = message;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.hidden = true; }, 2800);
  }

  var MOTION_IDS = { arena: 1, farm: 1, lighthouse: 1 };

  function asset(id) {
    var still = MOTION_IDS[id] && window.townMotionOn && !window.townMotionOn();
    return "assets/bldg-" + id + "-iso" + (still ? "-still" : "") + ".svg";
  }

  function refreshMotionArt() {
    DEFS.forEach(function (def) {
      var img = palBtns[def.id] && palBtns[def.id].querySelector("img");
      if (!img) return;
      var next = asset(def.id);
      if (img.getAttribute("src") !== next) img.src = next;
    });
    if (pads.length) render();
  }

  window.townRefreshMotion = refreshMotionArt;

  function buildPalette() {
    DEFS.forEach(function (def) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pal-btn";
      btn.dataset.id = def.id;
      var img = document.createElement("img");
      img.alt = "";
      img.src = asset(def.id);
      var copy = document.createElement("span");
      var name = document.createElement("span");
      name.className = "pal-name";
      name.textContent = def.name;
      var cost = document.createElement("span");
      cost.className = "pal-cost";
      cost.textContent = "💰" + def.cost.gold;
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
        if (r >= ROWS) img.src = "assets/ground-path.svg";
        else if (r < 0) {
          img.src = "assets/ground-step.svg";
          tile.classList.add("is-raised");
        } else if ((c + r) % 2) img.src = "assets/ground-tile-alt.svg";
        else img.src = "assets/ground-tile.svg";
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
        slab.src = "assets/ground-plot.svg";
        var shadow = document.createElement("img");
        shadow.className = "shadow";
        shadow.alt = "";
        shadow.src = "assets/shadow-iso.svg";
        shadow.hidden = true;
        var mark = document.createElement("img");
        mark.className = "mark";
        mark.alt = "";
        mark.hidden = true;
        var cap = document.createElement("p");
        cap.className = "cap";
        cap.hidden = true;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "cell-btn";
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
        pad.appendChild(slab);
        pad.appendChild(shadow);
        pad.appendChild(mark);
        pad.appendChild(sprite);
        pad.appendChild(ghost);
        pad.appendChild(badge);
        var ring = document.createElement("span");
        ring.className = "focus-ring";
        ring.setAttribute("aria-hidden", "true");
        pad.appendChild(cap);
        pad.appendChild(ring);
        pad.appendChild(btn);
        village.appendChild(pad);
        var cell = { c: c, r: r, el: pad, btn: btn, mark: mark, shadow: shadow, sprite: sprite, ghost: ghost, cap: cap, badge: badge };
        pads.push(cell);
        (function (cell) {
          btn.addEventListener("click", function (event) {
            if (event.detail !== 0) return;
            onCell(cell.c, cell.r);
          });
          btn.addEventListener("focus", function () { setHover(cell.c, cell.r); });
          btn.addEventListener("blur", function () {
            if (hover && hover.c === cell.c && hover.r === cell.r) setHover(null, null);
          });
        })(cell);
      }
    }
  }

  function setHover(c, r) {
    if (c === null) {
      if (!hover) return;
      hover = null;
    } else {
      if (hover && hover.c === c && hover.r === r) return;
      hover = { c: c, r: r };
    }
    render();
  }

  function onPalette(id) {
    var placed = findPos(id);
    var movingThis = mode === "move" && from && grid[keyOf(from.c, from.r)] === id;
    if ((mode === "place" && selectedId === id) || movingThis) {
      cancelAction();
      return;
    }
    if (placed) beginMove(placed.c, placed.r);
    else beginPlace(id);
  }

  function beginPlace(id) {
    mode = "place";
    selectedId = id;
    from = null;
    target = null;
    hover = null;
    render();
  }

  function beginMove(c, r) {
    mode = "move";
    selectedId = null;
    from = { c: c, r: r };
    target = null;
    hover = null;
    render();
  }

  function onCell(c, r) {
    if (mode === "idle") {
      if (grid[keyOf(c, r)]) beginMove(c, r);
      return;
    }
    target = { c: c, r: r };
    if (cellKind(c, r) === "illegal") showToast("呢格已經有建築");
    render();
  }

  function cancelAction() {
    var returnId = null;
    if (mode === "place") returnId = selectedId;
    if (mode === "move" && from) returnId = grid[keyOf(from.c, from.r)];
    endMode();
    showToast("已取消，資源未扣除");
    render();
    if (returnId && palBtns[returnId]) palBtns[returnId].focus();
  }

  function onConfirm() {
    if (btnConfirm.disabled || !target) return;
    if (cellKind(target.c, target.r) === "illegal") return;
    if (mode === "place") {
      var def = defById[selectedId];
      if (!def || !canAfford(def) || findPos(def.id)) return;
      var name = def.name;
      var focusAt = { c: target.c, r: target.r };
      spend(def);
      grid[keyOf(target.c, target.r)] = def.id;
      endMode();
      showToast("已放好" + name);
      render();
      focusCell(focusAt.c, focusAt.r);
      return;
    }
    if (mode === "move" && from) {
      var id = grid[keyOf(from.c, from.r)];
      var moved = defById[id].name;
      var dest = { c: target.c, r: target.r };
      if (dest.c === from.c && dest.r === from.r) {
        endMode();
        showToast("留返原位，資源未扣除");
        render();
        focusCell(dest.c, dest.r);
        return;
      }
      delete grid[keyOf(from.c, from.r)];
      grid[keyOf(dest.c, dest.r)] = id;
      endMode();
      showToast("已搬好" + moved + "，資源未扣除");
      render();
      focusCell(dest.c, dest.r);
    }
  }

  function focusCell(c, r) {
    pads.forEach(function (cell) {
      if (cell.c === c && cell.r === r) cell.btn.focus();
    });
  }

  function onReset() {
    grid = {};
    res = clone(START);
    endMode();
    hideOob();
    showToast("地圖已重置，資源還原");
    render();
  }

  function hideOob() {
    oobMark.hidden = true;
    map.classList.remove("is-oob");
  }

  /* Diamond center of cell (0,0) is pad origin + (80s, 121s).
     Pad left = 50% + (c - r - 0.5) * 84s - 80s. */
  function gridMetrics() {
    var pad = pads[0].el;
    var s = pad.offsetWidth / 160;
    return {
      s: s,
      stepX: 84 * s,
      stepY: 50 * s,
      origin: {
        x: pad.offsetLeft + 80 * s,
        y: pad.offsetTop + 121 * s
      }
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

  /* Inverse of the iso lattice. The drawn rhombus is the square
     |c - col| <= 0.5, |r - row| <= 0.5 in this space. */
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

  function showOob(clientX, clientY) {
    var point = localPoint(map, clientX, clientY);
    oobMark.hidden = false;
    oobMark.style.left = point.x + "px";
    oobMark.style.top = point.y + "px";
    map.classList.add("is-oob");
    showToast("出界，呢度放唔到");
    clearTimeout(oobTimer);
    oobTimer = setTimeout(hideOob, 1200);
  }

  function onVillagePointer(event) {
    if (mode === "idle") {
      if (hover) setHover(null, null);
      return;
    }
    var hit = cellAt(event.clientX, event.clientY);
    if (!hit) setHover(null, null);
    else setHover(hit.c, hit.r);
  }

  function onVillageClick(event) {
    if (event.target.closest(".cell-btn")) return;
    var hit = cellAt(event.clientX, event.clientY);
    if (hit) {
      onCell(hit.c, hit.r);
      return;
    }
    if (mode === "idle") return;
    showOob(event.clientX, event.clientY);
  }

  function ghostId() {
    if (mode === "place") return selectedId;
    if (mode === "move" && from) return grid[keyOf(from.c, from.r)];
    return null;
  }

  function renderCell(cell) {
    var occ = grid[keyOf(cell.c, cell.r)] || null;
    var kind = cellKind(cell.c, cell.r);
    var isSource = kind === "source";
    var shown = isSource ? null : occ;
    var isLock = target && target.c === cell.c && target.r === cell.r;
    var isHover = hover && hover.c === cell.c && hover.r === cell.r;
    var showGhost = false;
    var gid = ghostId();
    if (gid && mode !== "idle") {
      if (isLock) showGhost = true;
      else if (!target && isHover && kind !== "empty" && kind !== "occupied") showGhost = true;
    }

    cell.el.className = "pad is-" + kind
      + (isLock ? " is-locked" : "")
      + (showGhost && isHover ? " is-hover" : "")
      + (mode === "idle" && !occ ? " is-idle-empty" : "");

    var idleEmpty = mode === "idle" && !occ;
    cell.btn.disabled = idleEmpty;
    cell.btn.tabIndex = idleEmpty ? -1 : 0;

    if (showGhost) {
      cell.ghost.hidden = false;
      if (cell.ghost.getAttribute("src") !== asset(gid)) cell.ghost.src = asset(gid);
    } else {
      cell.ghost.hidden = true;
    }

    cell.shadow.hidden = !(shown || showGhost);

    if (shown) {
      cell.sprite.hidden = false;
      if (cell.sprite.getAttribute("src") !== asset(shown)) cell.sprite.src = asset(shown);
      cell.cap.hidden = false;
      cell.cap.textContent = defById[shown].name;
    } else {
      cell.sprite.hidden = true;
      cell.cap.hidden = true;
    }

    if (kind === "valid") {
      cell.mark.hidden = false;
      cell.mark.src = "assets/cell-valid.svg";
      cell.badge.hidden = showGhost;
      cell.badge.textContent = "可放";
      cell.badge.className = "badge";
    } else if (kind === "illegal") {
      cell.mark.hidden = false;
      cell.mark.src = "assets/cell-illegal.svg";
      cell.badge.hidden = false;
      cell.badge.textContent = "唔得";
      cell.badge.className = "badge is-bad";
    } else if (kind === "source") {
      cell.mark.hidden = false;
      cell.mark.src = "assets/plot-iso.svg";
      cell.badge.hidden = false;
      cell.badge.textContent = "原位";
      cell.badge.className = "badge";
    } else {
      cell.mark.hidden = true;
      cell.badge.hidden = true;
    }

    var label = "格 " + (cell.c + 1) + "-" + (cell.r + 1);
    if (mode === "idle" && occ) label = defById[occ].name + "，提起以搬去別格";
    else if (kind === "valid") label += "，可放置";
    else if (kind === "illegal") label += "，已有建築，唔可以放";
    else if (kind === "source") label += "，原本位置";
    cell.btn.setAttribute("aria-label", label);
  }

  function renderPalette() {
    DEFS.forEach(function (def) {
      var btn = palBtns[def.id];
      var placed = findPos(def.id);
      var pressed = (mode === "place" && selectedId === def.id)
        || (mode === "move" && from && grid[keyOf(from.c, from.r)] === def.id);
      btn.setAttribute("aria-pressed", pressed ? "true" : "false");
      btn.classList.toggle("is-placed", !!placed);
      btn.querySelector(".pal-cost").textContent = placed ? "已起 · 可搬" : "💰" + def.cost.gold;
      var full = def.name + "，" + costText(def) + (placed ? "，已起，撳一下就搬" : "，撳一下就預覽位置");
      btn.setAttribute("aria-label", full);
    });
    document.getElementById("placedCount").textContent = "已起 " + Object.keys(grid).length + "/10";
  }

  function renderResources() {
    ["gold", "wood", "brick", "glass", "gear"].forEach(function (name) {
      document.getElementById("res-" + name).textContent = String(res[name]);
    });
  }

  function renderBar() {
    var active = mode === "place" || mode === "move";
    placeBar.hidden = !active;
    if (!active) return;
    var gid = ghostId();
    var def = gid ? defById[gid] : null;
    var kind = target ? cellKind(target.c, target.r) : null;
    var affordable = mode !== "place" || (def && canAfford(def));
    var ok = !!target && kind !== "illegal" && affordable;
    btnConfirm.disabled = !ok;
    btnConfirm.textContent = mode === "move" ? "確定搬移" : "確定放置";
    if (!def) {
      placeStatus.textContent = "";
      return;
    }
    if (mode === "place" && !affordable) {
      placeStatus.textContent = def.name + " 資源唔夠。取消唔會扣：" + costText(def);
      return;
    }
    if (kind === "illegal") {
      placeStatus.textContent = "呢格已經有建築，未扣資源。";
      return;
    }
    if (mode === "move") {
      placeStatus.textContent = ok
        ? "預覽「" + def.name + "」新位置。搬屋唔扣資源。"
        : "金色格先至搬到。搬屋唔扣資源。";
      return;
    }
    placeStatus.textContent = ok
      ? "預覽「" + def.name + "」。確定先扣 " + costText(def) + "。"
      : "點金色格預覽。確定先扣 " + costText(def) + "，取消唔扣。";
  }

  function render() {
    var count = Object.keys(grid).length;
    emptyHint.hidden = mode !== "idle" || count > 0;
    pads.forEach(renderCell);
    renderPalette();
    renderResources();
    renderBar();
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

  buildPalette();
  buildGrid();
  render();
  fit();
  window.addEventListener("resize", fit);
  if (window.visualViewport) window.visualViewport.addEventListener("resize", fit);

  btnCancel.addEventListener("click", cancelAction);
  btnConfirm.addEventListener("click", onConfirm);
  document.getElementById("btnReset").addEventListener("click", onReset);
  village.addEventListener("pointermove", onVillagePointer);
  village.addEventListener("pointerleave", function () {
    if (hover) setHover(null, null);
  });
  village.addEventListener("click", onVillageClick);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && mode !== "idle") cancelAction();
  });

  var menu = document.querySelector(".mb");
  if (menu) menu.addEventListener("click", function () { showToast("建築證明稿未接主目錄"); });
  document.querySelectorAll(".footer-tab:not([aria-current='page'])").forEach(function (tab) {
    tab.addEventListener("click", function () { showToast("建築證明稿只示範城鎮首頁"); });
  });
})();
