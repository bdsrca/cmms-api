# 09 - Resource Model UI Direction

The portal should feel like a control plane, not a collection of temporary forms.

Current direction:

- Use Environment as the primary resource.
- Put related tools under the Environment detail page:
  - Overview
  - Code Lists
  - Validation Rules
  - Test Console
  - API Examples
  - Usage Logs
  - Settings
- Avoid making every small function a top-level menu item.

Code Lists should use:

- Top command bar
- Environment/category context
- Searchable table
- Row detail blade
- Import modal
- Preview-before-import validation

Next high-value resource tabs:

1. Prompt Version Manager
2. Saved Test Cases
3. Replay from Usage Logs
4. API Key Scopes

Validation Rules v1 is implemented and should remain separate from prompt management. Prompt changes can later consume validation context, but the first reliable layer is post-extraction validation.

AI Output Contract / Schema Manager v1 is implemented and should remain endpoint-level, not environment-level.
