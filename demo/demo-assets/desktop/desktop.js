/* Yaru Glass desktop simulation. Framework-free; opened directly from file://.
   Appearance formulas mirror the old preview and src/yaru_glass/theme_settings.py. */
"use strict";
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
// Absolute: a relative url() inside a custom property resolves against the stylesheet.
const ASSETS = new URL("demo-assets/desktop/", document.baseURI).href;
const WALLPAPERS = new URL("demo-assets/lockscreen/", document.baseURI).href;

const preview = $("#preview");
const slider = $("#transparency");
const output = $("#transparencyValue");
const solidControl = $("#solid");
const blurControl = $("#background-blur");
const boostControl = $("#boost");
const glassControl = $("#glass-style");
const presetControl = $("#preset");
const appEnabledControl = $("#app-enabled");
const appLevelControl = $("#app-level");
const filesEnabledControl = $("#files-enabled");
const filesLevelControl = $("#files-level");
const dialog = $("#preset-dialog");
const comboControls = new Map();

function iconUrl(name) {
  const svg = window.YARU_SYMBOLIC?.[name];
  return svg ? `url("data:image/svg+xml,${encodeURIComponent(svg)}")` : "none";
}
function applyIcons(root = document) {
  const nodes = root.matches?.("[data-icon]") ? [root, ...$$("[data-icon]", root)] : $$("[data-icon]", root);
  nodes.forEach(node => node.style.setProperty("--icon", iconUrl(node.dataset.icon)));
}
function setIcon(node, name) { node.dataset.icon = name; applyIcons(node); }
function sym(name, extra = "") { return `<span class="sym ${extra}" data-icon="${name}" style='--icon:${iconUrl(name)}'></span>`; }
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, ch => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[ch]));
}

/* ---------- Appearance model ---------- */
const presetDefinitions = {
  "Solid": {glass: "frost", shell: 0, solid: true, enabled: false, app: 25, files: 25},
  "Balanced Frost": {glass: "frost", shell: 25, solid: false, enabled: true, app: 25, files: 25},
  "Clear Crystal": {glass: "crystal", shell: 50, solid: false, enabled: true, app: 50, files: 50}
};
const state = {
  filesLiveOpacity: null,
  filesLiveMaterial: null,
  filesRestartConfirmed: false,
  wallpapers: {
    light: {current: "alpine", previous: "alpine"},
    dark: {current: "forest", previous: "forest"}
  }
};
function currentValues() {
  return {glass: preview.dataset.glass, shell: Number(slider.value), solid: solidControl.checked,
          appEnabled: appEnabledControl.checked, filesEnabled: filesEnabledControl.checked,
          app: Number(appLevelControl.value), files: Number(filesLevelControl.value),
          boost: boostControl.checked, backgroundBlur: blurControl.checked};
}
function presetName(values = currentValues()) {
  return Object.entries(presetDefinitions).find(([, target]) =>
    values.glass === target.glass && values.shell === target.shell && values.solid === target.solid &&
    values.appEnabled === target.enabled && values.filesEnabled === target.enabled &&
    values.app === target.app && values.files === target.files)?.[0] ?? "Custom";
}
function boostAlpha(alpha) { return boostControl.checked ? alpha + (1 - alpha) / 2 : alpha; }

function updatePreview() {
  const percent = Number(slider.value);
  const factor = 1 - percent / 100;
  const dark = preview.dataset.theme === "dark";
  const floor = dark ? 0.70 : 0.58;
  const crystal = preview.dataset.glass === "crystal";
  const glassFactor = crystal ? 0.55 : 1;
  const bases = dark
    ? {panel: .45, menu: .80, dialog: .94, notification: .86}
    : {panel: .62, menu: .80, dialog: .92, notification: .84};
  preview.style.setProperty("--alpha-factor", String(factor));
  Object.entries(bases).forEach(([name, alpha]) => {
    preview.style.setProperty(`--${name}-opacity`, String(solidControl.checked ? 1 :
      boostAlpha(floor + (1 - floor) * alpha * factor * glassFactor)));
  });
  preview.style.setProperty("--dock-opacity", String(solidControl.checked ? 1 : boostAlpha((dark ? .35 : .30) * factor)));
  slider.disabled = solidControl.checked;
  preview.dataset.blur = blurControl.checked && !solidControl.checked ? "on" : "off";
  preview.style.setProperty("--shell-blur", `blur(${crystal ? 6 : 30}px)`);
  output.value = `${percent}%`;
  output.textContent = `${percent}%`;
  glassControl.value = preview.dataset.glass;
  const values = currentValues();
  const appAlpha = values.appEnabled ? 1 - (1 - (dark ? .80 : .70)) * values.app / 50 * (crystal ? 1 : .7) : 1;
  const filesAlpha = values.filesEnabled ? 1 - .30 * values.files / 50 * (crystal ? 1 : .7) : 1;
  const filesOpacity = boostAlpha(filesAlpha);
  preview.style.setProperty("--app-opacity", String(boostAlpha(appAlpha)));
  preview.style.setProperty("--files-opacity", String(filesOpacity));
  if (state.filesLiveOpacity === null) state.filesLiveOpacity = filesOpacity;
  if (state.filesLiveMaterial === null) state.filesLiveMaterial = values.filesEnabled;
  preview.dataset.appGlass = String(values.appEnabled);
  preview.dataset.filesGlass = String(state.filesLiveMaterial);
  preview.style.setProperty("--files-live-opacity", String(state.filesLiveOpacity));
  appLevelControl.disabled = !values.appEnabled;
  filesLevelControl.disabled = !values.filesEnabled;
  $("#app-value").textContent = `${values.app}%`;
  $("#files-value").textContent = `${values.files}%`;
  const percentOpaque = Math.round(filesOpacity * 100);
  $("#files-opacity").textContent = `Saved background: ${percentOpaque}% opaque (${100 - percentOpaque}% see-through). ` +
    "File content stays 100% opaque. Slider is a relative level, not literal transparency.";
  refreshOverview(values);
  syncComboControls();
  $$('input[type="range"]').forEach(control => {
    const min = Number(control.min || 0);
    const max = Number(control.max || 100);
    control.style.setProperty("--range-progress", `${(Number(control.value) - min) / (max - min) * 100}%`);
  });
}
function refreshOverview(values = currentValues()) {
  const filesLine = state.filesRestartConfirmed ? "restart confirmed in this session" : "live CSS unknown; restart if needed";
  $("#preset-status").textContent =
    `Saved preset: ${presetName(values)} · Readability boost: ${values.boost ? "On" : "Off"}\n` +
    `Shell: ${values.glass === "crystal" ? "Crystal" : "Frost"} / ${values.shell} · Solid: ${values.solid ? "On" : "Off"}\n` +
    `Dynamic blur preference: ${values.backgroundBlur ? "On" : "Off"} · Effective: ${preview.dataset.blur}\n` +
    "Project GTK theme: active · GTK4 link: configured\n" +
    `Files: ${filesLine}. Shell pixels are not inspected.`;
}
function filesSettingsChanged() {
  state.filesRestartConfirmed = false;
  $("#files-status").textContent = state.filesLiveOpacity === Number(preview.style.getPropertyValue("--files-opacity"))
    ? "Saved. Files already shows these settings."
    : "Saved. Restart Files to load the new appearance.";
}

/* Confirmation dialog shaped like Adw.MessageDialog. */
let pendingAction = null;
function confirmAction(heading, body, action, {apply = "Apply", destructive = false} = {}) {
  $("#dialog-title").textContent = heading;
  $("#preset-preview").textContent = body;
  const applyButton = $("#dialog-apply");
  applyButton.textContent = apply;
  applyButton.classList.toggle("suggested", !destructive);
  applyButton.classList.toggle("destructive", destructive);
  pendingAction = action;
  dialog.returnValue = "cancel";
  dialog.dataset.theme = preview.dataset.theme;
  dialog.showModal();
  $("#dialog-cancel").focus();
}
dialog.addEventListener("close", () => {
  const action = pendingAction;
  pendingAction = null;
  if (dialog.returnValue === "apply" && action) action();
});
dialog.addEventListener("cancel", () => { dialog.returnValue = "cancel"; });

const LABELS = {
  shell: {title: "Shell", glass: "Glass style", shell: "Transparency level", solid: "Solid backgrounds",
          boost: "Readability boost", backgroundBlur: "Dynamic background blur"},
  app: {title: "Settings app", appEnabled: "Transparency", app: "Transparency level"},
  files: {title: "Files", filesEnabled: "Transparency", files: "Transparency level"}
};
function formatValue(key, value) {
  if (key === "glass") return value === "crystal" ? "Crystal" : "Frost";
  if (key === "shell" || key === "app" || key === "files") return `${value}%`;
  if (key === "appEnabled" || key === "filesEnabled") return value ? "Enabled" : "Disabled";
  return value ? "On" : "Off";
}
function formatChanges(patch) {
  const current = currentValues();
  const lines = [];
  Object.entries(LABELS).forEach(([section, labels]) => {
    const keys = Object.keys(labels).filter(key => key !== "title" && key in patch);
    if (!keys.length) return;
    lines.push(labels.title);
    keys.forEach(key => lines.push(`  ${labels[key]}: ${formatValue(key, current[key])} → ${formatValue(key, patch[key])}`));
  });
  return lines.join("\n");
}
function applyPatch(patch) {
  const filesBefore = [filesEnabledControl.checked, filesLevelControl.value].join();
  if ("glass" in patch) preview.dataset.glass = patch.glass;
  if ("shell" in patch) slider.value = patch.shell;
  if ("solid" in patch) solidControl.checked = patch.solid;
  if ("boost" in patch) boostControl.checked = patch.boost;
  if ("backgroundBlur" in patch) blurControl.checked = patch.backgroundBlur;
  if ("appEnabled" in patch) appEnabledControl.checked = patch.appEnabled;
  if ("app" in patch) appLevelControl.value = patch.app;
  if ("filesEnabled" in patch) filesEnabledControl.checked = patch.filesEnabled;
  if ("files" in patch) filesLevelControl.value = patch.files;
  updatePreview();
  if (filesBefore !== [filesEnabledControl.checked, filesLevelControl.value].join()) filesSettingsChanged();
  $("#shell-status").textContent = "Applied and saved.";
}
function presetPatch(name) {
  const target = presetDefinitions[name];
  return {glass: target.glass, shell: target.shell, solid: target.solid,
          appEnabled: target.enabled, app: target.app, filesEnabled: target.enabled, files: target.files};
}
$("#preview-preset").addEventListener("click", () => {
  const name = presetControl.value;
  const patch = presetPatch(name);
  confirmAction(`Apply ${name}?`, formatChanges(patch) +
    "\n\nReadability boost, blur preference and wallpapers stay unchanged. " +
    "Files requires a separate confirmed restart; it will not restart automatically.",
    () => applyPatch(patch));
});
function confirmReset(section, patch) {
  let body = formatChanges(patch) + "\n\nOnly the listed settings will be reset. Other sections and wallpapers stay unchanged.";
  if ("filesEnabled" in patch) body += " Files may require a separate confirmed restart; Files will not restart automatically.";
  confirmAction(`Reset ${section}?`, body, () => applyPatch(patch));
}
$("#reset-boost").addEventListener("click", () => confirmReset("Readability boost", {boost: false}));
$("#reset-shell").addEventListener("click", () => confirmReset("Shell", {
  shell: 25, glass: "frost", solid: false, backgroundBlur: true}));
$("#reset-app").addEventListener("click", () => confirmReset("Settings app", {appEnabled: false, app: 25}));
$("#reset-files").addEventListener("click", () => confirmReset("Files", {filesEnabled: false, files: 25}));
$$("[data-files-preset]").forEach(button => button.addEventListener("click", () => {
  const level = Number(button.dataset.filesPreset);
  filesEnabledControl.checked = level > 0;
  filesLevelControl.value = level;
  updatePreview();
  filesSettingsChanged();
}));
$("#restart-files").addEventListener("click", () => confirmAction("Restart Files?",
  "This closes all Files windows and reopens your Home folder. Finish all copies, moves and other file " +
  "operations first. Only continue when no transfers are running.",
  () => restartFiles(), {apply: "Transfers finished — Restart", destructive: true}));
function loadFilesAppearance() {
  state.filesLiveOpacity = Number(preview.style.getPropertyValue("--files-opacity")) || 1;
  state.filesLiveMaterial = filesEnabledControl.checked;
  preview.dataset.filesGlass = String(state.filesLiveMaterial);
  preview.style.setProperty("--files-live-opacity", String(state.filesLiveOpacity));
}
function restartFiles() {
  const status = $("#files-status");
  status.textContent = "Stopping Files…";
  closeWindow("files");
  setTimeout(() => {
    status.textContent = "Opening Files with the saved appearance…";
    loadFilesAppearance();
    openApp("files", {path: "Home"});
    state.filesRestartConfirmed = true;
    status.textContent = "Files restarted with the saved appearance.";
    refreshOverview();
  }, 350);
}

[slider, solidControl, blurControl, boostControl, appEnabledControl, appLevelControl].forEach(control =>
  control.addEventListener("input", () => { updatePreview(); $("#shell-status").textContent = "Applied and saved."; }));
[filesEnabledControl, filesLevelControl].forEach(control => control.addEventListener("input", () => {
  updatePreview();
  filesSettingsChanged();
}));
glassControl.addEventListener("change", () => { preview.dataset.glass = glassControl.value; updatePreview(); });

/* Stack switcher tabs: arrow keys, Home and End like Gtk.StackSwitcher focus handling. */
const tabs = $$('[role="tab"]', $("#win-glass"));
function selectPage(button) {
  tabs.forEach(tab => {
    const selected = tab === button;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $(`#${tab.getAttribute("aria-controls")}`).hidden = !selected;
  });
}
tabs.forEach((button, index) => {
  button.addEventListener("click", () => selectPage(button));
  button.addEventListener("keydown", event => {
    let next;
    if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
    if (event.key === "ArrowLeft") next = tabs[(index + tabs.length - 1) % tabs.length];
    if (event.key === "Home") next = tabs[0];
    if (event.key === "End") next = tabs[tabs.length - 1];
    if (next) { event.preventDefault(); selectPage(next); next.focus(); }
  });
});

/* Wallpapers: light/dark pair switched by the style, as in the native Wallpapers page. */
const WALLPAPER_CHOICES = {
  alpine: {label: "alpine.jpg", css: `url("${WALLPAPERS}alpine.jpg")`},
  forest: {label: "forest.jpg", css: `url("${WALLPAPERS}forest.jpg")`},
  coast: {label: "coast.jpg", css: `url("${WALLPAPERS}coast.jpg")`},
  white: {label: "plain-white.png", css: "linear-gradient(#ffffff, #ffffff)"},
  dark: {label: "plain-dark.png", css: "linear-gradient(#1a1a1a, #1a1a1a)"}
};
function wallpaperPath(key) { return `~/Pictures/Wallpapers/${WALLPAPER_CHOICES[key].label}`; }
function updateWallpapers() {
  ["light", "dark"].forEach(mode => {
    const key = state.wallpapers[mode].current;
    $(`#thumb-${mode}`).style.backgroundImage = WALLPAPER_CHOICES[key].css;
    $(`#path-${mode}`).textContent = wallpaperPath(key);
  });
  const active = WALLPAPER_CHOICES[state.wallpapers[preview.dataset.theme].current];
  $("#wallpaper").style.backgroundImage = active.css;
  preview.dataset.backdrop = state.wallpapers[preview.dataset.theme].current;
  preview.style.setProperty("--wallpaper-image", active.css);
}
const chooser = $("#chooser-dialog");
let chooserMode = "light";
let chooserSelection = null;
function openChooser(mode) {
  chooserMode = mode;
  chooserSelection = state.wallpapers[mode].current;
  $("#chooser-title").textContent = `Choose ${mode} wallpaper`;
  $("#chooser-grid").innerHTML = Object.entries(WALLPAPER_CHOICES).map(([key, item]) =>
    `<button type="button" role="radio" data-wallpaper="${key}" aria-checked="${key === chooserSelection}">` +
    `<span style='background-image:${item.css}'></span><span>${item.label}</span></button>`).join("");
  chooser.dataset.theme = preview.dataset.theme;
  chooser.returnValue = "cancel";
  chooser.showModal();
}
$("#chooser-grid").addEventListener("click", event => {
  const button = event.target.closest("[data-wallpaper]");
  if (!button) return;
  chooserSelection = button.dataset.wallpaper;
  $$("[data-wallpaper]", chooser).forEach(item => item.setAttribute("aria-checked", String(item === button)));
});
$("#chooser-grid").addEventListener("dblclick", event => {
  if (event.target.closest("[data-wallpaper]")) chooser.close("select");
});
chooser.addEventListener("close", () => {
  if (chooser.returnValue !== "select" || !chooserSelection) return;
  const slot = state.wallpapers[chooserMode];
  if (slot.current !== chooserSelection) { slot.previous = slot.current; slot.current = chooserSelection; }
  updateWallpapers();
});
$$("[data-choose]").forEach(button => button.addEventListener("click", () => openChooser(button.dataset.choose)));
$$("[data-restore]").forEach(button => button.addEventListener("click", () => {
  const slot = state.wallpapers[button.dataset.restore];
  [slot.current, slot.previous] = [slot.previous, slot.current];
  updateWallpapers();
}));

function setTheme(theme) {
  preview.dataset.theme = theme;
  $("#qt-dark").setAttribute("aria-pressed", String(theme === "dark"));
  $$("[data-style]").forEach(card => card.setAttribute("aria-checked", String(card.dataset.style === theme)));
  [dialog, chooser].forEach(item => { item.dataset.theme = theme; });
  updateWallpapers();
  updatePreview();
}

/* ---------- Applications ---------- */
const APPS = {
  files: {name: "Files", icon: "apps/org.gnome.Nautilus.png", window: "win-files", keywords: "nautilus folder"},
  terminal: {name: "Terminal", icon: "apps/org.gnome.Terminal.png", window: "win-terminal", keywords: "console shell"},
  editor: {name: "Text Editor", icon: "apps/org.gnome.TextEditor.png", window: "win-editor", keywords: "gedit notes"},
  glass: {name: "Yaru Glass Settings", icon: "apps/preferences-desktop-theme.png", window: "win-glass", keywords: "theme transparency appearance"},
  settings: {name: "Settings", icon: "apps/org.gnome.Settings.png", window: "win-settings", keywords: "preferences control center"},
  "app-center": {name: "App Center", icon: "apps/app-center.png", keywords: "software snap store"},
  help: {name: "Help", icon: "apps/org.gnome.Yelp.png", keywords: "yelp documentation"},
  calculator: {name: "Calculator", icon: "apps/org.gnome.Calculator.png"},
  calendar: {name: "Calendar", icon: "apps/org.gnome.Calendar.png"},
  characters: {name: "Characters", icon: "apps/org.gnome.Characters.png", keywords: "emoji"},
  clocks: {name: "Clocks", icon: "apps/org.gnome.clocks.png", keywords: "alarm timer"},
  weather: {name: "Weather", icon: "apps/org.gnome.Weather.png"},
  monitor: {name: "System Monitor", icon: "apps/org.gnome.SystemMonitor.png", keywords: "process task"},
  baobab: {name: "Disk Usage Analyzer", icon: "apps/org.gnome.baobab.png", keywords: "baobab storage"}
};
// Precomputed from the bundled icons using Ubuntu Dock's dominant-color palette.
const APP_COLORS = {
  files: "#e65150", terminal: "#e6e6e6", editor: "#d9e6db", glass: "#e6506e",
  settings: "#e6e6e6", "app-center": "#e67c50", help: "#50a8e6", calculator: "#e6bb50",
  calendar: "#50e6d8", characters: "#5093e6", clocks: "#e6cbce", weather: "#50e6b7",
  monitor: "#cdd4e6", baobab: "#e66d50"
};
const FAVORITES = ["files", "terminal", "editor", "glass", "settings", "app-center", "help"];
const windowsLayer = $("#windows");
$$(".window").forEach(win => windowsLayer.append(win));
let zTop = 10;
let focusedWindow = null;
const narrow = () => window.innerWidth <= 760;

function appIcon(app) { return ASSETS + APPS[app].icon; }
function windowFor(app) { return APPS[app]?.window ? $(`#${APPS[app].window}`) : $("#win-generic"); }
function openWindows() { return $$(".window").filter(win => win.dataset.state); }

function addWindowControls(win) {
  const end = $$(".headerbar", win).at(-1).querySelector(".end") ?? $$(".headerbar", win).at(-1);
  const controls = document.createElement("div");
  controls.className = "window-controls";
  controls.innerHTML =
    `<button type="button" class="minimize" aria-label="Minimize"><i>${sym("window-minimize")}</i></button>` +
    `<button type="button" class="maximize" aria-label="Maximize"><i>${sym("window-maximize")}</i></button>` +
    `<button type="button" class="close" aria-label="Close"><i>${sym("window-close")}</i></button>`;
  end.append(controls);
  $(".minimize", controls).addEventListener("click", () => minimizeWindow(win));
  $(".maximize", controls).addEventListener("click", () => toggleMaximize(win));
  $(".close", controls).addEventListener("click", () => closeWindow(win.dataset.app));
}

function focusWindow(win) {
  if (!win) return;
  if (++zTop > 400) {
    openWindows().sort((a, b) => a.style.zIndex - b.style.zIndex).forEach((item, index) => { item.style.zIndex = 10 + index; });
    zTop = 10 + openWindows().length;
  }
  win.hidden = false;
  win.dataset.state = "open";
  win.classList.remove("minimizing");
  win.style.zIndex = zTop;
  focusedWindow = win;
  $$(".window").forEach(item => item.classList.toggle("backdrop", item !== win));
  renderDock();
  updateDockVisibility();
}
function focusTopWindow() {
  const top = openWindows().filter(win => win.dataset.state === "open")
    .sort((a, b) => b.style.zIndex - a.style.zIndex)[0];
  focusedWindow = null;
  if (top) focusWindow(top);
  else { $$(".window").forEach(item => item.classList.add("backdrop")); renderDock(); updateDockVisibility(); }
}
function openApp(app, options = {}) {
  closePopups();
  closeOverview();
  if (!APPS[app]) return;
  const win = windowFor(app);
  const wasOpen = win.dataset.state && win.dataset.app === app;
  if (!APPS[app].window) {
    win.dataset.app = app;
    win.setAttribute("aria-label", APPS[app].name);
    $("#generic-title").textContent = APPS[app].name;
    $("#generic-heading").textContent = APPS[app].name;
    $("#generic-icon").src = appIcon(app);
  }
  if (!wasOpen) {
    APP_HOOKS[app]?.open?.(options, win);
  } else if (Object.keys(options).length) {
    APP_HOOKS[app]?.open?.(options, win);
  }
  focusWindow(win);
  APP_HOOKS[app]?.focus?.(win);
}
function minimizeWindow(win) {
  win.classList.add("minimizing");
  const done = () => {
    if (!win.classList.contains("minimizing")) return;
    win.hidden = true;
    win.dataset.state = "minimized";
    win.classList.remove("minimizing");
    focusTopWindow();
  };
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) done(); else setTimeout(done, 200);
}
function closeWindow(app) {
  const win = windowFor(app);
  if (!win.dataset.state || win.dataset.app !== app) return;
  APP_HOOKS[app]?.close?.(win);
  win.hidden = true;
  delete win.dataset.state;
  win.classList.remove("maximized", "tiled-left", "tiled-right", "minimizing");
  focusTopWindow();
}
function toggleMaximize(win, force) {
  const maximize = force ?? !(win.classList.contains("maximized") || win.classList.contains("tiled-left") || win.classList.contains("tiled-right"));
  win.classList.remove("tiled-left", "tiled-right");
  win.classList.toggle("maximized", maximize);
  const button = $(".window-controls .maximize", win);
  button.setAttribute("aria-label", maximize ? "Restore" : "Maximize");
  setIcon($(".sym", button), maximize ? "window-restore" : "window-maximize");
  updateDockVisibility();
}
function enableDragging(win) {
  $$(".headerbar", win).forEach(bar => {
    bar.addEventListener("dblclick", event => {
      if (!event.target.closest("button, input, select, a")) toggleMaximize(win);
    });
    bar.addEventListener("pointerdown", event => {
      if (event.button !== 0 || event.target.closest("button, input, select, a") ||
          (narrow() && (win.id !== "win-glass" || window.innerWidth <= 580))) return;
      focusWindow(win);
      const start = {x: event.clientX, y: event.clientY, left: win.offsetLeft, top: win.offsetTop};
      let moved = false;
      bar.setPointerCapture(event.pointerId);
      const move = moveEvent => {
        const dx = moveEvent.clientX - start.x;
        const dy = moveEvent.clientY - start.y;
        if (!moved && Math.hypot(dx, dy) < 4) return;
        if (!moved && win.matches(".maximized, .tiled-left, .tiled-right")) {
          const width = win.offsetWidth;
          toggleMaximize(win, false);
          start.left = moveEvent.clientX - Math.min(win.offsetWidth / 2, moveEvent.clientX * win.offsetWidth / width);
          start.top = 0;
          start.x = moveEvent.clientX;
          start.y = moveEvent.clientY;
        }
        moved = true;
        const panel = $("#panel").offsetHeight;
        win.style.left = `${Math.round(start.left + moveEvent.clientX - start.x)}px`;
        win.style.top = `${Math.max(panel, Math.round(start.top + moveEvent.clientY - start.y))}px`;
        updateDockVisibility();
      };
      const up = upEvent => {
        bar.removeEventListener("pointermove", move);
        bar.removeEventListener("pointerup", up);
        bar.removeEventListener("pointercancel", up);
        if (!moved) return;
        const panel = $("#panel").offsetHeight;
        if (upEvent.clientY <= panel + 2) toggleMaximize(win, true);
        else if (upEvent.clientX <= 2) { win.classList.add("tiled-left"); updateDockVisibility(); }
        else if (upEvent.clientX >= window.innerWidth - 3) { win.classList.add("tiled-right"); updateDockVisibility(); }
      };
      bar.addEventListener("pointermove", move);
      bar.addEventListener("pointerup", up);
      bar.addEventListener("pointercancel", up);
    });
  });
  win.addEventListener("pointerdown", () => { if (focusedWindow !== win) focusWindow(win); }, true);
  new ResizeObserver(() => updateDockVisibility()).observe(win);
}
$$(".window").forEach(win => { addWindowControls(win); enableDragging(win); });
$$("[data-sidebar-toggle]").forEach(button => button.addEventListener("click", () => {
  button.closest(".files-layout, .settings-layout").classList.toggle("sidebar-open");
}));

/* ---------- Ubuntu Dock (Dash to Dock profile: bottom, intellihide, 40px icons) ---------- */
const dock = $("#dock");
const dockItems = $("#dock-items");
const dockLabel = $("#dock-label");
const dockState = {autohide: true, hovered: false, revealed: false};
function runningApps() {
  return openWindows().map(win => win.dataset.app).filter(app => APPS[app]);
}
function renderDock() {
  const running = runningApps();
  const apps = [...new Set([...FAVORITES, ...running])];
  const focusedApp = focusedWindow && !focusedWindow.hidden ? focusedWindow.dataset.app : null;
  dockItems.innerHTML = apps.map(app =>
    `<button class="dock-item${focusedApp === app ? " focused" : ""}" type="button" data-dock-app="${app}" aria-label="${APPS[app].name}"` +
    `${running.includes(app) ? ' data-running="true"' : ""}><img src="${appIcon(app)}" alt="">` +
    `${running.includes(app) ? `<span class="dashes" aria-hidden="true" style="--app-color:${APP_COLORS[app]}">` +
      '<i></i>'.repeat(Math.min(4, running.filter(value => value === app).length)) + '</span>' : ""}</button>`).join("") +
    '<span class="dock-separator" role="separator"></span>' +
    `<button class="dock-item" type="button" data-dock-action="trash" aria-label="Trash"><img src="${ASSETS}places/user-trash.png" alt=""></button>` +
    `<button class="dock-item" type="button" data-dock-action="show-apps" aria-label="Show Apps" aria-pressed="${!$("#app-grid").hidden && !$("#overview").hidden}">${sym("view-app-grid-ubuntu")}</button>`;
}
dockItems.addEventListener("click", event => {
  const item = event.target.closest(".dock-item");
  if (!item) return;
  hideDockLabel();
  if (item.dataset.dockAction === "trash") { openApp("files", {path: "Trash"}); return; }
  if (item.dataset.dockAction === "show-apps") {
    if (!$("#overview").hidden && !$("#app-grid").hidden) closeOverview(); else openOverview("apps");
    return;
  }
  const app = item.dataset.dockApp;
  const win = windowFor(app);
  if (win.dataset.state && win.dataset.app === app) {
    if (win === focusedWindow && !win.hidden && $("#overview").hidden) minimizeWindow(win);
    else { closeOverview(); focusWindow(win); }
  } else openApp(app);
});
dockItems.addEventListener("pointerover", event => {
  const item = event.target.closest(".dock-item");
  if (item) showDockLabel(item);
});
dockItems.addEventListener("pointerout", event => { if (!event.relatedTarget?.closest?.(".dock-item")) hideDockLabel(); });
dockItems.addEventListener("focusin", event => { const item = event.target.closest(".dock-item"); if (item) showDockLabel(item); });
dockItems.addEventListener("focusout", hideDockLabel);
function showDockLabel(item) {
  const rect = item.getBoundingClientRect();
  dockLabel.textContent = item.getAttribute("aria-label");
  dockLabel.hidden = false;
  dockLabel.style.left = `${rect.left + rect.width / 2}px`;
  dockLabel.style.top = `${rect.top - dockLabel.offsetHeight - 10}px`;
}
function hideDockLabel() { dockLabel.hidden = true; }
function dockRect() {
  const width = dock.offsetWidth;
  const left = dock.offsetLeft - width / 2;
  return {left, right: left + width, top: dock.offsetTop, bottom: dock.offsetTop + dock.offsetHeight};
}
function updateDockVisibility() {
  const area = dockRect();
  const overlap = openWindows().some(win => {
    if (win.hidden) return false;
    const rect = win.getBoundingClientRect();
    return rect.left < area.right && rect.right > area.left && rect.top < area.bottom && rect.bottom > area.top;
  });
  const hide = dockState.autohide && overlap && !dockState.hovered && !dockState.revealed && $("#overview").hidden;
  dock.classList.toggle("autohidden", hide);
  dock.inert = hide;
}
dock.addEventListener("pointerenter", () => { dockState.hovered = true; updateDockVisibility(); });
dock.addEventListener("pointerleave", () => {
  dockState.hovered = false;
  dockState.revealed = false;
  setTimeout(updateDockVisibility, 400);
});
$("#dock-hotzone").addEventListener("pointerenter", () => { dockState.revealed = true; updateDockVisibility(); });
window.addEventListener("resize", () => { updateDockVisibility(); layoutWorkspace(); });

/* ---------- Activities overview ---------- */
const overview = $("#overview");
const overviewSearch = $("#overview-search");
function openOverview(mode = "windows") {
  closePopups();
  $("#banner").hidden = true;
  overview.hidden = false;
  $("#activities").setAttribute("aria-pressed", "true");
  overviewSearch.value = "";
  showOverviewMode(mode);
  updateDockVisibility();
  overviewSearch.focus();
}
function closeOverview() {
  if (overview.hidden) return;
  overview.hidden = true;
  delete preview.dataset.overview;
  $("#windows").style.transform = "";
  $("#activities").setAttribute("aria-pressed", "false");
  renderDock();
  updateDockVisibility();
}
function showOverviewMode(mode, filter = "") {
  const apps = mode === "apps";
  preview.dataset.overview = mode;
  $("#workspace-preview").hidden = apps;
  $("#app-grid").hidden = !apps;
  if (apps) {
    const query = filter.trim().toLowerCase();
    const matches = Object.entries(APPS).filter(([, app]) =>
      !query || `${app.name} ${app.keywords ?? ""}`.toLowerCase().includes(query));
    $("#app-grid").innerHTML = matches.length ? matches.map(([id, app]) =>
      `<button class="app-tile" type="button" data-launch="${id}"><img src="${appIcon(id)}" alt=""><span>${app.name}</span></button>`).join("")
      : '<p class="overview-empty">No Results</p>';
  } else {
    const wins = openWindows().filter(win => win.dataset.state === "open")
      .sort((a, b) => a.style.zIndex - b.style.zIndex);
    $("#workspace-preview").innerHTML = wins.length ? wins.map(win =>
      `<button class="window-preview" type="button" data-preview="${win.id}" aria-label="${escapeHtml(win.getAttribute("aria-label"))}">` +
      `<img src="${appIcon(win.dataset.app)}" alt=""><span class="title">${escapeHtml(win.getAttribute("aria-label"))}</span></button>`).join("")
      : '<p class="overview-empty">No open windows</p>';
    layoutWorkspace();
  }
  renderDock();
}
/* Like GNOME, the overview shows the real windows scaled into a workspace thumbnail. */
function layoutWorkspace() {
  const layer = $("#windows");
  const area = $("#workspace-preview");
  if (overview.hidden || area.hidden) return;
  const desk = preview.getBoundingClientRect();
  const box = area.getBoundingClientRect();
  const scale = Math.max(.1, Math.min(box.width / desk.width, box.height / desk.height));
  const left = box.left - desk.left + (box.width - desk.width * scale) / 2;
  const top = box.top - desk.top + (box.height - desk.height * scale) / 2;
  layer.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
  $$(".window-preview", area).forEach(button => {
    const win = $(`#${button.dataset.preview}`);
    Object.assign(button.style, {
      left: `${left - (box.left - desk.left) + win.offsetLeft * scale}px`,
      top: `${top - (box.top - desk.top) + win.offsetTop * scale}px`,
      width: `${win.offsetWidth * scale}px`,
      height: `${win.offsetHeight * scale}px`,
    });
  });
}
overviewSearch.addEventListener("input", () => showOverviewMode(overviewSearch.value ? "apps" : "windows", overviewSearch.value));
overviewSearch.addEventListener("keydown", event => {
  if (event.key === "Enter") $("#app-grid [data-launch]")?.click();
});
overview.addEventListener("click", event => {
  const launch = event.target.closest("[data-launch]");
  const previewButton = event.target.closest("[data-preview]");
  if (launch) openApp(launch.dataset.launch);
  else if (previewButton) { closeOverview(); focusWindow($(`#${previewButton.dataset.preview}`)); }
  else if (!event.target.closest(".overview-search")) closeOverview();
});
$("#activities").addEventListener("click", () => overview.hidden ? openOverview() : closeOverview());

/* ---------- Panel popups ---------- */
const POPUPS = {"logo-button": "logo-menu", "status-button": "quick-settings", "clock": "date-menu"};
function closePopups(except) {
  Object.entries(POPUPS).forEach(([buttonId, popupId]) => {
    if (popupId === except) return;
    $(`#${popupId}`).hidden = true;
    $(`#${buttonId}`).setAttribute("aria-expanded", "false");
  });
  if (except !== "gtk-popover") closeGtkPopover();
}
Object.entries(POPUPS).forEach(([buttonId, popupId]) => {
  $(`#${buttonId}`).addEventListener("click", () => {
    const popup = $(`#${popupId}`);
    const open = popup.hidden;
    closePopups(popupId);
    popup.hidden = !open;
    $(`#${buttonId}`).setAttribute("aria-expanded", String(open));
    if (open) {
      $("#banner").hidden = true;
      if (popupId === "date-menu") { calendarMonth = startOfMonth(new Date()); selectedDay = new Date(); renderCalendar(); renderMessages(); }
      $("button, input, a", popup)?.focus({preventScroll: true});
    }
  });
});
document.addEventListener("pointerdown", event => {
  if (event.target.closest(".glass-card, .panel-button, .gtk-popover, [aria-haspopup], dialog")) return;
  closePopups();
});
$("#logo-menu").addEventListener("click", event => {
  const item = event.target.closest(".popup-menu-item");
  if (!item) return;
  closePopups();
  const action = item.dataset.action;
  if (item.dataset.open) openApp(item.dataset.open);
  else if (action === "about") openApp("settings", {page: "about"});
  else if (action === "activities") openOverview();
  else if (action === "app-grid") openOverview("apps");
  else if (action === "force-quit" && focusedWindow && !focusedWindow.hidden) {
    const app = focusedWindow.dataset.app;
    closeWindow(app);
    notify({app: "settings", title: `${APPS[app].name} was force quit`, body: "Simulated — the window was closed."});
  }
});
$("#quick-settings").addEventListener("click", event => {
  const opener = event.target.closest("[data-open]");
  if (opener) openApp(opener.dataset.open, opener.dataset.settingsPage ? {page: opener.dataset.settingsPage} : {});
});
$("#qs-lock").addEventListener("click", () => {
  window.parent.postMessage({type: "lock"}, "*");
});
$("#desktop-home").addEventListener("dblclick", () => openApp("files", {path: "Home"}));
$("#desktop-home").addEventListener("click", event => event.currentTarget.classList.add("selected"));
$("#desktop-home").addEventListener("keydown", event => { if (event.key === "Enter") openApp("files", {path: "Home"}); });
$("#wallpaper").addEventListener("pointerdown", () => $("#desktop-home").classList.remove("selected"));

/* ---------- Quick Settings ---------- */
const qs = {wifi: true, network: "Home Network", bluetooth: false, airplane: false, night: false, power: "Balanced", muted: false};
function volumeIcon(value) {
  if (qs.muted || value === 0) return "audio-volume-muted";
  return value < 34 ? "audio-volume-low" : value < 67 ? "audio-volume-medium" : "audio-volume-high";
}
function updateQuickSettings() {
  const volume = Number($("#volume").value);
  $("#qt-wifi").setAttribute("aria-pressed", String(qs.wifi));
  $("#wifi-subtitle").textContent = qs.wifi ? qs.network : "Off";
  $("#qt-bluetooth").setAttribute("aria-pressed", String(qs.bluetooth));
  $("#qt-airplane").setAttribute("aria-pressed", String(qs.airplane));
  $("#qt-night").setAttribute("aria-pressed", String(qs.night));
  $("#qt-power").setAttribute("aria-pressed", String(qs.power !== "Balanced"));
  $("#power-subtitle").textContent = qs.power;
  const powerIcon = {"Performance": "power-profile-performance", "Balanced": "power-profile-balanced", "Power Saver": "power-profile-power-saver"}[qs.power];
  setIcon($("#power-mode-icon"), powerIcon);
  $$("[data-network]").forEach(item => item.setAttribute("aria-checked", String(qs.wifi && item.dataset.network === qs.network)));
  $$("[data-power]").forEach(item => item.setAttribute("aria-checked", String(item.dataset.power === qs.power)));
  setIcon($("#panel-network"), qs.airplane ? "airplane-mode" : qs.wifi ? "network-wireless-signal-excellent" : "network-wireless-offline");
  $("#panel-bluetooth").hidden = !qs.bluetooth;
  setIcon($("#panel-volume"), volumeIcon(volume));
  setIcon($("#qs-volume-icon"), volumeIcon(volume));
  $("#mute").setAttribute("aria-pressed", String(qs.muted));
  $("#night-light").hidden = !qs.night;
  $("#brightness-dim").style.opacity = String((100 - Number($("#brightness").value)) / 100 * .7);
  SETTINGS_SYNC.forEach(fn => fn());
  updatePreview();
}
const SETTINGS_SYNC = [];
$("#qt-wifi").addEventListener("click", () => { qs.wifi = !qs.wifi; if (qs.wifi) qs.airplane = false; updateQuickSettings(); });
$("#qt-bluetooth").addEventListener("click", () => { qs.bluetooth = !qs.bluetooth; if (qs.bluetooth) qs.airplane = false; updateQuickSettings(); });
$("#qt-airplane").addEventListener("click", () => {
  qs.airplane = !qs.airplane;
  if (qs.airplane) { qs.wifi = false; qs.bluetooth = false; }
  updateQuickSettings();
});
$("#qt-night").addEventListener("click", () => { qs.night = !qs.night; updateQuickSettings(); });
$("#qt-power").addEventListener("click", () => { qs.power = qs.power === "Balanced" ? "Performance" : "Balanced"; updateQuickSettings(); });
$("#qt-dark").addEventListener("click", () => setTheme(preview.dataset.theme === "dark" ? "light" : "dark"));
$("#mute").addEventListener("click", () => { qs.muted = !qs.muted; updateQuickSettings(); });
$("#volume").addEventListener("input", () => { qs.muted = false; updateQuickSettings(); });
$("#brightness").addEventListener("input", updateQuickSettings);
$$(".qt-arrow, #qs-power").forEach(button => button.addEventListener("click", () => {
  const target = $(`#${button.getAttribute("aria-controls")}`);
  const open = target.hidden;
  $$(".qs-submenu").forEach(menu => { menu.hidden = true; });
  $$(".qt-arrow, #qs-power").forEach(item => item.setAttribute("aria-expanded", "false"));
  target.hidden = !open;
  button.setAttribute("aria-expanded", String(open));
}));
$$("[data-network]").forEach(item => item.addEventListener("click", () => {
  qs.network = item.dataset.network; qs.wifi = true; qs.airplane = false; updateQuickSettings();
}));
$$("[data-power]").forEach(item => item.addEventListener("click", () => { qs.power = item.dataset.power; updateQuickSettings(); }));
$("#qs-screenshot").addEventListener("click", () => {
  closePopups();
  const flash = document.createElement("div");
  flash.style.cssText = "position:absolute;inset:0;z-index:3000;background:#fff;opacity:.85;transition:opacity .35s;pointer-events:none";
  preview.append(flash);
  requestAnimationFrame(() => requestAnimationFrame(() => { flash.style.opacity = "0"; }));
  setTimeout(() => flash.remove(), 450);
  notify({app: "files", icon: "places/folder-pictures.png", title: "Screenshot captured",
          body: "Simulated — no image was saved."});
});
const sessionDialog = $("#session-dialog");
const SESSION_TEXT = {
  restart: ["Restart", "The system will restart automatically in 60 seconds."],
  poweroff: ["Power Off", "The system will power off automatically in 60 seconds."],
  logout: ["Log Out", "User will be logged out automatically in 60 seconds."]
};
let pendingSession = null;
$$("[data-session]").forEach(item => item.addEventListener("click", () => {
  closePopups();
  if (item.dataset.session === "suspend") {
    const screen = $("#suspend-screen");
    screen.hidden = false;
    screen.focus();
    return;
  }
  pendingSession = item.dataset.session;
  const [title, text] = SESSION_TEXT[pendingSession];
  $("#session-title").textContent = title;
  $("#session-text").textContent = text;
  $("#session-confirm").textContent = title;
  sessionDialog.returnValue = "cancel";
  sessionDialog.showModal();
}));
sessionDialog.addEventListener("close", () => {
  if (sessionDialog.returnValue === "confirm" && pendingSession) {
    if (pendingSession === "logout") {
      window.parent.postMessage({type: "logout"}, "*");
    } else {
      notify({app: "settings", title: `${SESSION_TEXT[pendingSession][0]} requested`,
              body: "This is a browser simulation; nothing was changed on your computer."});
    }
  }
  pendingSession = null;
});
["click", "keydown"].forEach(type => $("#suspend-screen").addEventListener(type, event => { event.currentTarget.hidden = true; }));

/* ---------- Notifications and calendar ---------- */
const messages = [];
let bannerTimer = 0;
function notify({app = "glass", icon, title, body}) {
  const message = {id: Date.now() + Math.random(), app, icon: icon ?? APPS[app].icon, source: APPS[app]?.name ?? "System",
                   title, body, time: new Date()};
  messages.unshift(message);
  renderMessages();
  if ($("#dnd").checked || !$("#date-menu").hidden) return;
  const banner = $("#banner");
  banner.innerHTML = messageHtml(message, false);
  banner.hidden = false;
  clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => { banner.hidden = true; }, 4500);
}
function messageHtml(message, dismissable = true) {
  const time = message.time.toLocaleTimeString("en-GB", {hour: "2-digit", minute: "2-digit"});
  return `<div class="message" role="group" data-message="${message.id}" tabindex="0">` +
    `<img src="${ASSETS}${message.icon}" alt=""><span class="source">${escapeHtml(message.source)}</span>` +
    `<span class="time">${time}</span><strong>${escapeHtml(message.title)}</strong><p>${escapeHtml(message.body)}</p>` +
    (dismissable ? `<button class="icon-button dismiss" type="button" aria-label="Dismiss notification">${sym("window-close")}</button>` : "") +
    "</div>";
}
function renderMessages() {
  $("#message-list").innerHTML = messages.map(message => messageHtml(message)).join("");
  $("#message-placeholder").hidden = messages.length > 0;
  $("#clear-notifications").disabled = messages.length === 0;
}
$("#message-list").addEventListener("click", event => {
  const item = event.target.closest("[data-message]");
  if (!item) return;
  const index = messages.findIndex(message => String(message.id) === item.dataset.message);
  const [message] = messages.splice(index, 1);
  renderMessages();
  if (!event.target.closest(".dismiss") && APPS[message.app]) openApp(message.app);
});
$("#banner").addEventListener("click", () => {
  $("#banner").hidden = true;
  const message = messages[0];
  if (message && APPS[message.app]) openApp(message.app);
});
$("#clear-notifications").addEventListener("click", () => { messages.length = 0; renderMessages(); });
$("#dnd").addEventListener("change", () => {
  if ($("#dnd").checked) $("#banner").hidden = true;
});

const startOfMonth = date => new Date(date.getFullYear(), date.getMonth(), 1);
const sameDay = (a, b) => a.toDateString() === b.toDateString();
let calendarMonth = startOfMonth(new Date());
let selectedDay = new Date();
function renderCalendar() {
  const today = new Date();
  $("#today-weekday").textContent = today.toLocaleDateString("en-GB", {weekday: "long"});
  $("#today-full").textContent = today.toLocaleDateString("en-GB", {day: "numeric", month: "long", year: "numeric"});
  $("#cal-title").textContent = calendarMonth.toLocaleDateString("en-GB", {month: "long", year: "numeric"});
  const first = new Date(calendarMonth);
  first.setDate(1 - (first.getDay() + 6) % 7);
  const names = ["M", "T", "W", "T", "F", "S", "S"];
  let html = names.map(name => `<span class="weekday" role="columnheader">${name}</span>`).join("");
  for (let i = 0; i < 42; i++) {
    const day = new Date(first.getFullYear(), first.getMonth(), first.getDate() + i);
    const classes = ["calendar-day",
      day.getMonth() !== calendarMonth.getMonth() ? "other-month" : "",
      day.getDay() === 0 || day.getDay() === 6 ? "weekend" : "",
      sameDay(day, today) ? "today" : "",
      sameDay(day, selectedDay) && !sameDay(day, today) ? "selected" : ""].filter(Boolean).join(" ");
    html += `<button class="${classes}" type="button" role="gridcell" data-day="${day.toISOString()}" ` +
      `aria-label="${day.toLocaleDateString("en-GB", {weekday: "long", day: "numeric", month: "long"})}" ` +
      `aria-selected="${sameDay(day, selectedDay)}">${day.getDate()}</button>`;
  }
  $("#calendar-grid").innerHTML = html;
  const diff = Math.round((new Date(selectedDay.toDateString()) - new Date(today.toDateString())) / 864e5);
  $("#events-title").textContent = diff === 0 ? "Today" : diff === 1 ? "Tomorrow" : diff === -1 ? "Yesterday" :
    selectedDay.toLocaleDateString("en-GB", {weekday: "long", day: "numeric", month: "long"});
}
$("#calendar-grid").addEventListener("click", event => {
  const day = event.target.closest("[data-day]");
  if (!day) return;
  selectedDay = new Date(day.dataset.day);
  if (selectedDay.getMonth() !== calendarMonth.getMonth()) calendarMonth = startOfMonth(selectedDay);
  renderCalendar();
});
$("#cal-prev").addEventListener("click", () => { calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1); renderCalendar(); });
$("#cal-next").addEventListener("click", () => { calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1); renderCalendar(); });
$("#today-button").addEventListener("click", () => { calendarMonth = startOfMonth(new Date()); selectedDay = new Date(); renderCalendar(); });
function updateClock() {
  const now = new Date();
  $("#clock-text").textContent = `${now.toLocaleDateString("en-GB", {day: "numeric", month: "short"})}  ` +
    now.toLocaleTimeString("en-GB", {hour: "2-digit", minute: "2-digit"});
}

/* ---------- GTK popover menus ---------- */
const gtkPopover = $("#gtk-popover");
let popoverAnchor = null;
function openGtkPopover(anchor, items, {role = "menu", selected = -1} = {}) {
  if (popoverAnchor === anchor && !gtkPopover.hidden) { closeGtkPopover(); return; }
  closePopups("gtk-popover");
  closeGtkPopover();
  popoverAnchor = anchor;
  gtkPopover.setAttribute("role", role);
  if (anchor.id) gtkPopover.setAttribute("aria-labelledby", anchor.id);
  else gtkPopover.removeAttribute("aria-labelledby");
  gtkPopover.innerHTML = items.map((item, index) => item === "-" ? "<hr>" :
    `<button type="button" role="${role === "listbox" ? "option" : "checked" in item ? "menuitemcheckbox" : "menuitem"}" data-index="${index}"` +
    `${role === "listbox" ? ` aria-selected="${index === selected}"` :
      "checked" in item ? ` aria-checked="${item.checked}"` : ""}>${escapeHtml(item.label)}` +
    `${role === "listbox" || "checked" in item ? sym("object-select", "check") : ""}</button>`).join("");
  gtkPopover.onclick = event => {
    const button = event.target.closest("[data-index]");
    if (!button) return;
    closeGtkPopover();
    items[Number(button.dataset.index)].action();
  };
  gtkPopover.hidden = false;
  anchor.setAttribute("aria-expanded", "true");
  const rect = anchor.getBoundingClientRect();
  const left = Math.min(Math.max(4, rect.right - gtkPopover.offsetWidth), window.innerWidth - gtkPopover.offsetWidth - 4);
  gtkPopover.style.left = `${left}px`;
  gtkPopover.style.top = `${Math.max(4, Math.min(rect.bottom + 6, window.innerHeight - gtkPopover.offsetHeight - 4))}px`;
  ($(`[data-index="${selected}"]`, gtkPopover) ?? $("button", gtkPopover))?.focus();
}
function closeGtkPopover() {
  if (gtkPopover.hidden) return;
  gtkPopover.hidden = true;
  popoverAnchor?.setAttribute("aria-expanded", "false");
  popoverAnchor = null;
}
gtkPopover.addEventListener("keydown", event => {
  const options = $$("button", gtkPopover);
  const index = options.indexOf(document.activeElement);
  if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 :
      (index + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
    options[next]?.focus();
  } else if (event.key === "Tab" && gtkPopover.getAttribute("role") === "listbox") {
    const anchor = popoverAnchor;
    closeGtkPopover();
    anchor?.focus();
  } else if (event.key.length === 1 && !event.ctrlKey && !event.altKey && !event.metaKey &&
             gtkPopover.getAttribute("role") === "listbox") {
    const option = [...options.slice(index + 1), ...options.slice(0, index + 1)]
      .find(button => button.textContent.trim().toLowerCase().startsWith(event.key.toLowerCase()));
    if (option) { event.preventDefault(); option.focus(); }
  }
});
function syncComboControls() {
  comboControls.forEach((button, select) => {
    $(".combo-value", button).textContent = select.selectedOptions[0]?.textContent ?? "";
    button.disabled = select.disabled;
  });
}
function initializeComboControls() {
  $$(".combo select").forEach(select => {
    const row = select.closest(".gtk-row");
    const label = $(".row-text > span", row);
    const description = $(".row-text > small", row);
    label.id = `${select.id}-label`;
    if (description) description.id = `${select.id}-description`;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "combo-trigger";
    button.id = `${select.id}-trigger`;
    button.setAttribute("role", "combobox");
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", gtkPopover.id);
    button.setAttribute("aria-labelledby", `${label.id} ${select.id}-value`);
    if (description) button.setAttribute("aria-describedby", description.id);
    button.innerHTML = `<span class="combo-value" id="${select.id}-value"></span>`;
    select.after(button);
    select.hidden = true;
    comboControls.set(select, button);
    const open = () => openGtkPopover(button, [...select.options].map(option => ({
      label: option.textContent,
      action: () => {
        select.value = option.value;
        select.dispatchEvent(new Event("input", {bubbles: true}));
        select.dispatchEvent(new Event("change", {bubbles: true}));
        syncComboControls();
        button.focus();
      }
    })), {role: "listbox", selected: select.selectedIndex});
    button.addEventListener("click", event => { event.preventDefault(); open(); });
    button.addEventListener("keydown", event => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (gtkPopover.hidden || popoverAnchor !== button) open();
      }
    });
    row.addEventListener("click", event => {
      if (!event.target.closest("button")) { event.preventDefault(); button.click(); }
    });
    select.addEventListener("change", syncComboControls);
  });
  syncComboControls();
}

/* ---------- Files ---------- */
const FS = {
  "Home": [["Desktop", "folder"], ["Documents", "folder"], ["Downloads", "folder"], ["Music", "folder"],
           ["Pictures", "folder"], ["Videos", "folder"], [".config", "folder", true], ["notes.txt", "text", false, "1 kB"]],
  "Home/Desktop": [],
  "Home/Documents": [["Project plan.odt", "document", false, "18 kB"], ["Invoice.pdf", "pdf", false, "96 kB"],
                     ["todo.txt", "text", false, "1 kB"]],
  "Home/Downloads": [["yaru-glass-theme-2.1.1.tar.gz", "package", false, "1.2 MB"], ["podcast.mp3", "audio", false, "24 MB"]],
  "Home/Music": [["Ambient.ogg", "audio", false, "5 MB"]],
  "Home/Pictures": [["Wallpapers", "folder"], ["Screenshot.png", "image", false, "412 kB"]],
  "Home/Pictures/Wallpapers": [["alpine.jpg", "photo:alpine", false, "380 kB"], ["forest.jpg", "photo:forest", false, "410 kB"],
                               ["coast.jpg", "photo:coast", false, "350 kB"]],
  "Home/Videos": [],
  "Home/.config": [["yaru-glass", "folder"]],
  "Home/.config/yaru-glass": [["settings.json", "text", false, "1 kB"], ["app-appearance.json", "text", false, "1 kB"]],
  "Trash": [],
  "Starred": [],
  "Recent": [["todo.txt", "text", false, "Documents"], ["Screenshot.png", "image", false, "Pictures"], ["notes.txt", "text", false, "Home"]]
};
const TEXT_FILES = {
  "notes.txt": "Yaru Glass notes\n\n- Frost is the default glass style.\n- Crystal keeps more of the wallpaper visible.\n- Files transparency needs a Files restart.\n",
  "todo.txt": "Today\n\n[x] Try Clear Crystal\n[ ] Pick a dark wallpaper\n[ ] Restart Files after changing its transparency\n",
  "settings.json": '{\n  "transparency": 25,\n  "glass_mode": "frost",\n  "solid": false,\n  "readability_boost": false\n}\n',
  "app-appearance.json": '{\n  "enabled": true,\n  "transparency": 25\n}\n'
};
const PLACES = [
  ["Recent", "document-open-recent", "Recent"], ["Starred", "starred", "Starred"], ["Home", "user-home", "Home"],
  ["Documents", "folder-documents", "Home/Documents"], ["Downloads", "folder-download", "Home/Downloads"],
  ["Music", "folder-music", "Home/Music"], ["Pictures", "folder-pictures", "Home/Pictures"],
  ["Videos", "folder-videos", "Home/Videos"], ["Trash", "user-trash", "Trash"], "-",
  ["Other Locations", "list-add", "Other Locations"]
];
const files = {path: "Home", history: ["Home"], index: 0, view: "grid", hidden: false, query: "", selected: null};
function fileIcon(type, name) {
  if (type.startsWith("photo:")) return null;
  const special = {"Desktop": "user-desktop", "Documents": "folder-documents", "Downloads": "folder-download", "Music": "folder-music",
                   "Pictures": "folder-pictures", "Videos": "folder-videos"};
  if (type === "folder") return `places/${files.path === "Home" && special[name] ? special[name] : "folder"}.png`;
  return `mimetypes/${{text: "text-x-generic", image: "image-x-generic", audio: "audio-x-generic", video: "video-x-generic",
    document: "x-office-document", pdf: "application-pdf", package: "package-x-generic"}[type]}.png`;
}
$("#files-places").innerHTML = PLACES.map(place => place === "-" ? '<div class="sidebar-separator" role="separator"></div>' :
  `<button class="sidebar-row" type="button" data-place="${place[2]}">${sym(place[1])}<span>${place[0]}</span></button>`).join("");
function renderFiles() {
  const path = files.path;
  $$("[data-place]").forEach(row => row.setAttribute("aria-current", String(row.dataset.place === path)));
  const crumbs = path === "Home" || path.startsWith("Home/") ? path.split("/") : [path];
  $("#files-pathbar").innerHTML = crumbs.map((crumb, index) => {
    const target = crumbs.slice(0, index + 1).join("/");
    const icon = index === 0 && crumb === "Home" ? sym("user-home") : "";
    return `${index ? '<span class="sep">/</span>' : ""}<button type="button" data-crumb="${escapeHtml(target)}"` +
      `${index === crumbs.length - 1 ? ' aria-current="page"' : ""}>${icon}${escapeHtml(crumb)}</button>`;
  }).join("");
  const title = crumbs.at(-1);
  $("#win-files").setAttribute("aria-label", title);
  $("#files-back").disabled = files.index === 0;
  $("#files-forward").disabled = files.index >= files.history.length - 1;
  const content = $("#files-content");
  content.dataset.view = files.view;
  const query = files.query.trim().toLowerCase();
  const entries = (FS[path] ?? []).filter(([name, , hidden]) => (files.hidden || !hidden) && (!query || name.toLowerCase().includes(query)));
  $("#file-list").innerHTML = entries.map(([name, type, , meta]) => {
    const icon = fileIcon(type, name);
    const image = icon ? `<img src="${ASSETS}${icon}" alt="">` :
      `<img src="${WALLPAPERS}${type.slice(6)}.jpg" alt="" style="object-fit:cover;border-radius:4px">`;
    return `<button class="file-item" type="button" role="option" aria-selected="${files.selected === name}" data-file="${escapeHtml(name)}" ` +
      `data-type="${type}">${image}<span>${escapeHtml(name)}</span><span class="meta">${escapeHtml(meta ?? (type === "folder" ? `${(FS[`${path}/${name}`] ?? []).length} items` : ""))}</span></button>`;
  }).join("");
  const empty = $("#files-empty");
  empty.hidden = entries.length > 0;
  if (!entries.length) {
    const [iconName, heading, text] = query ? ["edit-find", "No Results Found", "Try a different search."] :
      path === "Trash" ? ["user-trash", "Trash is Empty", ""] :
      path === "Starred" ? ["starred", "No Starred Files", "Use the Star action to add files here."] :
      path === "Other Locations" ? ["computer", "Other Locations", "Network and other locations are not part of the simulation."] :
      ["folder-documents", "Folder is Empty", ""];
    setIcon($("#files-empty-icon"), iconName);
    $("#files-empty-title").textContent = heading;
    $("#files-empty-text").textContent = text;
  }
  renderDock();
}
function filesNavigate(path, push = true) {
  if (!(path in FS) && path !== "Other Locations") return;
  if (push && path !== files.path) {
    files.history = files.history.slice(0, files.index + 1);
    files.history.push(path);
    files.index = files.history.length - 1;
  }
  files.path = path;
  files.selected = null;
  files.query = "";
  $("#files-search").value = "";
  $("#files-floating").hidden = true;
  $(".files-layout").classList.remove("sidebar-open");
  renderFiles();
}
function filesNotice(text) {
  const notice = $("#files-floating");
  notice.textContent = text;
  notice.hidden = false;
  clearTimeout(filesNotice.timer);
  filesNotice.timer = setTimeout(() => { notice.hidden = true; }, 3000);
}
function openFileEntry(name, type) {
  if (type === "folder") filesNavigate(files.path === "Recent" ? "Home" : `${files.path}/${name}`);
  else if (type === "text") openApp("editor", {file: name});
  else filesNotice(`Opening “${name}” is not part of the simulation`);
}
$("#files-places").addEventListener("click", event => {
  const row = event.target.closest("[data-place]");
  if (row) filesNavigate(row.dataset.place);
});
$("#files-pathbar").addEventListener("click", event => {
  const crumb = event.target.closest("[data-crumb]");
  if (crumb) filesNavigate(crumb.dataset.crumb);
});
$("#file-list").addEventListener("click", event => {
  const item = event.target.closest("[data-file]");
  if (!item) return;
  files.selected = item.dataset.file;
  $$("[data-file]").forEach(entry => entry.setAttribute("aria-selected", String(entry === item)));
});
$("#file-list").addEventListener("dblclick", event => {
  const item = event.target.closest("[data-file]");
  if (item) openFileEntry(item.dataset.file, item.dataset.type);
});
$("#file-list").addEventListener("keydown", event => {
  const item = event.target.closest("[data-file]");
  if (item && event.key === "Enter") { event.preventDefault(); openFileEntry(item.dataset.file, item.dataset.type); }
});
$("#files-content").addEventListener("click", event => {
  if (event.target.closest("[data-file]")) return;
  files.selected = null;
  $$("[data-file]").forEach(entry => entry.setAttribute("aria-selected", "false"));
});
$("#files-back").addEventListener("click", () => { if (files.index > 0) filesNavigate(files.history[--files.index], false); });
$("#files-forward").addEventListener("click", () => {
  if (files.index < files.history.length - 1) filesNavigate(files.history[++files.index], false);
});
$("#files-view-toggle").addEventListener("click", event => {
  files.view = files.view === "grid" ? "list" : "grid";
  event.currentTarget.setAttribute("aria-label", files.view === "grid" ? "View as list" : "View as grid");
  setIcon($(".sym", event.currentTarget), files.view === "grid" ? "view-list" : "view-grid");
  renderFiles();
});
$("#files-search-toggle").addEventListener("click", event => {
  const bar = $("#files-search-bar");
  bar.hidden = !bar.hidden;
  event.currentTarget.setAttribute("aria-pressed", String(!bar.hidden));
  if (!bar.hidden) $("#files-search").focus();
  else { files.query = ""; $("#files-search").value = ""; renderFiles(); }
});
$("#files-search").addEventListener("input", event => { files.query = event.target.value; renderFiles(); });
$("#files-menu-button").addEventListener("click", event => openGtkPopover(event.currentTarget, [
  {label: "New Folder…", action: () => {
    if (!files.path.startsWith("Home")) { filesNotice("Folders cannot be created here"); return; }
    const list = FS[files.path];
    let name = "New Folder";
    for (let i = 2; list.some(([entry]) => entry === name); i++) name = `New Folder ${i}`;
    list.push([name, "folder"]);
    FS[`${files.path}/${name}`] = [];
    files.selected = name;
    renderFiles();
  }},
  "-",
  {label: "Show Hidden Files", checked: files.hidden, action: () => { files.hidden = !files.hidden; renderFiles(); }},
  "-",
  {label: "About Files", action: () => filesNotice("Files 46 — simulated for the Yaru Glass demo")}
]));
const APP_HOOKS = {
  files: {
    open(options) {
      if (options.path) filesNavigate(options.path);
      else if (!$("#win-files").dataset.state) filesNavigate("Home");
    },
    focus: () => loadFilesIfClosed()
  }
};
// Files keeps its loaded CSS until it is restarted or closed and reopened.
let filesWasClosed = true;
function loadFilesIfClosed() {
  if (!filesWasClosed) return;
  filesWasClosed = false;
  loadFilesAppearance();
}
APP_HOOKS.files.close = () => { filesWasClosed = true; };

/* ---------- Terminal ---------- */
const terminalOutput = $("#terminal-output");
const terminalInput = $("#terminal-input");
const terminalHistory = [];
let terminalHistoryIndex = 0;
const TERMINAL_WELCOME = "Welcome to the Yaru Glass demo shell. Type 'help' for the simulated commands.\n";
function terminalReset() { terminalOutput.textContent = TERMINAL_WELCOME; terminalInput.value = ""; }
function terminalPrint(text) {
  terminalOutput.append(text.endsWith("\n") || !text ? text : `${text}\n`);
  $("#terminal-body").scrollTop = $("#terminal-body").scrollHeight;
}
const COMMANDS = {
  help: () => "Simulated commands: help, ls, pwd, whoami, date, uname, echo, clear, nautilus, gnome-text-editor, yaru-glass-settings, exit",
  ls: args => (FS[`Home${args[0] ? `/${args[0].replace(/\/$/, "")}` : ""}`] ?? null)?.filter(([, , hidden]) => !hidden || args.includes("-a"))
    .map(([name]) => name).join("  ") ?? `ls: cannot access '${args[0]}': No such file or directory`,
  pwd: () => "/home/user",
  whoami: () => "user",
  date: () => new Date().toString(),
  uname: args => args.includes("-a") ? "Linux ubuntu 6.8.0-generic #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux" : "Linux",
  echo: args => args.join(" "),
  clear: () => { terminalOutput.textContent = ""; return ""; },
  nautilus: () => { openApp("files", {path: "Home"}); return ""; },
  "gnome-text-editor": () => { openApp("editor"); return ""; },
  "yaru-glass-settings": () => { openApp("glass"); return ""; },
  exit: () => { setTimeout(() => closeWindow("terminal"), 0); return ""; },
  sudo: () => "sudo: administrative commands are disabled in this simulation",
  cd: () => "cd: the simulated shell stays in your Home folder"
};
terminalInput.addEventListener("keydown", event => {
  if (event.key === "ArrowUp" || event.key === "ArrowDown") {
    event.preventDefault();
    terminalHistoryIndex = Math.max(0, Math.min(terminalHistory.length, terminalHistoryIndex + (event.key === "ArrowUp" ? -1 : 1)));
    terminalInput.value = terminalHistory[terminalHistoryIndex] ?? "";
    return;
  }
  if (event.key === "l" && event.ctrlKey) { event.preventDefault(); terminalOutput.textContent = ""; return; }
  if (event.key !== "Enter") return;
  const line = terminalInput.value;
  terminalInput.value = "";
  terminalPrint(`user@ubuntu:~$ ${line}`);
  if (line.trim()) { terminalHistory.push(line); }
  terminalHistoryIndex = terminalHistory.length;
  const [command, ...args] = line.trim().split(/\s+/);
  if (!command) return;
  const result = COMMANDS[command] ? COMMANDS[command](args) : `${command}: command not found`;
  if (result) terminalPrint(result);
});
$("#terminal-body").addEventListener("click", () => { if (!getSelection().toString()) terminalInput.focus(); });
$("#terminal-new-tab").addEventListener("click", () => { terminalReset(); terminalInput.focus(); });
$("#terminal-menu-button").addEventListener("click", event => openGtkPopover(event.currentTarget, [
  {label: "Clear Terminal", action: () => { terminalOutput.textContent = ""; terminalInput.focus(); }},
  {label: "Reset Terminal", action: () => { terminalReset(); terminalInput.focus(); }},
  "-",
  {label: "Close Window", action: () => closeWindow("terminal")}
]));
APP_HOOKS.terminal = {open: () => terminalReset(), focus: () => setTimeout(() => terminalInput.focus(), 0)};

/* ---------- Text Editor ---------- */
const editorText = $("#editor-text");
const editor = {name: null, saved: "", untitled: 1};
function editorUpdate() {
  const modified = editorText.value !== editor.saved;
  const name = editor.name ?? `Untitled Document ${editor.untitled}`;
  $("#editor-title").textContent = `${modified ? "• " : ""}${name}`;
  $("#editor-subtitle").textContent = editor.name ? (FS["Home/Documents"].some(([entry]) => entry === editor.name) ? "~/Documents" : "~") : "Draft";
  $("#win-editor").setAttribute("aria-label", `${name} - Text Editor`);
  const before = editorText.value.slice(0, editorText.selectionStart).split("\n");
  $("#editor-status").textContent = `Ln ${before.length}, Col ${before.at(-1).length + 1}`;
}
function editorLoad(name) {
  editor.name = name;
  editor.saved = name ? TEXT_FILES[name] ?? "" : "";
  editorText.value = editor.saved;
  editorUpdate();
}
["input", "keyup", "click"].forEach(type => editorText.addEventListener(type, editorUpdate));
function editorSave() {
  if (!editor.name) {
    editor.name = `Untitled Document ${editor.untitled}.txt`;
    FS["Home/Documents"].push([editor.name, "text", false, "1 kB"]);
  }
  TEXT_FILES[editor.name] = editorText.value;
  editor.saved = editorText.value;
  editorUpdate();
  notify({app: "editor", title: "Document saved", body: `${editor.name} was saved to Documents (simulated).`});
  if ($("#win-files").dataset.state) renderFiles();
}
$("#editor-new").addEventListener("click", () => { editor.untitled += 1; editorLoad(null); editorText.focus(); });
$("#editor-open").addEventListener("click", event => openGtkPopover(event.currentTarget,
  Object.keys(TEXT_FILES).map(name => ({label: name, action: () => { editorLoad(name); editorText.focus(); }}))));
$("#editor-menu-button").addEventListener("click", event => openGtkPopover(event.currentTarget, [
  {label: "Save", action: editorSave},
  {label: "Discard Changes", action: () => { editorText.value = editor.saved; editorUpdate(); }},
  "-",
  {label: "Close Window", action: () => closeWindow("editor")}
]));
editorText.addEventListener("keydown", event => {
  if (event.key === "s" && event.ctrlKey) { event.preventDefault(); editorSave(); }
});
APP_HOOKS.editor = {
  open: options => { if (options.file) editorLoad(options.file); else if (!$("#win-editor").dataset.state) editorLoad(null); },
  focus: () => setTimeout(() => editorText.focus(), 0)
};

/* ---------- GNOME Settings ---------- */
const SETTINGS_PAGES = [
  ["wifi", "Wi-Fi", "network-wireless"], ["bluetooth", "Bluetooth", "bluetooth-active"],
  ["displays", "Displays", "video-display"], ["sound", "Sound", "audio-volume-high"],
  ["power", "Power", "power-profile-balanced"], "-",
  ["appearance", "Appearance", "preferences-desktop-appearance"], ["ubuntu", "Ubuntu Desktop", "view-dual"],
  ["apps", "Apps", "preferences-desktop-apps"], ["privacy", "Privacy & Security", "preferences-system-privacy"], "-",
  ["about", "System", "preferences-system"]
];
let settingsPage = "appearance";
$("#settings-nav").innerHTML = SETTINGS_PAGES.map(page => page === "-" ? '<div class="sidebar-separator" role="separator"></div>' :
  `<button class="sidebar-row" type="button" data-settings="${page[0]}">${sym(page[2])}<span>${page[1]}</span></button>`).join("");
function switchRow(id, title, subtitle, checked) {
  return `<label class="gtk-row" for="${id}"><span class="row-text"><span>${title}</span>${subtitle ? `<small>${subtitle}</small>` : ""}</span>` +
    `<input class="switch" type="checkbox" role="switch" id="${id}" aria-label="${title}"${checked ? " checked" : ""}></label>`;
}
function infoRow(title, value) {
  return `<div class="gtk-row"><span class="row-text"><span>${title}</span></span><span class="row-suffix">${escapeHtml(value)}</span></div>`;
}
function group(title, body, description = "") {
  return `<div class="prefs-group">${title ? `<h3>${title}</h3>` : ""}${description ? `<p class="description">${description}</p>` : ""}` +
    `<div class="boxed-list">${body}</div></div>`;
}
const SETTINGS_RENDER = {
  wifi: () => group("", switchRow("set-wifi", "Wi-Fi", "", qs.wifi)) +
    group("Visible Networks", ["Home Network", "Café Guest", "Library"].map(name =>
      `<button class="gtk-row" type="button" data-set-network="${name}">${sym("network-wireless-signal-excellent")}` +
      `<span class="row-text"><span>${name}</span></span>${sym("object-select", "net-check")}</button>`).join("")),
  bluetooth: () => group("", switchRow("set-bluetooth", "Bluetooth", "", qs.bluetooth)) +
    `<p class="dim-label" id="set-bluetooth-text"></p>`,
  displays: () => group("Built-in display", infoRow("Resolution", "1920 × 1080 (16∶9)") + infoRow("Refresh Rate", "60.00 Hz") +
    infoRow("Scale", "100 %")) + group("", switchRow("set-night", "Night Light", "Makes the screen warmer", qs.night)),
  sound: () => group("Output", `<div class="gtk-row scale-row"><span class="row-text"><span>Volume</span></span>` +
    `<div class="scale"><input class="gtk-range" type="range" id="set-volume" min="0" max="100" aria-label="Output volume"></div></div>` +
    infoRow("Output Device", "Speakers – Built-in Audio")),
  power: () => group("Power Mode", ["Performance", "Balanced", "Power Saver"].map(mode =>
    `<label class="gtk-row"><span class="row-text"><span>${mode}</span></span><input type="radio" name="set-power" value="${mode}" ` +
    `aria-label="${mode}" style="accent-color:var(--accent);width:18px;height:18px"></label>`).join("")) +
    group("Battery", infoRow("Charge", "80 % — charging")),
  appearance: () => `<div class="prefs-group"><h3>Style</h3><div class="boxed-list"><div class="style-cards" role="radiogroup" aria-label="Style">` +
    ["light", "dark"].map(style => `<button class="style-card" type="button" role="radio" data-style="${style}" ` +
      `aria-checked="${preview.dataset.theme === style}"><span class="thumb" style='background-image:${WALLPAPER_CHOICES[state.wallpapers[style].current].css}'></span>` +
      `<span>${style === "light" ? "Default" : "Dark"}</span></button>`).join("") + "</div></div></div>" +
    group("Background", `<button class="gtk-row" type="button" id="set-open-wallpapers">${sym("preferences-desktop-wallpaper")}` +
      `<span class="row-text"><span>Light and dark wallpapers</span><small>Managed by Yaru Glass Settings</small></span>${sym("go-next")}</button>`) +
    group("Theme", `<button class="gtk-row" type="button" id="set-open-glass"><img src="${appIcon("glass")}" alt="" width="32" height="32">` +
      `<span class="row-text"><span>Yaru Glass</span><small>Glass style, transparency and app opt-ins</small></span>${sym("go-next")}</button>`),
  ubuntu: () => group("Desktop Icons", switchRow("set-home-icon", "Show Personal folder", "", !$("#desktop-home").hidden)) +
    group("Dock", switchRow("set-autohide", "Auto-hide the Dock", "The dock hides when any windows overlap with it", dockState.autohide) +
      `<div class="gtk-row scale-row"><span class="row-text"><span>Icon size</span></span><div class="scale">` +
      `<input class="gtk-range" type="range" id="set-icon-size" min="16" max="64" step="2" aria-label="Dock icon size"></div>` +
      `<output id="set-icon-size-value"></output></div>` + infoRow("Position on screen", "Bottom")),
  about: () => `<div class="about-logo">${sym("view-app-grid-ubuntu")}<strong>Ubuntu</strong></div>` +
    group("", infoRow("Device Name", "ubuntu") + infoRow("OS Name", "Ubuntu 24.04 LTS") + infoRow("GNOME Version", "46") +
      infoRow("Windowing System", "Wayland") + infoRow("Theme", "Yaru Glass") + infoRow("Memory", "16.0 GiB"))
};
function renderSettingsPage(page) {
  settingsPage = page;
  const entry = SETTINGS_PAGES.find(item => item[0] === page);
  $("#settings-title").textContent = page === "about" ? "About" : entry[1];
  $$("[data-settings]").forEach(row => row.setAttribute("aria-current", String(row.dataset.settings === page)));
  $("#settings-body").innerHTML = `<div class="prefs-page" style="max-width:640px;margin:0 auto;width:100%">` +
    (SETTINGS_RENDER[page]?.() ?? `<div class="placeholder-body" style="background:transparent">${sym(entry[2])}` +
      `<h2>${entry[1]}</h2><p>This panel is not part of the simulation.</p></div>`) + "</div>";
  $(".settings-layout").classList.remove("sidebar-open");
  syncSettings();
}
function syncSettings() {
  const body = $("#settings-body");
  const set = (selector, fn) => { const node = $(selector, body); if (node) fn(node); };
  set("#set-wifi", node => { node.checked = qs.wifi; });
  $$("[data-set-network]", body).forEach(row => { $(".net-check", row).style.visibility = qs.wifi && row.dataset.setNetwork === qs.network ? "visible" : "hidden"; });
  set("#set-bluetooth", node => { node.checked = qs.bluetooth; });
  set("#set-bluetooth-text", node => { node.textContent = qs.bluetooth ? "Visible as “ubuntu”. Searching for devices…" : "Bluetooth Turned Off — turn on to connect devices."; });
  set("#set-night", node => { node.checked = qs.night; });
  set("#set-volume", node => { if (document.activeElement !== node) node.value = $("#volume").value; });
  $$('[name="set-power"]', body).forEach(radio => { radio.checked = radio.value === qs.power; });
  $$("[data-style]", body).forEach(card => card.setAttribute("aria-checked", String(card.dataset.style === preview.dataset.theme)));
  set("#set-icon-size", node => {
    node.value = parseInt(getComputedStyle(preview).getPropertyValue("--dock-icon"), 10);
    $("#set-icon-size-value").textContent = `${node.value}`;
  });
  $$('input[type="range"]', body).forEach(control => control.style.setProperty("--range-progress",
    `${(Number(control.value) - Number(control.min)) / (Number(control.max) - Number(control.min)) * 100}%`));
}
SETTINGS_SYNC.push(syncSettings);
$("#settings-nav").addEventListener("click", event => {
  const row = event.target.closest("[data-settings]");
  if (row) renderSettingsPage(row.dataset.settings);
});
$("#settings-body").addEventListener("change", event => {
  const target = event.target;
  if (target.id === "set-wifi") { qs.wifi = target.checked; if (qs.wifi) qs.airplane = false; }
  else if (target.id === "set-bluetooth") { qs.bluetooth = target.checked; if (qs.bluetooth) qs.airplane = false; }
  else if (target.id === "set-night") qs.night = target.checked;
  else if (target.name === "set-power") qs.power = target.value;
  else if (target.id === "set-autohide") { dockState.autohide = target.checked; updateDockVisibility(); return; }
  else if (target.id === "set-home-icon") { $("#desktop-home").hidden = !target.checked; return; }
  else return;
  updateQuickSettings();
});
$("#settings-body").addEventListener("input", event => {
  const target = event.target;
  if (target.id === "set-volume") { $("#volume").value = target.value; qs.muted = false; updateQuickSettings(); }
  if (target.id === "set-icon-size") {
    preview.style.setProperty("--dock-icon", `${target.value}px`);
    syncSettings();
    updateDockVisibility();
  }
});
$("#settings-body").addEventListener("click", event => {
  const network = event.target.closest("[data-set-network]");
  const style = event.target.closest("[data-style]");
  if (network) { qs.network = network.dataset.setNetwork; qs.wifi = true; qs.airplane = false; updateQuickSettings(); }
  else if (style) setTheme(style.dataset.style);
  else if (event.target.closest("#set-open-wallpapers")) { openApp("glass"); selectPage($("#tab-wallpapers")); }
  else if (event.target.closest("#set-open-glass")) { openApp("glass"); selectPage($("#tab-shell")); }
});
$("#settings-search-button").addEventListener("click", event => openGtkPopover(event.currentTarget,
  SETTINGS_PAGES.filter(page => page !== "-").map(page => ({label: page[1], action: () => renderSettingsPage(page[0])}))));
$(".settings-sidebar .headerbar .end .gtk-button").addEventListener("click", event => openGtkPopover(event.currentTarget, [
  {label: "Help", action: () => openApp("help")},
  {label: "About Settings", action: () => renderSettingsPage("about")}
]));
APP_HOOKS.settings = {open: options => renderSettingsPage(options.page ?? "appearance")};

/* ---------- Keyboard and start-up ---------- */
document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    if (!gtkPopover.hidden) { const anchor = popoverAnchor; closeGtkPopover(); anchor?.focus(); return; }
    const open = Object.entries(POPUPS).find(([, popupId]) => !$(`#${popupId}`).hidden);
    if (open) { closePopups(); $(`#${open[0]}`).focus(); return; }
    if (!overview.hidden) closeOverview();
  }
  if (event.key === "Meta" || event.key === "OS") overview.hidden ? openOverview() : closeOverview();
});
document.addEventListener("pointerdown", event => {
  if (!gtkPopover.hidden && !event.target.closest(".gtk-popover, [aria-haspopup]")) closeGtkPopover();
});

applyIcons();
initializeComboControls();
setTheme(matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
updateQuickSettings();
renderCalendar();
renderMessages();
updateClock();
setInterval(updateClock, 15000);
loadFilesAppearance();
openApp("glass");
setTimeout(() => notify({app: "glass", title: "Yaru Glass desktop simulation",
  body: "Everything runs in this page. Nothing on your computer is changed."}), 700);
