# Repository inventory

Inventory date: 2026-09-03 (Asia/Seoul)

The repository was an empty, newly initialized Git worktree when discovery began. `main` had no commits, no remotes, tags, other branches, or submodules. The only project file was the untracked `CodexResearchInstructions.md`. There were no kernel or U-Boot trees, DTS files, build scripts, containers, rootfs tools, hardware-control utilities, or pre-existing project documentation.

Commands run:

```text
pwd
git status --short --branch
git remote -v
git branch -a
git tag -l
git submodule status
find . -maxdepth 3 -type f -print | sort
```

Initial result:

```text
/var/home/user/repos/blikvm4-pikvm
## No commits yet on main
?? CodexResearchInstructions.md
```

All files under `research/`, `lab/`, and `tests/` were added by this research pass. Upstream source checkouts used for comparison were shallow temporary clones under `/tmp` and are not repository dependencies. Their pinned revisions are recorded in [sources.md](sources.md).

