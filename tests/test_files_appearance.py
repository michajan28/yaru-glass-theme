import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/yaru_glass"))
sys.path.insert(0, str(ROOT / "scripts"))
import files_appearance as files


def setUpModule():
    state = tempfile.TemporaryDirectory(prefix="yaru-files-state-")
    unittest.addModuleCleanup(state.cleanup)
    environment = patch.dict(os.environ, {"XDG_STATE_HOME": state.name})
    environment.start()
    unittest.addModuleCleanup(environment.stop)


class FilesSettingsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.paths = (root / "light.css", root / "dark.css")
        for path in self.paths:
            path.write_text("/* unrelated GTK rules */\n")
        self.settings = root / "files.json"
        for item in (
            patch.object(files, "CONFIG_DIR", root),
            patch.object(files, "CSS_PATHS", self.paths),
            patch.object(files, "SETTINGS_FILE", self.settings),
            patch.object(files, "load_settings", return_value={"glass_mode": "frost", "transparency": 15,
                                                             "readability_boost": False}),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_opt_in_roundtrip_disable_and_preserved_other_css(self):
        self.assertEqual(files.load(), {"enabled": False, "transparency": 25})
        for enabled in (True, False):
            files.save({"enabled": enabled, "transparency": 35})
            self.assertEqual(files.load(), {"enabled": enabled, "transparency": 35})
            for path in self.paths:
                self.assertTrue(path.read_text().startswith("/* unrelated GTK rules */"))
                self.assertEqual(files.START in path.read_text(), enabled)

    def test_mode_refresh_preserves_preferences_and_is_idempotent(self):
        files.save({"enabled": True, "transparency": 50})
        before = self.settings.read_bytes()
        original = self.paths[0].read_text()
        files.refresh("crystal")
        self.assertNotEqual(self.paths[0].read_text(), original)
        self.assertEqual(self.settings.read_bytes(), before)
        with patch.object(files, "atomic_write") as write:
            files.refresh("crystal")
            write.assert_not_called()

    def test_save_failure_restores_both_stylesheets_and_setting(self):
        files.save({"enabled": True, "transparency": 25})
        previous = [p.read_bytes() for p in (*self.paths, self.settings)]
        write = files.atomic_write

        def fail_setting(path, text):
            if path == self.settings:
                raise OSError("read only")
            write(path, text)

        with patch.object(files, "atomic_write", side_effect=fail_setting):
            with self.assertRaisesRegex(RuntimeError, "Previous CSS restored"):
                files.save({"enabled": False, "transparency": 0})
        self.assertEqual([p.read_bytes() for p in (*self.paths, self.settings)], previous)

    def test_invalid_configuration_and_broken_block_are_explicit(self):
        self.settings.write_text('{"enabled": "yes", "transparency": 25}')
        with self.assertRaises(ValueError):
            files.load()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            files.replace_css(files.START, {"enabled": False, "transparency": 0}, "frost")

    def test_refresh_failure_rolls_back_both_variants(self):
        files.save({"enabled": True, "transparency": 50})
        previous = [p.read_bytes() for p in self.paths]
        write = files.atomic_write
        failed = False

        def fail_once(path, text):
            nonlocal failed
            if path == self.paths[1] and not failed:
                failed = True
                raise OSError("failed second variant")
            write(path, text)

        with patch.object(files, "atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(RuntimeError, "Previous CSS restored"):
                files.refresh("crystal")
        self.assertEqual([p.read_bytes() for p in self.paths], previous)

    def test_full_gtk_build_preserves_enabled_preference(self):
        import build
        files.save({"enabled": True, "transparency": 50})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "theme"
            build.build_gtk(build.VARIANTS[0], output, "crystal")
            text = (output / "gtk-4.0/libadwaita.css").read_text()
            self.assertEqual(text.count(files.START), 1)
            self.assertIn("alpha(@window_bg_color, 0.700000)", text)
            self.assertIn("windowcontrols", text)

    def test_selectors_are_scoped_and_no_whole_window_opacity(self):
        css = files.css({"enabled": True, "transparency": 50}, "crystal")
        selectors = [line.strip() for line in css.splitlines()
                     if line.rstrip().endswith((",", "{"))]
        self.assertTrue(selectors)
        self.assertTrue(all(selector.startswith("window.nautilus-window") for selector in selectors))
        self.assertNotIn("opacity:", css)
        self.assertIn("background-color: @view_bg_color;", css)


try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gdk, GLib, Gtk
    UI_AVAILABLE = Gtk.init_check()
except (ImportError, ValueError):
    UI_AVAILABLE = False


@unittest.skipUnless(UI_AVAILABLE, "GTK4/libadwaita and a display are required")
class FilesRenderTests(unittest.TestCase):
    def test_real_split_view_rendering_is_scoped_and_content_stays_solid(self):
        Adw.init()
        manager = Adw.StyleManager.get_default()
        original_scheme = manager.get_color_scheme()
        provider = Gtk.CssProvider()
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        errors = []
        provider.connect("parsing-error", lambda p, section, error: errors.append(str(error)))
        window = Adw.Window(default_width=900, default_height=520)
        split = Adw.OverlaySplitView(min_sidebar_width=240, max_sidebar_width=240)
        sidebar = Adw.ToolbarView()
        sidebar.add_top_bar(Adw.HeaderBar())
        sidebar_list = Gtk.ListBox(css_classes=["navigation-sidebar"])
        sidebar_label = Gtk.Label(label="Home", xalign=0)
        sidebar_list.append(sidebar_label)
        sidebar.set_content(sidebar_list)
        content = Adw.ToolbarView()
        content.add_top_bar(Adw.HeaderBar())
        content.set_content(Gtk.Box(css_classes=["view"], vexpand=True))
        split.set_sidebar(sidebar)
        split.set_content(content)
        window.set_content(split)
        paintable = Gtk.WidgetPaintable.new(window)
        window.present()
        context = GLib.MainContext.default()

        def alpha_at(x, y):
            for _ in range(12):
                while context.pending():
                    context.iteration(False)
                time.sleep(.025)
            snapshot = Gtk.Snapshot.new()
            paintable.snapshot(snapshot, window.get_width(), window.get_height())
            texture = window.get_renderer().render_texture(snapshot.to_node(), None)
            image = Gdk.pixbuf_get_from_texture(texture)
            offset = y * image.get_rowstride() + x * image.get_n_channels()
            pixel = image.get_pixels()[offset:offset + 4]
            color = sidebar_label.get_style_context().get_color()

            def luminance(rgb):
                return sum(weight * (v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4)
                           for v, weight in zip(rgb, (.2126, .7152, .0722)))

            foreground = luminance((color.red, color.green, color.blue))
            alpha = pixel[3] / 255
            for backdrop in ((0, 0, 0), (1, 1, 1), (.2, .6, .9), (.9, .3, .6)):
                background = luminance(tuple(pixel[i] / 255 * alpha + backdrop[i] * (1 - alpha)
                                             for i in range(3)))
                a, b = sorted((foreground, background))
                self.assertGreaterEqual((b + .05) / (a + .05), 4.5)
            self.assertEqual(sidebar_label.get_opacity(), 1)
            return pixel[3]

        try:
            for scheme in (Adw.ColorScheme.FORCE_LIGHT, Adw.ColorScheme.FORCE_DARK):
                manager.set_color_scheme(scheme)
                for mode, boost in ((mode, boost) for mode in ("frost", "crystal") for boost in (False, True)):
                    for level in (0, 25, 50):
                        provider.load_from_data(files.css({"enabled": True, "transparency": level}, mode, boost).encode())
                        window.add_css_class("nautilus-window")
                        expected = 1 - .30 * level / 50 * (1 if mode == "crystal" else .7)
                        if boost:
                            expected += (1 - expected) / 2
                        self.assertAlmostEqual(alpha_at(30, 200) / 255, expected, delta=.015)
                        self.assertAlmostEqual(alpha_at(460, 20) / 255, expected, delta=.015)
                        self.assertEqual(alpha_at(460, 200), 255)
                        self.assertEqual(window.get_opacity(), 1)
                    window.remove_css_class("nautilus-window")
                    self.assertEqual(alpha_at(30, 200), 255, "Other app sidebar must remain solid")
                    self.assertEqual(alpha_at(460, 20), 255, "Other app headerbar must remain solid")
            self.assertEqual(errors, [])
        finally:
            window.destroy()
            manager.set_color_scheme(original_scheme)
            Gtk.StyleContext.remove_provider_for_display(display, provider)


if __name__ == "__main__":
    unittest.main()
