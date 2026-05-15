---
name: visual-regression-check
description: Capture and compare before/after UI screenshots using Playwright MCP tools. Use for visual regression checks, screenshot evidence, UI edit validation, and before-after diffs.
user-invocable: true
argument-hint: "[route-or-screen] - Optional route/screen to capture (e.g. '/', '/travelers', 'flight search form')"
---

# Visual Regression Check Skill

## When to Use

Use this skill whenever a task changes UI behavior or styling.

- Component/layout/style edits in src/**/\*.tsx, src/**/_.jsx, src/\*\*/_.css
- MUI wrapper migrations and token/style refactors
- Accessibility-related UI changes that can alter visual state
- Any request mentioning screenshot, regression, or before/after validation

## Required Tools

- Playwright MCP UI tools for browser navigation and screenshots

## Workflow

### 1. Identify Visual Scope

Determine which routes/states changed and capture both desktop + mobile views.

Minimum scope:

- 1 desktop screenshot per changed screen/state
- 1 mobile screenshot per changed screen/state

### 2. Capture Baseline (Before Editing)

Use Playwright MCP tools to open the target route/state and capture baseline screenshots.

Save files under:

- artifacts/visual/before/<screen>-desktop.png
- artifacts/visual/before/<screen>-mobile.png

### 3. Apply Code Changes

Perform the requested edits.

### 4. Capture Final (After Editing)

Use the same route/state and viewport sizes as baseline.

Save files under:

- artifacts/visual/after/<screen>-desktop.png
- artifacts/visual/after/<screen>-mobile.png

### 5. Compare and Report

Compare before/after pairs and summarize:

- expected changes
- unexpected changes
- screens that need follow-up

### 6. Stage Evidence

Stage at least one before and one after screenshot when UI files are staged.

Store screenshot evidence in the repository under:

- artifacts/visual/before/\*.png
- artifacts/visual/after/\*.png

## Naming Convention

Use predictable names to simplify review:

- <route-or-feature>-desktop.png
- <route-or-feature>-mobile.png

Examples:

- artifacts/visual/before/home-desktop.png
- artifacts/visual/after/home-desktop.png
- artifacts/visual/before/travellers-mobile.png
- artifacts/visual/after/travellers-mobile.png

## Output Checklist

- [ ] Baseline screenshots captured before edits
- [ ] Final screenshots captured after edits
- [ ] Desktop + mobile included
- [ ] Unexpected diffs documented
- [ ] Screenshots staged for UI-related commits
