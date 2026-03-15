# Generated data correctness

Short assessment of what the seeder gets right and what to watch for (especially with MongoDB).

---

## What is correct

- **Enums**: All allowed values are covered (e.g. `posture`: active, suspended, closed; `status`: draft … cancelled). Edge-case strategy ensures at least one row per enum value.
- **Required vs optional**: Required fields are always present; optional fields (e.g. `created_at`) can be null or empty for boundary rows.
- **Boundary rows**: Min/max and null cases are generated (e.g. `"a"`, long strings, `0.0`, `10000000000.0`, `null`) where the schema allows.
- **Types**: Values match declared types (string, number, enum). Validator enforces NOT NULL, enum membership, length, and numeric bounds when the schema supplies them.

---

## Issues in the example (and fixes)

### 1. **`tenants.name` longer than 120 characters**

- **Schema**: `"name": { "type": "string", "maxLength": 120 }`.
- **Problem**: Some generated names are longer than 120 (e.g. long `name_776647xxx…`).
- **Cause**: The MongoDB parser did not read `maxLength` from the JSON schema, so the generator had no length limit.
- **Fix**: The Mongo parser now sets `FieldDef.max_length` from `maxLength` (and `min_length` from `minLength`). Regenerating with the updated code will keep `name` ≤ 120. The validator already rejects rows that exceed `max_length`.

### 2. **`orders.tenant_id` does not reference real tenants**

- **Expectation**: Each `orders.tenant_id` should be one of the `tenant_id` values inserted in `tenants`.
- **Problem**: Generated `orders` use random strings like `"tenant_id_571413..."` that do not appear in the inserted `tenants` list, so the seed is not referentially consistent.
- **Cause**: For SQL we have explicit `REFERENCES` and `foreign_keys` in the normalized schema; the generator uses those to fill FK columns from parent PKs. The MongoDB JSON schema you used does not declare relationships (it’s just `properties` + `required`). So the pipeline does not know that `orders.tenant_id` “points to” `tenants.tenant_id`, and it generates independent strings.
- **Ways to fix** (for future work):
  - **Option A**: Extend the Mongo schema format to allow optional relationship hints (e.g. `tenant_id: { type: "string", ref: "tenants.tenant_id" }`), and have the parser create `ForeignKeyDef`-like metadata so the generator can resolve `tenant_id` from inserted tenants.
  - **Option B**: Infer relationships by name (e.g. `tenant_id` → collection `tenants`, field `tenant_id`) and wire the generator the same way as SQL FKs.
  - **Option C**: Keep schema as-is and document that for Mongo you must either add relationship metadata to the schema or post-process the seed so `orders.tenant_id` is replaced with actual `tenants.tenant_id` values.

---

## Summary

| Aspect              | Correct? | Note |
|---------------------|----------|------|
| Enum coverage       | Yes      | All enum values appear. |
| Required fields     | Yes      | No missing required fields. |
| Optional / null     | Yes      | null/empty used only where allowed. |
| String length       | Now yes  | After parser fix, `maxLength` is enforced. |
| Mongo refs          | No       | `orders.tenant_id` not tied to inserted tenants; needs schema or logic for relationships. |

So: the data is **correct per field-level constraints** (type, enum, required, and now length). For **referential consistency in MongoDB**, the schema or generator would need to express and use parent–child relationships (e.g. `tenant_id` → `tenants.tenant_id`).
