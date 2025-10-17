# MVC Refactoring - Planning Documents

## Quick Links

1. **[Architecture Proposal](01-architecture.md)**
   - MVC structure overview
   - Directory layout
   - Layer responsibilities
   - Benefits and rationale

2. **[Consistent CLI Options](02-consistent-options.md)**
   - Current inconsistencies
   - Proposed standard options
   - Command-specific standardization
   - Deprecation plan

3. **[Output Formats](03-output-formats.md)**
   - TUI vs Plain mode philosophy
   - Example outputs for all commands
   - Color scheme
   - Icons and Unicode handling
   - Implementation examples

4. **[Migration Plan](04-migration-plan.md)**
   - 8-week phased approach
   - Step-by-step implementation guide
   - Testing strategy
   - Risk mitigation
   - Success metrics

5. **[Before & After Comparison](05-before-after.md)**
   - Visual comparisons of current vs proposed output
   - Side-by-side examples for all command types
   - Improvements summary

6. **[Models and Type Resolution](06-models-and-types.md)**
   - Pydantic models for all entities
   - Userish/Folderish resolver pattern (like Git's "committish")
   - Type safety and validation
   - Flexible user/folder resolution across commands

## Goals

### Primary Goals
- ✨ **Consistent formatting** across all commands
- 🎨 **Rich TUI interface** when attached to terminal
- 📝 **Simple plain output** when piped or scripted
- 🔧 **Standardized options** for similar operations
- 🧪 **Better testability** with clear separation of concerns

### Secondary Goals
- 📊 Multiple output formats (JSON, CSV, table, list)
- 🎯 Improved error messages and user feedback
- 🚀 Better performance through streaming
- 📚 Comprehensive documentation

## Quick Start

To review these documents:

```bash
# View in your editor
code _work/planning/

# View in terminal with less
less _work/planning/01-architecture.md

# View with syntax highlighting (if you have bat)
bat _work/planning/03-output-formats.md

# Generate rendered preview (if you want to create it)
./_work/planning/render.sh
```

## Decision Points

Before proceeding, we need to decide:

1. **Architecture**: Approve the MVC structure? Any changes needed?
2. **Options**: Agree on standard options? Any additions/changes?
3. **Output**: Happy with TUI vs plain formatting approach?
4. **Timeline**: Does 8-week plan seem reasonable?
5. **Testing**: Coverage target of 80-90% acceptable?

## Next Steps

After reviewing:

1. Discuss and refine proposals
2. Get stakeholder buy-in
3. Create Phase 0 implementation branch
4. Begin implementation (start with base classes)
5. Iterative development following migration plan

## Questions to Consider

- Should we support `--format json` from day one or add later?
- Do we want interactive features (like selecting from list with arrow keys)?
- Should there be a config file for output preferences?
- Do we want to add pagination/less-like scrolling for large outputs?
- Should we support themes/color schemes?

## Notes

- All code should remain backward compatible until 2.0.0
- Feature flags will control new vs old behavior during transition
- Documentation must be updated in lockstep with code changes
- Each phase should be independently releasable
