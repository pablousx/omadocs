# Website and GitHub Pages

The public site is plain HTML, CSS, and a small optional JavaScript file in `site/`. No build step, framework, CDN, external fonts, analytics, or server is required. The home page, privacy policy, and terms all work without JavaScript; theme selection, preview tabs, and command copying are enhancements.

## Preview locally

From the repository root:

```bash
python scripts/check-site.py
python -m http.server 8765 --directory site --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/`. Pages are `index.html`, `privacy.html`, and `terms.html`. All internal links and assets are relative, so the site works under the GitHub project path `/omadocs/` and at a custom domain root.

## Publish

The included `.github/workflows/pages.yml` uploads **only `site/`**, never the plugin source, local state, or Google configuration. It uses GitHub’s official static Pages actions. It is manual: pushing a commit does not deploy it.

1. Review and commit the site, `scripts/check-site.py`, and the workflow to the repository’s default branch.
2. In the repository, open **Settings → Pages → Build and deployment → Source**, and select **GitHub Actions**.
3. In **Actions → Publish website to GitHub Pages**, select **Run workflow** on `main`.
4. Follow the deployment URL. The repository has the maintainer-configured custom domain `https://sites.steralynx.com/`; preserve the root `CNAME` and Pages domain settings. Without a custom domain, the default address would be `https://pablousx.github.io/omadocs/`.
5. Verify all three pages on the published URL, both color themes, the install command, and mobile layout.

Repeat the manual workflow for updates. GitHub repository and environment rules may require an approval before deployment. Nothing in the local development workflow publishes the site.

Reference: [Creating a GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site) and GitHub’s [static site workflow](https://github.com/actions/starter-workflows/blob/main/pages/static.yml).

## Content to maintain

- `site/index.html`: plugin behavior, version, install command, and included Desktop application configuration and honest release validation limits. Do not claim clean-user consent was tested until it has been observed. The desktop preview is illustrative, with fictional filenames and `.test` accounts.
- `site/privacy.html`: actual file access, Google permission, local storage/retention, removal, website hosting, and contact information.
- `site/terms.html`: software behavior, MIT license, dependencies, responsibilities, and limitations. No company, jurisdiction, or support guarantee has been invented.
- Shared header/footer markup is deliberately plain HTML in each page. Keep navigation and contact changes consistent across all three.
- The contact currently points to `https://github.com/pablousx/omadocs/issues`. Issues are public; both policies tell visitors not to post private data and to request a private channel for sensitive matters. Replace this with a dedicated support/privacy email if one is provided.
- The site stores only the selected theme in `localStorage` under `omadocs-theme`. It loads no third-party resources; GitHub Pages still handles hosting request data under GitHub’s own privacy policy.
- Legal page effective dates are September 9, 2026. Review these policies as the maintainer before publishing and update dates when their substance changes.

## Google consent-screen use

Once published, the URLs are suitable as the site’s homepage, privacy-policy page, and terms page. Use the real deployed URLs in Google Cloud. Pages deployment by itself does not complete Google’s OAuth production/branding verification: verify control of the domain used for the consent screen and follow the requirements shown for the production project.

These pages describe the existing plugin. They do not bundle credentials or change its OAuth configuration. See [the OAuth ADR](oauth-adr.md) and [release checklist](release-checklist.md) for that separate work.

## Validation

`python scripts/check-site.py` checks local links, anchor destinations, assets, page metadata/structure, project-path compatibility, and the publication directory’s file types without external dependencies. The Pages workflow runs it before uploading.

Browser verification covers desktop, tablet, and narrow mobile layouts; both themes; reduced motion; keyboard navigation; preview tabs; copying and the denied-clipboard fallback; and no-JavaScript reading/navigation. Browser tools are development-only and are not deployed.

### Local verification — September 9, 2026

- All three pages passed browser layout checks at 1440, 1024, 768, 390, and 320 pixels wide, without horizontal overflow.
- The preview tabs passed mouse and arrow-key interaction checks and retained a stable frame height.
- Theme persistence across navigation, command copying, denied-clipboard fallback, FAQ disclosure, and no-JavaScript page rendering passed.
- Axe found no WCAG A/AA violations in 12 combinations of page, theme, and desktop/mobile viewport. Reduced-motion behavior, skip-link focus, and keyboard theme switching also passed. Automated checks complement the visual review; they do not certify every accessibility scenario.
- Browser page-error and external-resource request counts were both zero. The complete deployment folder is approximately 92 KB.
- Desktop and phone screenshots were visually reviewed and kept outside the repository. The GitHub Pages workflow was prepared locally; see the later publication record for deployment status.
