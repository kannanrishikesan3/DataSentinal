# Product

## Register

product

## Users

Enterprise security team members using DataSentinel to manage endpoint data-risk
discovery across their organization's fleet (Windows/Linux/macOS). Three roles:

- **Admin** — registers endpoints, creates enrollment tokens, manages scan
  policies, assigns policies to endpoints/groups.
- **Analyst** — triages findings day-to-day: marks false positives, suppresses
  noise, creates exclusion rules, reviews scans and reports.
- **Viewer** — read-only oversight: audits findings, scans, and policies without
  the ability to change anything.

Context: used at a desk, often across a full workday, frequently side-by-side
with other monitoring tools. Sessions are task-driven (triage a finding, check
an endpoint's status, pull a compliance report), not exploratory browsing.

## Product Purpose

DataSentinel discovers PII and secrets left on endpoint filesystems, scores the
risk, and gives security teams one place to see it, triage it, and prove to
auditors it's handled. Success looks like: an analyst can tell within seconds
whether a new finding is real and how bad it is, and an admin can onboard a new
fleet of endpoints in minutes via a reusable enrollment token.

## Brand Personality

Vigilant, precise, unflashy. This is instrumentation for people who are
already good at their job — the interface should feel like it respects that,
the way a well-built monitoring tool (Datadog, Grafana) does: dense with real
signal, fast to scan, never decorative for its own sake. Confidence through
restraint, not through flourish.

## Anti-references

- Generic AI-generated SaaS template look: purple/blue gradients, big rounded
  hero cards, glassmorphism, gradient text, hero-metric-with-sparkline
  clichés — this is the single most important thing to avoid.
- Marketing-site visual language of any kind (this product has no marketing
  surface — everything here is a working tool).
- Legacy enterprise cruft (cramped gray-on-gray forms, tiny unreadable type,
  inconsistent spacing) is also wrong — the goal is Datadog-grade density,
  not enterprise-software staleness.

## Design Principles

1. **Density with clarity** — surface a lot of real data per screen (severity
   breakdowns, tables, filters) the way Datadog/Grafana do, but use type scale,
   spacing rhythm, and grouping — never decoration — to keep it scannable.
2. **Severity is the primary signal, everywhere** — Critical/High/Medium/Low/
   Informational must be instantly, consistently distinguishable across every
   page, chart, and badge, using one shared token set, not per-page color
   choices.
3. **Trust through restraint** — a security tool must read as authoritative
   and calm. No flourish that isn't earning its place; nothing that looks like
   it's selling something.
4. **Fast triage over decoration** — every screen's layout optimizes for the
   analyst's actual next action (is this real? what do I do?), not for visual
   novelty.
5. **One consistent pattern per interaction type** — tables, dialogs, filters,
   and status indicators behave identically everywhere in the app, so nothing
   needs relearning between the ten nav pages.

## Accessibility & Inclusion

Standard WCAG 2.1 AA: sufficient color contrast in both light and dark mode
(severity colors must not rely on hue alone — pair with icon/label/position),
full keyboard navigation, visible focus states, and no motion that can't be
reduced (`prefers-reduced-motion`).
