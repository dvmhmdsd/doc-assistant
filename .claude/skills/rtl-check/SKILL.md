---
name: rtl-check
description: Validates Arabic RTL layout integrity. Checks for logical Tailwind properties (ps, me) and ensures directional UI elements (back arrows, etc.) are handled.
user-invocable: true
---

## Protocol

1. **Logical Properties:** Ensure `pl-*` is replaced with `ps-*` and `mr-*` with `me-*`.
2. **i18n Alignment:** Verify all text uses `t('key')` from `use-intl` (NOT `next-intl`).
3. **Mirroring:** Identify UI elements that should flip in RTL (e.g., breadcrumb arrows) and those that shouldn't (e.g., media play buttons).
4. **Font Loading:** Check if the specific Arabic typeface is applied correctly via CSS variables.
