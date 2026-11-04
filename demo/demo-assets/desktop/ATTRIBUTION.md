# Desktop Demo Assets

The theme demo bundles these icons so it can render the Ubuntu desktop offline.
They come from the Ubuntu `yaru-theme-icon` package, version
24.04.2-0ubuntu1 ([upstream Yaru project](https://github.com/ubuntu/yaru)).

| Directory | Source in `/usr/share/icons/Yaru` |
| --- | --- |
| `apps/` | `48x48@2x/apps/` and `48x48@2x/categories/preferences-desktop-theme.png` |
| `places/` | `48x48@2x/places/` |
| `symbolic-icons.js` | `scalable/*/` symbolic SVG icons, inlined as strings |

Yaru icons are Copyright 2018 Sam Hewitt and the Yaru contributors and are
licensed under the [Creative Commons Attribution-ShareAlike 4.0 International
License](https://creativecommons.org/licenses/by-sa/4.0/). These files are not
covered by the project's source-code license. Any changes to them must be shared
under the same license.

The PNG icons are unmodified. The symbolic SVGs were changed only by removing
editor metadata and whitespace and embedding them in `symbolic-icons.js`, because
browsers block CSS mask images loaded from `file://` URLs.

The Ubuntu logo (`view-app-grid-ubuntu` in `symbolic-icons.js`) is a trademark of
Canonical Ltd. It is used only to depict the Ubuntu Dock as it appears on Ubuntu.
This project is not affiliated with or endorsed by Canonical.

Wallpapers are reused from the [lock-screen demo assets](../lockscreen/ATTRIBUTION.md).
The bundled Inter font keeps its license in
[assets/fonts/Inter/LICENSE.txt](../../../assets/fonts/Inter/LICENSE.txt).
