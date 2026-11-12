import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GdkPixbuf from 'gi://GdkPixbuf';

export const PREFERENCE_KEYS = [
    'enabled', 'wallpaper-uri', 'clock-format', 'clock-weight', 'appearance',
];

export const CHOICES = {
    'clock-format': ['24', '12'],
    'clock-weight': ['bold', 'light'],
    appearance: ['auto', 'light', 'dark'],
};

export function imageUri(file) {
    const path = file?.get_path();
    if (!path)
        throw new Error('Choose an image on this computer.');
    const info = file.query_info(
        'standard::type,standard::size,access::can-read',
        Gio.FileQueryInfoFlags.NONE, null);
    if (info.get_file_type() !== Gio.FileType.REGULAR ||
        !info.get_attribute_boolean('access::can-read'))
        throw new Error('Choose a readable image file.');
    if (info.get_size() > 64 * 1024 * 1024)
        throw new Error('Choose an image smaller than 64 MiB.');
    const [format, width, height] = GdkPixbuf.Pixbuf.get_file_info(path);
    if (!format || width <= 0 || height <= 0 || width * height > 64 * 1024 * 1024)
        throw new Error('The image is invalid or too large to preview.');
    GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 256, 144, true);
    return Gio.File.new_for_path(GLib.canonicalize_filename(path, null)).get_uri();
}

export function writePreference(settings, key, value) {
    if (!PREFERENCE_KEYS.includes(key) || !settings.is_writable(key))
        throw new Error('This preference is locked or unsupported.');
    const written = key === 'enabled'
        ? settings.set_boolean(key, value)
        : settings.set_string(key, value);
    if (!written)
        throw new Error('GNOME refused the preference. Your previous choice was retained.');
    if (settings.delay_apply)
        settings.apply();
}

export function resetPreferences(settings) {
    if (PREFERENCE_KEYS.some(key => !settings.is_writable(key)))
        throw new Error('Some preferences are locked by system policy; nothing was reset.');
    settings.delay();
    for (const key of PREFERENCE_KEYS)
        settings.reset(key);
    settings.apply();
}
