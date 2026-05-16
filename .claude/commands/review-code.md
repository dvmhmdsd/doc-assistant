---
description: Run a full multi-agent code review (architect, senior-fe, tester) with a consistent checklist.
handoffs:
  - label: Architecture Review
    agent: architect
    prompt: |
      Review the requested scope for architecture and maintainability.
      Focus on module boundaries, abstractions, coupling, and long-term scalability.
      Output only findings ordered by severity with exact file paths and concrete fixes.
    send: true
  - label: Frontend Quality Review
    agent: senior-fe
    prompt: |
      Review the requested scope as a React 19 + TanStack expert.
      Focus on correctness, performance, React patterns, query key conventions, and strict type-safety.
      Also suggest simplification opportunities that reduce complexity without behavior changes.
      Output only findings ordered by severity with exact file paths and concrete fixes.
    send: true
  - label: Testing Review
    agent: tester
    prompt: |
      Review the requested scope for testing risks and quality gaps.
      Focus on missing scenarios, brittle tests, insufficient mocks, and regression risk.
      Output only findings ordered by severity with exact file paths and concrete test additions.
    send: true
---

## User Input

```text
$ARGUMENTS
```

You MUST consider the user input before proceeding.

## Workflow

1. Define review scope from `$ARGUMENTS`.
2. If scope is empty, review staged + unstaged changes.
3. Run quick quality checks before review when feasible:
   - `npm run lint`
   - `npm run typecheck`
   - `npm run test:related`
4. Execute handoffs in order: `architect` -> `senior-fe` -> `tester`.
5. Consolidate results into one final review:
   - Findings only, ordered by severity.
   - Include exact file paths.
   - Include suggested fix per finding.
6. If no findings, state that explicitly and list residual risks.
