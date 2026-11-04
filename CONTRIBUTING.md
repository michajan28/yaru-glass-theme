# Contributing

## Start with an issue

Open a GitHub issue before starting code changes. Use the issue number in a
feature or bugfix branch based on `main`:

```text
feature/123-short-description
bugfix/456-short-description
```

Use lowercase letters, numbers, and hyphens in the description. Pull requests
must target `main` and include `Closes #123` (or the matching issue number) in
their description. CI checks the branch format, target branch, issue reference,
and that the referenced number is an issue in this repository.

## Pull requests

Only the repository owner and collaborators they add can open pull requests;
only collaborators with write access can merge them. Direct updates to `main`
are blocked, including for administrators. Every pull request needs passing CI,
signed commits, and resolved review conversations. No review approval is required
while the owner is the only collaborator, so the owner can merge their own PR
after the required checks pass. This does not bypass the PR or signing rules.

Configure Git to sign commits using a GitHub-registered SSH or GPG signing key.
For an SSH signing key, enable signing in this repository:

```sh
git config --local gpg.format ssh
git config --local user.signingkey "$HOME/.ssh/github_signing.pub"
git config --local commit.gpgsign true
```

GitHub must show the commits as **Verified**. Enabling signing does not sign
existing commits retroactively.

Run the checks described in [Development](README.md#development) before opening
a pull request. Keep changes focused and explain behavior changes and validation
in the PR description.

## Security reports

Do not report vulnerabilities in public issues. See the [security policy](SECURITY.md)
for private reporting instructions.
