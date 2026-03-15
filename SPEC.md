# Fulcra Personal Context Skill: product spec

## Context

Fulcra already exposes rich personal data through its Python client and developer APIs: authenticated access, user preferences, calendars, workouts, locations, and time-series metrics. The current client is optimized for notebooks and exploratory analysis. Personal agents need a sharper tool: deterministic JSON, fixed semantic commands, and a durable memory layer that turns raw place strings and custom metric ids into user-specific meaning.

The Agent Skills spec gives us a clean packaging model for that tool: a skill directory with a `SKILL.md`, optional `scripts/`, `references/`, and `assets/`, plus a progressive-disclosure structure that keeps the main skill concise and pushes detailed material into referenced files.

## Problem

A strong personal agent needs three things at once:

1. current truth from Fulcra
2. deterministic transforms that reduce noise
3. durable memory of what those truths mean for this specific user

Without a clean split, the system either stays generic and forgetful or becomes personal in a messy, opaque way.

## Product hypotheses

### Hypothesis 1

A very small command surface will outperform a broad CLI for agent reliability.

The command set in this spec is deliberately narrow:

- `auth login`
- `auth status`
- `auth logout`
- `bootstrap`
- `checkin`
- `sleep`
- `visits`
- `workouts`

The agent should usually start with `checkin`, then follow up with one focused command when needed.

### Hypothesis 2

A Markdown memory file will make agent state more legible and more useful than a JSON profile cache for durable user semantics.

`fulcra-agent-memory.md` is designed to hold facts like:

- timezone
- selected calendars and their human names
- known custom metric meanings
- named recurring places such as `Home` or `Gym`

Markdown keeps that memory readable, editable, and auditable.

### Hypothesis 3

The most valuable place-learning loop starts with deterministic location grouping and ends with lightweight user questions.

The script should derive visits and movement from Fulcra location data.
The skill should notice repeated unknown places, ask concise naming questions, and write back durable place memory.

### Hypothesis 4

Bootstrap should be a first-class command.

`get_user_info()` already carries high-leverage defaults such as timezone, periods of day, selected calendars, selected metrics, and service status. A first-class `bootstrap` command lets the agent seed durable memory cleanly in one step. The Fulcra Life API explicitly covers user preferences and related features, while the Python client uses Device Authorization Flow for auth and the library docs show the browser-based `authorize()` pattern used in demo notebooks.

## Product principles

### One strong center of gravity

`checkin` is the center of gravity.

### Fixed semantics

Each command means one thing.
The skill carries the SOP.
The script carries deterministic transforms.

### JSON on stdout, diagnostics on stderr

Agent Skills guidance recommends structured output, concise `--help`, and non-interactive script behavior, with data on stdout and diagnostics on stderr.

### Files for legible state

- auth state: `~/.config/fulcra-agent/auth.json`
- durable learned memory: `./fulcra-agent-memory.md`

### Reuse the current Fulcra auth shape

Fulcra’s Python client uses Auth0 Device Authorization Flow and opens or prints a browser URL for the user to authenticate. This skill adopts that exact login pattern.

## Users and jobs

### Primary user

An AI coding or life-ops agent that should know what is happening in the user’s life right now.

### Secondary user

The human operator who wants the agent’s state and memory to stay inspectable.

### Core jobs

- ground the agent in the last 24 hours
- summarize last night’s sleep
- summarize recent workouts
- summarize recent location visits and movement
- seed durable memory from Fulcra preferences
- learn semantic place names over time

## Skill architecture

```text
fulcra-personal-context/
├── SKILL.md
├── scripts/
│   └── fulcra_agent.py
├── references/
│   ├── REFERENCE.md
│   └── MEMORY.md
└── assets/
    └── fulcra-agent-memory.template.md
```

This matches the Agent Skills directory model and keeps `SKILL.md` short while moving implementation detail into `references/` and memory scaffolding into `assets/`.

## Runtime choice

Use a single self-contained Python script with inline PEP 723 metadata and run it with:

```bash
uv run scripts/fulcra_agent.py <subcommand>
```

The Agent Skills scripting guide recommends self-contained scripts with inline dependencies and shows `uv run` as the preferred way to execute them. It also notes that `uvx` is a strong one-off runner, but this skill is better served by a bundled script with an explicit command path.

### Dependency

Fulcra python library at https://github.com/fulcradynamics/fulcra-api-python/

## Fulcra capability envelope

The skill centers on Fulcra calls that are clearly available today:

- browser-based `authorize()` login via the Python client
- user preferences and related account metadata through `get_user_info()` as used in the bootstrap workflow
- metrics discovery via `metrics_catalog`
- calendar inventory and events via `/calendars` and `/calendar_events`
- Apple workouts via `/apple_workouts`
- location updates and visits via `/apple_location_updates` and `/apple_location_visits`

The script adds deterministic transforms on top of those primitives, especially for location grouping.

## Command model

### `bootstrap`

Purpose:

- seed durable memory in one pass

Behavior:

- call `get_user_info()`
- call `calendars()`
- call `metrics_catalog()`
- return normalized JSON with raw user info and resolved calendar/metric views

### `checkin`

Purpose:

- give the agent one compact board-state summary

Behavior:

- use the user timezone
- summarize last 24 hours
- include current location
- include visits and movement
- include the latest completed sleep cycle
- include workouts
- include the next calendar event in the next 12 hours

### `sleep`

Purpose:

- latest completed main sleep cycle

### `visits`

Purpose:

- last 24 hours of place visits and movement

### `workouts`

Purpose:

- recent workouts from the last 7 days

## Location processing model

This skill uses the exact separation of concerns we discussed:

- the script samples Fulcra truth and groups it deterministically
- the skill remembers what recurring places mean for this user

### Sampling algorithm

For the `visits` command and the location part of `checkin`:

1. sample one point per minute across the last 24 hours
2. call `location_at_time(..., reverse_geocode=True)` for each minute
3. derive a canonical place key from reverse-geocoded address or rounded coordinates
4. collapse contiguous equal keys into segments
5. merge short same-key gaps
6. emit visit segments and movement segments

This yields a stable place timeline that is easy to enrich with memory.

## Memory model

### Auth

The script owns:

```text
~/.config/fulcra-agent/auth.json
```

### Durable memory

The skill owns:

```text
./fulcra-agent-memory.md
```

### Memory content

Persist:

- identity and timezone
- periods of day
- location-resolution preferences
- selected calendars and resolved names
- selected metrics and resolved descriptions
- custom metrics that still need human names
- service status
- confirmed places
- candidate places

### Place learning

The skill should:

1. read `visits` or `checkin`
2. match places against memory
3. enrich known places
4. accumulate recurring unknown places as candidates
5. ask a short naming question when the place is worth remembering
6. write the answer back into memory

## Why this split is clean

The script remains generic and deterministic.
The memory file remains personal and legible.
The skill remains the orchestrator.

That is the center of gravity of the design.

## Script requirements

The Agent Skills scripting guidance makes three decisions especially valuable here:

- the script should accept all input through command-line arguments and never depend on interactive terminal prompts during ordinary execution
- the script should provide concise `--help` output so the agent can learn its interface quickly
- the script should use structured output on stdout and keep diagnostics on stderr

This spec adopts those requirements directly.

## Deliverables in this draft

This draft includes:

- a complete `SKILL.md`
- a detailed implementation reference
- a memory-schema reference
- a starter memory template
- a compact scripts README

The standalone file for `SKILL.md` lives at:

```text
fulcra-personal-context/SKILL.md
```

## Acceptance criteria

### Skill packaging

- the skill validates with `skills-ref validate`
- `SKILL.md` stays concise and operational
- detailed material lives in `references/`
- the memory template lives in `assets/`

### Script behavior

- `uv run scripts/fulcra_agent.py --help` works
- `auth login` performs browser-based Fulcra login
- every successful command emits exactly one JSON object to stdout
- diagnostics remain on stderr
- command semantics are fixed and easy to predict

### Memory behavior

- `bootstrap` can seed `fulcra-agent-memory.md`
- repeated unknown places can accumulate as candidate places
- confirmed places can enrich future visit results
- custom metrics can gain human meaning over time
