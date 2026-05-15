---
name: feature-scaffold
description: Scaffolds a new feature module with the standard directory structure under src/features/.
user-invocable: true
argument-hint: "[feature-name] - Name of the new feature module to scaffold (e.g., 'rewards')"
---

## Protocol

1. **Create Directory Structure**: Generate the standard feature module layout:

   ```
   src/features/[name]/
   ├── components/     # Feature-specific React components
   ├── hooks/          # Feature-specific hooks and query options
   ├── types/          # Feature-specific TypeScript types
   ├── utils/          # Feature-specific utility functions
   └── index.ts        # Public API barrel export
   ```

2. **Generate Boilerplate Files**:
   - `index.ts` — barrel export for the feature's public API
   - `hooks/use[Name]QueryOptions.ts` — query options skeleton following the `queryOptions()` pattern
   - `types/types.ts` — feature-specific type definitions

3. **Follow Project Conventions**:
   - Use `@/` alias for all imports from `src/`
   - Use `use-intl` for any translatable strings (NOT `next-intl`)
   - API types come from `src/types/codegen.ts` — never duplicate them
   - Use `npm` as the package manager (NOT `pnpm` or `yarn`)

4. **Optional Extras** (create only if requested):
   - `contexts/[Name]Context/` — context folder with `[Name]Context.ts` + `[Name]ContextProvider.tsx` + `index.ts`
   - Route file in `src/app/routes/` — TanStack Router file-based route with loader

5. **Post-Scaffold**:
   - Add any new i18n namespace keys to `messages/en.json` and `messages/ar.json`
   - Run `npm run validate-translations` to verify translation parity
