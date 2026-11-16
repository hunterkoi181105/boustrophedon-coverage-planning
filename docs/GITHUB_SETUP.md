# Publishing and collaboration setup

## Publish the source tree

Extract the archive. Open a terminal **inside `coverage-planning`**, not its parent.
Install Python dependencies and run tests before the initial commit.

```sh
git init -b main
git add .
git commit -m "Initialize BCD, TSP, and direction-aware GTSP project"
gh auth login
gh repo create boustrophedon-coverage-planning --private --source=. --remote=origin --push
```

The last command requires GitHub CLI, an authenticated account, and permission to
create a repository. It creates a remote and pushes the current commit. It does
not need an access token embedded in a file. Review repository visibility before
changing `--private` to `--public`.

Without GitHub CLI, create an empty repository in GitHub's interface without an
auto-generated README, license, or gitignore. Then connect its URL and push:

```sh
git remote add origin https://github.com/YOUR_USERNAME/boustrophedon-coverage-planning.git
git push -u origin main
```

The placeholder is for your account; it is not a pre-created repository.

## Lightweight workflow

Use `main` for working, tested code and short-lived branches for changes, such as
`feature/decomposition`, `feature/sweep-states`, and `feature/gtsp-improvements`.
Make a pull request with a test and a small map that demonstrates the behavior.
Keep raw large experiment outputs out of Git; summarize meaningful results in
`docs/`. `results/`, environment folders, caches, and credentials are ignored.

After the first push, check the Actions tab. The included workflow installs the
package, compiles the Python sources, runs pytest on Python 3.11-3.13 on Ubuntu
and Windows, and executes a CLI smoke test. Its configuration is not evidence
that remote runs have already passed.

When modifying style, the optional development dependency Ruff can be used:

```sh
python -m ruff check --fix .
python -m ruff format .
```

Style tools are not a required CI gate in this starter. Do not automatically apply
algorithmic changes just to satisfy formatting or linting output.

## Before making the repository public

Remove private map data and personal files. Review third-party licenses and course
rules for public solutions. Replace generic project metadata as appropriate.
No GitHub account, author email, or institutional identity is assumed by this package.
