import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';
import {createPreferences} from './preferences.js';

export default class LockScreenPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        createPreferences(this.getSettings(), window);
    }
}
