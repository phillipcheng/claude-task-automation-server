# Ending Criteria Prompts - Unified Prompt Library

## Overview

The **Ending Criteria Prompts** feature is integrated into the unified **Prompt Library** system, allowing users to save and load reusable ending criteria templates alongside other prompt types. This provides a consistent experience across all prompt management.

## Features

✅ **Save Criteria Templates** - Save current ending criteria along with max iterations and max tokens as a named template
✅ **Load Saved Templates** - Use the unified Prompt Library modal to browse and select criteria templates
✅ **Persistent Storage** - Templates stored in database and survive server restarts
✅ **Unified UI** - Same interface for all prompt types (task descriptions, criteria, custom inputs)
✅ **Category Filtering** - Filter prompts by "criteria" category in the library
✅ **Full CRUD** - Create, read, update, and delete criteria templates
✅ **API Support** - Full REST API for programmatic access

## How to Use

### Via Web UI

#### Saving a Criteria Template

1. Fill in your ending criteria, max iterations, and max tokens in the task creation form
2. Click the **💾 Save as Prompt** button next to the criteria field
3. A modal appears with:
   - Title field (required)
   - Category pre-selected as "criteria"
   - Tags field (optional)
   - Content field (pre-filled with your criteria)
4. Enter a descriptive title and click **💾 Save**
5. The template is now saved in the Prompt Library!

#### Loading a Saved Template

1. Click the **📚 Load Prompt** button next to the criteria field
2. The Prompt Library modal opens
3. Use the category filter dropdown to select "criteria" (or search by keywords)
4. Click **✓ Use This** on your desired template
5. All fields are automatically populated:
   - Ending criteria text
   - Max iterations
   - Max tokens

### Via API

#### Save a Criteria Prompt

```bash
curl -X POST "http://localhost:8000/api/v1/prompts" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Build Success Test",
    "content": "Build runs successfully with zero errors and all tests pass",
    "category": "criteria",
    "criteria_config": {
      "criteria": "Build runs successfully with zero errors and all tests pass",
      "max_iterations": 15,
      "max_tokens": 50000
    }
  }'
```

#### List All Criteria Prompts

```bash
curl "http://localhost:8000/api/v1/prompts?category=criteria"
```

#### Get a Specific Prompt

```bash
curl "http://localhost:8000/api/v1/prompts/{prompt_id}"
```

#### Update a Prompt

```bash
curl -X PUT "http://localhost:8000/api/v1/prompts/{prompt_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "criteria_config": {
      "criteria": "Updated criteria",
      "max_iterations": 20,
      "max_tokens": 60000
    }
  }'
```

#### Delete a Prompt

```bash
curl -X DELETE "http://localhost:8000/api/v1/prompts/{prompt_id}"
```

## Implementation Details

### Database Schema

**Table:** `prompts`

New column added:
- `criteria_config` (JSON): Stores the ending criteria configuration
  ```json
  {
    "criteria": "Success condition description",
    "max_iterations": 20,
    "max_tokens": 50000
  }
  ```

### API Endpoints

All endpoints are under `/api/v1/prompts`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/prompts` | Create a new prompt/template |
| GET | `/prompts` | List all prompts (supports `?category=criteria` filter) |
| GET | `/prompts/{id}` | Get a specific prompt |
| PUT | `/prompts/{id}` | Update a prompt |
| DELETE | `/prompts/{id}` | Delete a prompt |
| POST | `/prompts/{id}/use` | Mark prompt as used (increments usage count) |

### Files Modified

1. **app/models/prompt.py** - Added `criteria_config` JSON column
2. **app/schemas.py** - Updated `PromptCreate`, `PromptUpdate`, `PromptResponse` with `criteria_config` field
3. **app/api/endpoints.py** - Updated create and update endpoints to handle `criteria_config`
4. **static/index.html** - Added UI controls and JavaScript functions for save/load functionality
5. **migrations/add_criteria_config_to_prompts.sql** - Database migration script

## Example Use Cases

### Use Case 1: Standard Build Task
```json
{
  "title": "Standard Build Success",
  "criteria_config": {
    "criteria": "Build completes successfully with zero errors and warnings",
    "max_iterations": 15,
    "max_tokens": 40000
  }
}
```

### Use Case 2: File Creation Task
```json
{
  "title": "File Creation Task",
  "criteria_config": {
    "criteria": "File exists with correct content and format",
    "max_iterations": 10,
    "max_tokens": 20000
  }
}
```

### Use Case 3: Test Suite Success
```json
{
  "title": "All Tests Pass",
  "criteria_config": {
    "criteria": "All unit tests, integration tests, and e2e tests pass successfully",
    "max_iterations": 25,
    "max_tokens": 80000
  }
}
```

### Use Case 4: Code Refactoring
```json
{
  "title": "Refactoring Complete",
  "criteria_config": {
    "criteria": "Code is refactored, all tests still pass, and code quality metrics improved",
    "max_iterations": 30,
    "max_tokens": 100000
  }
}
```

## Benefits

1. **Time Saving** - No need to re-type common criteria patterns
2. **Consistency** - Ensures same criteria and limits are used for similar tasks
3. **Reusability** - Build a library of common task completion patterns
4. **Team Collaboration** - Share criteria templates across team members
5. **Best Practices** - Standardize iteration/token limits for different task types

## Testing

The feature has been tested with the following scenarios:

### Test 1: Create Criteria Prompt
✅ Successfully created "Build Success Test" with criteria and limits
✅ Returned complete JSON with all fields populated

### Test 2: Create Second Prompt
✅ Successfully created "File Creation Task" template
✅ Both prompts stored independently

### Test 3: List Criteria Prompts
✅ API returns array of all criteria prompts
✅ Each prompt includes full `criteria_config` object
✅ Category filter working correctly

### Test 4: UI Integration
✅ Dropdown populates on page load
✅ Selecting a template fills all form fields correctly
✅ Save button creates new prompts successfully

## Future Enhancements

Potential improvements for future versions:

- [ ] Prompt categories/tags for better organization
- [ ] Search/filter functionality in dropdown
- [ ] Default/favorite prompts
- [ ] Import/export prompt collections
- [ ] Prompt usage statistics and recommendations
- [ ] Template variables for dynamic criteria

## Migration

To add this feature to an existing installation:

```bash
# Run the migration
mysql -u root -psitebuilder claudesys < migrations/add_criteria_config_to_prompts.sql

# Restart the server
python -m app.main
```

## Conclusion

The Ending Criteria Prompts feature is **fully implemented and tested**. Users can now save and load ending criteria templates through both the web UI and REST API, making task creation faster and more consistent.

---

**Status:** ✅ Complete
**Tested:** Yes
**Production Ready:** Yes
**Documentation:** Complete
