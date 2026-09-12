# Upload and enforcement bootstrap

## Observed delivery state

The connected account resolved to `LadyElinor`. `LadyElinor/Adiona` already existed
as a public, empty repository when this task began. The first attempt to create
`README.md` returned HTTP 403, `Resource not accessible by integration`.

No repository file, commit, issue, permission, visibility setting or branch rule
was changed through that denied call. The exact missing GitHub permission or
installation selection was not conclusively diagnosed. The repository was built,
validated and committed locally instead. The included Git bundle and source
archive contain the same local seed.

## Connected-app route

Grant the connected GitHub integration the appropriate write access to
`LadyElinor/Adiona`, including access to the repository if the installation is
limited to selected repositories. Do not share a token in chat, loosen unrelated
repositories, disable protections, or enable blanket access merely to bypass an
error. A retry should first read the remote state to avoid overwriting new work.

## Local Git route

The repository archive includes its local `.git` history and an `origin` pointing
to the intended repository. After extraction, from the `Adiona` directory:

```bash
python -m unittest discover -s tests -v
python -m adiona demo
git remote -v
git ls-remote origin
git push -u origin main
```

The push uses your normal local Git authentication. It is not performed by the
archive or by running the demo. Review the remote before pushing. If remote
history now exists, reconcile it rather than forcing an overwrite.

Alternatively, restore the bundle into a new directory:

```bash
git clone Adiona.bundle Adiona
cd Adiona
git remote set-url origin https://github.com/LadyElinor/Adiona.git
git push -u origin main
```

The bundle clone initially gives `origin` the local bundle path, so the explicit
remote change above is necessary. Use a new destination directory.

## After a successful upload

Observe the actual GitHub Actions results. Only then configure branch protection
or rulesets with the actual check contexts and producing application. Require
appropriate review, dismiss stale reviews, restrict bypass, forbid force pushes
and branch deletion, and separately protect constitutional changes and secrets.
The included CODEOWNERS file names the known owner, not a nonexistent review team.
A single owner is not independent constitutional review.

The workflow verifies code; it does not merge, deploy, grant authority or protect
a branch by existing as a file. Adiona's deployment check remains closed even
when CI passes.
