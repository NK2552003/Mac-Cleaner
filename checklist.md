## Checklist

### Optimization
- [ ] Profile duplicate detection and hashing hot paths
- [ ] Reduce redundant filesystem stats during scans
- [ ] Tune scan batching and progress update frequency

### CLI Visuals
- [ ] Refresh duplicate finder table layout for clarity
- [ ] Add consistent status icons and color palette
- [ ] Improve spacing and headings in Rich panels

### Issue Fixes
- [ ] Audit recent bug reports and reproduce top 3
- [ ] Add regression tests for resolved issues
- [ ] Validate error handling for permission-denied paths

### CLI Gaps
- [ ] Add `dashboard` to the top-level subcommand list docstring
- [ ] Align scan `--profile` help text with supported profiles (beginner/developer/professional/designer/student/children)
- [ ] Add `--no-save-history` (and wire into scan/clean) to disable history persistence
- [ ] Add a non-interactive mode to skip first-run profile prompt (default to beginner)

### Safety & Consistency
- [ ] Use safety validation + undo staging for duplicate deletions (avoid raw `unlink`)
- [ ] Make scan `--dry-run` either set global dry-run or remove to avoid no-op confusion
