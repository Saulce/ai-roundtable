# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

Repo: `Saulce/ai-roundtable`.

## Conventions

- **Create**: `gh issue create --title "..." --body-file <file> --label "..."`
- **Read**: `gh issue view <number> --comments`
- **List**: `gh issue list --state open --json number,title,body,labels --jq '...'`
- **Comment**: `gh issue comment <number> --body "..."`
- **Labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number>`

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue labelled `wayfinder:map`; tickets are its child issues.

- **Map**: issue #1, label `wayfinder:map`, holds Destination / Notes / Decisions-so-far / Tickets / Not-yet-specified / Out-of-scope.
- **Child ticket**: an issue with a `Part of #1` line at the top of the body, label `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Listed in the map's `## Tickets` task list.
- **Blocking**: fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body (native issue dependencies only if enabled).
- **Frontier**: `gh issue list --state open` filtered to `Part of #1`; drop any with an open blocker or an assignee; map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, `gh issue close <n>`, then append a context pointer to the map's Decisions-so-far and check the task list item.
