# Custom Preface and Suffix Templates

## Overview

The `generate_context` tool now supports custom preface and suffix text via external template files.

## New Command Line Options

```bash
--preface-file PATH    Path to file containing custom preface text
--suffix-file PATH     Path to file containing custom suffix text
```

## Usage

### Default Behavior (No Custom Templates)

```bash
generate_context --dry-run
```

Uses the built-in default preface and suffix text.

### Custom Preface

```bash
generate_context --preface-file my_preface.txt --dry-run
```

### Custom Suffix

```bash
generate_context --suffix-file my_suffix.txt --dry-run
```

### Both Custom

```bash
generate_context --preface-file my_preface.txt --suffix-file my_suffix.txt --dry-run
```

## Template Files

### Preface Template

The preface template supports the `{chunk_count}` placeholder, which will be replaced with the actual number of chunks.

Example `my_preface.txt`:
```
You are reviewing a codebase split into {chunk_count} parts.
Please analyze the code carefully.

When you receive chunk_{chunk_count:04d}.txt (the last chunk), provide a summary.
```

### Suffix Template

The suffix template is inserted as-is at the end of the last chunk.

Example `my_suffix.txt`:
```
End of context. Please provide your analysis now.
```

## Example Template Files

Two example template files are included:
- `preface_template_example.txt` - Contains the default preface text
- `suffix_template_example.txt` - Contains the default suffix text

You can copy and modify these as starting points for your custom templates.

## Notes

- Template files must be UTF-8 encoded text files
- The preface template is inserted after the header (timestamp, project root) and before "--- END PREFACE ---"
- The suffix template is added as the final line of the last chunk
- If a template file doesn't exist or can't be read, the tool will exit with an error
- Without custom templates, the tool uses the built-in defaults (maintains backward compatibility)
