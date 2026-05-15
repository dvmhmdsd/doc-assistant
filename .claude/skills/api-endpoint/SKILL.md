---
name: api-endpoint
description: Generates a complete API integration layer — API call function, query options, and MSW mock handler.
user-invocable: true
argument-hint: "[endpoint-description] - Description of the API endpoint (e.g., 'GET /trips/:id' or 'POST /bookings')"
---

## Protocol

1. **API Function**: Create the API call function using the configured `api` axios instance from `@/api/api.ts`:

   ```typescript
   import { api } from "@/api/api";

   export const fetchEntity = async (id: string): Promise<EntityType> => {
     const { data } = await api.get(`/endpoint/${id}`);
     return data;
   };
   ```

2. **Query Options** (for GET endpoints): Create a `queryOptions` factory in the appropriate feature's `hooks/` directory:

   ```typescript
   import { queryOptions } from "@tanstack/react-query";

   export const entityQueryOptions = (id: string) =>
     queryOptions({
       queryKey: ["entity", id],
       queryFn: () => fetchEntity(id),
     });
   ```

3. **Mutation Hook** (for POST/PUT/DELETE endpoints): Create a mutation hook with proper cache invalidation:

   ```typescript
   import { useMutation, useQueryClient } from "@tanstack/react-query";

   export const useCreateEntity = () => {
     const queryClient = useQueryClient();
     return useMutation({
       mutationFn: createEntity,
       onSuccess: () => {
         queryClient.invalidateQueries({ queryKey: ["entities"] });
       },
     });
   };
   ```

4. **MSW Handler**: Create an MSW 2.0 handler in `src/tests/mocks/`:

   ```typescript
   import { http, HttpResponse } from "msw";

   export const entityHandlers = [
     http.get(`${BASE_API_URL}/endpoint/:id`, () => {
       return HttpResponse.json(entityFactory.build());
     }),
   ];
   ```

5. **Types**: Use auto-generated types from `src/types/codegen.ts` when available. Only create custom types in the feature's `types/` if needed for frontend-specific shapes.

6. **Conventions**:
   - Query keys follow `[entity, id?, sub-entity?]` pattern
   - Use `@/` alias for all imports
   - Use Fishery factories from `src/tests/factories/` for test data
   - Never edit `src/types/codegen.ts` — it's auto-generated
