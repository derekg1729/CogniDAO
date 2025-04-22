# Task: Define Blotato API Schemas
:type: Task
:status: todo
:project: [[project-blotato-integration]]
:owner:

## Description
Define Pydantic models and generate JSON schemas for the Blotato `/v2/posts` API endpoint based on the provided documentation. This ensures type safety and adherence to the API contract.

Reference API: <https://help.blotato.com/api-reference/publish-post-v2-posts>

## Action Items
- [ ] Define Pydantic model `BlotatoPostRequest` for the main request body.
- [ ] Define nested Pydantic model `BlotatoPostObject` for the `post` field.
- [ ] Define nested Pydantic model `BlotatoContentObject` for the `content` field.
- [ ] Define nested Pydantic model `BlotatoAdditionalPost` for items in `additionalPosts`.
- [ ] Define Pydantic models for each specific `target` type (Webhook, Twitter, LinkedIn, Facebook, Instagram, TikTok, Pinterest, Threads, Bluesky, YouTube) using `Literal` for `targetType` and inheriting common fields if applicable.
- [ ] Define a Union type or use discriminated unions for the `target` field in `BlotatoPostObject`.
- [ ] Use `Enum` for fields with fixed values (e.g., `platform`, `privacyLevel`, `mediaType`, `replyControl`, `privacyStatus`).
- [ ] Add appropriate `Field` descriptions and validation constraints.
- [ ] Create/update `scripts/generate_schemas.py` to include these new models.
- [ ] Run the script to generate `.schema.json` files in `schemas/backend/`.
- [ ] Commit the generated schema files.

## Test Criteria
- Pydantic models pass validation for various valid API request examples.
- Pydantic models raise validation errors for invalid API request structures.
- Running `scripts/generate_schemas.py` successfully outputs `.schema.json` files for all defined Blotato models in `schemas/backend/`.
- The generated JSON schemas accurately reflect the structure and constraints of the Pydantic models.

## Dependencies
- None 