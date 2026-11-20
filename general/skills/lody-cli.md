---
title: Lody CLI
description: Official Lody Skill that teaches agents to drive Lody from a terminal with the `lody` CLI — sessions, schedules, agent configs, Roles, MCP servers, projects, machines, and the background runtime.
authors:
  - name: LodyAI
    url: https://github.com/LodyAI
languages: [en]
tags: [lody, cli, skill, sessions, schedules, runtime]
source: https://github.com/LodyAI/Lody/tree/main/skills/lody-cli
license: Apache-2.0
---

`lody-cli` is the official Skill maintained in the [LodyAI/Lody](https://github.com/LodyAI/Lody) repository. It teaches an agent to use the `lody` command (installed with `npm i -g lody` or run as `npx lody`) instead of guessing flags.

## About this resource

The Skill covers both jobs of the CLI: running the Lody runtime on a machine (`lody start`, `lody daemon …`) and acting as a one-shot client for workspace resources. It documents what built-in `--help` leaves out:

- Prerequisites: Node.js version, sign-in without blocking on a browser prompt, and how the desktop app's runtime relates to `lody start`.
- Calling context: which `LODY_*` environment variables are available inside a Lody session, and which arguments an external coding agent must pass explicitly.
- A typical flow for handing a task to a Lody agent, then waiting for and reading the result.
- A command reference for sessions, schedules, agent configs, Roles, MCP servers, workspaces, machines, projects, and the desktop app.
- Failure handling for authentication and dispatch, plus a list of destructive or shared-state commands to confirm with the user first.

The Skill targets the cloud edition of Lody; the open-source local edition is out of scope.

## Read or use

[Original source](https://github.com/LodyAI/Lody/tree/main/skills/lody-cli) — `skills/lody-cli/SKILL.md` in LodyAI/Lody, licensed Apache-2.0.

Install the `skills/lody-cli` directory with your agent's usual Skill installation method. It works in a Lody session or in any external coding agent that supports Skills and can run shell commands. Then ask in plain language, for example “use Lody to start a session on project X and report back” or “list my Lody schedules”.
