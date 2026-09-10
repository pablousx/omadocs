# Repository rules

Two GitHub branch rulesets protect the default branch:

- [Open source baseline](../.github/rulesets/open-source.json) requires pull requests, resolved review conversations, and squash merging, and blocks deletion and force pushes. Required approvals remain at zero while the project has one maintainer.
- [omadocs CI](../.github/rulesets/ci.json) requires the GitHub Actions checks `Repository checks`, `Python tests`, and `Website validation`, with the branch up to date before merging.

Both grant `pablousx` (GitHub user ID `66285146`) an **Always allow** bypass, including direct pushes and bypassing failed checks. Normal changes should still use pull requests and passing CI.

The [CI workflow](../.github/workflows/ci.yml) runs for every pull request and pushes to `main`, with read-only repository permissions. Python tests run on Ubuntu 24.04 with system Python and desktop test dependencies. Website validation runs separately. Native Omarchy/QML validation remains a local check described in [development](development.md).

## Reuse on other repositories

GitHub personal accounts have no account-wide branch ruleset. Import `open-source.json` into each selected repository through **Settings → Rules → Rulesets → Import a ruleset**, or create it through the API:

```bash
gh api --method POST repos/OWNER/REPO/rulesets --input .github/rulesets/open-source.json
```

The template targets the default branch, regardless of its name. It grants bypass specifically to `pablousx`; replace the actor ID when using it for a different maintainer. Enable squash merging in the destination repository. Copies are independent: later template changes do not update GitHub automatically, and repeated POST requests create additional rulesets. Update an existing ruleset with PUT to `repos/OWNER/REPO/rulesets/RULESET_ID`.

Keep required checks specific to each repository. Import `ci.json` only after that repository has successfully run checks with the exact names and GitHub Actions source specified in the file. The integration ID `15368` identifies GitHub Actions on github.com.

Centrally managed rulesets across multiple repositories require an organization on GitHub Team or Enterprise. See GitHub's [organization ruleset documentation](https://docs.github.com/en/organizations/managing-organization-settings/creating-rulesets-for-repositories-in-your-organization) and [repository ruleset API](https://docs.github.com/en/rest/repos/rules).

The shared community files, labels, security settings, and setup script are described in [GitHub repository configuration](../GITHUB_SETUP.md).
