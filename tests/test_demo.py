"""Exercise the standalone demo in the installed WebKit engine."""
import json
import threading
import time
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gdk, GLib, Gtk, WebKit
    AVAILABLE = Gtk.init_check() and Gdk.Display.get_default() is not None
except (ImportError, ValueError):
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, "GTK4/WebKit 6 and a display are required")
class WebKitDemoCase(unittest.TestCase):
    demo_path = "demo/index.html"

    @classmethod
    def setUpClass(cls):
        cls.window = Gtk.Window(default_width=1100, default_height=650)
        cls.window.set_decorated(False)
        cls.web = WebKit.WebView()
        cls.window.set_child(cls.web)
        cls.window.present()
        cls.loaded = False
        cls.load_error = None
        cls.web.connect("load-changed", cls.on_load)
        cls.web.connect("load-failed", cls.on_load_error)
        cls.web.load_uri((Path(__file__).resolve().parents[1] / cls.demo_path).as_uri())
        cls.wait_for(lambda: cls.loaded or cls.load_error)
        if cls.load_error:
            raise RuntimeError(cls.load_error)

    @classmethod
    def on_load(cls, _web, event):
        if event == WebKit.LoadEvent.FINISHED:
            cls.loaded = True

    @classmethod
    def on_load_error(cls, _web, _event, uri, error):
        cls.load_error = f"{uri}: {error}"
        return False

    @classmethod
    def wait_for(cls, predicate):
        context = GLib.MainContext.default()
        deadline = time.monotonic() + 20
        while not predicate():
            if time.monotonic() > deadline:
                raise TimeoutError("Demo browser operation timed out")
            while context.pending():
                context.iteration(False)
            time.sleep(.01)

    @classmethod
    def tearDownClass(cls):
        cls.window.destroy()

    def resize_viewport(self, width, height):
        # A mapped window may miss a single resize request, so repeat it until the page reports the size.
        deadline = time.monotonic() + 20
        while True:
            self.window.set_default_size(width, height)
            retry = time.monotonic() + 1
            try:
                self.wait_for(lambda: time.monotonic() > retry or (
                    abs(int(self.js("innerWidth")) - width) <= 1 and abs(int(self.js("innerHeight")) - height) <= 1))
            except TimeoutError:
                pass
            if abs(int(self.js("innerWidth")) - width) <= 1 and abs(int(self.js("innerHeight")) - height) <= 1:
                return
            if time.monotonic() > deadline:
                raise TimeoutError(f"Demo viewport did not resize to {width}x{height}: page {self.js('innerWidth')}x{self.js('innerHeight')}, window {self.window.get_width()}x{self.window.get_height()}, maximized={self.window.is_maximized()}")

    def js(self, script):
        result = []

        def finished(web, task):
            try:
                result.append((web.evaluate_javascript_finish(task).to_string(), None))
            except GLib.Error as exc:
                result.append((None, exc))

        self.web.evaluate_javascript(script, -1, None, None, None, finished)
        self.wait_for(lambda: result)
        if result[0][1]:
            raise result[0][1]
        return result[0][0]


class DemoTests(WebKitDemoCase):
    demo_path = "demo/desktop-view.html"

    def setUp(self):
        self.window.set_default_size(1100, 650)
        type(self).loaded = False
        uri = (Path(__file__).resolve().parents[1] / self.demo_path).as_uri()
        token = str(time.monotonic_ns())
        self.web.load_uri(f"{uri}?test={token}")
        self.wait_for(lambda: type(self).loaded)
        self.wait_for(lambda: self.js(f"String(location.search === '?test={token}' && document.readyState === 'complete' && typeof openApp === 'function')") == "true")

    def test_alpha_matrix_and_independent_files_window(self):
        result = self.js("""JSON.stringify((() => {
          const check = (condition, message) => { if (!condition) throw Error(message); };
          openApp('files');
          check(!document.querySelector('#win-glass').contains(document.querySelector('#win-files')), 'Files nested');
          let count = 0;
          for (const dark of [false, true]) for (const crystal of [false, true])
          for (const level of [0,25,50]) for (const boost of [false,true]) for (const solid of [false,true]) {
            preview.dataset.theme = dark ? 'dark' : 'light';
            preview.dataset.glass = crystal ? 'crystal' : 'frost';
            slider.value = level; solidControl.checked = solid; boostControl.checked = boost;
            appEnabledControl.checked = true; filesEnabledControl.checked = true;
            appLevelControl.value = level; filesLevelControl.value = level;
            updatePreview();
            const tint = alpha => boost ? alpha + (1-alpha)/2 : alpha;
            const expectedApp = tint(1-(1-(dark?.8:.7))*level/50*(crystal?1:.7));
            const expectedFiles = tint(1-.3*level/50*(crystal?1:.7));
            const expectedMenu = solid ? 1 : tint((dark?.7:.58)+(1-(dark?.7:.58))*.8*(1-level/100)*(crystal?.55:1));
            const style = getComputedStyle(preview);
            for (const [name,expected] of [['app',expectedApp],['files',expectedFiles],['menu',expectedMenu]]) {
              check(Math.abs(Number(style.getPropertyValue('--'+name+'-opacity'))-expected)<.00001, name+' alpha');
            }
            check(!getComputedStyle(document.querySelector('.files-content')).backgroundColor.startsWith('rgba'), 'Content transparent');
            check(slider.disabled===solid, 'Solid slider');
            count++;
          }
          appEnabledControl.checked = false; filesEnabledControl.checked = false;
          updatePreview();
          check(getComputedStyle(preview).getPropertyValue('--app-opacity')==='1', 'Disabled app');
          check(getComputedStyle(preview).getPropertyValue('--files-opacity')==='1', 'Disabled Files');
          return count;
        })())""")
        self.assertEqual(int(result), 48)

    def test_settings_starts_floating_and_stays_floating_when_it_fits(self):
        for width in (1100, 680):
            self.resize_viewport(width, 720)
            result = self.js("""JSON.stringify((() => {
              const win = document.querySelector('#win-glass');
              const bounds = win.getBoundingClientRect();
              return !win.classList.contains('maximized') && bounds.width === 540 &&
                bounds.left > 0 && bounds.right < innerWidth && bounds.bottom < innerHeight &&
                getComputedStyle(win).borderRadius !== '0px';
            })())""")
            self.assertEqual(result, "true", width)

    def test_ubuntu_combo_popovers_selection_keyboard_and_cancel(self):
        result = self.js("""JSON.stringify((() => {
          const check = (condition, message) => { if (!condition) throw Error(message); };
          const trigger = document.querySelector('#preset-trigger');
          check(presetControl.hidden && trigger.getAttribute('role') === 'combobox', 'Custom select');
          trigger.click();
          check(gtkPopover.getAttribute('role') === 'listbox', 'Listbox');
          check(gtkPopover.querySelectorAll('[role=option]').length === 3, 'Preset options');
          check(document.activeElement.getAttribute('aria-selected') === 'true', 'Selected row focus');
          const before = JSON.stringify(currentValues());
          document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key:'End', bubbles:true}));
          check(document.activeElement.textContent.trim() === 'Clear Crystal', 'End');
          document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowUp', bubbles:true}));
          check(document.activeElement.textContent.trim() === 'Balanced Frost', 'Arrow');
          document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key:'s', bubbles:true}));
          check(document.activeElement.textContent.trim() === 'Solid', 'Type ahead');
          document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
          check(gtkPopover.hidden && document.activeElement === trigger, 'Escape restores focus');
          check(JSON.stringify(currentValues()) === before, 'Cancel did not apply');
          trigger.click(); gtkPopover.querySelector('[data-index="2"]').click();
          check(presetControl.value === 'Clear Crystal' && trigger.textContent === 'Clear Crystal', 'Selected value');
          check(JSON.stringify(currentValues()) === before, 'Preset still requires confirmation');
          const glass = document.querySelector('#glass-style-trigger');
          glass.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown', bubbles:true}));
          gtkPopover.querySelector('[data-index="1"]').click();
          check(preview.dataset.glass === 'crystal' && glass.textContent === 'Crystal', 'Style applied');
          applyPatch({glass:'frost'});
          check(glass.textContent === 'Frost', 'Programmatic sync');
          glass.click();
          document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key:'Tab', bubbles:true}));
          check(gtkPopover.hidden && document.activeElement === glass, 'Tab closes');
          return true;
        })())""")
        self.assertEqual(result, "true")

    def test_layered_default_and_independent_dynamic_blur(self):
        result = self.js("""JSON.stringify((() => {
          const blur = selector => {
            const style = getComputedStyle(document.querySelector(selector));
            return (style.backdropFilter || style.webkitBackdropFilter || '').includes('blur');
          };
          if (document.querySelector('#glass-sample') || preview.dataset.material !== 'layered') return false;
          document.querySelector('#status-button').click();
          for (const glass of ['frost', 'crystal']) {
            applyPatch({glass, backgroundBlur: true, solid: false});
            if (!['#panel', '#quick-settings', '.dock-bg'].every(blur)) return false;
            if (['#win-glass', '#win-files'].some(blur)) return false;
            applyPatch({solid: true});
            if (!blurControl.checked || ['#panel', '#quick-settings', '.dock-bg'].some(blur)) return false;
            applyPatch({solid: false});
            if (!blur('#panel')) return false;
            applyPatch({backgroundBlur: false});
            applyPatch(presetPatch('Balanced Frost'));
            if (blurControl.checked || blur('#panel')) return false;
          }
          return getComputedStyle(document.querySelector('#panel')).backgroundImage.includes('linear-gradient');
        })())""")
        self.assertEqual(result, "true")

    def test_layered_material_preserves_appearance_controls(self):
        result = self.js("""JSON.stringify((() => {
          const check = (condition, message) => { if (!condition) throw Error(message); };
          const before = [glassControl.value, slider.value];
          applyPatch({backgroundBlur: false});
          for (const [theme, backdrop] of [['light', 'white'], ['dark', 'dark'], ['light', 'alpine']]) {
            state.wallpapers[theme].current = backdrop;
            setTheme(theme);
            for (const glass of ['frost', 'crystal']) {
              glassControl.value = glass;
              glassControl.dispatchEvent(new Event('change'));
              const style = getComputedStyle(document.querySelector('#panel'));
              const cardStyle = getComputedStyle(document.querySelector('#quick-settings'));
              check(preview.dataset.material === 'layered', 'Layered material delivered');
              check(preview.dataset.backdrop === backdrop, 'Wallpaper backdrop selected');
              check(!style.backdropFilter || style.backdropFilter === 'none', 'Layered sample stays unblurred');
              check(style.backgroundImage.includes('linear-gradient'), 'Layered reflections present');
              check(style.borderTopColor !== 'rgba(0, 0, 0, 0)', 'Layered rim present');
              check(cardStyle.boxShadow.includes('inset'), 'Layered menu depth present');
              check(glassControl.value === glass && slider.value === before[1], 'Appearance controls preserved');
              if (theme === 'light' && backdrop === 'white' && glass === 'frost') window.frostSheen = style.backgroundImage;
              if (theme === 'light' && backdrop === 'white' && glass === 'crystal') window.crystalSheen = style.backgroundImage;
            }
          }
          check(window.frostSheen !== window.crystalSheen, 'Frost and Crystal reflections differ');
          state.wallpapers.light.current = 'alpine';
          state.wallpapers.dark.current = 'forest';
          updateWallpapers();
          return true;
        })())""")
        self.assertEqual(result, "true")

    def test_dock_dashes_use_icon_colors_and_window_counts(self):
        result = self.js("""JSON.stringify((() => {
          openApp('files'); openApp('terminal');
          const files = document.querySelector('[data-dock-app="files"] .dashes i');
          const terminal = document.querySelector('[data-dock-app="terminal"] .dashes i');
          if (!files || !terminal) return false;
          const style = getComputedStyle(files);
          if (parseFloat(style.width) <= parseFloat(style.height) ||
              style.backgroundColor === getComputedStyle(terminal).backgroundColor) return false;
          const second = document.createElement('div');
          second.className = 'window'; second.dataset.app = 'files'; second.dataset.state = 'open';
          document.querySelector('#windows').append(second);
          renderDock();
          const count = document.querySelectorAll('[data-dock-app="files"] .dashes i').length;
          second.remove(); renderDock();
          closeWindow('files');
          return count === 2 && !document.querySelector('[data-dock-app="files"] .dashes');
        })())""")
        self.assertEqual(result, "true")

    def test_preset_cancel_apply_and_keyboard_tabs(self):
        self.js("selectPage(document.querySelector('#tab-shell')); presetControl.value='Solid'; document.querySelector('#preview-preset').click(); 'opened'")
        self.assertEqual(self.js("document.activeElement.id"), "dialog-cancel")
        before = self.js("JSON.stringify(currentValues())")
        self.js("document.querySelector('#dialog-cancel').click(); 'cancel'")
        self.wait_for(lambda: self.js("String(!dialog.open)") == "true")
        self.assertEqual(self.js("JSON.stringify(currentValues())"), before)
        for name in ("Solid", "Balanced Frost", "Clear Crystal"):
            self.js(f"presetControl.value={json.dumps(name)}; document.querySelector('#preview-preset').click(); document.querySelector('#dialog-apply').click(); 'apply'")
            self.wait_for(lambda: self.js("String(document.querySelector('#preset-status').textContent.includes(" +
                                        json.dumps(f"Saved preset: {name} ·") + "))") == "true")
        self.js("document.querySelector('#tab-shell').dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true})); 'key'")
        self.assertEqual(self.js("document.activeElement.id"), "tab-wallpapers")
        self.assertEqual(self.js("String(document.querySelector('#page-wallpapers').hidden)"), "false")

    def test_preset_confirmation_uses_readable_named_values(self):
        self.js("""appEnabledControl.checked=false; filesEnabledControl.checked=false; updatePreview();
          presetControl.value='Clear Crystal'; document.querySelector('#preview-preset').click(); 'opened'""")
        self.assertEqual(self.js("document.querySelector('#dialog-title').textContent"), "Apply Clear Crystal?")
        body = self.js("document.querySelector('#preset-preview').textContent")
        for line in ("Shell", "Glass style: Frost → Crystal", "Transparency level: 25% → 50%",
                     "Solid backgrounds: Off → Off", "Settings app", "Transparency: Disabled → Enabled", "Files"):
            self.assertIn(line, body)
        self.js("dialog.close('cancel'); 'cancel'")

    def test_mobile_has_no_horizontal_overflow(self):
        for width in (320, 390):
            self.resize_viewport(width, 650)
            for script in ("closePopups(); 'ok'", "document.querySelector('#status-button').click(); 'ok'",
                           "closePopups(); document.querySelector('#clock').click(); 'ok'",
                           "closePopups(); openApp('files'); 'ok'", "openApp('settings'); 'ok'"):
                self.js(script)
                self.assertEqual(self.js("String(document.documentElement.scrollWidth<=innerWidth && preview.scrollWidth<=innerWidth)"), "true", script)
            self.assertEqual(self.js("String(document.querySelector('#win-settings').getBoundingClientRect().right<=innerWidth)"), "true")

    def test_notification_animation_stays_centered_after_viewport_resize(self):
        for width in (1100, 320, 390, 680):
            self.resize_viewport(width, 650)
            for progress in (0, 0.1, 0.5, 0.99):
                result = json.loads(self.js(f"""JSON.stringify((() => {{
                  const banner = document.querySelector('#banner');
                  banner.hidden = true;
                  void banner.offsetWidth;
                  notify({{title: 'Responsive notification', body: 'Animation must stay inside the desktop.'}});
                  for (const animation of banner.getAnimations()) {{
                    animation.pause();
                    animation.currentTime = {progress} * 250;
                  }}
                  const bounds = banner.getBoundingClientRect();
                  return {{width: innerWidth, left: bounds.left, right: bounds.right,
                    center: (bounds.left + bounds.right) / 2,
                    overflow: preview.scrollWidth > innerWidth}};
                }})())"""))
                with self.subTest(width=width, progress=progress):
                    self.assertGreaterEqual(result["left"], 0, result)
                    self.assertLessEqual(result["right"], width, result)
                    self.assertAlmostEqual(result["center"], width / 2, delta=1, msg=result)
                    self.assertFalse(result["overflow"], result)
            self.js("document.querySelector('#banner').hidden = true; 'hidden'")

    def test_notification_reduced_motion_preserves_centering(self):
        self.resize_viewport(320, 650)
        css = (Path(__file__).resolve().parents[1] /
               "demo/demo-assets/desktop/desktop.css").read_text()
        self.js(f"""const motionStyle = document.createElement('style');
          motionStyle.id = 'test-motion-style';
          motionStyle.textContent = {json.dumps(css)};
          document.head.append(motionStyle); 'ready'""")
        result = json.loads(self.js("""JSON.stringify((() => {
          for (const rule of document.querySelector('#test-motion-style').sheet.cssRules)
            if (rule.conditionText === '(prefers-reduced-motion: reduce)')
              rule.media.mediaText = 'all';
          notify({title: 'Reduced motion', body: 'Centered without animation.'});
          const banner = document.querySelector('#banner');
          const bounds = banner.getBoundingClientRect();
          return {animation: getComputedStyle(banner).animationName,
            left: bounds.left, right: bounds.right, overflow: preview.scrollWidth > innerWidth};
        })())"""))
        self.assertEqual(result["animation"], "none")
        self.assertGreaterEqual(result["left"], 0, result)
        self.assertLessEqual(result["right"], 320, result)
        self.assertAlmostEqual(result["left"], 320 - result["right"], delta=1, msg=result)
        self.assertFalse(result["overflow"], result)

    def test_wallpaper_chooser_switches_with_dark_style(self):
        self.js("setTheme('light'); document.querySelector('[data-choose=light]').click(); 'ok'")
        self.assertEqual(self.js("String(document.querySelector('#chooser-dialog').open)"), "true")
        self.js("document.querySelector('[data-wallpaper=white]').click(); document.querySelector('#chooser-dialog').close('select'); 'ok'")
        self.wait_for(lambda: self.js("preview.dataset.backdrop") == "white")
        self.assertIn("255, 255, 255", self.js("document.querySelector('#wallpaper').style.backgroundImage"))
        self.js("document.querySelector('[data-choose=dark]').click(); document.querySelector('[data-wallpaper=dark]').click(); document.querySelector('#chooser-dialog').close('cancel'); 'ok'")
        self.wait_for(lambda: self.js("String(!document.querySelector('#chooser-dialog').open)") == "true")
        self.js("document.querySelector('#qt-dark').click(); 'ok'")
        self.assertEqual(self.js("preview.dataset.theme + ' ' + preview.dataset.backdrop"), "dark forest")
        self.js("document.querySelector('[data-choose=dark]').click(); document.querySelector('[data-wallpaper=dark]').click(); document.querySelector('#chooser-dialog').close('select'); 'ok'")
        self.wait_for(lambda: self.js("preview.dataset.backdrop") == "dark")
        self.assertEqual(self.js("document.querySelector('#qt-dark').getAttribute('aria-pressed')"), "true")
        self.js("document.querySelector('[data-restore=light]').click(); document.querySelector('#qt-dark').click(); 'ok'")
        self.assertEqual(self.js("preview.dataset.theme"), "light")
        self.assertNotEqual(self.js("preview.dataset.backdrop"), "white")

    def test_dock_launch_minimize_overview_and_close(self):
        files_button = "document.querySelector('#dock-items [aria-label=Files]')"
        self.assertEqual(self.js("String(document.querySelector('#win-files').hidden)"), "true")
        self.js(f"{files_button}.click(); 'ok'")
        self.assertEqual(self.js("focusedWindow.id"), "win-files")
        self.assertEqual(self.js(f"{files_button}.dataset.running"), "true")
        self.js(f"{files_button}.click(); 'ok'")
        self.wait_for(lambda: self.js("document.querySelector('#win-files').dataset.state") == "minimized")
        self.js(f"{files_button}.click(); 'ok'")
        self.assertEqual(self.js("document.querySelector('#win-files').dataset.state"), "open")
        self.js("document.querySelector('#activities').click(); 'ok'")
        self.assertEqual(self.js("String(!overview.hidden && preview.dataset.overview === 'windows')"), "true")
        self.assertIn("scale", self.js("document.querySelector('#windows').style.transform"))
        self.assertEqual(self.js("String(document.querySelectorAll('.window-preview').length)"), "2")
        self.js("document.querySelector('[data-preview=win-glass]').click(); 'ok'")
        self.assertEqual(self.js("String(overview.hidden) + focusedWindow.id + document.querySelector('#windows').style.transform"), "truewin-glass")
        self.js("document.querySelector('[data-dock-action=show-apps]').click(); overviewSearch.value='edit'; overviewSearch.dispatchEvent(new Event('input')); 'ok'")
        self.assertEqual(self.js("String(Boolean(document.querySelector('#app-grid [data-launch=editor]')))"), "true")
        self.js("overviewSearch.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter'})); 'ok'")
        self.assertEqual(self.js("String(overview.hidden) + focusedWindow.id"), "truewin-editor")
        self.js("document.querySelector('#win-files .window-controls .close').click(); 'ok'")
        self.wait_for(lambda: self.js("String(document.querySelector('#win-files').hidden)") == "true")
        self.assertEqual(self.js(f"String({files_button}.dataset.running)"), "undefined")

    def test_files_live_opacity_changes_only_after_confirmed_restart(self):
        self.js("openApp('files'); filesEnabledControl.checked=true; filesLevelControl.value=0; filesLevelControl.dispatchEvent(new Event('input')); 'ok'")
        live = self.js("getComputedStyle(preview).getPropertyValue('--files-live-opacity')")
        self.js("filesLevelControl.value=50; filesLevelControl.dispatchEvent(new Event('input')); 'ok'")
        self.assertEqual(self.js("getComputedStyle(preview).getPropertyValue('--files-live-opacity')"), live)
        self.js("document.querySelector('#restart-files').click(); 'ok'")
        self.assertEqual(self.js("document.querySelector('#dialog-apply').textContent"), "Transfers finished — Restart")
        self.js("document.querySelector('#dialog-cancel').click(); 'ok'")
        self.assertEqual(self.js("getComputedStyle(preview).getPropertyValue('--files-live-opacity')"), live)
        self.js("document.querySelector('#restart-files').click(); document.querySelector('#dialog-apply').click(); 'ok'")
        self.wait_for(lambda: self.js("String(document.querySelector('#files-status').textContent.startsWith('Files restarted'))") == "true")
        self.assertEqual(self.js("getComputedStyle(preview).getPropertyValue('--files-opacity')"),
                         self.js("getComputedStyle(preview).getPropertyValue('--files-live-opacity')"))
        self.assertNotEqual(self.js("getComputedStyle(preview).getPropertyValue('--files-live-opacity')"), live)
        self.assertEqual(self.js("String(document.querySelector('#win-files').hidden)"), "false")

    def test_quick_settings_date_menu_and_apps_are_interactive(self):
        result = self.js("""JSON.stringify((() => {
          const check = (condition, message) => { if (!condition) throw Error(message); };
          document.querySelector('#status-button').click();
          check(!document.querySelector('#quick-settings').hidden, 'Quick Settings open');
          check(document.querySelector('#status-button').getAttribute('aria-expanded')==='true', 'Expanded');
          document.querySelector('#qt-wifi').click();
          check(document.querySelector('#qt-wifi').getAttribute('aria-pressed')==='false', 'Wi-Fi off');
          check(document.querySelector('#panel-network').dataset.icon==='network-wireless-offline', 'Panel icon follows');
          document.querySelector('#clock').click();
          check(document.querySelector('#quick-settings').hidden && !document.querySelector('#date-menu').hidden, 'Popups exclusive');
          check(document.querySelectorAll('#calendar-grid .calendar-day').length>=35, 'Calendar days');
          const title = document.querySelector('#cal-title').textContent;
          document.querySelector('#cal-next').click();
          check(document.querySelector('#cal-title').textContent!==title, 'Calendar navigates');
          closePopups();
          openApp('terminal');
          const input = document.querySelector('#terminal-input');
          input.value='echo glass';
          input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true}));
          check(document.querySelector('#terminal-output').textContent.includes('\\nglass\\n'), 'Terminal echo');
          openApp('settings', {page: 'appearance'});
          check(!document.querySelector('#win-settings').hidden, 'Settings opens');
          return true;
        })())""")
        self.assertEqual(result, "true")

    def test_symbolic_icons_are_inline_and_controls_accessible(self):
        result = self.js("""JSON.stringify((() => {
          const check = (condition, message) => { if (!condition) throw Error(message); };
          const icons = [...document.querySelectorAll('[data-icon]')];
          check(icons.length > 20, 'Icons present');
          for (const node of icons) {
            check(window.YARU_SYMBOLIC[node.dataset.icon], 'Missing icon ' + node.dataset.icon);
            check(node.style.getPropertyValue('--icon').includes('data:image/svg+xml'), 'Inline icon ' + node.dataset.icon);
          }
          for (const theme of ['light','dark']) {
            setTheme(theme);
            for (const input of document.querySelectorAll('.switch')) {
              check(getComputedStyle(input).appearance==='none', 'Stock checkbox');
              check(input.getAttribute('role')==='switch' && (input.getAttribute('aria-label') || input.labels.length), 'Switch accessibility');
            }
            document.querySelector('#preview-preset').click();
            check(dialog.dataset.theme===theme, 'Dialog theme');
            const bg = getComputedStyle(dialog).backgroundColor;
            check(bg===(theme==='dark'?'rgb(56, 56, 56)':'rgb(250, 250, 250)'), 'Dialog background ' + bg);
            check(getComputedStyle(document.querySelector('#dialog-apply')).backgroundColor!==getComputedStyle(document.querySelector('#dialog-cancel')).backgroundColor, 'Suggested button');
            dialog.close('cancel');
          }
          return true;
        })())""")
        self.assertEqual(result, "true")


class LockscreenDemoTests(WebKitDemoCase):
    demo_path = "demo/login-view.html"

    def setUp(self):
        self.window.set_default_size(1100, 650)
        type(self).loaded = False
        uri = (Path(__file__).resolve().parents[1] / self.demo_path).as_uri()
        token = str(time.monotonic_ns())
        self.web.load_uri(f"{uri}?test={token}")
        self.wait_for(lambda: type(self).loaded)
        self.wait_for(lambda: self.js(f"String(location.search === '?test={token}' && document.readyState === 'complete' && typeof setScene === 'function')") == "true")

    def test_scene_transitions_and_focus(self):
        self.assertEqual(self.js("world.dataset.state"), "locked")
        self.js("document.querySelector('#continue').click(); 'continue'")
        self.assertEqual(self.js("world.dataset.state"), "identity")
        self.assertEqual(self.js("document.activeElement.id"), "unlock")
        self.js("document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true})); 'back'")
        self.assertEqual(self.js("world.dataset.state"), "locked")
        self.js("document.querySelector('#continue').click(); document.querySelector('#unlock').click(); 'unlock'")
        self.assertEqual(self.js("world.dataset.state"), "desktop")
        self.assertEqual(self.js("document.activeElement.id"), "relock")
        self.js("document.querySelector('#relock').click(); 'relock'")
        self.assertEqual(self.js("world.dataset.state"), "locked")
        self.assertEqual(self.js("document.activeElement.id"), "continue")
        self.assertEqual(self.js("String(document.querySelector('#desktop').hidden)"), "true")

    def test_modal_escape_priority_and_keyboard_guards(self):
        self.js("document.body.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true})); 'advance'")
        self.assertEqual(self.js("world.dataset.state"), "identity")
        self.js("document.querySelector('#customize').click(); 'open'")
        self.assertEqual(self.js("String(settings.open)"), "true")
        self.assertEqual(self.js("document.activeElement.id"), "close-settings")
        self.js("document.querySelector('#profile-name').focus(); document.querySelector('#profile-name').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); 'edit'")
        self.assertEqual(self.js("world.dataset.state"), "identity")
        self.js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',cancelable:true})); 'close'")
        self.wait_for(lambda: self.js("document.activeElement.id") == "customize")
        self.assertEqual(self.js("String(settings.open)"), "false")
        self.assertEqual(self.js("world.dataset.state"), "identity")
        self.js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'})); 'back'")
        self.assertEqual(self.js("world.dataset.state"), "locked")
        self.js("document.querySelector('#customize').dispatchEvent(new KeyboardEvent('keydown',{key:' ',bubbles:true})); 'guard'")
        self.assertEqual(self.js("world.dataset.state"), "locked")

    def test_notification_privacy_dismiss_clear_and_reset(self):
        self.assertEqual(self.js("String(document.querySelectorAll('.notification').length)"), "2")
        self.assertNotIn("afternoon", self.js("document.querySelector('#notifications').outerHTML"))
        self.assertNotIn("Jamie", self.js("document.querySelector('#notifications').outerHTML"))
        self.js("document.querySelector('#show-previews').click(); 'show'")
        self.assertIn("Jamie", self.js("document.querySelector('#notifications').textContent"))
        self.js("document.querySelector('#show-previews').click(); 'hide'")
        self.assertNotIn("Jamie", self.js("document.querySelector('#notifications').outerHTML"))
        self.js("document.querySelector('.dismiss').click(); 'dismiss'")
        self.assertEqual(self.js("String(document.querySelectorAll('.notification').length)"), "1")
        self.assertEqual(self.js("document.activeElement.getAttribute('aria-label')"), "Dismiss Messages notification")
        self.js("document.querySelector('#clear-notifications').click(); 'clear'")
        self.assertEqual(self.js("String(document.querySelector('#empty').hidden)"), "false")
        self.assertEqual(self.js("document.activeElement.id"), "continue")
        self.js("document.querySelector('#reset-notifications').click(); 'reset'")
        self.assertEqual(self.js("String(document.querySelectorAll('.notification').length)"), "2")
        self.assertEqual(self.js("String(document.querySelector('#empty').hidden)"), "true")

    def test_clock_identity_and_customization(self):
        result = json.loads(self.js("""JSON.stringify((() => {
          const morning = new Date(2026, 10, 2, 0, 7);
          const afternoon = new Date(2026, 10, 2, 13, 9);
          return [clockParts(morning,false),clockParts(morning,true),clockParts(afternoon,true)];
        })())"""))
        self.assertEqual(result, [{"digits": "00:07", "period": ""},
                                  {"digits": "12:07", "period": "AM"},
                                  {"digits": "01:09", "period": "PM"}])
        self.js("document.querySelector('#profile-name').value=' <b>Alex</b> '; document.querySelector('#profile-name').dispatchEvent(new Event('input')); 'name'")
        self.assertEqual(self.js("document.querySelector('.name').textContent"), "<b>Alex</b>")
        self.assertEqual(self.js("String(document.querySelectorAll('.name b').length)"), "0")
        self.js("document.querySelector('#profile-name').value='   '; document.querySelector('#profile-name').dispatchEvent(new Event('input')); 'empty'")
        self.assertEqual(self.js("document.querySelector('.name').textContent"), "Alex Morgan")
        self.js("document.querySelector('input[name=weight][value=light]').click(); document.querySelector('input[name=format][value=\"12\"]').click(); 'clock'")
        self.assertEqual(self.js("document.querySelector('#clock-block').dataset.weight"), "light")
        self.assertIn(self.js("document.querySelector('#period').textContent"), ("AM", "PM"))
        for appearance in ("light", "dark", "auto"):
            self.js(f"document.querySelector('#appearance').value={json.dumps(appearance)}; document.querySelector('#appearance').dispatchEvent(new Event('change')); 'appearance'")
            expected = appearance if appearance != "auto" else self.js("colorScheme.matches ? 'dark' : 'light'")
            self.assertEqual(self.js("world.dataset.appearance"), expected)
        self.js("document.querySelector('input[name=avatar][value=sea]').click(); 'avatar'")
        self.wait_for(lambda: self.js("String([...document.querySelectorAll('img.avatar')].every(image=>image.complete && image.naturalWidth>0 && image.src.endsWith('avatar-sea.jpg'))) ") == "true")

    def account_labels(self):
        return json.loads(self.js("JSON.stringify([...document.querySelectorAll('.account-button')].map(button=>button.getAttribute('aria-label')))"))

    def test_switch_user_login_list_and_logout(self):
        self.js("document.querySelector('#continue').click(); document.querySelector('#switch-user').click(); 'switch'")
        self.assertEqual(self.js("world.dataset.state"), "accounts")
        self.assertEqual(self.js("document.activeElement.dataset.account"), "alex")
        self.assertEqual(self.account_labels(), ["Alex Morgan, Session locked", "Robin Chen", "Sam Patel"])
        self.assertEqual(self.js("String(document.querySelectorAll('#accounts .notification').length)"), "0")
        self.assertEqual(self.js("String(document.querySelectorAll('img.avatar').length > 0 && document.querySelectorAll('#account-list .avatar.initials').length === 2)"), "true")

        self.js("document.querySelector('[data-account=robin]').click(); 'robin'")
        self.assertEqual(self.js("document.querySelector('#identity-name').textContent"), "Robin Chen")
        self.assertEqual(self.js("document.querySelector('#unlock-label').textContent"), "Simulate log in")
        self.assertEqual(self.js("String(document.querySelector('#switch-user').hidden)"), "true")
        self.js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'})); 'back'")
        self.assertEqual(self.js("world.dataset.state"), "accounts")
        self.assertEqual(self.js("document.activeElement.dataset.account"), "robin")

        self.js("document.querySelector('[data-account=robin]').click(); document.querySelector('#unlock').click(); 'login'")
        self.assertEqual(self.js("document.querySelector('#desktop-name').textContent"), "Robin Chen")
        self.js("document.querySelector('#relock').click(); 'relock'")
        self.assertEqual(self.js("document.querySelector('#locked-name').textContent"), "Robin Chen")
        self.assertEqual(self.js("String(document.querySelectorAll('.notification').length)"), "1")

        self.js("document.querySelector('#continue').click(); document.querySelector('#switch-user').click(); 'switch'")
        self.assertEqual(self.account_labels(), ["Alex Morgan, Signed in", "Robin Chen, Session locked", "Sam Patel"])
        self.js("document.querySelector('#accounts-back').click(); document.querySelector('#continue').click(); document.querySelector('#unlock').click(); document.querySelector('#logout').click(); 'logout'")
        self.assertEqual(self.js("world.dataset.state"), "accounts")
        self.assertEqual(self.account_labels(), ["Alex Morgan, Signed in", "Robin Chen", "Sam Patel"])
        self.assertEqual(self.js("String(document.querySelector('#accounts-back').hidden)"), "true")
        self.js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'})); 'no lock screen'")
        self.assertEqual(self.js("world.dataset.state"), "accounts")

        self.js("document.querySelector('[data-account=alex]').click(); 'alex'")
        self.assertEqual(self.js("document.querySelector('#identity-status').textContent"), "Signed in")
        self.assertEqual(self.js("document.querySelector('#unlock-label').textContent"), "Simulate unlock")
        self.js("document.querySelector('#back').click(); document.querySelector('[data-account=sam]').click(); document.querySelector('#unlock').click(); document.querySelector('#relock').click(); 'sam'")
        self.assertEqual(self.js("document.querySelector('#locked-name').textContent"), "Sam Patel")
        self.assertEqual(self.js("String(document.querySelector('#empty').hidden)"), "false")

    def test_local_assets_fonts_and_wallpaper_choices(self):
        self.wait_for(lambda: self.js("String([...document.images].every(image=>image.complete && image.naturalWidth>0))") == "true")
        self.wait_for(lambda: self.js("document.fonts.status") == "loaded")
        self.assertEqual(self.js("String(document.fonts.check('16px Inter'))"), "true")
        self.assertEqual(self.js("String([...document.querySelectorAll('[src],[href]')].every(element => !/^https?:/.test(element.src || element.href)))"), "true")
        self.assertEqual(self.js("String(document.querySelectorAll('input[type=password]').length)"), "0")
        for wallpaper in ("forest", "coast", "alpine"):
            self.js(f"document.querySelector('input[name=wallpaper][value={wallpaper}]').click(); 'wallpaper'")
            self.wait_for(lambda: self.js("String(document.querySelector('#wallpaper').complete && document.querySelector('#wallpaper').naturalWidth>0)") == "true")
            self.assertTrue(self.js("document.querySelector('#wallpaper').src").endswith(f"/{wallpaper}.jpg"))

    def test_responsive_geometry_and_settings_scrolling(self):
        self.js("document.querySelector('#profile-name').value='W'.repeat(40); document.querySelector('#profile-name').dispatchEvent(new Event('input')); 'long name'")
        for width, height in ((320, 650), (390, 740), (1366, 760), (1100, 480)):
            self.resize_viewport(width, height)
            for hour_format in ("12", "24"):
                self.js(f"document.querySelector('input[name=format][value=\"{hour_format}\"]').click(); 'format'")
                result = self.js("""JSON.stringify((() => {
                  const bounds = selector => document.querySelector(selector).getBoundingClientRect();
                  const clock = bounds('.clock-block');
                  const notifications = bounds('.notification-area');
                  const profile = bounds('#continue');
                  return {
                    overflow: document.documentElement.scrollWidth > innerWidth,
                    overlap: clock.bottom > notifications.top || notifications.bottom > profile.top,
                    clockFits: clock.left >= 0 && clock.right <= innerWidth,
                    profileFits: profile.left >= 0 && profile.right <= innerWidth
                  };
                })())""")
                self.assertEqual(json.loads(result), {"overflow": False, "overlap": False, "clockFits": True, "profileFits": True}, (width, height, hour_format))
            self.js("document.querySelector('#customize').click(); 'open'")
            self.assertEqual(self.js("String(settings.scrollWidth <= settings.clientWidth && settings.getBoundingClientRect().bottom <= innerHeight && settings.getBoundingClientRect().top >= 0)"), "true")
            self.js("document.querySelector('#reset-notifications').scrollIntoView(); 'scroll'")
            self.assertEqual(self.js("String(document.querySelector('#reset-notifications').getBoundingClientRect().bottom <= settings.getBoundingClientRect().bottom)"), "true")
            self.js("settings.close(); 'close'")
            self.wait_for(lambda: self.js("document.activeElement.id") == "customize")

    def test_reduced_motion_and_opaque_fallback(self):
        self.js("""for (const rule of document.styleSheets[0].cssRules) {
          if (rule.conditionText === '(prefers-reduced-motion: reduce)') rule.media.mediaText = 'all';
        }; 'reduce'""")
        self.assertEqual(self.js("getComputedStyle(document.querySelector('.scene')).animationName"), "none")
        self.js("""const rules = document.styleSheets[0].cssRules;
          for (let index=rules.length-1; index>=0; index--) {
            if (rules[index].conditionText?.includes('backdrop-filter')) document.styleSheets[0].deleteRule(index);
          }; 'fallback'""")
        self.assertEqual(self.js("getComputedStyle(document.querySelector('.notification')).backgroundColor"), "rgba(25, 30, 28, 0.94)")


class IntegratedDemoTests(WebKitDemoCase):
    demo_path = "demo/index.html"

    def test_actual_login_button_opens_desktop(self):
        # WebKit isolates file iframe DOMs; run the real controls inside the child.
        manager = self.web.get_user_content_manager()
        script = WebKit.UserScript.new("""
          if (location.pathname.endsWith('/login-view.html')) {
            document.querySelector('[data-account=robin]').click();
            document.querySelector('#unlock').click();
          }
        """, WebKit.UserContentInjectedFrames.ALL_FRAMES,
            WebKit.UserScriptInjectionTime.END, None, None)
        manager.add_script(script)
        self.addCleanup(manager.remove_all_scripts)
        type(self).loaded = False
        self.web.reload()
        self.wait_for(lambda: type(self).loaded)
        self.wait_for(lambda: self.js("String(!document.querySelector('#desktop-view').hidden)") == "true")
        self.assertEqual(self.js("String(document.querySelector('#login-view').inert)"), "true")
        self.assertEqual(self.js("String(document.querySelector('#desktop-view').inert)"), "false")

    def test_unexpected_origin_source_and_message_do_not_log_in(self):
        self.js("showLogin('login'); 'reset'")
        result = self.js("""JSON.stringify((() => {
          const login = document.querySelector('#login-view');
          const desktop = document.querySelector('#desktop-view');
          for (const [origin, source, data] of [
            ['https://unexpected.example', login.contentWindow, {type:'login-success', account:'robin'}],
            [location.origin, window, {type:'login-success', account:'robin'}],
            [location.origin, desktop.contentWindow, {type:'login-success', account:'robin'}],
            [location.origin, login.contentWindow, null],
            [location.origin, login.contentWindow, 'login-success'],
            [location.origin, login.contentWindow, {type:'unknown'}]
          ]) {
            window.dispatchEvent(new MessageEvent('message', {origin, source, data}));
            if (!desktop.hidden || login.hidden) return false;
          }
          return true;
        })())""")
        self.assertEqual(result, "true")

    def test_http_actual_login_lock_unlock_logout_and_null_origin_rejection(self):
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *_args):
                pass

        directory = Path(__file__).resolve().parents[1] / "demo"
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(directory)))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            type(self).loaded = False
            self.web.load_uri(f"http://127.0.0.1:{server.server_port}/index.html")
            self.wait_for(lambda: type(self).loaded)
            self.wait_for(lambda: self.js(
                "String(document.querySelector('#login-view').contentDocument?.readyState === 'complete' && "
                "!!document.querySelector('#login-view').contentDocument?.querySelector('#unlock'))"
            ) == "true")
            self.js("""window.dispatchEvent(new MessageEvent('message', {
              origin:'null', source:document.querySelector('#login-view').contentWindow,
              data:{type:'login-success', account:'robin'}
            })); 'untrusted'""")
            self.assertEqual(self.js("String(document.querySelector('#desktop-view').hidden)"), "true")
            self.js("""{ const child = document.querySelector('#login-view').contentDocument;
              child.querySelector('[data-account=robin]').click(); child.querySelector('#unlock').click(); } 'login'""")
            self.wait_for(lambda: self.js("String(!document.querySelector('#desktop-view').hidden)") == "true")
            self.assertEqual(self.js("""String((() => {
              const child = document.querySelector('#desktop-view').contentDocument;
              const win = child.querySelector('#win-glass');
              const bounds = win.getBoundingClientRect();
              return !win.classList.contains('maximized') && bounds.width === 540 && bounds.left > 0;
            })())"""), "true")
            self.js("""{ const child = document.querySelector('#desktop-view').contentDocument;
              child.querySelector('#status-button').click(); child.querySelector('#qs-lock').click(); } 'lock'""")
            self.wait_for(lambda: self.js("String(!document.querySelector('#login-view').hidden)") == "true")
            self.assertIn("mode=locked&account=robin", self.js("document.querySelector('#login-view').src"))
            self.wait_for(lambda: self.js(
                "String(document.querySelector('#login-view').contentDocument?.readyState === 'complete' && "
                "document.querySelector('#login-view').contentWindow.location.search.includes('mode=locked'))"
            ) == "true")
            self.js("""{ const child = document.querySelector('#login-view').contentDocument;
              child.querySelector('#continue').click(); child.querySelector('#unlock').click(); } 'unlock'""")
            self.wait_for(lambda: self.js("String(!document.querySelector('#desktop-view').hidden)") == "true")
            self.js("""{ const child = document.querySelector('#desktop-view').contentDocument;
              child.querySelector('[data-session=logout]').click();
              child.querySelector('#session-confirm').click(); } 'logout'""")
            self.wait_for(lambda: self.js("String(!document.querySelector('#login-view').hidden)") == "true")
            self.assertIn("mode=login&account=robin", self.js("document.querySelector('#login-view').src"))
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            type(self).loaded = False
            self.web.load_uri((directory / "index.html").as_uri())
            self.wait_for(lambda: type(self).loaded)

    def test_login_lock_and_logout_route_between_views(self):
        # Each test starts at account selection, including after a real iframe login.
        self.js("showLogin('login'); 'reset'")
        self.assertEqual(self.js("String(document.querySelector('#login-view').hidden)"), "false")
        self.assertEqual(self.js("String(document.querySelector('#desktop-view').hidden)"), "true")
        self.assertIn("mode=login", self.js("document.querySelector('#login-view').src"))

        self.js("""window.dispatchEvent(new MessageEvent('message', {
          source: document.querySelector('#login-view').contentWindow,
          origin: location.origin,
          data: {type: 'login-success', account: 'robin'}
        })); 'login'""")
        self.wait_for(lambda: self.js("String(!document.querySelector('#desktop-view').hidden)") == "true")
        self.assertEqual(self.js("String(document.querySelector('#login-view').hidden)"), "true")

        self.js("""window.dispatchEvent(new MessageEvent('message', {
          source: document.querySelector('#desktop-view').contentWindow,
          origin: location.origin,
          data: {type: 'lock'}
        })); 'lock'""")
        self.assertEqual(self.js("String(document.querySelector('#login-view').hidden)"), "false")
        self.assertIn("mode=locked&account=robin", self.js("document.querySelector('#login-view').src"))

        self.js("""window.dispatchEvent(new MessageEvent('message', {
          source: document.querySelector('#login-view').contentWindow,
          origin: location.origin,
          data: {type: 'login-success', account: 'robin'}
        })); 'unlock'""")
        self.wait_for(lambda: self.js("String(!document.querySelector('#desktop-view').hidden)") == "true")
        self.js("""window.dispatchEvent(new MessageEvent('message', {
          source: document.querySelector('#desktop-view').contentWindow,
          origin: location.origin,
          data: {type: 'logout'}
        })); 'logout'""")
        self.assertEqual(self.js("String(document.querySelector('#login-view').hidden)"), "false")
        self.assertIn("mode=login&account=robin", self.js("document.querySelector('#login-view').src"))

        self.js("""window.dispatchEvent(new MessageEvent('message', {
          source: window, data: {type: 'logout'}
        })); 'ignore untrusted source'""")
        self.assertEqual(self.js("String(document.querySelector('#login-view').hidden)"), "false")


class LoginViewTests(WebKitDemoCase):
    demo_path = "demo/login-view.html"

    def setUp(self):
        self.window.set_default_size(1100, 650)
        type(self).loaded = False
        uri = (Path(__file__).resolve().parents[1] / self.demo_path).as_uri()
        token = str(time.monotonic_ns())
        self.web.load_uri(f"{uri}?mode=login&test={token}")
        self.wait_for(lambda: type(self).loaded)
        self.wait_for(lambda: self.js(f"String(location.search === '?mode=login&test={token}' && document.readyState === 'complete' && typeof setScene === 'function')") == "true")

    def test_login_mode_starts_with_account_selection(self):
        self.assertEqual(self.js("world.dataset.state"), "accounts")
        self.assertEqual(self.js("String(document.querySelector('#locked').hidden)"), "true")
        self.assertEqual(self.js("String(document.querySelector('#accounts-back').hidden)"), "true")
        self.assertEqual(self.js("document.activeElement.dataset.account"), "alex")
        self.js("document.querySelector('[data-account=robin]').click(); 'select'")
        self.assertEqual(self.js("document.querySelector('#unlock-label').textContent"), "Simulate log in")
        self.js("document.querySelector('#unlock').click(); 'sign in'")
        self.assertEqual(self.js("world.dataset.state"), "desktop")
        self.assertEqual(self.js("document.querySelector('#desktop-name').textContent"), "Robin Chen")
