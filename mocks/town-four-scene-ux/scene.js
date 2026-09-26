/* Four-scene kid loop. Demo state only — no API, no spend on cancel.
   Scenes 1 and 2 are playable. Scenes 3 and 4 are labeled shells for the next tip.
   Building art is loaded from the locked proof pack and is not redrawn here. */
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

  var grid = clone(SEED);
  var res = clone(START);
  var pads = [];
  var palBtns = {};
  var toastTimer = 0;
  var motionOn = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var state = {
    scene: 1,
    sheet: false,
    sheetId: "library",
    listOpen: false,
    pad: null,
    bldg: null,
    hover: null
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
      render();
      return;
    }
    state.sheet = false;
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
    if (id && defById[id]) state.sheetId = id;
    state.sheet = true;
    render();
    var title = document.getElementById("sheetTitle");
    if (title) title.focus();
  }

  function closeSheet() {
    state.sheet = false;
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
      if (sameCell(state.pad, { c: c, r: r })) {
        showToast("預覽緊呢格。確定放置要等下一提示。取消唔會扣資源。");
      } else {
        showToast("下一提示先至可以搬去第二格。取消唔會扣資源。");
      }
    }
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
        var shadow = document.createElement("img");
        shadow.className = "shadow";
        shadow.alt = "";
        shadow.src = ASSET + "shadow-iso.svg";
        shadow.hidden = true;
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
    else if (kind === "valid") label += "，可以放。搬位要等下一提示";
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
    document.getElementById("btnBuild").hidden = state.scene !== 1 || state.sheet;
    document.getElementById("listLauncher").hidden = !(state.scene === 2 && !state.listOpen && !state.sheet);
    palette.hidden = !(state.scene === 2 && state.listOpen && !state.sheet);
    document.getElementById("hint").hidden = state.sheet || state.scene === 3 || (state.scene === 2 && state.listOpen);

    if (showReady) {
      var status = document.getElementById("readyStatus");
      var go = document.getElementById("btnToScene3");
      go.disabled = !readyToPreview();
      if (readyToPreview()) {
        status.textContent = "已揀「" + defById[state.bldg].name + "」同呢格空地。去場景 3 睇預覽。確定要等下一提示，而家未扣資源。";
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
      document.getElementById("placeStatus").textContent =
        "預覽「" + def.name + "」。下一提示先至可以搬格同確定。取消唔扣示範資源（💰" + res.gold + "）。";
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
    document.getElementById("sheetTitle").textContent = def.name;
    document.getElementById("sheetLevel").textContent = "Lv.1 · 示範";
    document.getElementById("sheetNote").textContent = findPos(def.id)
      ? "可以升級，或者打開呢座屋嘅功能。兩個掣都係下一提示，而家撳唔到，亦唔扣資源。"
      : "放好之後就會見到呢個面板。升級同功能都係下一提示，而家未扣資源。";
    var art = document.getElementById("sheetArt");
    var next = asset(def.id);
    if (art.getAttribute("src") !== next) art.src = next;
    document.getElementById("btnUpgrade").textContent = "升級（下一提示）· " + "💰50 🪵2";

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
    def.fns.forEach(function (label) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "fn";
      btn.disabled = true;
      btn.textContent = label + "（下一提示）";
      fns.appendChild(btn);
    });
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
    state.scene = 1;
    state.sheet = false;
    state.sheetId = "library";
    state.listOpen = false;
    state.pad = null;
    state.bldg = null;
    state.hover = null;
    showToast("示範已重置。資源未變。");
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
  document.getElementById("btnConfirm").addEventListener("click", function () {
    showToast("確定放置係下一提示。而家未扣資源。");
  });
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
