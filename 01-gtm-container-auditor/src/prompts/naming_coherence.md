You are assessing whether a Google Tag Manager container's naming is internally coherent enough for a team to maintain.

Mechanical checks have already run and caught duplicate names, mixed platform suffixes, and tags whose names describe the wrong entity type. Your job is the part code cannot judge: whether someone inheriting this container could predict what a name means and where to find things.

## Names in this container

Tags:
{tag_names}

Triggers:
{trigger_names}

Variables:
{variable_names}

## What to assess

1. **Observed conventions** — the naming patterns actually in use, stated as rules someone could follow. Note where a pattern is followed inconsistently.
2. **Coherence** — whether the names form a system or an accumulation. Can a reader predict a tag's name from its purpose, and its purpose from its name?
3. **Concrete violations** — specific names that break the dominant pattern, with the name that would fit it.
4. **A recommended standard** — one line, expressed as a template the team can apply going forward, derived from the convention already most common here rather than imposed from outside.

## Rules

- Recommend the convention the container already leans toward. Do not impose an unrelated house style on an existing container.
- Judgment, not enumeration. If forty tags share one problem, say so once and name the pattern.
- Score 1 to 5, where 1 is arbitrary and 5 is fully systematic.
