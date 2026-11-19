---
title: Verify a Lody Pi profile's packages and skills
description: Check that every package declared in a Pi agent settings.json is installed, count the skills each package contributes, reconcile that against what Pi actually loads, and diff against a baseline so silent changes are caught.
authors:
  - name: ltx15382710886-png
    url: https://github.com/ltx15382710886-png
languages: [en]
tags: [pi, packages, skills, diagnostics, drift]
source: https://github.com/ltx15382710886-png/pi-profile-check
---

# Verify a Lody Pi profile's packages and skills

A Lody Pi session loads its resources through two independent channels, and only one of them is
visible in the desktop app.

| Channel | Supplies | Where it is configured |
| --- | --- | --- |
| Extensions passed with `-e` | extension code: tools, hooks, prompt sections | the extension picker in provider settings |
| `packages` in the agent `settings.json` | skills, prompt templates, themes | the file itself |

A package that exists in only one channel loads half of itself: its tools work while its skills stay
invisible, or the reverse. Nothing reports that. Pi warns about a package it cannot install and keeps
running, and a package filtered with `{"source": …, "skills": []}` looks like a healthy install from
the outside.

This guide checks the profile from outside the harness: every declaration is resolved, every
package's skills are counted, and those counts are reconciled against what Pi actually loads.

## Relevance to Lody

Inside Lody, `settings.json` is the only place package skills come from — the desktop app does not
edit or display that list. Two consequences follow:

- Installing a Pi package into a Lody profile is a file-level operation, so a mistake leaves no trace
  in the UI. The `$`-mention menu does not read `packages`; a skill can be loaded and still not be
  offered there.
- Profiles drift. A package added by a script, a version pin changed by an update, or a package
  directory moved all change what the model can do, without an obvious signal.

The same reconciliation is what a `doctor` command does for other harnesses. Pi ships none, and
`pi list` reports declarations without versions, skill counts, or a comparison against what loaded.

## Prerequisites

- Node.js 20 or newer.
- The Pi CLI for the measurement step. It is discovered from `~/.lody/agent-binaries/pi/*` by highest
  version; `PI_CLI` or `--pi-cli` overrides it. Without one, `--no-measure` still checks declarations.
- Inside a Lody Pi session, `PI_CODING_AGENT_DIR` already points at that profile. **Outside one it
  does not**, so the checker refuses to guess: pass `--agents-dir <dir>`, or `--default-dir` for the
  terminal Pi profile at `~/.pi/agent`.

## Usage

```sh
git clone https://github.com/ltx15382710886-png/pi-profile-check
cd pi-profile-check

node bin/pi-profile-check.mjs                    # inside a Lody Pi session
node bin/pi-profile-check.mjs --default-dir      # terminal Pi profile
node bin/pi-profile-check.mjs --update-baseline  # accept the current state as the baseline
node bin/pi-profile-check.mjs --drift-ok         # print drift, still exit 0
node bin/pi-profile-check.mjs --json             # machine-readable
```

What it reports, per package: where the declaration resolves to, the installed version, whether a
pinned version matches, and how many skills the package contributes. Then the extensions Lody injects
by path, the declared-versus-loaded skill totals, and any difference from the baseline.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | clean |
| `1` | problem: a package is missing, a pinned version does not match, fewer skills load than are declared, or an injected extension path is gone |
| `3` | drift only: the profile differs from the baseline, nothing is broken |
| `2` | usage error, including "no agent directory given" |

Problems always win over drift. Drift has its own code so CI can tell "look at the baseline" from
"this is broken": after an update or a package change the profile is expected to drift, and failing
that with the same code as a broken install teaches people to ignore the check.

## Verification

The comparison that matters is *fewer skills loaded than declared*. Reproduce it without installing
anything else:

```sh
mkdir -p <tmp>/agent <tmp>/pkg/skills/one
printf '{"name":"p","version":"1.0.0","pi":{"skills":["./skills"]}}' > <tmp>/pkg/package.json
printf -- '---\nname: one\ndescription: "test"\n---\n' > <tmp>/pkg/skills/one/SKILL.md
printf '{"packages":["<tmp>/pkg"]}' > <tmp>/agent/settings.json
printf '{"skills":[]}' > <tmp>/measured.json

PI_CODING_AGENT_DIR=<tmp>/agent node bin/pi-profile-check.mjs \
  --baseline /dev/null --measure-json <tmp>/measured.json
# declared 1, loaded 0 -> exit 1
```

The repository's own suite (`sh test/run-tests.sh`) covers the same ground plus git sources, relative
paths, the `skills: []` object form, drift and the exit-code plumbing; the one case that needs a real
Pi build is skipped when none is installed.

## Limitations

- **User-level settings only.** The `settings.json` next to the agent directory is read. A project
  `.pi/settings.json` is not, because Pi honours it only after project trust is granted.
- **Local entries are reported, not counted.** `settings.skills` and `settings.extensions` appear as a
  note; because they change what Pi loads, a mismatch they cause shows up as "loaded more than
  declared", never as a failure.
- **Approximate file reading.** The per-package count walks declared roots and expands globs. Anything
  Pi's loader does beyond that is visible only in the measured number.
- **Two Lody internals.** `LODY_PI_EXTENSIONS` and the `~/.lody/agent-binaries/pi/*` layout belong to
  Lody's bundled runtime rather than to public Pi documentation. If either changes, the tool needs a
  patch. It is an unofficial utility, not affiliated with Lody or with Pi.
- The baseline file holds absolute paths; keep it out of version control.
