import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import Gtk from 'gi://Gtk';

import {CHOICES, imageUri, resetPreferences, writePreference} from './settings.js';

export function createPreferences(settings, window) {
    const page = new Adw.PreferencesPage({
        title: 'Lock Screen', icon_name: 'system-lock-screen-symbolic',
    });
    const group = new Adw.PreferencesGroup({
        title: 'Yaru Glass Lock Screen',
        description: 'Enable the extension in Extensions or Extension Manager first. ' +
            'These preferences customize the native session lock screen, not the login screen. ' +
            'GNOME still handles authentication and notification privacy.',
    });
    page.add(group);
    const status = new Adw.ActionRow({title: 'Preferences are saved independently of the theme.'});
    const enabled = new Adw.SwitchRow({title: 'Custom lock-screen appearance'});
    group.add(enabled);
    const rows = {};
    for (const [key, title, labels] of [
        ['clock-format', 'Clock format', ['24 hour', '12 hour']],
        ['clock-weight', 'Clock weight', ['Bold', 'Light']],
        ['appearance', 'Appearance', ['Follow system', 'Light', 'Dark']],
    ]) {
        rows[key] = new Adw.ComboRow({
            title, model: Gtk.StringList.new(labels),
        });
        group.add(rows[key]);
    }

    const wallpaper = new Adw.ActionRow({title: 'Lock wallpaper'});
    const picture = new Gtk.Picture({width_request: 256, height_request: 144,
        can_shrink: true, content_fit: Gtk.ContentFit.CONTAIN});
    const choose = new Gtk.Button({label: 'Choose image', valign: Gtk.Align.CENTER});
    const follow = new Gtk.Button({label: 'Follow desktop', valign: Gtk.Align.CENTER});
    wallpaper.add_suffix(choose);
    wallpaper.add_suffix(follow);
    group.add(wallpaper);
    const preview = new Adw.PreferencesGroup();
    preview.add(picture);
    page.add(preview);
    const actions = new Adw.PreferencesGroup();
    const reset = new Gtk.Button({label: 'Reset lock-screen preferences',
        halign: Gtk.Align.START});
    actions.add(reset);
    actions.add(status);
    page.add(actions);
    window.add(page);

    let syncing = false;
    let closed = false;
    let chooser = null;
    let resetDialog = null;
    function error(problem) {
        console.error(`[Yaru Glass Lock Screen preferences] ${problem.message}`);
        status.title = problem.message;
        status.add_css_class('error');
    }
    function render() {
        if (closed)
            return;
        syncing = true;
        enabled.active = settings.get_boolean('enabled');
        enabled.sensitive = settings.is_writable('enabled');
        for (const [key, row] of Object.entries(rows)) {
            row.selected = CHOICES[key].indexOf(settings.get_string(key));
            row.sensitive = settings.is_writable(key);
        }
        syncing = false;
        choose.sensitive = follow.sensitive = settings.is_writable('wallpaper-uri');
        const uri = settings.get_string('wallpaper-uri');
        wallpaper.subtitle = uri ? 'Independent image selected' : 'Following the desktop wallpaper';
        picture.set_paintable(null);
        if (uri) {
            try {
                const file = Gio.File.new_for_uri(uri);
                imageUri(file);
                picture.set_filename(file.get_path());
            } catch (problem) {
                error(new Error('Wallpaper preview unavailable. Choose a readable local image.'));
            }
        }
    }
    function change(key, value) {
        if (syncing || closed)
            return;
        try {
            writePreference(settings, key, value);
            status.remove_css_class('error');
            status.title = 'Preference saved. The extension must be enabled to apply it.';
        } catch (problem) {
            error(problem);
        }
        render();
    }
    enabled.connect('notify::active', () => change('enabled', enabled.active));
    for (const [key, row] of Object.entries(rows))
        row.connect('notify::selected', () => change(key, CHOICES[key][row.selected]));
    follow.connect('clicked', () => change('wallpaper-uri', ''));
    choose.connect('clicked', () => {
        if (closed || chooser)
            return;
        chooser = new Gtk.FileChooserNative({
            title: 'Choose lock wallpaper', transient_for: window, modal: true,
            action: Gtk.FileChooserAction.OPEN, accept_label: 'Choose', cancel_label: 'Cancel',
        });
        const filter = new Gtk.FileFilter();
        filter.add_pixbuf_formats();
        chooser.add_filter(filter);
        chooser.connect('response', (dialog, response) => {
            try {
                if (!closed && response === Gtk.ResponseType.ACCEPT)
                    change('wallpaper-uri', imageUri(dialog.get_file()));
            } catch (problem) {
                error(problem);
            } finally {
                dialog.destroy();
                chooser = null;
            }
        });
        chooser.show();
    });
    reset.connect('clicked', () => {
        if (closed || resetDialog)
            return;
        resetDialog = new Adw.MessageDialog({
            transient_for: window, modal: true, heading: 'Reset lock-screen preferences?',
            body: 'Turn customization off and restore its default choices. ' +
                'Desktop preferences and extension activation are not changed.',
        });
        resetDialog.add_response('cancel', 'Cancel');
        resetDialog.add_response('reset', 'Reset');
        resetDialog.set_response_appearance('reset', Adw.ResponseAppearance.DESTRUCTIVE);
        resetDialog.set_default_response('cancel');
        resetDialog.set_close_response('cancel');
        resetDialog.connect('response', (dialog, response) => {
            if (!closed && response === 'reset') {
                try {
                    resetPreferences(settings);
                    status.remove_css_class('error');
                    status.title = 'Lock-screen preferences reset. Desktop settings were not changed.';
                    render();
                } catch (problem) {
                    error(problem);
                }
            }
            resetDialog = null;
            dialog.destroy();
        });
        resetDialog.present();
    });
    const changed = settings.connect('changed', render);
    window.connect('close-request', () => {
        closed = true;
        settings.disconnect(changed);
        chooser?.destroy();
        resetDialog?.destroy();
        chooser = resetDialog = null;
        return false;
    });
    render();
    return {page, enabled, rows, choose, follow, reset, status, picture,
        get chooser() { return chooser; },
        get resetDialog() { return resetDialog; }};
}
