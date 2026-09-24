/* Page toggle for the three sample buildings. The animated SVG has no
   reduced-motion media query, so choosing 開 plays it even when the OS asks
   for less motion. Choosing 關 swaps in the still cutout. */
(function () {
  var KEY = "town-proof-motion";
  var osReduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function resolve(explicit) {
    if (explicit === "on") return true;
    if (explicit === "off") return false;
    return !osReduce;
  }

  var on = resolve(stored());

  function paint() {
    document.documentElement.classList.toggle("motion-on", on);
    document.documentElement.classList.toggle("motion-off", !on);
    var btn = document.getElementById("btnMotion");
    if (btn) {
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "動畫 開" : "動畫 關";
    }
    var note = document.getElementById("motionOs");
    if (note) note.textContent = "系統減少動態：" + (osReduce ? "開" : "關");
    document.querySelectorAll("img[data-motion]").forEach(function (img) {
      var id = img.getAttribute("data-motion");
      var next = "assets/bldg-" + id + "-iso" + (on ? "" : "-still") + ".svg";
      if (img.getAttribute("src") !== next) img.src = next;
    });
    if (window.townRefreshMotion) window.townRefreshMotion();
  }

  window.townMotionOn = function () { return on; };

  window.townSetMotion = function (next) {
    on = !!next;
    try { localStorage.setItem(KEY, on ? "on" : "off"); } catch (e) {}
    paint();
  };

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("btnMotion");
    if (btn) {
      btn.addEventListener("click", function () { window.townSetMotion(!on); });
    }
    paint();
  });
})();
