import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as UserWidget from 'resource:///org/gnome/shell/ui/userWidget.js';

import {DemoLayout, supportedDialog} from './layout.js';

export default class LockScreenExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._interface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._background = new Gio.Settings({schema_id: 'org.gnome.desktop.background'});
        this._connections = [];
        this._idle = 0;
        this._dialog = null;
        this._connect(this._settings, 'changed', (_settings, key) => {
            if (key !== 'runtime-status')
                this._queueRefresh();
        });
        this._connect(this._interface, 'changed::color-scheme', () => this._queueRefresh());
        this._connect(this._background, 'changed', () => this._queueRefresh());
        this._connect(Main.sessionMode, 'updated', () => this._queueRefresh());
        this._connect(Main.screenShield, 'lock-screen-shown', () => this._queueRefresh());
        this._connect(Main.screenShield._lockDialogGroup, 'child-added',
            () => this._queueRefresh());
        this._connect(Main.layoutManager, 'monitors-changed', () => this._queueRefresh());
        this._refresh();
    }

    _connect(object, signal, callback) {
        this._connections.push([object, object.connect(signal, callback)]);
    }

    _queueRefresh() {
        if (this._idle)
            return;
        this._idle = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._idle = 0;
            this._refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    _status(value) {
        if (this._settings.get_string('runtime-status') !== value)
            this._settings.set_string('runtime-status', value);
    }

    _refresh() {
        this._detach();
        if (!this._settings.settings_schema.has_key('contract-version') ||
            this._settings.get_uint('contract-version') !== 1) {
            console.error('[Yaru Glass lock screen] Unsupported preferences contract; native appearance retained.');
            this._status('unsupported');
            return;
        }
        if (!this._settings.get_boolean('enabled') || Main.sessionMode.isGreeter) {
            this._status('inactive');
            return;
        }
        const dialog = Main.screenShield?._dialog;
        if (!dialog) {
            this._status('ready');
            return;
        }
        if (!supportedDialog(dialog)) {
            console.error('[Yaru Glass lock screen] Unsupported native actor layout; native appearance retained.');
            this._status('unsupported');
            return;
        }
        try {
            this._attach(dialog);
            this._status('active');
        } catch (error) {
            console.error(`[Yaru Glass lock screen] Appearance failed (${error.name}); native appearance restored.`);
            this._detach();
            this._status('error');
        }
    }

    _attach(dialog) {
        this._dialog = dialog;
        this._destroyId = dialog.connect('destroy', () => this._detach(true));
        this._mainBox = dialog._stack.get_parent();
        this._originalLayout = this._mainBox.layout_manager;
        this._dateIndex = dialog._clock.get_children().indexOf(dialog._clock._date);
        this._originalClip = dialog._notificationsBox.clip_to_allocation;
        dialog._notificationsBox.clip_to_allocation = true;
        dialog._clock.set_child_below_sibling(dialog._clock._date, dialog._clock._time);
        dialog.add_style_class_name('yaru-glass-lock');
        const dark = this._settings.get_string('appearance') === 'dark' ||
            (this._settings.get_string('appearance') === 'auto' &&
                this._interface.get_string('color-scheme') === 'prefer-dark');
        dialog.add_style_class_name(dark ? 'yaru-lock-dark' : 'yaru-lock-light');
        if (this._settings.get_string('clock-weight') === 'light')
            dialog.add_style_class_name('yaru-lock-light-clock');
        this._profile = new UserWidget.UserWidget(dialog._user);
        this._profile.add_style_class_name('yaru-lock-profile');
        this._profile.add_child(new St.Icon({
            icon_name: 'go-next-symbolic',
            icon_size: 20,
            y_align: Clutter.ActorAlign.CENTER,
        }));
        this._mainBox.add_child(this._profile);
        this._layout = new DemoLayout(dialog, this._profile, this._originalLayout);
        this._mainBox.layout_manager = this._layout;
        this._clockId = dialog._clock._wallClock.connect('notify::clock',
            () => this._updateClock());
        this._updateClock();
        this._createWallpaper();
        this._mainBox.queue_relayout();
    }

    _updateClock() {
        const format = this._settings.get_string('clock-format') === '12' ? '%I:%M %p' : '%H:%M';
        this._dialog._clock._time.text = GLib.DateTime.new_now_local().format(format);
    }

    _createWallpaper() {
        let uri = this._settings.get_string('wallpaper-uri');
        if (!uri) {
            const dark = this._interface.get_string('color-scheme') === 'prefer-dark';
            uri = this._background.get_string(dark ? 'picture-uri-dark' : 'picture-uri');
        }
        const file = Gio.File.new_for_uri(uri);
        if (!file.get_path() || !file.query_exists(null))
            throw new Error('WallpaperUnavailable');
        this._wallpaper = new Clutter.Actor();
        this._dialog.insert_child_above(this._wallpaper, this._dialog._backgroundGroup);
        for (const monitor of Main.layoutManager.monitors) {
            const image = new St.Widget({
                x: monitor.x,
                y: monitor.y,
                width: monitor.width,
                height: monitor.height,
                style_class: 'yaru-lock-wallpaper',
                style: `background-image: url("${file.get_uri().replace(/"/g, '%22')}");`,
            });
            image.add_child(new St.Widget({
                width: monitor.width,
                height: monitor.height,
                style_class: 'yaru-lock-shade',
            }));
            this._wallpaper.add_child(image);
        }
    }

    _detach(destroying = false) {
        const dialog = this._dialog;
        if (!dialog)
            return;
        this._dialog = null;
        if (!destroying) {
            if (this._destroyId)
                dialog.disconnect(this._destroyId);
            if (this._clockId)
                dialog._clock._wallClock.disconnect(this._clockId);
            if (this._mainBox.layout_manager === this._layout)
                this._mainBox.layout_manager = this._originalLayout;
            this._layout?.restore();
            dialog._clock.set_child_at_index(dialog._clock._date, this._dateIndex);
            dialog._clock._updateClock();
            dialog._notificationsBox.clip_to_allocation = this._originalClip;
            for (const name of ['yaru-glass-lock', 'yaru-lock-dark', 'yaru-lock-light',
                'yaru-lock-light-clock', 'yaru-lock-compact'])
                dialog.remove_style_class_name(name);
            this._wallpaper?.destroy();
            this._profile?.destroy();
        }
        this._wallpaper = null;
        this._profile = null;
        this._layout = null;
        this._originalLayout = null;
        this._mainBox = null;
        this._destroyId = 0;
        this._clockId = 0;
    }

    disable() {
        if (this._idle) {
            GLib.source_remove(this._idle);
            this._idle = 0;
        }
        for (const [object, id] of this._connections)
            object.disconnect(id);
        this._connections = [];
        this._detach();
        this._status('inactive');
        this._settings = null;
        this._interface = null;
        this._background = null;
    }
}
