---
name: omadocs-publish
description: Prepare and publish omadocs releases, update the published Omarchy plugin or installed copies, and deploy its GitHub Pages website. Use for release and distribution work, not Codex marketplace plugins.
---

# Publish and update omadocs

Read root `AGENTS.md`, `docs/release-checklist.md`, and `docs/repository-rules.md`. For website work also read `docs/website.md`. Paths below are repository-relative.

## Identify the deliverable

The plugin is distributed from `https://github.com/pablousx/omadocs.git`. The public site is a separate manual Pages deployment of `site/`. A local development install is a copied runtime, not a published Git installation. Confirm current Git remote/default branch and relevant installed Omarchy command help before mutations; repository docs describe intended rules, not proof of current remote settings.

Use existing authorization. A request to prepare a release does not authorize pushing, tagging remotely, merging, publishing a GitHub release, submitting a directory listing, or deploying Pages. Prepare the diff, version, checks, limitations, and exact target first; ask only for any missing authorization. An explicit request to publish/update that target already supplies authorization within that scope.

## Prepare the publication tree

1. Inspect Git status/diff, current release tags and target branch. Preserve unrelated local work; release only the reviewed changes. Prefer a PR with current passing `Python tests` and `Website validation` checks. Local QML/native validation is additional to CI.
2. For a versioned release, update `manifest.json` version, `omadocs/__init__.py` `VERSION`, and `pyproject.toml` project version together. Search README/site/docs for the previous version and update current-release claims while preserving historical records. Keep permanent ID `io.github.pablousx.omadocs` and manifest schema 1. Do not add Codex metadata or cachebuster suffixes.
3. Run the release checklist on the final tree:

   ```bash
   python -m unittest discover -s tests -v
   python scripts/check-qml.py
   python scripts/check-ui.py
   omarchy plugin validate .
   python scripts/check-site.py
   python scripts/check-release.py
   ```

4. Review the actual staged/publication file set for private/generated artifacts. `check-release.py` examines tracked and nonignored untracked files, not Git history or ignored files. It rejects symlinks, generated/private artifacts, credential-shaped JSON and common token patterns, and checks identity/version/client schema. Inspect the intended commit as well; a clean checker is not a substitute for diff review. Use `--custom-setup` only when the release explicitly requires users' own credentials.
5. Complete native checks and authorized live gates in `docs/release-checklist.md`. Record precise results/limitations in `docs/validation.md`; do not claim fresh-user consent or DOCX/XLSX/PPTX editor behavior from fake tests. Keep README and website claims consistent. Missing live evidence prevents advertising full production validation; it must be disclosed in a development release.
6. For a versioned GitHub release, build the source archive, standalone license copy, and `SHA256SUMS` from the reviewed clean commit with `python scripts/build-release.py`. Build twice and compare hashes, inspect the ZIP inventory, and validate an extracted copy. These assets supplement the Git-based installation path; they do not replace `omarchy plugin add` or update.

## Publish the plugin source

After review and applicable authorization, push the prepared branch/PR and merge according to current repository rules. Confirm the remote default branch contains the intended commit and CI passed. If a versioned tag/GitHub release is in scope, create it from that verified commit with notes describing changes, update instructions, checks, and known limitations. Check existing tag/release first; do not overwrite a published tag. Attach the reviewed ZIP, `SHA256SUMS`, and versioned license copy. No package registry upload is used; the archive is a source artifact and the current install mechanism remains Git-based.

**A tag alone does not update users.** The installed Omarchy updater inspected for this project fetches `origin HEAD` and fast-forwards to it. The intended release must be on the remote default branch. Confirm the current updater implementation if the host version differs. Publish fixes through a new forward commit/release; do not force-push shared history as rollback.

If a plugin-directory listing must be updated, identify its actual repository/entry and requirements first. This repository does not define an automated directory submission workflow. Prepare the concrete listing change and submit only within authorization; do not invent a marketplace endpoint.

## Install or update the published plugin

For a clean Quattro user profile with no conflicting plugin ID:

```bash
omarchy plugin add https://github.com/pablousx/omadocs.git --enable
```

For an existing Git-managed installation:

```bash
git -C "$HOME/.config/omarchy/plugins/io.github.pablousx.omadocs" status --short
git -C "$HOME/.config/omarchy/plugins/io.github.pablousx.omadocs" remote -v
omarchy plugin update io.github.pablousx.omadocs
```

Inspect and preserve local modifications before updating: the installed updater can reset to `ORIG_HEAD` if post-merge validation fails. Confirm origin points at the intended repository. Use the explicit plugin ID so unrelated plugins are not updated. For an authorized noninteractive add/update, append `--yes` (the CLI otherwise requires terminal confirmation). Check current `--help` first.

The updater requires `.git`, fetches origin HEAD, fast-forwards, validates and rescans. Diverged history needs investigation, not a forced reset. `scripts/install-local.py` instead refreshes only its owned development copy; it cannot publish anything and is not the updater for a Git install.

If a development copy occupies the ID, prefer a clean profile for distribution testing. Switching an existing profile requires preserving its installation and following `docs/uninstall.md` for MIME/launcher implications before removing/replacing anything. Do not silently delete a working install to make add succeed.

After update, compare installed Git HEAD and manifest version to the published commit, run plugin validation, open the panel, and inspect relevant shell diagnostics. Let an active helper settle before expecting replacement. Smoke-test agreed picker/keyboard/account flows and unchanged MIME behavior; use Reopen for an existing copy instead of unintentionally uploading again. Record clean-install, update and removal results separately. Do not erase account state/keyring to simulate a clean user.

## Publish or update the website

Run `python scripts/check-site.py` and the applicable browser checks in `docs/website.md` before deploying. Ensure the intended site commit is on the selected remote ref. Pages uses `.github/workflows/pages.yml` with `workflow_dispatch`; pushing does not deploy it. Keep artifact path `site`, relative project links, and no `CNAME` unless an explicitly requested domain migration changes that design.

After authorization, use Actions → **Publish website to GitHub Pages** → Run workflow on the reviewed ref (normally `main`), or the equivalent:

```bash
gh workflow run pages.yml --repo pablousx/omadocs --ref main
```

Find and watch the specific dispatched run; respect environment approvals and verify its commit. Verify the deployed home, privacy and terms pages under `https://pablousx.github.io/omadocs/`, assets, install command, themes and mobile layout. Successful dispatch is not proof of deployment. For a site rollback, revert the relevant site change in a new commit and dispatch again within the authorized scope.

Report version/commit, PR/tag/release or deployment URL as applicable, actual check results, installed-update verification, and remaining live-validation limits. Distinguish source publication from Pages deployment and local installation.
