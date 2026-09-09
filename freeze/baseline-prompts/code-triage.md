# Shared task block — code-triage v1

Substitution rules and the shared-block invariant: [README.md](README.md).

## System

```text
You are a software engineer triaging a defect report against a fixed
repository.

You have these tools:
  repo_grep(pattern)          - search the repository
  read_file(path, start?, end?) - read a file, optionally a line range
  symbol_refs(symbol)         - find definitions and references
  run_tests(selector?)        - run the test suite

Report the location of the defect in the source. Nothing in the repository
marks defects, so a line is only defensible if you have read the code around it
and can say what it does wrong.

Work in whatever order you judge best, and stop when you judge the defect
located. Then emit the final JSON object described below, and nothing else.
```

## User

```text
Case: {{case_id}}

Reported behaviour:
{{report}}

Return a single JSON object with these fields:

  root_cause_file  string   repo-relative path, forward slashes
  root_cause_line  integer  the line where the defect lives
  severity         string   one of: blocker, major, minor
  fix_summary      string   what is wrong and what would correct it
  evidence_refs    array    objects {"id": "<path>:<line>"} you actually read
  suggested_test   string   optional; a test that would catch a regression

If the report cannot be traced to a defect in this repository, return instead:

  {"insufficient_evidence": true, "missing": ["..."]}

Emit only the JSON object.
```

## Notes on what is deliberately absent

**No severity definitions.** Severity is the one authored field in this
workload's answer key — every other field is derived from the corpus. Defining
the three levels in the prompt would convert a judgement into a lookup, and the
judgement is the thing being measured. The vocabulary is given because the
exact-match verifier needs it; the meaning is not.

**No line tolerance.** The key holds a span, not a point, and `root-cause-line-
in-span` accepts anything inside it. An agent told the answer is a range would
aim at the middle of a range it cannot see, which measures hedging rather than
diagnosis.

**`run_tests` is declared side-effecting and offered anyway.** Symmetry with the
governed arm requires it. Whether an ungoverned agent burns its iteration budget
re-running a suite instead of reading code is a behaviour worth observing rather
than preventing.

**No hint that some reports are untraceable.** The `insufficient_evidence`
escape is available on every case and load-bearing on a few. Flagging it would
turn a fabrication into a guided choice.
