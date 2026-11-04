# Yaru Glass 2.2.1

## Status and defect

Local compatibility hotfix for Ubuntu 24.04 / GNOME 46 and Ubuntu 26.04 /
GNOME 50. The extension version policy and Layered appearance are unchanged.

The 2.2.0 writer encoded tuple-valued stock colors as `av` (arrays of variants)
instead of `(dddd)` (four doubles). Blur my Shell 77 rejected the **whole library**
and used schema defaults without deleting the invalid saved entries. This hid
the Yaru pipelines in preferences and made running actors fall back to Default.
The earlier tuple test asserted the wrong format; saved settings were not proof
that the consumer accepted or rendered those effects.

## Fix and upgrade

- Preserve native numeric color tuples; repair existing variant-array colors
  without resetting the library or losing unrelated pipelines and color values.
- Compare serialized variants before treating an unchanged apply as a no-op.
  Restoration uses the same fixed writer.
- On format repair only, disable and reenable Blur my Shell through GNOME's public
  API, checking its disabled/active state. This rebuilds panel, popup and dock
  actors that had cached Default even though their saved assignment named Yaru.
  Normal valid reapplication does not write or restart anything.
- Attempt reenable even after a disabling failure; report failures and roll back
  managed settings rather than announcing success.

Install the new archive in place using its normal installer, then let its managed
appearance apply. Preferences and ownership backups are preserved; a purge is not
required. Close and reopen an already-open Blur my Shell preferences window.
No library reset or manual per-component pipeline configuration is required.

## Executed validation

All desktop changes and screenshots were confined to the previously authorized
disposable guests, not the host desktop.

| Check | GNOME 46 | GNOME 50 |
|---|---|---|
| Full source suite, including native UI/demo and isolated packaging/lifecycle | 176 passed, no skips | 176 passed, no skips |
| Full suite from the extracted archive | 176 passed, no skips, on final rerun | 176 passed, no skips |
| Real 2.2.0 installer followed by in-place 2.2.1 upgrade; preferences and ownership backups byte-identical | Passed | Passed |
| Actual installed v77 GJS parser/settings/manager accepts six managed IDs and stock/user pipelines; old encoding rejected | Passed | Passed |
| Reproduce invalid library using the real pre-fix installed writer | Passed | Passed |
| Repair without changing the saved mode; actual panel, popup and dock actors carry Frost IDs and attached effects, not Default | Passed | Passed |
| Switch to Crystal; actual actors carry Crystal IDs and attached effects | Passed | Passed |
| Quick Settings and calendar open while runtime actor snapshots are checked | Passed | Passed |
| Native extension preferences visibly list Frost and Crystal panel, popup and dock | Passed | Passed |
| Blur-off and Solid remain disabled during repair | Passed | Passed |
| Repeated apply is idempotent; unrelated user color pipeline and restoration survive and parse correctly | Passed | Passed |

Targeted host suite: 43 tests passed, including the actual upstream GJS consumer.
An earlier full host run had two demo viewport-resize timeouts; it is **not**
reported as a full pass. The unchanged demo suite passes on both guests at
1920x1080 with idle inhibition; GNOME 46 retains its dedicated WebKit AppArmor
test profile. See [guest setup](KNOWLEDGE_BASE.md#guest-webkit-test-launch).
The GNOME 46 extracted suite also had intermittent mobile-overflow failures
before its final complete pass. The isolated 27-test demo suite and the final
176-test rerun passed unchanged. This test instability remains a known limitation;
no demo assertion or product code was changed to obtain a pass.

## Limits and release boundary

The actual actor checks prevent the previous false positive based only on dconf.
They are not arbitrary-wallpaper accessibility, fractional-scaling or hardware
performance certification. Both guests use software rendering. Existing
libadwaita accent warnings and WebKit shutdown warnings remain observable.
Logo Menu remains omitted on GNOME 50; no extension policy or third-party code
was patched by this hotfix. A read-only release recheck found published version 45
(tag 75631) still forwarding non-button/touch events to `super.vfunc_event`;
metadata advertising Shell 50/51 does not establish working event handling.

The local package uses curated repository profiles, without live dconf capture:
`dist/releases/verified/yaru-glass-theme-2.2.1.tar.gz` and its adjacent SHA256 file.
The verified package adds this final evidence to the earlier candidate; runtime
sources and tests are identical. The initial local candidate is not overwritten.
Historical 2.2.0 and 2.1.1 archives are preserved. No Git staging/commit, push,
remote publication or host install is included in release preparation.
