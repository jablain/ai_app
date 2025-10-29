# generate_context.py - Update Summary

## What Was Implemented

### 1. Custom Template Support

Added ability to customize the preface and suffix text via external files.

#### New CLI Options:
- `--preface-file PATH` - Specify a custom preface template file
- `--suffix-file PATH` - Specify a custom suffix template file

### 2. Template Features

#### Preface Template
- Supports `{chunk_count}` placeholder for dynamic chunk count insertion
- Inserted after the header (timestamp, project root) in chunk 1
- Falls back to built-in default if not specified

#### Suffix Template
- Plain text, no placeholders needed
- Appended as the last line of the final chunk
- Falls back to built-in default if not specified

### 3. Implementation Details

**Modified Functions:**
- `make_preface_lines()` - Now accepts optional `preface_text` parameter
- `add_final_suffix()` - Now accepts optional `suffix_text` parameter
- `chunk_with_preface_and_suffix()` - Passes custom text through to helpers
- `main()` - Loads custom template files if provided

**New Functions:**
- `load_text_file_or_default()` - Loads text from file with error handling

**New Constants:**
- `DEFAULT_PREFACE_TEXT` - Built-in default preface
- `DEFAULT_SUFFIX_TEXT` - Built-in default suffix

### 4. Error Handling

- Exits with code 2 if template file doesn't exist
- Exits with code 2 if template file is not a regular file
- Exits with code 2 if template file can't be read
- Clear error messages to stderr

### 5. Backward Compatibility

- Works exactly as before when no custom templates specified
- All existing tests still pass
- No breaking changes to CLI or behavior

## Files Included

1. **generate_context.py** - Updated script with template support
2. **preface_template_example.txt** - Example preface template (the default)
3. **suffix_template_example.txt** - Example suffix template (the default)
4. **TEMPLATE_USAGE.md** - Documentation for the template feature

## Testing Performed

✅ Default behavior (no templates) works as before
✅ Custom preface file loads and substitutes {chunk_count}
✅ Custom suffix file loads correctly
✅ Both custom files work together
✅ Error handling for missing/invalid files
✅ All discovery modes still work correctly
✅ All output scope options still work correctly

## Usage Examples

### Use defaults (backward compatible):
```bash
generate_context --dry-run
```

### Custom preface only:
```bash
generate_context --preface-file my_preface.txt --dry-run
```

### Custom suffix only:
```bash
generate_context --suffix-file my_suffix.txt --dry-run
```

### Both custom:
```bash
generate_context --preface-file my_preface.txt --suffix-file my_suffix.txt --dry-run
```

### Combined with other options:
```bash
generate_context --discover project --to-project-root \
  --preface-file templates/preface.txt \
  --suffix-file templates/suffix.txt
```
