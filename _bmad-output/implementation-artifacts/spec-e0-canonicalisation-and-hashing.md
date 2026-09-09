---
title: 'E0 — Canonicalisation and hashing'
type: 'feature'
created: '2026-09-09'
status: 'done'
baseline_commit: 'NO_VCS'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/specs/spec-OutcomeFuse/SPEC.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/BUILD-ORDER.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Every hash in OutcomeFuse — contract identity, tool-call keys, progress fingerprints, result digests, rubric freeze, baseline freeze — must be produced by one function, because the freeze tool runs before the governor exists and the two must still agree. Nothing else in the system can be built until that function and its two admissible hashing routes exist.

**Approach:** Stand up the uv project skeleton and one core-owned canonicaliser package exposing exactly two routes: a **structure route** (typed model → canonical JSON → SHA-256) and a **file-digest route** (sorted path + file-byte SHA-256 manifest, itself hashed through the structure route). Every digest is returned as a typed record carrying its route id and normalisation version; a digest presented without a route id is rejected rather than defaulted.

## Boundaries & Constraints

**Always:**
- The canonicaliser is **pure**: no clock, no randomness, no network, no filesystem reads — except the file-digest route, which reads only the file bytes it is explicitly handed paths for.
- Exactly **two** admissible routes exist. No component may hash by any other means, and no additional route may be introduced in this spec.
- Normalisation is **specified and versioned**. `1.0` and `1` must produce an identical digest.
- File-digest paths are **POSIX-separated, NFC-normalised, byte-sorted**; text artifacts are digested with **LF line endings**, so a Windows freeze and a Linux freeze over the same tree agree.
- Every hashed artifact **declares its route id**. Route selection is never inferred from the input's shape.
- Unrepresentable or ambiguous input (NaN, ±Inf, non-string mapping keys, unsupported types) is **rejected loudly**, never coerced.
- Python 3.12+, `uv` for dependency management, `pytest` for tests, `src/` layout.

**Ask First:**
- Adding any third hashing route, or changing the normalisation rules after this spec's tests pass.
- Adding runtime dependencies beyond `pydantic`.

**Never:**
- Do not implement any other epic's surface — no contract schema, verifier registry, ledger, record store, or freeze-campaign tooling. E0 supplies the primitive those epics consume.
- Do not use `json.dumps` defaults, `hash()`, `pickle`, `repr()`, or any locale- or platform-dependent formatting on the hashing path.
- Do not silently default a route, silently classify a file as text/binary by sniffing content, or silently skip an unreadable file.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Numeric equivalence | `{"a": 1}` and `{"a": 1.0}` | Identical digest | N/A |
| Key order independence | `{"a":1,"b":2}` and `{"b":2,"a":1}` | Identical digest | N/A |
| Array order significance | `[1,2]` vs `[2,1]` | Different digests | N/A |
| Unicode normalisation | NFC and NFD spellings of the same string | Identical digest | N/A |
| Bool vs int | `True` and `1` | **Different** digests | N/A |
| Non-finite number | `float("nan")`, `float("inf")` | Rejected | Raise `CanonicalisationError` naming the value |
| Non-string mapping key | `{1: "a"}` | Rejected | Raise `CanonicalisationError` naming the key type |
| Unsupported type | `datetime`, `set`, custom object | Rejected | Raise `CanonicalisationError` naming the type |
| Cross-process agreement | Same structure hashed in-process and via the module CLI in a subprocess | Identical digest | N/A |
| Text line endings | Same tree with CRLF vs LF in a text-suffixed file | Identical manifest digest | N/A |
| Binary file bytes | Same tree with differing bytes in a binary file | Different manifest digest | N/A |
| Path separators | Manifest built from `a\b.py` vs `a/b.py` | Identical manifest digest | N/A |
| Missing route id | Digest record deserialised with route id absent or empty | Rejected | Raise `RouteDeclarationError`; never default |
| Unknown route id | Digest record declaring `structure/v2` | Rejected | Raise `RouteDeclarationError` naming the route |
| Missing manifest file | Path listed but absent on disk | Rejected | Raise `FileNotFoundError`; never skip |

</frozen-after-approval>

## Code Map

Greenfield — the repository contains planning artifacts only (`.agents/`, `.github/`, `doc/`, `_bmad/`, `_bmad-output/`). There is no `pyproject.toml`, no `src/`, and no version control. Every file below is new.

Read-only evidence that constrains this work (do not edit):
- `_bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md` -- **AD-6 (lines 107–115)** is the governing rule: one canonicaliser, canonical JSON + SHA-256, versioned normalisation, single numeric form, the file-digest manifest route, POSIX/NFC/byte-sorted paths, LF text digests, route-id declaration, exactly two routes. **Source tree (lines ~440–470)** fixes the package layout and `workspace/` output conventions.
- `_bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/BUILD-ORDER.md` -- **§E0** states the acceptance bar verbatim ("two independent processes… including for `1.0` versus `1`"; cross-platform file-digest agreement; route-id rejection) and establishes that E0 blocks E1a → E3 → E1b → E2.
- `_bmad-output/specs/spec-OutcomeFuse/SPEC.md` -- Constraints section: core purity, "one canonicalisation function serves every hash… exactly two admissible routes, each hashed artifact declaring which route it used."

Files this spec creates:
- `pyproject.toml` -- uv project root, src layout, `requires-python >=3.12`, runtime dep `pydantic>=2`, dev deps `pytest` + `ruff`, pytest/ruff config.
- `src/outcomefuse/__init__.py`, `src/outcomefuse/core/__init__.py` -- package roots.
- `src/outcomefuse/core/canon/__init__.py` -- the public API surface every later epic imports.
- `src/outcomefuse/core/canon/canonical_json.py` -- normalisation `v1`: the serialiser and its rejection rules.
- `src/outcomefuse/core/canon/digest.py` -- `Digest` record, route registry, structure route, digest verification.
- `src/outcomefuse/core/canon/file_manifest.py` -- file-digest route.
- `src/outcomefuse/core/canon/__main__.py` -- minimal CLI, the "second independent process" the acceptance bar requires.
- `tests/core/canon/` -- the test suite.

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- create the uv project: `requires-python = ">=3.12"`, src layout, `pydantic>=2`, dev group with `pytest` and `ruff`, `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `pythonpath = ["src"]`, `--strict-markers` and `xfail_strict = true`, and a ruff `target-version` -- `pythonpath` matters: without it the suite only runs after an install, an undeclared precondition.
- [x] `src/outcomefuse/__init__.py`, `src/outcomefuse/core/__init__.py`, `src/outcomefuse/py.typed` -- package roots plus the PEP 561 marker, since the package is fully annotated and later epics type-check against it.
- [x] `src/outcomefuse/core/canon/canonical_json.py` -- implement normalisation `v1` (see Design Notes) as `canonical_bytes(value) -> bytes`, plus `CanonicalisationError`. **`canonical_bytes` raises no exception type other than `CanonicalisationError`**: bound recursion depth, detect cycles, reject lone surrogates, and bound the Decimal exponent. Reject non-finite numbers, non-string mapping keys, and unsupported types -- this is the single point where two implementations could diverge.
- [x] `src/outcomefuse/core/canon/digest.py` -- define `NORMALISATION_VERSION`, the frozen route-id registry (`structure/v1`, `file-digest/v1`), the immutable `Digest` model with a constrained `sha256`, the **shared envelope helper** that is the only place a SHA-256 is computed (see Design Notes), `hash_structure(value) -> Digest`, and `require_route(digest, expected) -> None` verifying route **and** normalisation version -- route declaration is what stops two freeze tools disagreeing silently, and the envelope is what stops two routes producing the same digest.
- [x] `src/outcomefuse/core/canon/file_manifest.py` -- implement `build_file_manifest(root, entries, text_suffixes=DEFAULT_TEXT_SUFFIXES)` where each entry is either a path (mode derived from suffix) or an explicit `(path, mode)` declaration, producing sorted `{path, sha256, mode}` records, and `hash_file_manifest(...) -> Digest` **delegating to the shared envelope helper rather than hashing itself**. Enforce root containment against symlinks and require a regular file -- cross-platform freeze agreement and the containment guarantee both live here.
- [x] `src/outcomefuse/core/canon/__init__.py` -- re-export the public API (`Digest`, `hash_structure`, `hash_file_manifest`, `build_file_manifest`, `require_route`, `canonical_bytes`, `ManifestEntry`, route constants, error types, `NORMALISATION_VERSION`, `DEFAULT_TEXT_SUFFIXES`) so callers never reach into submodules.
- [x] `src/outcomefuse/core/canon/__main__.py` -- read a JSON structure or a manifest request from stdin under a bounded read size, validate that `paths` is a list of strings and `text_suffixes` (when present) is a list of strings, print the `Digest` as JSON, exit non-zero with the error name on rejection -- exists so determinism can be proven across process boundaries, and it consumes untrusted input.
- [x] `tests/core/canon/test_canonical_json.py` -- cover every I/O Matrix row for normalisation: numeric equivalence, key order, array order, Unicode NFC/NFD, bool-vs-int distinction, and each rejection case. Add the error-contract cases: cycles, over-deep nesting, lone surrogates, and an out-of-range Decimal exponent -- each must raise `CanonicalisationError`, never `RecursionError`, `UnicodeEncodeError`, or a hang.
- [x] `tests/core/canon/test_digest.py` -- route registry, `Digest` immutability, `sha256` shape enforcement on **deserialised** records, the missing/empty/non-string/unknown route-id rejections with distinct messages, and `require_route` rejecting a mismatched `normalisation`.
- [x] `tests/core/canon/test_domain_separation.py` -- assert the two routes cannot collide: the same payload hashed through each route yields different `sha256`, and a structure-route hash of a manifest-shaped dict does not equal that manifest's file-digest.
- [x] `tests/core/canon/test_file_manifest.py` -- CRLF-vs-LF equivalence for text suffixes and for an **explicitly declared** extensionless text file, **content-difference detection for a text-suffixed file**, byte-difference detection for binary files, `a\b.py`-vs-`a/b.py` path equivalence, NFC path normalisation, byte-sort ordering, drive-qualified path rejection, symlink-escape rejection, directory-as-path rejection, invalid `text_suffixes` rejection, and the missing-file failure. Include one **golden** assertion pinning an exact `sha256` for a fixed two-file tree.
- [x] `tests/core/canon/test_cross_process.py` -- hash the same structure and the same tree in-process and via `python -m outcomefuse.core.canon` in a `subprocess`, assert digests are identical, and include the `1.0`-versus-`1` case, a request carrying custom `text_suffixes`, and malformed/invalid-JSON stdin.

**Acceptance Criteria:**
- Given the same structure, when it is hashed by an in-process import and by a separate process invoking the module CLI, then both produce byte-identical `sha256` values, `route`, and `normalisation`.
- Given a file tree whose text files differ only in line endings and whose paths differ only in separator style, when a file-digest manifest is built over it from either form, then the resulting `Digest` is identical.
- Given a digest record whose route id is absent, empty, or unrecognised, when it is verified, then `RouteDeclarationError` is raised and no route is assumed.
- Given one payload, when it is hashed through the structure route and through the file-digest route, then the two `sha256` values differ — no digest is comparable across routes or across normalisation versions.
- Given a record declaring a `normalisation` other than the pinned version, when `require_route` runs, then it is rejected rather than accepted as interchangeable.
- Given an extensionless text file declared `text`, when the tree is hashed with CRLF and with LF line endings, then the digests are identical.
- Given a path that resolves outside the root — via `..`, an absolute or drive-qualified path, or a symlink — when a manifest is built, then it is rejected before any bytes are read.
- Given two trees differing only in the *content* of a text-suffixed file, when each is hashed, then the digests differ.
- Given any input `canonical_bytes` cannot represent — including a cyclic structure, an over-deep structure, a lone surrogate, or an out-of-range Decimal exponent — then `CanonicalisationError` is raised, and no other exception type escapes.
- Given `uv run pytest`, when the suite runs on a clean checkout, then every test passes with no network access and no writes outside pytest's temporary directories.

## Spec Change Log

### 2026-09-09 — review loop 1

**Triggering findings (all three review layers, independently):**
1. *Cross-route and cross-version digest collision.* `hash_structure` hashed the bare payload while `hash_file_manifest` hashed `{"route": ..., "entries": [...]}`, so a structure-route hash of a manifest-shaped dict was byte-identical to that manifest's file-digest. `NORMALISATION_VERSION` was stamped on the `Digest` record but never mixed into the hashed bytes, so a future `v2` digest could equal a `v1` digest of the same input. `require_route` checked the route id and ignored `normalisation` entirely.
2. *Extensionless text files silently CRLF-sensitive.* `mode` was always derived from the suffix, so `Dockerfile`, `Makefile`, `LICENSE` and every extensionless script fell to `binary` and re-acquired the line-ending sensitivity the route exists to remove — defeating the spec's own cross-platform acceptance criterion on any realistic freeze set. `ManifestEntry.mode`'s docstring claimed the mode was "declared", but no caller could declare it.
3. *Verification gaps that made the above invisible.* No test asserted that a text-suffixed file's **content** affects its digest (the text branch could hash the path instead and stay green); no golden value pinned the manifest payload shape; the drive-letter guard and the CLI's `text_suffixes` override were unreachable by any test.
4. *Error contract leaks and unbounded input on an untrusted surface.* Cycles and deep nesting escaped as `RecursionError`, lone surrogates as `UnicodeEncodeError`, and a large `Decimal` exponent expanded without bound — all reachable from the CLI, which reads stdin. Symlinks inside the root defeated the textual `..` guard.

**Amended:** Design Notes now specify a single shared envelope helper binding route id and normalisation version into every hashed payload, with both routes delegating to it; explicit per-path `mode` declaration; root containment resolved against symlinks; a closed error contract for `canonical_bytes`; and constrained `Digest` fields. Tasks and Acceptance Criteria were extended to match. The `<frozen-after-approval>` block was not touched.

**Known-bad state avoided:** freezing E1b's rubric, answer keys and verifier tests against digests that are not route- or version-bound, and whose text-file branch is unverified. BUILD-ORDER is explicit that re-freezing after the governor exists is precisely what §8.2 forbids — so a canonicaliser defect found later cannot be corrected, only absorbed.

**KEEP — these worked and must survive re-derivation:**
- The hand-written serialiser rather than `json.dumps`: `bool` checked before `int`, NFC on keys and values, keys sorted by encoded bytes, `Decimal(str(float))` with integral-vs-fixed-point formatting and no exponent notation.
- `test_exact_canonical_form_is_pinned` asserting a literal canonical byte string — extend this style to the manifest, do not remove it.
- The split between the **lookup** path (caller's spelling, because the filesystem stores the name it was given) and the **recorded** path (NFC). NFC-normalising before the syscall breaks on NTFS.
- `mode` recorded in the manifest rather than re-derived by a reader.
- `model_config = ConfigDict(frozen=True, extra="forbid")` on both models, and the `model_validator(mode="before")` that makes an absent route id unrepresentable at deserialisation rather than merely unchecked.
- The `text_suffixes` parameter, the CLI's stdin/stdout shape, and the `subprocess`-based cross-process test design.
- Rejecting rather than coercing: NFC key collisions, duplicate manifest paths, and path traversal.

## Design Notes

**The shared envelope — the single point where SHA-256 is computed:**
Both routes go through one private helper. Nothing else in the package calls `hashlib.sha256` on a canonical payload.
```python
def _sealed(route: str, payload: Any) -> Digest:
    envelope = {"normalisation": NORMALISATION_VERSION, "payload": payload, "route": route}
    return Digest(route=route, normalisation=NORMALISATION_VERSION,
                  sha256=hashlib.sha256(canonical_bytes(envelope)).hexdigest())
```
`hash_structure(value)` is `_sealed(ROUTE_STRUCTURE, value)`; `hash_file_manifest(...)` is `_sealed(ROUTE_FILE_DIGEST, list(entries))`. Binding the route id **and** the normalisation version into the hashed bytes is what makes a digest non-comparable across routes and across versions — the record field alone only *describes* the digest, it does not *constrain* it. A second copy of the hashing step is exactly the divergence AD-6 forbids.

**Normalisation `v1` — the exact rules that must be reproducible:**
- Serialise to UTF-8 bytes with no insignificant whitespace (JSON separators `,` and `:`).
- Mapping keys must be `str`; NFC-normalise them and sort by their **UTF-8 byte sequence**, not by Python's default string ordering.
- NFC-normalise all string values. Reject strings containing lone surrogates rather than letting `UnicodeEncodeError` escape.
- Check `bool` **before** numeric types — `True` is an `int` subclass in Python, and `True` must not collide with `1`.
- Numbers: reject NaN and ±Inf. Convert via `Decimal(str(value))` for `float` (Python's shortest round-trip repr is deterministic for IEEE-754 doubles), then emit integral values as a plain integer string (`-0` → `0`, no leading zeros) and non-integral values as fixed-point with trailing zeros stripped — never exponent notation. This is what makes `1.0` and `1` collide by design. Because output is exponent-free, reject any `Decimal` whose exponent magnitude exceeds a declared bound (4096 is ample) — otherwise `Decimal("1E+1000000")` is finite, accepted, and expands to megabytes.
- Accepted input types: `pydantic.BaseModel` (dumped in python mode), `Mapping`, `Sequence` (excluding `str`/`bytes`), `str`, `bool`, `int`, `float`, `Decimal`, `None`. Everything else raises.
- **Closed error contract:** `canonical_bytes` raises `CanonicalisationError` and nothing else. Track visited container ids to reject cycles, and bound nesting depth (64), so self-referential or pathological input never surfaces as `RecursionError`.

**File-digest route:** each entry is `{"path": <posix, NFC>, "sha256": <hex>, "mode": "text"|"binary"}`, sorted by encoded path bytes. Text files are read as bytes, then `\r\n` and lone `\r` are normalised to `\n` before hashing.

`mode` is **declarable, not merely derived**. `build_file_manifest` accepts each entry as either a bare path — mode inferred from the lowercased suffix — or an explicit `(path, mode)` pair that wins outright. Suffix inference alone puts `Dockerfile`, `Makefile`, `LICENSE` and every extensionless script into `binary`, where a CRLF checkout and an LF checkout of the same tree produce different digests: the precise FR65 spurious-drift refusal AD-6 exists to prevent. Validate `text_suffixes` members as lowercase dot-prefixed strings, since the lookup lowercases the suffix and a `.PY` entry would otherwise match nothing silently.

**Containment.** The textual guard (reject `..`, leading `/`, drive-qualified first segment) is necessary but not sufficient — a symlink inside the root defeats it entirely. Resolve each target and confirm it stays under the resolved root, and require a regular file, so a directory or device node becomes a domain error rather than an OS-dependent `IsADirectoryError`/`PermissionError`. This route reads paths that reach it from the CLI's stdin.

**`Digest` field constraints:** `sha256` matches `^[0-9a-f]{64}$` and `normalisation` is non-empty, enforced on **deserialised** records, not just freshly produced ones. `require_route` verifies the declared normalisation equals the pinned version, and converts a pydantic `ValidationError` into `RouteDeclarationError` so callers face one error type. `_check_route` must report a non-string route as such rather than calling it "empty".

**Placement note:** the architecture's source tree comment lists `canonicalise` under `core/contract/`, but AD-6 describes it as a core-owned function serving the fuse, the ledger and the harness alike, and the freeze tool must import it without dragging in contract schemas. This spec places it at `core/canon/`. Flag at review if the literal tree should win.

## Verification

**Commands:**
- `uv sync` -- expected: environment resolves with `pydantic`, `pytest`, `ruff`.
- `uv run pytest -q` -- expected: all tests pass, zero failures.
- `uv run ruff check src tests` -- expected: no violations.
- `'{"a": 1.0}' | uv run python -m outcomefuse.core.canon structure` -- expected: prints a JSON digest whose `sha256` matches the digest for `{"a": 1}`, and differs from the file-digest of an equivalently-shaped manifest.

## Suggested Review Order

**Start here — the invariant everything else serves**

- One envelope binds route id and version into the hashed bytes; the only SHA-256 in the package.
  [`digest.py:92`](../../../src/outcomefuse/core/canon/digest.py#L92)

- The two admissible routes and the pinned normalisation version, as literals.
  [`digest.py:20`](../../../src/outcomefuse/core/canon/digest.py#L20)

**Normalisation `v1` — the single divergence point between implementations**

- Type dispatch: `bool` before `int`, so `True` never collides with `1`.
  [`canonical_json.py:64`](../../../src/outcomefuse/core/canon/canonical_json.py#L64)

- Keys NFC-normalised then sorted by UTF-8 bytes; collisions rejected, not coerced.
  [`canonical_json.py:113`](../../../src/outcomefuse/core/canon/canonical_json.py#L113)

- Exponent-free decimal rendering — this is what makes `1.0` and `1` collide by design.
  [`canonical_json.py:205`](../../../src/outcomefuse/core/canon/canonical_json.py#L205)

- Integer width bounded explicitly, so acceptance never depends on `PYTHONINTMAXSTRDIGITS`.
  [`canonical_json.py:189`](../../../src/outcomefuse/core/canon/canonical_json.py#L189)

- The three bounds that close the error contract: depth, decimal exponent, integer digits.
  [`canonical_json.py:29`](../../../src/outcomefuse/core/canon/canonical_json.py#L29)

**Route declaration — what stops two freeze tools disagreeing silently**

- Route enforced at construction and at deserialisation; `model_copy` cannot smuggle one past.
  [`digest.py:43`](../../../src/outcomefuse/core/canon/digest.py#L43)

- Absent, null, empty, non-string and unknown routes each diagnose distinctly.
  [`digest.py:78`](../../../src/outcomefuse/core/canon/digest.py#L78)

- Verifies route *and* normalisation — the two fields that jointly define comparability.
  [`digest.py:107`](../../../src/outcomefuse/core/canon/digest.py#L107)

**File-digest route — cross-platform agreement and containment**

- Mode is declarable per entry, not only inferred; extensionless text files depend on this.
  [`file_manifest.py:70`](../../../src/outcomefuse/core/canon/file_manifest.py#L70)

- Textual guard rejects `..`, absolute and drive-qualified paths before any syscall.
  [`file_manifest.py:173`](../../../src/outcomefuse/core/canon/file_manifest.py#L173)

- Resolution seam — the post-resolve containment check a symlink would otherwise defeat.
  [`file_manifest.py:131`](../../../src/outcomefuse/core/canon/file_manifest.py#L131)

- Suffix inference lowercases; `.csv` deliberately excluded because quoted CRLF is data.
  [`file_manifest.py:192`](../../../src/outcomefuse/core/canon/file_manifest.py#L192)

- Delegates to the shared envelope rather than hashing again — AD-6's whole point.
  [`file_manifest.py:121`](../../../src/outcomefuse/core/canon/file_manifest.py#L121)

**CLI — the second independent process, and the trust boundary**

- Bounded stdin, validated request shape, error name without a traceback.
  [`__main__.py:36`](../../../src/outcomefuse/core/canon/__main__.py#L36)

- `paths` accepts `[path, mode]`, so declared modes are reachable across the boundary.
  [`__main__.py:92`](../../../src/outcomefuse/core/canon/__main__.py#L92)

**Tests that would catch a regression the others would not**

- Pinned canonical bytes — the literal a second implementation must reproduce.
  [`test_canonical_json.py:49`](../../../tests/core/canon/test_canonical_json.py#L49)

- Non-BMP keys, where UTF-8 and UTF-16 orderings actually disagree.
  [`test_canonical_json.py:54`](../../../tests/core/canon/test_canonical_json.py#L54)

- Proves the two routes cannot produce the same digest for one payload.
  [`test_domain_separation.py:20`](../../../tests/core/canon/test_domain_separation.py#L20)

- Golden tree digest; catches any drift in the manifest payload shape.
  [`test_file_manifest.py:159`](../../../tests/core/canon/test_file_manifest.py#L159)

- The acceptance bar: a separate process must reproduce the digest exactly.
  [`test_cross_process.py:63`](../../../tests/core/canon/test_cross_process.py#L63)

- Containment guard, driven without link privileges so it cannot regress unnoticed.
  [`test_file_manifest.py:214`](../../../tests/core/canon/test_file_manifest.py#L214)
