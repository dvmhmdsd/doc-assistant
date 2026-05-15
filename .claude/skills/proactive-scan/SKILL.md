---
name: proactive-scan
description: Scans a feature area or file for proactive improvement opportunities — misplaced files, raw MUI usage, types in wrong modules, missing factories, stale deps, i18n gaps. Returns a prioritized list of small PRs to open.
user-invocable: true
argument-hint: "[path] - Feature dir or file to scan (e.g. src/features/hotels)"
---

## Protocol

You are acting as a proactive senior engineer scanning an area of the codebase for improvements that should be made — not because a ticket exists, but because they make the codebase better and prevent future bugs.

### 1. File Co-location Check

- Are hooks, types, API calls, and components for this feature inside the feature's own directory (`src/features/<name>/`)?
- Flag any feature-specific files living in `src/hooks/`, `src/components/`, or `src/types/` generics.
- **Output:** list of files to move, grouped by type (hooks / types / API / icons).

### 2. Raw MUI Leakage Check

- Scan for direct imports from `@mui/material` (e.g. `Typography`, `Card`, `Avatar`, `Select`, `Slider`, `Dialog`).
- Check which of these have project wrappers in `src/components/`.
- **Output:** table of raw MUI imports → whether a wrapper exists → action (use wrapper / create wrapper).

### 3. Types-in-Context Check

- Are any types or interfaces exported from Context files (`*Context.ts`, `*ContextProvider.tsx`)?
- **Output:** list of types to extract to a dedicated types module.

### 4. Inline Styles & Token Check

- Look for hardcoded hex colors, px values, or repeated `sx={{ ... }}` patterns that should be Tailwind tokens or wrapper props.
- **Output:** list of instances with suggested token replacement.

### 5. Missing Fishery Factories

- Check `src/tests/factories/` for factories covering domain objects used in this feature.
- List domain objects (response shapes, form types) that lack a factory.
- **Output:** list of factories to create.

### 6. i18n Gap Check

- Are there any hardcoded user-facing strings (not using `useTranslations`) in the scanned files?
- Run `npm run validate-translations` to check en.json / ar.json are in sync.
- **Output:** list of hardcoded strings with suggested translation key names.

### 7. Component Size & Concern Check

- Flag any component >150 lines or mixing business logic with render.
- Suggest extraction: what should become a hook, what should become a subcomponent.
- **Output:** refactor candidates with a one-line description of what to extract.

### 8. npm audit (if scanning broadly)

- Note: run `npm audit` and flag any high/critical vulnerabilities as a separate PR candidate.

### 9. Quality Check

- Flag any anti-patterns: large context providers, deeply nested components, excessive prop drilling, missing error handling, etc.
- Use the `/vercel-react-best-practices` skill to ensure adherence to best practices in React development & `/vercel-composition-patterns` skill to ensure components are composed in a maintainable and scalable way.
- Use `/security-reviewer` agent to flag any security issues in the code.
- Use `/simplicity-reviewer` agent to flag any code that could be simplified for better readability or maintainability.
- Use `/standards-reviewer` agent to ensure code adheres to the project's coding standards and conventions.
- Use `/performance-reviewer` agent to identify any potential performance issues in the code.
- Use `/audit-fe` skill for a comprehensive audit of the frontend codebase, checking for UI/UX consistency, accessibility, and code smells.
- Use `/architect` agent to evaluate the overall architecture of the feature and suggest improvements for scalability and maintainability.
- Use `context7` mcp for any documentation check for react, typescript, tailwind or testing patterns. This will help ensure that the code adheres to the project's established conventions and best practices.
- **Output:** list of best practice violations with suggested improvements.

### 10. Hidden bugs & UX Issues

- Look for any potential bugs: missing dependency arrays in `useEffect`, incorrect state updates, unhandled promise rejections, etc.
- Look for any UX issues: missing loading states, lack of error feedback, non-responsive design elements, etc.
- **Output:** list of potential bugs and UX issues with suggested fixes.

---

## Output Format

Return a prioritized list of **atomic PR candidates** — each should be doable in isolation:

```
## Proactive PR Candidates

### Priority 1 — Quick wins (< 30 min each)
- [ ] Move `src/hooks/useHotelSearch.ts` → `src/features/hotels/hooks/`
- [ ] Move `src/hooks/useRoomCombinations.ts` → `src/features/hotels/hooks/`
- [ ] Replace raw `<Typography>` with `<Text>` in HotelCard.tsx (wrapper exists)

### Priority 2 — Small improvements (30–90 min each)
- [ ] Extract `RoomSelectionTypes` from `HotelContext.ts` → `src/features/hotels/types.ts`
- [ ] Create Fishery factory for `HotelRoom` domain object
- [ ] Add missing Arabic translation keys: `hotels.noRoomsAvailable`, `hotels.selectRoom`

### Priority 3 — Refactors (need a focused session)
- [ ] Split `HotelSummaryPage.tsx` (220 lines) — extract `useHotelSummary` hook
- [ ] Wrap raw `<Dialog>` usage in hotels feature (3 instances, Dialog wrapper exists)
```

Each item should be small enough to be a standalone PR. Do not bundle — atomic is the goal.
