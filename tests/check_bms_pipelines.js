import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const [extensionPath, variantPath, selectedMode] = ARGV;
const live = variantPath === '--live';
if (!live && GLib.getenv('GSETTINGS_BACKEND') !== 'memory')
    throw new Error('Use GSETTINGS_BACKEND=memory; this check must not change desktop settings');
if (live && !['frost', 'crystal'].includes(selectedMode))
    throw new Error('Live read-only check requires the expected Frost/Crystal mode');

const uri = Gio.File.new_for_path(extensionPath).get_uri();
const {unpack_pipelines, pack_pipelines} = await import(`${uri}/settings/pipeline_settings.js`);
const {Settings} = await import(`${uri}/settings/settings.js`);
const {KEYS} = await import(`${uri}/settings/keys.js`);
const {PipelinesManager} = await import(`${uri}/pipelines/pipelines_manager.js`);
const source = Gio.SettingsSchemaSource.new_from_directory(
    `${extensionPath}/schemas`, Gio.SettingsSchemaSource.get_default(), false);
const schema = source.lookup('org.gnome.shell.extensions.blur-my-shell', false);
const settings = Gio.Settings.new_full(schema, null, null);
let value;
if (live) {
    value = settings.get_value('pipelines');
} else {
    const [, bytes] = GLib.file_get_contents(variantPath);
    value = GLib.Variant.parse(null, new TextDecoder().decode(bytes), null, null);
    settings.set_value('pipelines', value);
}
const parsed = unpack_pipelines(value);
const roundtrip = unpack_pipelines(pack_pipelines(parsed));
if (JSON.stringify(parsed) !== JSON.stringify(roundtrip))
    throw new Error('Upstream pipeline roundtrip changed values');

const preferences = new Settings(KEYS, settings);
const manager = new PipelinesManager(preferences);
if (preferences.has_invalid_value('general', 'pipelines'))
    throw new Error('Blur my Shell fell back to its default library');
if (Object.keys(manager.pipelines).length !== Object.keys(parsed).length)
    throw new Error('Blur my Shell dropped pipelines');
for (const mode of (selectedMode === '--library-only' ? [] : ['frost', 'crystal'])) {
    for (const [area, component] of [['panel', 'panel'], ['popup', 'popup'], ['dock', 'dash_to_dock']]) {
        const id = `pipeline_yaru_glass_${mode}_${area}`;
        if (!live)
            preferences[component].PIPELINE = id;
        if ((!live || mode === selectedMode) && preferences[component].PIPELINE !== id)
            throw new Error(`${mode} ${area}: pipeline assignment does not match`);
        if (!manager.pipelines[id])
            throw new Error(`${mode} ${area}: selected pipeline unavailable`);
        const effects = manager.pipelines[id].effects;
        if (effects[0].params.unscaled_radius !== (mode === 'frost' ? 30 : 6))
            throw new Error(`${mode} ${area}: wrong blur strength`);
    }
}
manager.destroy();
print(selectedMode === '--library-only'
    ? 'Restored library accepted by upstream parser and manager'
    : 'panel, popup, dock: Frost and Crystal accepted by upstream parser and manager');
if (live)
    print(`${selectedMode}: panel, popup, dock assignments confirmed (read-only)`);
