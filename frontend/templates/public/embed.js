(function () {
  if (window.SmartUniBot) return;
  var WIDGET = {{ widget_url|tojson }};
  var NAME = {{ config.name|tojson }};
  var TEASER = {{ teaser|tojson }};
  var MASCOT = {{ mascot|tojson }};
  var SEEN_KEY = "smartuni_bot_teaser_seen";
  var css = [
    "#sub-root{position:fixed;right:20px;bottom:20px;z-index:2147483000;font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif}",
    "#sub-launch{position:relative;width:64px;height:64px;border-radius:50%;border:0;padding:0;background:transparent;cursor:pointer;box-shadow:0 10px 28px rgba(0,40,80,.35);transition:transform .2s ease}",
    "#sub-launch:hover{transform:translateY(-2px) scale(1.04)}",
    "#sub-launch svg{width:64px;height:64px;display:block;border-radius:50%}",
    "#sub-root.open #sub-launch{display:none}",
    "#sub-launch .sub-ring{position:absolute;inset:-6px;border-radius:50%;border:2px solid rgba(0,82,140,.45);animation:sub-pulse 2.4s ease-out infinite;pointer-events:none}",
    "#sub-root.open #sub-launch .sub-ring,#sub-root.engaged #sub-launch .sub-ring{display:none}",
    "@keyframes sub-pulse{0%{transform:scale(.9);opacity:1}100%{transform:scale(1.35);opacity:0}}",
    "#sub-badge{position:absolute;top:-2px;right:-2px;min-width:20px;height:20px;padding:0 5px;border-radius:10px;background:#e5383b;color:#fff;font-size:11px;font-weight:700;line-height:20px;text-align:center;border:2px solid #fff;display:none}",
    "#sub-root.unread #sub-badge{display:block}",
    "#sub-teaser{position:absolute;right:76px;bottom:8px;width:max-content;max-width:250px;background:#fff;color:#1a2332;border-radius:16px 16px 4px 16px;padding:12px 30px 12px 14px;font-size:13.5px;line-height:1.45;box-shadow:0 10px 30px rgba(0,40,80,.22);cursor:pointer;opacity:0;transform:translateY(8px);pointer-events:none;transition:opacity .25s ease,transform .25s ease}",
    "#sub-teaser b{display:block;color:#00528c;margin-bottom:2px}",
    "#sub-teaser.show{opacity:1;transform:none;pointer-events:auto}",
    "#sub-teaser button{position:absolute;top:6px;right:6px;width:22px;height:22px;border:0;border-radius:50%;background:transparent;color:#5b6577;cursor:pointer;font-size:15px;line-height:22px;padding:0}",
    "#sub-teaser button:hover{background:#eef2f7}",
    "#sub-panel{position:absolute;right:0;bottom:0;width:390px;height:640px;max-width:calc(100vw - 24px);max-height:calc(100vh - 40px);border-radius:20px;overflow:hidden;background:#fff;box-shadow:0 20px 60px rgba(0,30,60,.3);opacity:0;transform:translateY(16px) scale(.96);transform-origin:bottom right;pointer-events:none;transition:opacity .22s ease,transform .22s ease}",
    "#sub-root.open #sub-panel{opacity:1;transform:none;pointer-events:auto}",
    "#sub-panel iframe{width:100%;height:100%;border:0;display:block}",
    "#sub-root.open #sub-teaser{display:none}",
    "@media (max-width:520px){ #sub-root{right:14px;bottom:14px} #sub-panel{position:fixed;inset:0;width:100vw;height:100vh;max-width:none;max-height:none;border-radius:0} #sub-teaser{max-width:210px}}"
  ].join("");
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var root = document.createElement("div");
  root.id = "sub-root";
  root.innerHTML =
    '<div id="sub-panel" role="dialog" aria-label="' + NAME.replace(/"/g, "&quot;") + '"></div>' +
    '<div id="sub-teaser" role="button" tabindex="0"><button type="button" aria-label="Ẩn lời chào">&times;</button><b></b><span></span></div>' +
    '<button id="sub-launch" type="button" aria-label="Mở ' + NAME.replace(/"/g, "&quot;") + '">' +
    '<span class="sub-ring"></span>' + MASCOT +
    '<span id="sub-badge">1</span></button>';
  var panel = root.querySelector("#sub-panel");
  var teaser = root.querySelector("#sub-teaser");
  var launch = root.querySelector("#sub-launch");
  teaser.querySelector("b").textContent = NAME;
  teaser.querySelector("span").textContent = TEASER;
  var frame = null;
  var ready = false;
  var queue = [];

  function post(msg) {
    if (frame && ready) {
      try { frame.contentWindow.postMessage(Object.assign({ source: "smartuni-host" }, msg), "*"); } catch (e) {}
    } else {
      queue.push(msg);
    }
  }

  function seen() { try { return sessionStorage.getItem(SEEN_KEY) === "1"; } catch (e) { return false; } }
  function markSeen() { try { sessionStorage.setItem(SEEN_KEY, "1"); } catch (e) {} }
  function hideTeaser() { teaser.classList.remove("show"); markSeen(); }

  function open() {
    if (!frame) {
      frame = document.createElement("iframe");
      frame.src = WIDGET;
      frame.title = NAME;
      frame.setAttribute("allow", "clipboard-write");
      panel.appendChild(frame);
    }
    root.classList.add("open", "engaged");
    root.classList.remove("unread");
    hideTeaser();
    launch.setAttribute("aria-expanded", "true");
    post({ type: "focus" });
  }
  function close() {
    root.classList.remove("open");
    launch.setAttribute("aria-expanded", "false");
    launch.focus({ preventScroll: true });
  }
  function toggle() { root.classList.contains("open") ? close() : open(); }
  function ask(text) { open(); post({ type: "ask", text: String(text || "") }); }
  function contact() { open(); post({ type: "contact" }); }

  launch.addEventListener("click", toggle);
  teaser.addEventListener("click", function (ev) {
    if (ev.target.tagName === "BUTTON") { ev.stopPropagation(); hideTeaser(); root.classList.remove("unread"); return; }
    open();
  });
  teaser.addEventListener("keydown", function (ev) { if (ev.key === "Enter") open(); });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && root.classList.contains("open")) close(); });
  window.addEventListener("message", function (ev) {
    var d = ev.data;
    if (!d || d.source !== "smartuni-bot") return;
    if (d.type === "ready") {
      ready = true;
      queue.splice(0).forEach(post);
    }
    if (d.type === "close") close();
    if (d.type === "staff-message" && !root.classList.contains("open")) root.classList.add("unread");
  });

  function mount() {
    document.body.appendChild(root);
    var params = new URLSearchParams(location.search);
    if (params.get("chat") === "1" || location.hash === "#tu-van") { open(); return; }
    if (!seen()) {
      setTimeout(function () {
        if (!root.classList.contains("open")) { teaser.classList.add("show"); root.classList.add("unread"); }
      }, 2500);
    }
  }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
  window.SmartUniBot = { open: open, close: close, toggle: toggle, ask: ask, contact: contact };
})();
