---
title: 'OutcomeFuse Two-Minute Executive Demo'
type: 'chore'
created: '2026-09-17'
status: 'done'
route: 'one-shot'
---

# OutcomeFuse Two-Minute Executive Demo

## Intent

**Problem:** Provide a shareable two-minute executive demonstration of OutcomeFuse.

**Approach:** An isolated 1080p narrated walkthrough of real console captures from a
scripted supply-chain approval scenario. The governed arm withholds a refused
notification; the ungoverned arm records it. Show synthetic-data and fixture-counter
disclosures, explain citation-check limits, and avoid unsupported savings claims.
The MP4 uses captured states with gentle motion, not continuous screen recording.

Verification completed: 120.000 seconds, H.264 1920x1080 at 30 fps, AAC narration;
full media decode; nonblank pixel samples in all six scenes; matching artifact hashes;
browser playback and seeking; desktop and mobile player screenshots without page
overflow. Console text is best inspected fullscreen on a desktop or landscape display.
Both captured run chains verified. The governed arm passed its quality check and did
not invoke the notification tool. The player includes a transcript and optional WebVTT.

Independent review: 11 findings addressed, including two related dependency findings;
3 rejected as intentional local media packaging, a separate mobile edit, or additional
pilot-planning scope. No pre-existing issues were changed or deferred. No commit was
created because the user requested a video, not a source-control operation.

## Suggested Review Order

1. Watch the finished executive demonstration.
   [index.html:1](../../submission/executive-demo/index.html#L1)
2. Check narration, timing, and claim boundaries.
   [storyboard.json:1](../../submission/executive-demo/storyboard.json#L1)
3. Inspect captured events, run IDs, and full seals.
   [capture-evidence.json:1](../../submission/executive-demo/capture-evidence.json#L1)
4. Review capture assertions, media generation, and stale-audio protection.
   [render.cjs:1](../../submission/executive-demo/render.cjs#L1)
5. Follow reproducible build instructions and media-packaging limitations.
   [README.md:1](../../submission/executive-demo/README.md#L1)