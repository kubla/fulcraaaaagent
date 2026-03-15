---
name: fulcra-personal-context
description: Retrieves and summarizes personal context from Fulcra / Context — bootstrap user info, resolve calendars and metrics, summarize last night’s sleep, recent workouts, and recent location visits, and maintain a markdown memory file of durable user facts and named places. Use when grounding an agent in a user’s recent life state or when working with Fulcra data, Context data, sleep, workouts, calendars, metrics, or location history.
compatibility: Requires uv, Python 3.11+, internet access to Fulcra, and a browser for first-time login. Runs scripts/fulcra_agent.py with uv run.
license: Apache License 2.0
metadata:
  author: Michael J.J. Tiffany
  entrypoint: scripts/fulcra_agent.py
  memory-file: fulcra-agent-memory.md
---

# Fulcra Personal Context

## When to use this skill

Use this skill when the task involves Fulcra personal data or when the agent should ground itself in the user’s recent life state. Typical triggers:

- Fulcra / Context / Portal data
- recent personal check-ins
- last night’s sleep
- recent workouts
- recent location visits
- calendars the user cares about
- selected metrics and custom metrics
- durable memory about named places and user-specific meaning

## Core model

This skill has three parts:

1. `scripts/fulcra_agent.py` retrieves current truth from Fulcra and returns normalized JSON.
2. `fulcra-agent-memory.md` stores durable, user-specific learned facts in Markdown.
3. This `SKILL.md` defines the SOP for when to run the script, how to interpret results, and how to update memory.

## Files in this skill

- `scripts/fulcra_agent.py` — single Python entrypoint; run with `uv run`
- `references/REFERENCE.md` — command contract, algorithms, and implementation details
- `references/MEMORY.md` — memory schema and update SOP
- `assets/fulcra-agent-memory.template.md` — starter memory template

## Standard workflow

### 1. Ensure auth is available

Start with:

```bash
uv run scripts/fulcra_agent.py auth status
```

If auth is missing or expired, run:

```bash
uv run scripts/fulcra_agent.py auth login
```

The script prints login instructions to `stderr` and emits machine-readable JSON to `stdout`.

### 2. Bootstrap memory when needed

If `./fulcra-agent-memory.md` is missing, sparse, or stale, run:

```bash
uv run scripts/fulcra_agent.py bootstrap
```

Then update `./fulcra-agent-memory.md` using the SOP in [references/MEMORY.md](references/MEMORY.md).

Bootstrap is the standard way to seed:

- Fulcra user id
- timezone
- periods of day
- location resolution preferences
- selected calendars
- selected metrics
- resolved calendar names
- resolved metric descriptions where available
- service status

### 3. Use the smallest command that answers the task

For broad grounding, run:

```bash
uv run scripts/fulcra_agent.py checkin
```

For focused follow-up, run one of:

```bash
uv run scripts/fulcra_agent.py sleep
uv run scripts/fulcra_agent.py visits
uv run scripts/fulcra_agent.py workouts
```

### 4. Enrich script output with memory

The script returns Fulcra truth and deterministic transforms.
The memory file adds semantic meaning:

- place names like `Home`, `Gym`, or `Parents`
- notes about how the user thinks about those places
- user-facing names for custom metrics
- stable calendar preferences
- confirmed facts worth reusing in future sessions

### 5. Update memory when the task teaches something durable

Write back durable facts when the agent learns something the user will want remembered later:

- a repeated reverse-geocoded place now has a personal name
- a custom metric now has a human meaning
- a preferred or ignored calendar has been made explicit
- the user has clarified a stable routine or place fact

## Command quick reference

### Auth

```bash
uv run scripts/fulcra_agent.py auth login
uv run scripts/fulcra_agent.py auth status
uv run scripts/fulcra_agent.py auth logout
```

### Data and summaries

```bash
uv run scripts/fulcra_agent.py bootstrap
uv run scripts/fulcra_agent.py checkin
uv run scripts/fulcra_agent.py sleep
uv run scripts/fulcra_agent.py visits
uv run scripts/fulcra_agent.py workouts
```

## Output contract

The script writes exactly one JSON object to `stdout` on success.
Diagnostics and human-facing progress messages go to `stderr`.

Treat `stdout` as the source of parseable data.
Use `errors` inside the JSON object to reason about partial results.

## Memory file

The skill keeps durable learned state in:

```text
./fulcra-agent-memory.md
```

Create it from the bundled template if it does not exist:

```text
assets/fulcra-agent-memory.template.md
```

The memory file belongs to the workspace or agent deployment, not to the reusable skill package.

## Place-memory SOP

When `visits` or `checkin` returns repeated unknown places:

1. Read `./fulcra-agent-memory.md` and look for a matching remembered place.
2. Match first on exact reverse-geocoded string, then on centroid and radius.
3. If matched, enrich the result with the remembered label.
4. If unmatched but clearly recurring, add or update a candidate place entry.
5. Ask the user a short naming question once the place is worth remembering.
6. Promote the place from candidate to confirmed when the user answers.

Use concise prompts such as:

- “I keep seeing visits to ‘Planet Fitness, Dover, NH’. Should I remember this as ‘Gym’?”
- “This location appears to be a recurring overnight place. Should I remember it as ‘Home’?”

## Bootstrap and refresh cadence

Use this cadence unless the task calls for something more specific:

- `bootstrap` when memory is missing or stale
- `checkin` for general situational awareness
- `sleep` when the task is about recovery, sleep, or morning planning
- `visits` when the task is about place, errands, presence, movement, or routines
- `workouts` when the task is about exercise, training, recovery, or activity

A good default is to refresh bootstrap facts daily or whenever `timezone`, calendar selection, or selected metrics appear stale.

## Implementation notes for the coding model

- Keep `SKILL.md` lean and operational.
- Put detailed contracts and algorithms in [references/REFERENCE.md](references/REFERENCE.md).
- Put memory structure and writeback rules in [references/MEMORY.md](references/MEMORY.md).
- Keep the Python entrypoint in `scripts/fulcra_agent.py`.
- Use `uv run scripts/fulcra_agent.py ...`.
- Provide helpful `--help` output for the script and each subcommand.
- Keep JSON shapes stable across runs.

## References

- [Implementation reference](references/REFERENCE.md)
- [Memory schema and SOP](references/MEMORY.md)
- [Memory template](assets/fulcra-agent-memory.template.md)
