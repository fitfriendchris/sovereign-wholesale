# Engine Archetype Template

Use this template when defining a new revenue-engine archetype. Save as
`prompts/engines/<engine_id>.md`. Strategy Manager pulls from this directory when
designing a Project of this engine type.

---

```yaml
engine_id: <kebab-case>
display_name: <Human-readable>
one_liner: <what this engine does in one sentence>

target_buyer:
  who: <who pays>
  pain: <what hurts enough they'll pay>
  willingness_to_pay_usd_range: [<low>, <high>]

revenue_model:
  primary: <one_time | subscription | commission | per_lead | escrow>
  rationale: <why this model fits the buyer>

standard_milestones:
  - id: m1
    name: <…>
    typical_hours: <n>
    acceptance: <how we know it's done>
  - id: m2
    ...

typical_kpis:
  - <KPI 1, with target>
  - <KPI 2, with target>

common_kill_criteria:
  - <measurable, e.g. "no closed deals within 30 days of launch">

recommended_tech_stack:
  - <tool / service>
  - <tool / service>

owner_manager: <which Manager typically owns Projects in this engine>
contributors:
  - role: <Manager>
    when: <which milestone>

compliance_hot_spots:
  - <flag>: <why it matters>

typical_budget_usd: <n>
time_to_first_dollar_days: <n>

skills_to_consult:
  - state/skills/<skill>.md
  - state/skills/<skill>.md

playbook_steps:
  - <step 1>
  - <step 2>
  - <step 3>
```
