(function () {
  var stage = document.querySelector(".stage");
  if (!stage) return;
  var params = new URLSearchParams(location.search);

  function fit() {
    if (params.has("native")) {
      document.body.classList.add("is-native");
      stage.style.transform = "none";
      return;
    }
    var scale = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
    stage.style.transform = "translate(-50%, -50%) scale(" + scale + ")";
  }

  fit();
  window.addEventListener("resize", fit);

  var toast = document.getElementById("toast");
  function show(message) {
    if (!toast) return;
    toast.hidden = false;
    toast.textContent = message;
  }

  var menu = document.querySelector(".mb");
  if (menu) menu.addEventListener("click", function () { show("風格比較稿未接主目錄"); });

  document.querySelectorAll(".footer-tab:not([aria-current='page'])").forEach(function (tab) {
    tab.addEventListener("click", function () { show("風格比較稿只示範城鎮首頁"); });
  });
})();
