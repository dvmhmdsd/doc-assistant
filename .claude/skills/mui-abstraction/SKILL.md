---
name: mui-abstraction
description: Generates MUI component abstractions following the project's wrapper pattern. Covers the DZR-1412 epic tasks for consistent, type-safe, RTL-aware component wrappers.
user-invocable: true
argument-hint: "[component-name] - MUI component to abstract (e.g., 'Chip', 'TextField', 'Autocomplete')"
---

## Context

This skill implements tasks from the **DZR-1412 Epic** — abstracting raw MUI v7 imports behind project-specific wrappers. The goal is to centralise styling, enforce RTL/a11y defaults, and reduce direct `@mui/material` coupling across feature code.

## Reference: Existing Abstractions

Already abstracted (do NOT re-create):

- **IconButton** → `src/components/IconButton/IconButton.tsx` (DZR-1414)
- **Alert** → `src/components/Alert/Alert.tsx`
- **Avatar** → `src/components/Avatar/Avatar.tsx`
- **Drawer** → `src/components/Drawer/Drawer.tsx`
- **BackButton** (IconButton) → `src/components/BackButton/BackButton.tsx`
- **ConfirmDrawer** → `src/components/ConfirmDrawer/ConfirmDrawer.tsx`
- **OTPPopup** (Dialog) → `src/components/OTPPopup/OTPPopup.tsx`
- **ProgressStepper** (MobileStepper) → `src/components/ProgressStepper/ProgressStepper.tsx`
- **Snackbar** → `src/components/Snackbar/Snackbar.tsx`
- **PriceChangedModal** (Dialog) → `src/components/PriceChangedModal/PriceChangedModal.tsx`
- **EmailInput** (TextField) → `src/components/Inputs/EmailInput.tsx`
- **CurrencyInput** (TextField) → `src/components/Inputs/CurrencyInput.tsx`
- **TelInput** (mui-tel-input) → `src/components/Inputs/TelInput.tsx`

## Protocol

### 1. Audit Current Usage

Before creating the abstraction, search the codebase for all direct imports of the target MUI component:

```bash
grep -rn "from ['\"]@mui/material['\"]" src/ | grep "<ComponentName>"
grep -rn "from ['\"]@mui/material/<ComponentName>['\"]" src/
```

Document:

- How many files import it directly
- Which props are commonly used
- Any recurring `sx` overrides or patterns

### 2. Create the Wrapper Component

**File structure:**

```
src/components/<ComponentName>/
├── <ComponentName>.tsx    # Wrapper component
└── index.ts               # Barrel export
```

**Wrapper pattern** (follow exactly):

```tsx
import clsx from "clsx";
import { <MuiComponent> as <MuiComponent>Base } from "@mui/material";
import type { <MuiComponentProps> } from "@mui/material";

// Only expose the props actually used in the project.
// Start with commonly-used props from the audit, expand later if needed.
type <ComponentName>Props = Pick<
  <MuiComponentProps>,
  "prop1" | "prop2" | "prop3" | "className"
> & {
  // Add project-specific props here (e.g., custom size mappings, icon overrides)
};

export function <ComponentName>({
  prop1,
  prop2,
  className,
  ...rest
}: <ComponentName>Props) {
  return (
    <MuiComponent>Base
      prop1={prop1}
      prop2={prop2}
      className={clsx("<base-wrapper-styles>", className)}
      {...rest}
    />
  );
}
```

**Barrel export (`index.ts`):**

```ts
export { <ComponentName> } from "./<ComponentName>";
```

### 3. Conventions to Follow

- **Import MUI as base**: `import { Button as ButtonBase } from "@mui/material"` when the wrapper shares the same name.
- **Type-narrow props**: Use `Pick<MuiProps, ...>` to expose only what the project needs. Do NOT re-export the full MUI prop type.
- **Embed project defaults**: Bake in default `sx` overrides, ARIA attributes, or RTL fixes so consumers don't repeat them.
- **RTL awareness**: For directional components (icons, navigation), use `rtl:-scale-x-100` or logical CSS properties (`paddingInlineStart` not `paddingLeft`).
- **Accessibility**: Add default ARIA roles/labels where MUI doesn't provide them out of the box.
- **No barrel index at `src/components/index.ts`**: Each component is imported individually from its folder.
- **Use `@/` alias**: All imports from `src/` use `@/` prefix.
- **Allow `className` on abstractions**: Include `className` in the narrowed props and merge with component defaults using `clsx(baseStyles, className)`.
- **Customization policy**: If a usage has substantial one-off styling, pass it through `className` on the abstraction. If the same customization pattern appears in multiple places, add a typed control prop and implement it internally.
- **Keep `sx` internal by default**: Prefer wrapper-owned `sx` logic and typed control props rather than leaking raw styling APIs.
- **Do NOT create `styled()` wrappers** unless the component requires pseudo-selectors or complex theme-dependent styles (like TelInput). Prefer `sx` prop.

### 3a. Design Decisions (Settled — Do Not Re-open)

These decisions were debated and resolved during DZR-1414. Apply them consistently to all future abstractions.

#### Expose `className` and merge it predictably

Abstractions should accept `className` and merge it with baseline wrapper styles:

```tsx
<MUIButtonBase className={clsx(baseStyles, className)} />
```

**Rule**: expose `className` on wrappers so consumers can extend styling when needed. Keep defaults in the wrapper and merge incoming classes via `clsx`.

#### Parent owns layout — wrapper divs are correct

When a consumer needs to position a wrapped component (e.g. `absolute end-1.5`, `shrink-0`, `justify-self-start`), the correct pattern is a wrapper `<div>` carrying only Tailwind layout classes:

```tsx
<div className="absolute end-1.5">
  <IconButton ...>...</IconButton>
</div>
```

A wrapper div carrying only layout classes (`shrink-0`, `absolute end-1.5`, grid/flex alignment) is correct and intentional. A wrapper div carrying color, typography, or border styling is a smell — revisit the component decomposition.

#### Structural variants for repeated customization patterns (e.g. `disablePadding`)

When the same customization appears in multiple places, encode it as a named boolean or enum prop that translates to internal styles. Keep one-off customizations on `className`; promote repeated patterns to control props.

```tsx
// consumer
<IconButton disablePadding>...</IconButton>

// abstraction — sx is same-system (emotion vs emotion), so specificity is predictable
sx={disablePadding ? { p: 0 } : undefined}
```

#### Custom token colors with pseudo-states → named variant + internal `sx`

When a component needs design-system token colors that are outside MUI's palette (e.g. `--color-text-interactive` with `&.Mui-disabled`), encode them as named color variants in the wrapper. Never leak token strings into consumers.

```tsx
// In the type union
color?: ... | "interactive" | "accent-bordered";

// In the implementation — use a lookup table typed as Record<CustomColor, SxProps<Theme>>
const customColorSx: Record<CustomColor, SxProps<Theme>> = { ... };
```

Use a **type-guard function** to avoid unsafe casts:

```tsx
function isCustomColor(color: string | undefined): color is CustomColor {
  return (
    color !== undefined && (CUSTOM_COLORS as readonly string[]).includes(color)
  );
}
```

**Naming rule for custom colors**: names are provisional until aligned with the design system team. Mark with a `TODO` comment and block adding a third custom color until existing names are confirmed.

**When to add a custom color variant** — all three must be true:

1. Used by ≥ 2 components
2. Cannot be expressed as a standard MUI palette color
3. Token name is stable (design system confirmed)

#### Do NOT expose `component` or `role` props

`component` is a MUI polymorphic escape hatch — exposing it leaks MUI internals. If a consumer needs an icon button that acts as a link, create a separate `IconButtonLink` using `createLink(MuiIconButton)` (same pattern as `ButtonLink` elsewhere in the codebase).

If a decorative icon lives inside a `<button>` and needs wrapping, use a plain `<span>` — not `<IconButton component="span" role={undefined}>`.

#### Type `sx` objects as `SxProps<Theme>`, not `object`

Internal sx constants must be typed as `SxProps<Theme>` from `@mui/material` so invalid MUI sx keys are caught at compile time:

```tsx
import type { SxProps, Theme } from "@mui/material";
const customColorSx: Record<CustomColor, SxProps<Theme>> = { ... };
```

#### No imported interfaces from MUI

Do not import MUI interfaces like `ButtonProps` or `TextFieldProps` directly. Instead, use custom types to create a narrowed prop type that only includes the props the project actually uses. This prevents unintentional coupling to MUI's full prop set and encourages intentional API design.

#### Testing focus: meaningful behavior, not passthrough internals

Do not add tests that only assert whether props are forwarded (or not forwarded) to MUI internals. Avoid low-value wrapper tests.

Test abstractions for:

- Edge cases
- Important prop combinations
- Valid/invalid value boundaries that affect runtime behavior
- Accessibility and RTL behavior when relevant

For test planning and generation, always use the `/tester` agent.

### 4. Complexity Guidelines

**EASY** (simple prop passthrough + defaults):

- IconButton, Chip, Badge, Link, Typography, ToggleButton/ToggleButtonGroup, Checkbox/Radio/RadioGroup/FormControlLabel, Skeleton/CircularProgress/LinearProgress

**MEDIUM** (composition of multiple MUI components or custom logic):

- TextField + InputAdornment, Select + MenuItem + FormControl, Drawer + SwipeableDrawer, Dialog + DialogContent/Title/Actions, Collapse, Slider, Menu, BottomNavigation, Tabs, mui-tel-input

**HARD** (complex interaction patterns):

- Autocomplete (depends on TextField abstraction — complete TextField first)

### 5. Migrate Consumers

After creating the wrapper:

1. **Find all direct imports** of the MUI component across `src/`
2. **Replace** with the new wrapper import: `import { <ComponentName> } from "@/components/<ComponentName>"`
3. **Handle customization at callsites**: use `className` for heavy one-off customizations. If the same customization repeats, introduce a typed control prop on the wrapper.
4. **Verify** no props broke — the wrapper should accept all previously-used props
5. **Ensure full adoption**: all callsites that used the raw MUI component should now use the abstraction
6. **Run checks**: `npm run typecheck && npm run lint && npm run test:related`

### 6. Validation Checklist

- [ ] No direct `@mui/material/<ComponentName>` imports remain in `src/` callsites for the abstracted component
- [ ] Wrapper uses `Pick<>` for type-narrowed props
- [ ] Wrapper accepts `className` and merges it with defaults via `clsx`
- [ ] Repeated customization patterns are modeled as typed control props
- [ ] Default ARIA attributes are set where appropriate
- [ ] RTL is handled for directional elements
- [ ] `npm run typecheck` passes
- [ ] `npm run lint` passes
- [ ] Related tests pass (`npm run test:related`)
- [ ] Tests focus on edge cases and meaningful prop/value combinations (guided by `/tester` agent)
- [ ] No regressions in the component's visual behavior
- [ ] Before/after screenshots captured for affected UI states (desktop + mobile) using Playwright MCP tools

## Workflow

1. Start by using jira-analyzer agent to identify all direct imports of the target MUI component and document usage patterns using the ticket number the user provides.
2. Capture baseline screenshots for impacted UI states using `/visual-regression-check` (desktop + mobile).
3. Create the wrapper component following the established pattern.
4. Migrate all callsites to use the new wrapper, handling customizations with `className` or new control props as needed.
5. Capture final screenshots for the same states and compare against baseline.
6. Validate the implementation against the checklist, ensuring no direct MUI imports remain and that the wrapper is correctly integrated across the codebase.
7. Use the `/architect` agent to review the abstraction for adherence to design principles and consistency with existing wrappers.
8. Use the `/senior-fe` agent to review the code for best practices, maintainability, and potential edge cases.
9. Use the `/tester` agent to plan and generate meaningful tests that cover edge cases and important prop combinations, rather than just prop forwarding.
