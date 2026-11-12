import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import Meta from 'gi://Meta';
import St from 'gi://St';
import System from 'system';

import {DemoLayout, supportedDialog} from '../src/gnome-shell-extension/layout.js';

const Plugin = GObject.registerClass(class LockScreenTestPlugin extends Meta.Plugin {});
const compositor = Meta.create_context('Yaru Glass lock-screen layout test');
compositor.set_plugin_gtype(Plugin.$gtype);
compositor.configure(['lockscreen-layout-test', '--headless', '--wayland', '--no-x11']);
compositor.setup();

function verifyLayout() {
    const stage = compositor.get_backend().get_stage();
    globalThis.global = {stage};
    const context = St.ThemeContext.get_for_stage(stage);
    const resource = Gio.Resource.load('/usr/share/gnome-shell/gnome-shell-theme.gresource');
    resource._register();
    const themeFiles = Gio.resources_enumerate_children('/org/gnome/shell/theme',
        Gio.ResourceLookupFlags.NONE);
    const themeName = themeFiles.includes('gnome-shell-dark.css')
        ? 'gnome-shell-dark.css' : 'gnome-shell.css';
    const theme = new St.Theme({application_stylesheet: Gio.File.new_for_uri(
        `resource:///org/gnome/shell/theme/${themeName}`)});
    theme.load_stylesheet(Gio.File.new_for_path(ARGV[0]));
    context.set_theme(theme);
    stage.show();

    function check(condition, message) {
        if (!condition)
            throw new Error(message);
    }

    check(!supportedDialog(null), 'Absent native dialog was accepted');
    check(!supportedDialog({}), 'Unknown native dialog was accepted');

    let count = 0;
    for (const scale of [1, 2]) {
        context.scale_factor = scale;
        const viewports = [[320, 480], [1280, 800], [1920, 1080]];
        for (const [width, height, time] of viewports.flatMap(([width, height]) =>
            ['23:59', '11:59 PM'].map(time => [width, height, time]))) {
            for (const notificationHeight of [0, 80, 1200]) {
                let nativeAllocations = 0;
                const parent = new St.Widget({visible: true, style_class: 'yaru-glass-lock'});
                const clock = new St.BoxLayout({vertical: true, visible: true,
                    style_class: 'unlock-dialog-clock'});
                clock._time = new St.Label({text: time, style_class: 'unlock-dialog-clock-time'});
                clock._date = new St.Label({text: 'Monday November 9', style_class: 'unlock-dialog-clock-date'});
                clock._wallClock = {};
                clock.add_child(clock._date);
                clock.add_child(clock._time);
                clock.add_child(new St.Label({text: 'Click or press a key to unlock',
                    style_class: 'unlock-dialog-clock-hint'}));
                const stack = new St.Widget({name: 'stack', visible: true,
                    layout_manager: new Clutter.BinLayout()});
                stack.add_child(clock);
                const content = new St.BoxLayout({vertical: true,
                    style_class: 'unlock-dialog-notifications-container'});
                const filler = new St.Widget({height: notificationHeight * scale});
                content.add_child(filler);
                const scroll = new St.ScrollView({child: content, overlay_scrollbars: true,
                    enable_mouse_scrolling: false});
                scroll.set_policy(St.PolicyType.NEVER, St.PolicyType.NEVER);
                const notifications = new St.BoxLayout({name: 'notifications',
                    vertical: true, visible: notificationHeight > 0});
                notifications._scrollView = scroll;
                notifications.add_child(scroll);
                const profile = new St.BoxLayout({name: 'profile', visible: true,
                    style_class: 'yaru-lock-profile'});
                profile.add_child(new St.Icon({icon_name: 'avatar-default-symbolic',
                    style_class: 'user-icon'}));
                profile.add_child(new St.Label({text: 'Yaru Glass Test'}));
                const prompt = new St.Widget({visible: false});
                parent.add_child(stack);
                parent.add_child(notifications);
                parent.add_child(profile);
                const native = {
                    vfunc_get_preferred_width: () => [0, width],
                    vfunc_get_preferred_height: () => [0, height],
                    vfunc_allocate: () => nativeAllocations++,
                };
                const dialog = {
                    _clock: clock, _stack: stack, _promptBox: prompt,
                    _notificationsBox: notifications, _user: {}, _backgroundGroup: {},
                };
                parent.layout_manager = new DemoLayout(dialog, profile, native);
                stage.add_child(parent);
                check(supportedDialog(dialog), 'Compatible native actor hierarchy was rejected');
                notifications._scrollView = null;
                check(!supportedDialog(dialog), 'Missing native notification wrapper was accepted');
                notifications._scrollView = scroll;
                const box = new Clutter.ActorBox({x1: 0, y1: 0, x2: width, y2: height});
                parent.layout_manager.vfunc_allocate(parent, box);
                check(profile.visible, 'Profile is hidden in the clock view');
                for (const actor of [stack, notifications, profile]) {
                    const bounds = actor.get_allocation_box();
                    check(bounds.x1 >= 0 && bounds.x2 <= width + 1,
                        `${actor.name} horizontal allocation ${bounds.x1}:${bounds.x2} at ${width}x${height}, scale ${scale}`);
                    check(bounds.y1 >= 0 && bounds.y2 <= height + 1,
                        `Vertical allocation ${bounds.y1}:${bounds.y2} at ${width}x${height}, scale ${scale}`);
                    if (actor !== notifications || notificationHeight > 0) {
                        check(bounds.get_width() > 0 && bounds.get_height() > 0,
                            `${actor.name} was not allocated`);
                    }
                }
                check(notifications.get_allocation_box().y2 <= profile.get_allocation_box().y1,
                    'Notifications overlap the profile');
                check(clock._time.get_preferred_size()[2] <= stack.get_allocation_box().get_width() + 1,
                    `Clock overflows horizontally at ${width}x${height}, scale ${scale}, ${time}`);
                check(clock.get_preferred_size()[3] <= stack.get_allocation_box().get_height() + 1,
                    `Clock overflows vertically at ${width}x${height}, scale ${scale}, ${time}: ` +
                    `${clock.get_preferred_size()[3]} > ${stack.get_allocation_box().get_height()}`);
                if (notificationHeight > 0) {
                    const adjustment = scroll.vadjustment;
                    const overflow = adjustment.upper - adjustment.lower > adjustment.page_size;
                    check(scroll.vscrollbar_visible === overflow,
                        `Vertical scrollbar visibility does not match actual overflow: ` +
                        `${width}x${height}, scale ${scale}, content ${notificationHeight}; ` +
                        `visible=${scroll.vscrollbar_visible}, lower=${adjustment.lower}, ` +
                        `upper=${adjustment.upper}, page=${adjustment.page_size}`);
                    check(notificationHeight < 1200 || scroll.vscrollbar_visible,
                        'Overflowing notifications have no scrollbar');
                    check(!scroll.hscrollbar_visible, 'Unexpected horizontal scrollbar');
                    check(content.get_allocation_box().get_width() <=
                        notifications.get_allocation_box().get_width() + 1,
                    'Notification content overflows horizontally');
                    if (overflow) {
                        adjustment.value = adjustment.upper - adjustment.page_size;
                        check(adjustment.value > 0, 'Last notifications cannot be reached');
                    }
                    filler.height = 0;
                    parent.layout_manager.vfunc_allocate(parent, box);
                    check(!scroll.vscrollbar_visible, 'Scrollbar remains after content fits');
                    filler.height = notificationHeight * scale;
                    parent.layout_manager.vfunc_allocate(parent, box);
                    check(notificationHeight < 1200 || scroll.vscrollbar_visible,
                        'Scrollbar does not return after content grows');
                }
                const wide = new Clutter.ActorBox({x1: 0, y1: 0, x2: 1920, y2: 1080});
                parent.layout_manager.vfunc_allocate(parent, wide);
                check(clock._time.get_style().includes('font-size: 128px'),
                    'Clock does not grow back when the viewport expands');
                parent.layout_manager.vfunc_allocate(parent, box);
                check(clock._time.get_preferred_size()[2] <= stack.get_allocation_box().get_width() + 1,
                    'Clock does not fit after resizing back to a narrow viewport');
                prompt.visible = true;
                parent.queue_relayout();
                parent.layout_manager.vfunc_allocate(parent, box);
                check(nativeAllocations > 0, 'Authentication view did not delegate to native layout');
                check(!profile.visible, 'Extra profile is visible over native authentication');
                parent.layout_manager.restore();
                check(clock._time.get_style() === null, 'Original clock style was not restored');
                check(scroll.vscrollbar_policy === St.PolicyType.NEVER &&
                    scroll.overlay_scrollbars && !scroll.enable_mouse_scrolling,
                'Original native scrolling settings were not restored');
                parent.destroy();
                prompt.destroy();
                count++;
            }
        }
    }
    print(`${count} native lock-screen layout cases passed; authentication delegates to GNOME`);
}

try {
    verifyLayout();
} finally {
    compositor.get_backend().get_stage().destroy_all_children();
    globalThis.global = null;
    System.gc();
    compositor.destroy();
}
