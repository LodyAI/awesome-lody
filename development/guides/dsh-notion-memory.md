---
title: Automatic Notion memory for DeepSeek Harness
description: Make new DeepSeek Harness sessions inside Lody recall and save Notion memories automatically, using only $DSH_HOME/AGENTS.md.
authors:
  - name: ltx15382710886-png
    url: https://github.com/ltx15382710886-png
languages: [en]
tags: [memory, notion, mcp, deepseek-harness]
source: https://github.com/ltx15382710886-png/lody-dsh-notion-memory
---

# Automatic Notion memory for DeepSeek Harness

The DeepSeek Harness runtime inside Lody connects to the Notion MCP like any other workspace MCP server, but it has no instruction telling it *when* to use memory. A new session hands over cleanly and then never reads or writes Notion.

This guide makes new DSH sessions recall the user's Notion Memories before answering, and save durable preferences back, with a single file.

## Purpose and relevance to Lody

Lody injects workspace MCP servers into every DSH session, so the tools are already there. What is missing is the policy layer: which questions require a memory lookup, what counts as durable, and where a write belongs. Putting that policy in `$DSH_HOME/AGENTS.md` gives every new session of that provider the same rules without touching the runtime, the profile, or any plugin.

## Prerequisites

- The Notion MCP selected for the workspace, and authenticated as the user, so that `notion://docs/memory` and `id: "memory"` resolve.
- A DeepSeek Harness provider in Lody. The `standard`, `ptc`, and `cordis` agent presets mount the instruction loader; `minimal` does not and is out of scope.
- A Notion Memories database created by the Notion MCP memory tools.

## Usage

1. Find the provider home. It is the directory that holds the DSH `settings.yaml` for that agent configuration, typically under `~/.lody/dsh/providers/<provider-id>/`.
2. Copy the policy template from the linked repository to `$DSH_HOME/AGENTS.md` and replace the placeholder preferences with your own.
3. Keep it short. The loader renders a 65,536-byte baseline and drops broader files before truncating more specific ones.
4. Set `chmod 600` on the file. No restart is needed; new sessions pick it up.

The policy text should cover:

- Recall at the first request of every session, including a bare "hello": read `notion://docs/memory`, then `fetch id="memory"`.
- When to add `memory-search`: questions about previous decisions, preferences, people, deadlines, or anything that spans sessions.
- What never goes into memory: code, diffs, command output, versions, dependency lists, plans, temporary progress, credentials.
- The exact save shape: `parent: "memory"`, no `creation_mode`, one `Type` from `Profile` / `Preference` / `Work` / `People` / `Notes`, topic title, rationale, Notion date mentions.
- Deduplication: search first, update the existing topic page, create only for a genuinely new topic.

## Verification

A verbal claim that memory was read is not evidence. Check the tool trace instead.

1. Create a new session and send only `hello`.
2. Confirm the trace shows `read_mcp_resource` for `notion://docs/memory`, then a Notion `fetch` with `id: "memory"`, both before the reply.
3. Ask a preference question and confirm a `memory-search` call plus a cited Notion link.
4. Send a save request twice from two new sessions and confirm the second one creates nothing.

The linked repository includes `verify.sh`, which decodes the DSH session artifact (`session.v4.jsonl.zstd`) and prints the tool-call sequence, because the Lody transcript API does not expose tool calls.

## Limitations

- The file is injected as a user-role `<system-reminder>` with guidance-level wording ("use them as guidance when applicable"), not as a system prompt. A model can load it and still ignore it. If two fresh sessions both skip the recall calls, the instruction layer is working and the model is not; escalate to a real system-prompt section instead of adding more reminders.
- Editing the file does not change sessions that already started. Verify with new sessions.
- A custom agent preset would allow a real `dsh-persona` prefix, but Lody currently accepts only its four built-in preset values, so that route is unavailable. See the upstream issue linked from the repository.
- An isolated failed tool call can appear as a malformed argument payload followed by a successful retry. Do not read one failure as a policy failure.
