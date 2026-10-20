---
title: Set up tailnet-preview
description: Ask a coding Agent to set up private per-PR preview environments on your own machine.
authors:
  - name: riverscn
    url: https://github.com/riverscn
languages: [en]
tags: [preview-environments, tailscale, docker-compose, github-actions]
source: https://github.com/riverscn/tailnet-preview/blob/a54f9d549665ff44567c521372508103bc57ad53/README.md
license: MIT
---

# Set up tailnet-preview

## Purpose and relevance to Lody

Reuse the setup prompt from [tailnet-preview](https://github.com/riverscn/tailnet-preview) as a Lody Prompt Shortcut. It asks your coding Agent to follow the upstream agent guide and configure private preview environments for pull requests, while collecting steps that require your involvement and keeping secrets out of chat.

## Prerequisites

- A coding Agent in Lody with access to the target application repository and the upstream documentation.
- A GitHub repository you control and an application that runs in containers, preferably with a Docker Compose file.
- An always-on Linux machine with Docker and enough memory for the preview environments, plus a Tailscale account.

Read the upstream [host setup](https://github.com/riverscn/tailnet-preview/blob/main/docs/host-setup.md) and [security guidance](https://github.com/riverscn/tailnet-preview/blob/main/docs/security.md), especially before using a public repository: anyone who can push to the repository can run code on the preview host.

## Usage

1. Create a Prompt Shortcut in Lody using the name and slug in [prompt.yaml](prompt.yaml).
2. Copy [prompt.md](prompt.md) into the shortcut body.
3. Open a conversation for the application you want to configure, select your coding Agent, and use `/tailnet-preview`.
4. Follow the Agent's list of steps requiring your involvement. Enter credentials through the appropriate local or service settings, never in chat.

The prompt is plain text. Its reference to `docs/agent-guide.md` means the [upstream tailnet-preview agent guide](https://github.com/riverscn/tailnet-preview/blob/main/docs/agent-guide.md). No Role, Skill, or file is automatically bound by this shortcut.

## Source and license

[prompt.md](prompt.md) preserves the English README prompt verbatim from upstream commit [`a54f9d5`](https://github.com/riverscn/tailnet-preview/tree/a54f9d549665ff44567c521372508103bc57ad53). Copyright (c) 2026 riverscn; the upstream MIT notice is retained in [LICENSE](LICENSE).
