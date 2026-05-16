---
name: audit-fe
description: Performs a production-ready audit of React 19 components for UI/UX consistency, accessibility (ARIA), and code smells like "God Components" or prop drilling.
user-invocable: true
argument-hint: "[component-path] - Optional path to a specific file or directory to audit"
---

## Protocol

1. **Structural Audit:** Identify components >150 lines or missing `Suspense` boundaries.
2. **React 19 Patterns:** Verify usage of the `use` hook for data and `Action` patterns for forms.
3. **Design Tokens:** Flag any hardcoded colors/spacing not found in `src/app/styles.css` (Tailwind v4 uses CSS `@theme` — there is no `tailwind.config.js`).
4. **Business logic:** Detect and report any business logic in components that should be in hooks or context.
5. **Visual Regression Evidence:** For UI changes, require screenshots before and after edits (desktop + mobile) captured with Playwright MCP tools.
6. **Regression Reporting:** Include a concise summary of expected vs unexpected visual differences.
