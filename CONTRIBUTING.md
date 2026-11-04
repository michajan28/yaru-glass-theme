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
are blocked, including for administrators. Every pull request needs one
approval, passing CI, and resolved review conversations. The latest push must
be approved; authors cannot approve their own pull requests.

Run the checks described in [Development](README.md#development) before opening
a pull request. Keep changes focused and explain behavior changes and validation
in the PR description.

## Security reports

Do not report vulnerabilities in public issues. See the [security policy](SECURITY.md)
for private reporting instructions.
