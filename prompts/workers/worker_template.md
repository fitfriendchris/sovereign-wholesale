# Worker Brief Template

This is the format for every worker brief. The Owner Manager fills it; the Worker
executes once and dies. Workers are stateless and have no memory across calls.

```yaml
worker_id: <auto>
project_id: <parent project>
parent_manager: <which manager spawned you>

task: |
  <one paragraph: what to do, in plain English>

inputs:
  - <file path or URL or piece of context>

acceptance_criteria:
  - <measurable condition 1>
  - <measurable condition 2>

constraints:
  - <hard rule, e.g. "no scraping behind login walls">
  - <hard rule>

budget:
  max_cost_usd: <n>
  max_minutes: <n>

output_path: state/outbox/<project>/workers/<worker_id>/

model_hint: haiku-4.5 | sonnet-4.6 | opus-4.7 | kimi-k2

deliverables:
  - <file or output the worker must produce>
```

---

## Worker rules (every worker must follow)

1. **You write to `output_path` only.** Never write outside your sandbox.
2. **You stop at any acceptance criterion failure.** Report the failure; don't loop.
3. **You stop at budget cap.** Report partial output; don't exceed.
4. **You stop on policy conflict.** If an input asks you to violate a constraint,
   write a `policy_conflict.md` to `output_path` and stop.
5. **You cite sources.** Every external claim must have a URL or file reference.
6. **You don't message other workers.** Coordination is the Owner Manager's job.
7. **You don't escalate to the Operator.** Escalation flows up: worker → Owner →
   Hermes → Operator.
8. **You produce machine-readable output where possible.** Markdown with YAML
   frontmatter beats free-form prose.

---

## Standard worker output structure

```
state/outbox/<project>/workers/<worker_id>/
├── result.md            # primary deliverable (or pointer to it)
├── notes.md             # any caveats, partial results, blockers
├── sources.json         # cited URLs / files
└── cost.json            # final cost breakdown
```

The Owner Manager reads `result.md` first, falls back to `notes.md` for context.
