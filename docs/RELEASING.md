# Release process

Yaru Glass releases are cut from `main`; there is no release branch. GitHub
Actions CI runs on pull requests, pushes to `main`, and manual dispatch. Pushing
a `vX.Y.Z` tag starts the release workflow, which checks the tag against
`VERSION`, confirms its commit is on `main`, runs tests, builds and validates a
curated-profile archive, and creates a draft GitHub Release with the archive and
checksum attached. The workflow does not publish the release.

## Prepare the release

1. Merge the changes intended for the release to `main`.
2. Update `CHANGELOG.md`: move the verified Unreleased entries into a new version
   section. Update `VERSION`, README version references, and add
   `docs/RELEASE-X.Y.Z.md` with the validation evidence and limitations. Do not
   invent test results or publication dates.
3. Check the release changes and confirm the GitHub Actions CI run passes on the
   final `main` commit. The release workflow repeats the Python suite and shell
   syntax checks on the tagged commit:

   ```sh
   /usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -q
   bash -n scripts/install.sh scripts/uninstall.sh scripts/make-package.sh
   ```

   Recheck Logo Menu's released GNOME 50 event handling on every release.
   Restore its GNOME 50 integration only after actual menu/Activities interaction
   checks pass without `StWidget` virtual-function errors; metadata alone is not
   sufficient. Record unavailable GUI tests, skips, and visual validation limits
   in the release evidence.

## Build and verify the archive

The release workflow packages with supplied profiles; it does not capture the
runner's live desktop settings. To preflight packaging locally, use an empty
temporary directory:

```sh
out_dir="$(mktemp -d)"
./scripts/make-package.sh --curated-profiles "$out_dir"
```

The script may regenerate `docs/MANUAL.html` when `python3-markdown` is available.
Review the resulting documentation changes and confirm the archive includes the
intended sources, scripts, docs, profiles, licensed assets, and tests, without Git
metadata, caches, `dist/`, or runtime state. Then verify its checksum:

```sh
cd "$out_dir"
sha256sum -c yaru-glass-theme-X.Y.Z.tar.gz.sha256
```

Replace `X.Y.Z` with the value in `VERSION`. Keep the archive and checksum
together; both are release assets. The workflow also rejects packaging if manual
rendering changes tracked `docs/MANUAL.html` or if the archive is missing expected
files or contains excluded repository/runtime data.

## Tag and create a draft

After the release changes and evidence are committed on `main`, create and push
an annotated version tag from that commit. This starts the automated release
workflow:

```sh
git switch main
git pull --ff-only
git tag -a vX.Y.Z -m "Yaru Glass X.Y.Z"
git push origin vX.Y.Z
```

Wait for the workflow to pass, then review the generated **draft** release,
release notes, archive and checksum in GitHub. Verify the checksum if desired;
publish the draft manually only after review. If the workflow fails, fix the
release commit and move the tag only according to your repository's tag policy;
never force-update a published release tag.

Keep historical archives unchanged. Never capture live profiles, run the
installer/uninstaller, or test against a real desktop as part of this procedure
without explicit approval.
