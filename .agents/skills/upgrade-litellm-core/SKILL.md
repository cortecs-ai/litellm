---
name: upgrade-litellm-core
description: Periodically upgrade the Cortecs LiteLLM fork to a user-selected BerriAI upstream tag, discovering current stable tags when no version is supplied, preserving and auditing fork fixes against evaluator tests and documentation, maintaining the fix catalog, and excluding upstream enterprise code and GitHub Actions. Use for LiteLLM core upgrades or upstream tag merges, not ordinary provider updates or submodule upgrades.
---

# Upgrade LiteLLM Core

Upgrade the Cortecs fork from an exact upstream release tag on a new branch named `litellm-upgrade-[version]`. After validation, commit the merge and push that branch for manual review.

## Select the target version

If the user's current request already contains an exact target version, do not ask again. Accept a version with or without the leading `v`; resolve it to an exact upstream tag after fetching. If it matches multiple tags or only prereleases, show the matches and ask the user to choose rather than guessing.

If the user's current request does not contain a target version:

1. Confirm the working directory is the intended LiteLLM fork root and that `upstream` points to `https://github.com/BerriAI/litellm.git` or its SSH equivalent. If `upstream` is missing, add it with that canonical URL. If it points elsewhere, stop and ask before changing it.
2. Fetch upstream tags into the dedicated namespace used by this skill, without fetching submodules or changing local release tags:

   ```shell
   git -c submodule.recurse=false fetch --no-recurse-submodules --no-tags --prune upstream +refs/tags/*:refs/upstream-tags/*
   ```

3. From `refs/upstream-tags/`, select the five newest stable tags by semantic version. Treat only exact `vMAJOR.MINOR.PATCH` or `MAJOR.MINOR.PATCH` tags as stable; exclude tags with any suffix, including release candidates, development builds, and `-stable` variants. Resolve each candidate with `^{commit}` so broken or non-commit tags are not offered.
4. Ask: "Which LiteLLM version do you want to upgrade to? Latest stable upstream versions: [newest five tags]." Then wait for the user's choice. Do not create a branch, merge, or otherwise modify the working tree before the user answers.

If fetching fails or no stable tags can be resolved, report the exact problem and ask the user for an exact version instead of presenting a guessed or stale list.

## Preserve the fork

Treat every existing fork delta as intentional unless the user says otherwise. A merge completing without conflicts is not proof that fork fixes survived; audit their behavior after the merge.

Keep these repository-specific boundaries:

- Preserve the `litellm/cortecs` gitlink and all existing submodule work. Read its evaluator tests and documentation, run relevant tests, and update the evaluator fix catalog when a verified core fix is missing. These catalog updates are the explicit exception to leaving the submodule unchanged; do not update its checkout, initialize, clean, reset, or change its implementation.
- Remove the upstream top-level `enterprise/` package after the merge. Do not broadly delete core files or tests merely because their path or content contains the word `enterprise`; this fork currently retains such shared/core code.
- Restore the complete `.github/` tree from the pre-merge fork baseline. This preserves fork workflows and configuration while excluding upstream GitHub Actions and their support files.
- After verifying the target tag, create and switch to `litellm-upgrade-[version]` from the recorded pre-upgrade fork HEAD. Use the resolved version without its leading `v`, for example `litellm-upgrade-1.104.0`. Use a no-commit merge during resolution and validation, then create a merge commit and push only this new branch. Do not create a PR.
- Do not stash, reset, clean, or discard pre-existing work. A dirty superproject, excluding submodule dirt, is a blocker that must be reported to the user.

Read and follow the repository's `AGENTS.md` and `CLAUDE.md`. This skill's user-authorized exception permits committing and pushing the completed upgrade on its newly created branch. It does not authorize committing unrelated work, changing the submodule gitlink, or pushing another branch. An explicit no-commit/no-push instruction in the current upgrade request still takes precedence.

## Evaluator evidence

`litellm/cortecs/evaluator/` contains tests and documentation of core fixes. Start with the core-change catalog in `evaluator/system_test/README.md` and tests in `evaluator/system_test/patches/`, but independently inspect the fork delta: the catalog may be incomplete. Add verified missing fixes to the existing documentation using its format and evidence from code/history, without duplicating existing entries or inventing references or test coverage.

Some evaluator tests require a running router and real providers; others run in process. Read the catalog's `Live` labels, fixtures, and test setup before selecting tests. For live integration tests, start a local proxy from this upgraded checkout with `litellm/cortecs/proxy_config_dev.yaml` and load `litellm/cortecs/.env` as described in the validation workflow. A live test only verifies the upgrade when the running instance serves this upgraded checkout. Report unavailable prerequisites and untested behaviors accurately.

## Repeatable upgrades

Preserve upstream merge ancestry, reuse previous conflict resolutions with review, and keep the remaining core delta small by accepting proven upstream equivalents of fork fixes. Audit fixes on every upgrade and maintain the existing catalog incrementally. Commit the real merge with both the fork baseline and upstream target as parents; squashing or copying upstream files would lose ancestry and make later upgrades harder.

## Perform the upgrade

Once the target version is known, read [references/upgrade-workflow.md](references/upgrade-workflow.md) completely before running repository commands. Follow its preflight, exact-tag verification, merge, conflict-resolution, fork-delta audit, and validation steps.

If a core conflict cannot be resolved with confidence that both the upstream change and fork behavior survive, leave the merge in progress, identify the unresolved path and competing behaviors, and ask the user for direction. Never select all of `ours` or `theirs` across the tree.

## Handoff

Report the upgrade branch, resolved tag and target commit, the pre-merge baseline, conflicts and semantic resolutions, validation performed, and any failures or uncertainties. Include the merge commit and push result, or explain why the upgrade remains uncommitted and unpushed. Mention evaluator documentation left for separate submodule review.
