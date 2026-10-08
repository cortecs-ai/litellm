# LiteLLM Upstream Upgrade Workflow

Use this workflow only after the user has supplied the target version.

## 1. Establish a safe baseline

Confirm that the working directory is the intended LiteLLM fork root:

- `git rev-parse --show-toplevel` succeeds
- `.gitmodules` defines `litellm/cortecs`
- `upstream` points to `https://github.com/BerriAI/litellm.git` or its SSH equivalent

If `upstream` is missing, add it with that canonical URL. If it exists but points elsewhere, stop and ask before changing it.

If this exact target already has a merge in progress, inspect `MERGE_HEAD` and the current resolutions and resume that upgrade after establishing its original baseline; do not merge again or overwrite resolved work. Stop for a different merge or an ongoing rebase, cherry-pick, or revert. For a new upgrade, check the superproject with submodule changes ignored, including untracked files. If it is dirty, report the paths and wait; do not stash or clean them. Dirt confined to `litellm/cortecs/` may remain; record it before making any evaluator documentation changes.

Record before fetching or merging:

- `BASE_HEAD`: `git rev-parse HEAD`
- original branch name
- the baseline gitlink from `git ls-tree BASE_HEAD -- litellm/cortecs`
- the current submodule status for the final report, without changing it
- existing evaluator documentation changes and generated reports, so subsequent edits preserve the user's work

## 2. Fetch and resolve the exact upstream tag

Fetch upstream tags into a dedicated namespace so repeated fetches cannot overwrite or prune fork tags:

```shell
git -c submodule.recurse=false fetch --no-recurse-submodules --no-tags --prune upstream +refs/tags/*:refs/upstream-tags/*
```

Normalize a bare version such as `1.104.0` to `v1.104.0` only when that exact upstream tag exists. Resolve `refs/upstream-tags/SELECTED_TAG^{commit}`, verify the selected tag against `git ls-remote --tags upstream`, and record its peeled target commit. A moved tag or conflicting object identity needs investigation before merging; do not silently use an unrelated local tag or force-update `refs/tags`.

Do not substitute a newer tag, release branch, or prerelease. If the requested tag does not exist, show a short list of close upstream tag matches and ask the user to choose.

Before merging:

- If the target commit is already an ancestor of `BASE_HEAD`, report that the requested version is already incorporated and do not merge it again.
- Find `COMMON_BASE` with `git merge-base BASE_HEAD TARGET_COMMIT`.
- Confirm this looks like a forward upgrade. If the target is unrelated or older than the most recent upstream release already reachable from `BASE_HEAD`, stop and explain the evidence.
- Identify the last upstream release merge from ancestry. Use the actual merge base for this upgrade instead of replaying the fork's entire historical patch series. If previous upgrades were squashed or copied and ancestry is missing, report the limitation before attempting a large reconstruction.

### Create the upgrade branch

Before editing documentation or starting the merge, create and switch to `litellm-upgrade-[version]` from `BASE_HEAD`. Replace `[version]` with the exact resolved version, removing only a leading `v`; retain any prerelease suffix. For example, tag `v1.104.0` uses branch `litellm-upgrade-1.104.0`. Validate the name with `git check-ref-format --branch` and create it with `git -c submodule.recurse=false switch -c UPGRADE_BRANCH BASE_HEAD`.

Do not add a `codex/` prefix or an alternative suffix. If the branch already exists, never overwrite or reset it. Reuse it only when already on that branch and resuming a verified upgrade to this same target. Otherwise, report the existing branch and ask how to proceed. An already-incorporated target returns before branch creation. Keep the recorded baseline and submodule state intact throughout the switch.

## 3. Inventory fork changes

Inspect the full fork delta from `COMMON_BASE` to `BASE_HEAD` with rename and copy detection. Keep both a name-status inventory and the actual patch available during conflict resolution.

Classify the delta into:

- fork fixes and custom core behavior that must survive semantically
- the `.github/` fork snapshot, which must survive byte-for-byte
- deletion of the top-level `enterprise/` tree, which must remain deleted
- the `litellm/cortecs` gitlink, which must remain at the baseline value

Do not assume commit messages fully describe the fork fixes. Inspect the changed code and corresponding tests.

Read applicable instructions within the submodule before editing its evaluator documentation. Read `litellm/cortecs/evaluator/system_test/README.md`, its core-change catalog, relevant `patches/` tests, and fixtures. Map every core fix in the fork delta to catalog entries and actual tests; the catalog is evidence, not an exhaustive list.

For verified fixes missing from the catalog, add entries to the existing documentation in its established format. Include the problem, preserved behavior, affected core paths, code/history references, real regression test references, and live prerequisites. Use the existing date/author fields only when supported by history; explicitly mark unknown details and absent regression coverage. Update an existing entry when it already describes the fix. Do not invent issue IDs, links, tests, or a passing result. Preserve the submodule gitlink and leave documentation edits uncommitted for separate review.

## 4. Merge without committing

Confirm the current branch is the expected `litellm-upgrade-[version]` branch, then merge `TARGET_COMMIT` into it with `--no-commit --no-ff` and submodule recursion disabled. Enable Git's repository-local recorded conflict resolutions for this invocation, keeping automatic staging disabled:

```shell
git -c submodule.recurse=false -c rerere.enabled=true -c rerere.autoupdate=false merge --no-commit --no-ff TARGET_COMMIT
```

Review any reused resolution against the new upstream changes before staging it; an old resolution can be stale. After manual resolutions, run `git -c rerere.enabled=true rerere` to record supported conflict resolutions for later upgrades. Git cannot reuse every conflict type, including some modify/delete cases; enforce the explicit path exclusions each time. Stay on the upgrade branch through resolution, validation, and handoff.

Resolve conflicts by category:

- For `.github/`, restore the entire tree from `BASE_HEAD` into both the index and worktree.
- For top-level `enterprise/`, remove the entire tree from the merge result and index.
- For `litellm/cortecs`, restore only the index gitlink from `BASE_HEAD`; do not restore or check out the submodule worktree and never run `git submodule update`.
- Preserve the fork's `.gitmodules` entry and URL for `litellm/cortecs` so an upstream change cannot detach or redirect it.
- For core code and tests, inspect the merge base, fork side, and upstream side. Integrate upstream changes while preserving the intent and coverage of every fork fix. Never use blanket `ours` or `theirs` resolution.

When upstream independently implements a fork fix, retain the upstream implementation only after verifying semantic equivalence, including edge cases covered by fork tests. Remove truly redundant fork code rather than carrying two implementations, and record that decision in the existing catalog and handoff. Retain regression coverage even when a fork patch is superseded. Keep adaptations focused on affected behavior; broad refactors and whitespace churn would increase future conflicts.

After resolving each core conflict, stage the resolved path. Leave `MERGE_HEAD` present and do not commit.

## 5. Audit invariants and fork fixes

Before tests, verify all of the following:

- no unmerged entries remain
- `git diff BASE_HEAD -- .github` is empty
- the staged `litellm/cortecs` gitlink equals the recorded baseline gitlink
- the submodule checkout and pre-existing work are unchanged, with only deliberate evaluator documentation edits and identified test-generated artifacts added
- `.gitmodules` still defines the original `litellm/cortecs` path and URL
- no tracked or untracked top-level `enterprise/` tree remains
- the merge result contains no accidental changes outside the upstream merge, deliberate conflict resolutions, and required exclusions

For every fork-changed path from the `COMMON_BASE..BASE_HEAD` inventory, compare the original fork patch with the final result relative to `TARGET_COMMIT`. Confirm each fork hunk is either:

1. still present,
2. deliberately adapted to the new upstream code, or
3. replaced by an upstream implementation proven semantically equivalent.

Pay special attention to modify/delete conflicts, renamed files, tests removed upstream, configuration defaults, authentication, routing, callbacks, database behavior, and public API contracts. Do not silently drop a fix because its old context no longer applies.

## 6. Validate and hand off

Run evaluator regressions relevant to the preserved fixes, focused core tests for conflict-resolved or adapted behavior, and repository-required checks practical for the upgrade. Follow repository bootstrap guidance when dependencies have not been provisioned.

Use the catalog's `Live: No/Yes/Mixed` labels as a starting point and inspect fixtures and parametrization: even collecting a test can require external services. In-process tests should import this upgraded checkout. Live tests require a router serving this upgraded checkout, configured providers, and valid credentials. The current harness uses `LLM_ROUTER_URL`, `LLM_ROUTER_API_KEY`, and MongoDB configuration (`DOCDB_USER`, `DOCDB_PW`, `DOCDB_URL`, `SERVERLESS_DATABASE`, `SERVERLESS_COLLECTION`). Read current setup instructions rather than assuming these names or commands remain stable.

Reuse a suitable instance or launch the documented local development service when configuration is available. Verify which checkout/version it serves; tests against an older deployment do not validate the upgrade. Do not change a deployed service to make a test pass. When prerequisites are unavailable, complete independent tests and report the exact missing prerequisite and relevant untested regressions; skipped or uncollected live tests are not passes.

The evaluator currently writes `evaluator/system_test/system_test_report.json`. Record existing contents/status before running tests, identify generated changes separately from catalog edits, and preserve pre-existing reports. If a validation command rewrites other generated files, inspect those changes and retain only expected upgrade output.

Verify `.github/`, enterprise exclusion, gitlink, and fork behavior invariants again after validation. Update catalog references for adapted or upstream-superseded fixes without adding a duplicate entry on every upgrade.

Finish with a concise report containing:

- requested and resolved version, tag, and target commit
- `BASE_HEAD`, original branch, and upgrade branch
- conflict resolutions and any fork fixes replaced by upstream equivalents
- missing fixes added to the evaluator catalog, documentation paths, and any uncovered fixes
- confirmation of the `.github/`, `enterprise/`, and `litellm/cortecs` invariants
- tests/checks run and their results
- unresolved risks or items requiring manual review
- an explicit statement that no commit or push occurred and the staged merge is ready for user review

For the next periodic upgrade to benefit from this one, the user's eventual manual commit must preserve this merge's upstream parent. Explain this at handoff; do not create that commit yourself. Evaluator documentation edits are separate uncommitted submodule changes and need separate manual review/commit handling. A completed no-op rerun must not add duplicate catalog rows, repeat a merge, or rewrite unchanged documentation. Existing unresolved validation failures still need to be reported.

If validation fails, leave the reviewable merge state intact and report the exact failure. Do not abort the merge or discard resolved work unless the user explicitly requests it.
