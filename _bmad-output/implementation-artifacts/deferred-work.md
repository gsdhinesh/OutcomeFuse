# Deferred Work

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Publish normalisation `v1` as a normative written specification, not only as code plus test assertions.
  evidence: AD-6 requires the normalisation to be "specified and versioned". The rules are currently pinned by implementation and tests alone, which is enough for two processes of the same codebase but not for a second implementation or a future language port to reproduce them.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Decide how the file-digest route treats case-colliding manifest paths on case-insensitive filesystems.
  evidence: Duplicate detection keys on the exact NFC path, so `["A.PY", "a.py"]` yields two manifest entries for one physical file on Windows/macOS and one rejection on Linux — a cross-platform digest divergence the textual guards do not cover.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Decide how text-mode file digests treat byte-order marks and non-UTF-8 encodings.
  evidence: The text branch folds CR/CRLF only. A UTF-8 BOM changes the digest, and CR bytes occurring inside UTF-16 code units would be rewritten, so two distinct UTF-16 files could hash identically. E1b's freeze set should be checked against this before it is sealed.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Stream large files into the hasher instead of reading whole files into memory.
  evidence: The file-digest route uses `read_bytes()` plus an in-memory line-ending replace, so peak memory scales with the largest frozen artifact and doubles for text files. Not a correctness issue at MVP freeze-set sizes.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Complete packaging metadata before anything is distributed — license, classifiers, project URLs, and an sdist target.
  evidence: `readme` points at `doc/info.md`, outside the package, so an sdist build needs an explicit target; there is no license declaration. Irrelevant while the project is local-only, relevant the moment it is packaged.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Close the TOCTOU window between the containment check and the file read in the file-digest route.
  evidence: `resolve()`, `is_file()` and `read_bytes()` are separate syscalls against a path rather than one file descriptor, so a path swapped by a concurrent writer mid-build escapes the root. Requires a local attacker running during a freeze; out of scope for the MVP threat model, but the guard's comment claims more than it delivers.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Add a `verify(payload, digest)` helper that recomputes and compares, rather than only checking a digest's declared labels.
  evidence: `require_route` validates `route` and `normalisation` but never the `sha256`, so no caller can currently answer "does this digest actually match this payload?" E1b's drift refusal needs exactly that operation.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Decide policy for Windows-hostile path segments — reserved device names, trailing dots and spaces, and colons inside a segment.
  evidence: `CON`, `NUL`, `aux.py`, `a.py.` and `notes.py:stream` resolve differently on Windows than on Linux, so the same declared manifest can name different files on the two platforms. The current guards cover `..`, absolute, drive-qualified and null-byte paths only.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Run the suite on Linux as well as Windows, and type-check the package.
  evidence: The whole cross-platform agreement argument is currently reasoned rather than measured — no Linux execution has happened. The package also ships `py.typed`, asserting type completeness to later epics, with no mypy or pyright in the dev group to back it.

- source_spec: `spec-e0-canonicalisation-and-hashing.md`
  summary: Decide whether a CLI JSON payload should be limit-independent with respect to `PYTHONINTMAXSTRDIGITS`.
  evidence: `canonical_bytes` now bounds integer width itself, but `json.loads` performs its own str-to-int conversion first, so a 4000-digit literal on stdin still fails under a lowered `PYTHONINTMAXSTRDIGITS`. Closing it means changing how the CLI parses JSON.
