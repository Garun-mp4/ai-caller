# Product brief — AI Call Agent

## Product

AI Call Agent is a local-first CRM for one operator managing outbound calling. It connects lead records, campaigns, call outcomes and transcripts, scheduled callbacks, and local provider configuration in one workspace.

## Primary user and language

- Primary user: the owner/operator working alone.
- Primary interface language: Russian. English localization is a later product step.
- Primary surface: desktop. Core workflows remain usable on mobile.
- Default theme: light. Dark theme is available as an explicit preference.

## Main operator jobs

1. See today's calling activity and the next work that needs attention.
2. Import, search, filter, review, and update lead records.
3. Prepare a campaign and start it only after confirming contact authorization and compliance.
4. Schedule, reschedule, complete, and review callbacks.
5. Review calls, outcomes, summaries, and transcripts.
6. Configure the agent and inspect local provider status.

## Product constraints

- Local-first MVP backed by FastAPI and SQLite; provider integrations can run in mock mode.
- The UI must not imply that a mock provider is a production dialer.
- Leads marked Do Not Call must remain protected from calling actions.
- Starting a campaign requires an explicit compliance confirmation.
- Settings must not reveal secrets.
- Call/scheduler actions that bypass normal calling hours must be clearly identified as development tools.

## Success criteria

- The operator can understand the current state and next action without decoding raw enum values or provider JSON.
- High-risk actions have clear preconditions, confirmation, pending, success, and error states.
- Tables remain scannable at desktop widths and provide a usable mobile alternative.
- Empty, loading, and failed states explain what happened and what the operator can do next.
