import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GdkPixbuf from 'gi://GdkPixbuf';
import Gtk from 'gi://Gtk';

const root = Gio.File.new_for_path(ARGV[0]).get_uri();
const {createPreferences} = await import(`${root}/preferences.js`);
const {imageUri, writePreference} = await import(`${root}/settings.js`);

function check(condition, message) {
    if (!condition)
        throw new Error(message);
}
Adw.init();
const settings = Gio.Settings.new('org.yaru.glass.lockscreen');
const desktop = Gio.Settings.new('org.gnome.desktop.interface');
const shell = Gio.Settings.new('org.gnome.shell');
const before = desktop.get_string('clock-format');
const membership = shell.get_value('enabled-extensions').print(true);
const window = new Adw.PreferencesWindow();
const page = createPreferences(settings, window);
window.present();
check(!page.enabled.active, 'Customization must start off');
page.enabled.active = true;
page.rows['clock-format'].selected = 1;
check(settings.get_boolean('enabled'), 'Switch did not save');
check(settings.get_string('clock-format') === '12', 'Clock choice did not save');
check(settings.get_string('clock-weight') === 'bold', 'Partial edit changed weight');
check(desktop.get_string('clock-format') === before, 'Desktop clock was changed');
check(shell.get_value('enabled-extensions').print(true) === membership,
    'Preferences changed extension activation');

const image = GLib.build_filenamev([ARGV[1], 'wallpaper.png']);
const pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, true, 8, 24, 16);
pixbuf.fill(0x355785ff);
pixbuf.savev(image, 'png', [], []);
writePreference(settings, 'wallpaper-uri', imageUri(Gio.File.new_for_path(image)));
check(page.picture.get_paintable() !== null, 'Independent wallpaper preview missing');
for (const uri of ['https://example.invalid/a.png', 'file:///missing-lockscreen-image.png']) {
    let refused = false;
    try {
        imageUri(Gio.File.new_for_uri(uri));
    } catch {
        refused = true;
    }
    check(refused, 'Invalid image accepted');
}
const corrupt = Gio.File.new_for_path(GLib.build_filenamev([ARGV[1], 'bad.png']));
corrupt.replace_contents('not an image', null, false, Gio.FileCreateFlags.NONE, null);
let refused = false;
try {
    imageUri(corrupt);
} catch {
    refused = true;
}
check(refused, 'Corrupt image accepted');

page.choose.emit('clicked');
const chooser = page.chooser;
check(chooser !== null, 'Chooser not retained');
page.choose.emit('clicked');
check(page.chooser === chooser, 'Duplicate chooser created');
chooser.emit('response', Gtk.ResponseType.CANCEL);
check(page.chooser === null, 'Cancelled chooser retained');
page.choose.emit('clicked');
page.chooser.set_file(corrupt);
page.chooser.emit('response', Gtk.ResponseType.ACCEPT);
check(page.status.has_css_class('error'), 'Invalid selection error not surfaced');
check(settings.get_string('wallpaper-uri').endsWith('wallpaper.png'), 'Failed selection changed wallpaper');
page.follow.emit('clicked');
check(settings.get_string('wallpaper-uri') === '', 'Follow desktop did not clear override');
check(!page.status.has_css_class('error'), 'Successful change retained error');
page.reset.emit('clicked');
page.resetDialog.response('cancel');
check(settings.get_boolean('enabled'), 'Cancel changed preferences');
page.reset.emit('clicked');
page.resetDialog.response('reset');
check(!settings.get_boolean('enabled'), 'Reset did not turn customization off');
check(settings.get_string('clock-format') === '24', 'Reset did not restore clock');
page.rows['clock-format'].selected = 1;
check(!settings.has_unapplied, 'Changes after reset remained pending');
const fresh = Gio.Settings.new('org.yaru.glass.lockscreen');
check(fresh.get_string('clock-format') === '12', 'Change after reset was not committed');
check(shell.get_value('enabled-extensions').print(true) === membership,
    'Reset changed extension activation');
page.choose.emit('clicked');
window.emit('close-request');
check(page.chooser === null, 'Closing preferences retained chooser');
window.destroy();
print('PASS: independent Preferences partial edits, image validation/preview, chooser lifetime, reset/cancel.');
