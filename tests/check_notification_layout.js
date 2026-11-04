const {Clutter, Gio, GObject, Meta, St} = imports.gi;

const Plugin = GObject.registerClass(class NotificationLayoutTestPlugin extends Meta.Plugin {});
const compositor = Meta.create_context('Notification layout regression test');
compositor.set_plugin_gtype(Plugin.$gtype);
compositor.configure(['notification-layout-test', '--headless', '--wayland', '--no-x11']);
compositor.setup();

function check(condition, message) {
    if (!condition)
        throw new Error(message);
}

function verifyStylesheets(paths, solid) {
    check(paths.length > 0, 'Pass generated GNOME Shell stylesheet paths');
    const stage = compositor.get_backend().get_stage();
    const context = St.ThemeContext.get_for_stage(stage);
    for (const path of paths) {
        context.set_theme(new St.Theme({
            application_stylesheet: Gio.File.new_for_path(path),
        }));
        const panel = new St.Widget({name: 'panel'});
        stage.add_child(panel);
        const panelAlpha = panel.get_theme_node().get_background_color().alpha;
        check(solid ? panelAlpha === 255 : panelAlpha > 0 && panelAlpha < 255,
            `${path}: panel tint is overridden by the system theme`);
        const panelButton = new St.Widget({style_class: 'panel-button'});
        const panelIcon = new St.Widget({style_class: 'system-status-icon'});
        panel.add_child(panelButton);
        panelButton.add_child(panelIcon);
        check(panelIcon.get_theme_node().get_foreground_color().to_string() ===
            panelButton.get_theme_node().get_foreground_color().to_string(),
            `${path}: panel icon does not inherit the readable foreground`);
        panel.add_style_pseudo_class('overview');
        check(panel.get_theme_node().get_background_color().alpha === 0,
            `${path}: overview panel should be transparent`);
        check(panelIcon.get_theme_node().get_foreground_color().to_string() ===
            panelButton.get_theme_node().get_foreground_color().to_string(),
            `${path}: overview panel icon does not inherit its foreground`);
        panel.destroy();
        if (solid) {
            for (const style_class of ['popup-menu-content', 'popup-menu-content datemenu-popover',
                'candidate-popup-content', 'quick-settings', 'notification-banner',
                'switcher-list', 'workspace-switcher', 'osd-window', 'modal-dialog', 'end-session-dialog']) {
                const actor = new St.Widget({style_class});
                stage.add_child(actor);
                check(actor.get_theme_node().get_background_color().alpha === 255,
                    `${path}: ${style_class} is not opaque in Solid mode`);
                actor.destroy();
            }
            const container = new St.Widget({name: 'dashtodockContainer', style_class: 'bottom shrink fixed'});
            const dash = new St.Widget({name: 'dash'});
            const background = new St.Widget({style_class: 'dash-background'});
            stage.add_child(container);
            container.add_child(dash);
            dash.add_child(background);
            check(background.get_theme_node().get_background_color().alpha === 255, 'Solid dock is translucent');
            container.destroy();
        }
        for (const direction of [Clutter.TextDirection.LTR, Clutter.TextDirection.RTL]) {
            for (const state of ['', 'hover', 'focus', 'active']) {
                const parent = new St.Widget({
                    layout_manager: new Clutter.BinLayout(),
                    x_expand: true,
                    x_align: Clutter.ActorAlign.CENTER,
                });
                stage.add_child(parent);
                const banner = new St.Button({
                    style_class: 'message notification-banner',
                    x_expand: true,
                    y_expand: false,
                    text_direction: direction,
                });
                parent.add_child(banner);
                if (state)
                    banner.add_style_pseudo_class(state);
                const header = new St.BoxLayout({style_class: 'message-header'});
                header.add_child(new St.Label({text: 'Zasilanie'}));
                banner.set_child(header);
                const node = banner.get_theme_node();
                const [gradient] = node.get_background_gradient();
                check(gradient === St.GradientType.NONE,
                    `${path}, ${state}: notification gradient turns its shadow into a square halo`);
                const shadow = node.get_box_shadow();
                if (state === 'focus') {
                    check(shadow !== null && shadow.inset && shadow.spread === 2,
                        `${path}: notification keyboard focus ring is missing`);
                } else {
                    check(shadow !== null && !shadow.inset && shadow.blur <= 3 &&
                        shadow.spread === 0 && shadow.xoffset === 0 && shadow.yoffset === 1,
                        `${path}, ${state}: notification shadow exceeds the compact shadow budget`);
                    for (const side of [St.Side.LEFT, St.Side.RIGHT, St.Side.TOP, St.Side.BOTTOM])
                        check(shadow.blur * 1.5 + Math.abs(shadow.yoffset) <= node.get_margin(side),
                            `${path}, ${state}: notification shadow extends beyond its margin`);
                }
                const expectedWidth = node.get_width();
                const [minimum, natural] = parent.get_preferred_width(-1);
                check(expectedWidth > 0 && expectedWidth < 1000, `Invalid CSS width: ${expectedWidth}`);
                check(minimum < 1000 && natural < 1000,
                    `${path}, direction ${direction}, ${state}: overflowing banner ${minimum}/${natural}`);
                check(Math.abs(natural - expectedWidth) < 1, 'Banner no longer has its intended width');
                for (const side of [St.Side.LEFT, St.Side.RIGHT, St.Side.TOP, St.Side.BOTTOM])
                    check(node.get_padding(side) === 0, 'Inherited negative notification padding');
                parent.allocate(new Clutter.ActorBox({x1: 0, y1: 0, x2: natural, y2: 120}));
                check(banner.width < 1000, `Allocated banner is too wide: ${banner.width}`);
                check(header.get_theme_node().get_foreground_color().to_string() ===
                    node.get_foreground_color().to_string(), 'Notification header is dimmed');
                parent.destroy();
            }
        }
        print(`${path}: notification width, allocation, padding, compact shadow and header colour passed (LTR/RTL, all states)`);
    }
}

const solid = ARGV[0] === '--solid';
verifyStylesheets(solid ? ARGV.slice(1) : ARGV, solid);
imports.system.gc();
