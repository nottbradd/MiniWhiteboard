# Interaction performance - Mini Whiteboard 1.2

## V1.2 regression workload - 2026-10-20

Actual current source, Windows 11 build 26200 / Python 3.12.14 x64, Qt/PySide6
6.11.2. Offscreen GUI-thread timings measure event/painting work, not display FPS.
Repeated the 21 general cases, 28 screenshot cases (blank, 1080p, 1440p and 4K),
image/clipboard work and paired raster comparison. Screenshot cases use 60 frames
x 2 repeats, with 20 strokes, 20 shapes and 10 text objects.

| Operation with a 4K screenshot | Median event ms | p95 ms |
|---|---:|---:|
| draw | 1.548 | 2.748 |
| circular_erase | 0.881 | 1.181 |
| whole_stroke_erase | 0.307 | 0.574 |
| marquee | 0.674 | 1.333 |
| move_10 | 2.687 | 3.548 |
| resize_10 | 2.96 | 3.709 |
| rotate_10 | 3.42 | 4.207 |

Every screenshot case built its display cache once. Annotation work decoded or
painted the source background zero times. Detailed numbers are in the ignored
`verification/v12-*-performance` logs/JSON. Wrapped text hit testing now builds
its convenient textbox area directly; it avoids a Mac Qt stall from expanding
and unioning every glyph contour. Exact glyph geometry still drives bounds and
erasure. A regression bounds hit tolerance work independently of glyph count.

## Historical V1.1 measurements

# Interaction performance — Mini Whiteboard 1.1

## Cross-platform regression workload — 2026-10-01

Actual native Windows run: `verification/windows-cross-platform-performance.json`.
One 1920×1080 display at 100%; 30 frames × 2 repeats for each of 28 cases
(blank, 1080p, 1440p and 4K source × seven operations). This measures input-event
work and paint instrumentation, not monitor FPS. No native Mac timings exist yet.

| Operation with a 4K source | Median event (ms) | p95 event (ms) |
|---|---:|---:|
| Draw | 2.238 | 3.286 |
| Circular erase | 2.242 | 3.579 |
| Whole-stroke erase | 1.491 | 2.908 |
| Marquee | 2.176 | 4.367 |
| Move 10 | 4.842 | 6.687 |
| Resize 10 | 4.522 | 5.750 |
| Rotate 10 | 5.472 | 7.052 |

All 21 screenshot cases used one cache build, with zero source-image paint calls,
decodes or image-geometry builds during the measured gestures. The 4K source
display cache was 1264×793 pixels on this viewport. Existing identity tests still
pass. This confirms retention of the optimisation; it is not a claim of a new
speedup or mixed-DPI hardware validation. The shared benchmark now selects Cocoa
on macOS with `--native`; run it using the command in MACOS_CHECKLIST.md.

## Screenshot/background refinement — 2026-09-30

The verified extra work was repeated transformed, smoothly scaled source-image
painting under the canvas clip, plus overly broad invalidation while a freehand
stroke grew. The pre-refinement renderer already had decoded-image and geometry
caches and partial document updates. **It did not decode the screenshot, deep-copy
its pixels into undo, poll the clipboard, or repaint the entire board on every
pointer sample.** The reported severe stutter was not reproduced on this machine.
The changes remove measured unnecessary work; the results below do not establish
that every interaction became faster or that all hardware-specific stutter is gone.

### Rendering and interaction changes

- An original, unchanged, locked capture now has a board-local QImage cache at
  `ceil(viewport × DPR)` physical pixels, with DPR applied once. The source PNG
  and image object remain authoritative. The cache contains the smooth source
  rendering and canvas/control clipping; paints blit it at 1:1 through Qt's dirty
  event region, preserving stack order and transparent control holes.
- Annotation edits, selection, erasing and undo do not rebuild this cache. A new
  viewport, DPI or clip rebuilds it. Unlocking or modifying the image uses the
  existing editable image renderer; undo to the exact original locked state can
  reuse the background. Source pixels remain unchanged for quality/copying.
- Click, marquee and eraser queries use the cached editable-object order before
  bounds/detail work. Whole-stroke queries filter non-strokes before bounds.
  Locked image objects are omitted from Smart Guide target construction.
- Drawing dirties the changing curve tail using the last three points, the new
  point, stroke radius and antialias padding. A pixel comparison of incremental
  painting versus a fresh full render covers sharp changes in direction.
- Move/resize/rotation retain old/new selection dirty regions. Erasing retains
  swept/changed-object regions. Handles, guides and cursors remain on the passive
  overlay; marquee pointer movement causes no document repaint.
- History already shared immutable image objects/PNG byte buffers. Identity
  assertions verify sharing across all measured annotation transactions and undo.
  No image data serialization, clipboard access or per-frame image allocation was
  added to annotation gestures.

### Method

Windows 11 10.0.26200, Python 3.12.14, PySide6 6.11.2, one 1920×1080 display at
100%. Each blank/screenshot fixture contains exactly **20 strokes, 20 shapes and
10 text objects**. Source images are generated at 1920×1080, 2560×1440 and
3840×2160; this tests large source data on the available 1080p display, not capture
from physical 1440p/4K hardware. Group gestures transform 10 annotations.

The same script ran before production changes and after integration. Board outer
size is 1280×820; removing the 2 px visual inset increased the canvas from
1260×791 to 1264×793. Native Windows cases have 30 pointer updates × 2 repeats
(60 samples); offscreen cases have 40 × 3 (120 samples). Timings include gesture
updates and GUI-thread event processing. Commits, p95, paint costs, cache dimensions
and counters are recorded separately in JSON. cProfile ran separately with
24 updates and one repeat, so profiling overhead is absent from timing samples.

These short sequential local runs are sensitive to machine load, event delivery
and warmed caches. They are not display FPS measurements or long-duration tests.
No statistical confidence bounds are claimed.

### Native Windows event medians (ms)

| Operation | 4K source before | 4K source after | Blank after |
|---|---:|---:|---:|
| Draw | 1.699 | 1.385 | 1.289 |
| Circular erase | 1.613 | 1.814 | 1.796 |
| Whole-stroke erase | 1.174 | 1.424 | 1.249 |
| Marquee | 1.530 | 1.861 | 1.524 |
| Move 10 | 3.410 | 3.740 | 3.524 |
| Resize 10 | 3.253 | 3.528 | 3.466 |
| Rotate 10 | 3.921 | 4.090 | 4.583 |

After refinement, the 4K-source fixture is within 0.34 ms of the blank fixture
for six operations; its rotation median is lower than blank, illustrating timing
variation. Drawing improved in the before/after run; the other native medians
increased. Thus **there is no across-the-board total-event speedup claim**. The
consistent evidence is reuse of the source rendering, smaller drawing updates,
and near-blank native interaction cost in this workload.

All after-refinement source sizes:

| Operation | Blank | 1080p source | 1440p source | 4K source |
|---|---:|---:|---:|---:|
| Draw | 1.289 | 1.386 | 1.383 | 1.385 |
| Circular erase | 1.796 | 1.679 | 1.752 | 1.814 |
| Whole-stroke erase | 1.249 | 1.486 | 1.327 | 1.424 |
| Marquee | 1.524 | 1.997 | 1.698 | 1.861 |
| Move 10 | 3.524 | 4.014 | 4.021 | 3.740 |
| Resize 10 | 3.466 | 3.701 | 3.674 | 3.528 |
| Rotate 10 | 4.583 | 4.400 | 4.159 | 4.090 |

### Offscreen event medians (ms)

| Operation | 4K source before | 4K source after | Blank after |
|---|---:|---:|---:|
| Draw | 1.806 | 2.227 | 1.373 |
| Circular erase | 0.590 | 0.754 | 0.563 |
| Whole-stroke erase | 0.247 | 0.340 | 0.263 |
| Marquee | 0.568 | 0.652 | 0.446 |
| Move 10 | 2.409 | 2.660 | 2.053 |
| Resize 10 | 2.601 | 3.327 | 2.105 |
| Rotate 10 | 3.141 | 3.034 | 2.439 |

Most 4K offscreen medians increased, with larger draw/resize differences than in
the native run. This is retained as a limitation, not hidden by the cache counters.
The cache optimisation alone does not establish an overall responsiveness win in
this backend. Geometry, mask creation, overlay updates and event processing still
contribute to total time; longer native testing on the affected hardware remains
necessary if visible stutter persists.

### Work eliminated and paint area

In the native 4K case, source-image paints during the sampled gestures (including
release) went from **62 / 50 / 10 / 0 / 60 / 60 / 54** for drawing, circular erase,
whole-stroke erase, marquee, move, resize and rotation to **zero in all cases**.
Every screenshot fixture built one display cache during setup and reused it for
the gesture. Image decode and image paint-data construction counters were zero
both before and after during interaction.

Mean drawing document paint area fell from **3.410% to 0.576%** per paint event,
including release: about **83% less area**. Offscreen it fell from 3.359% to
0.404% (about 88%). Native after-refinement areas for the other operations were
0.102% circular erase, 0.509% whole-stroke erase, 0% marquee, 5.33% movement,
5.40% resize and 23.871% rotation. Large selections can legitimately dirty much
of a board; no unconditional small-region guarantee is made.

All source sizes used a **1264×793** display cache at DPR 1 (4,009,408 pixel-buffer
bytes, about 3.82 MiB per screenshot board, in addition to retained source data).
Synthetic DPR 1, 1.25, 1.5 and 2 tests verify physical dimensions and pixel equality
against direct rendering. Actual mixed-DPI display transitions remain untested.

### Paired raster comparison

To isolate the source-raster work from unrelated GUI costs, `raster_cache_check`
alternates direct source rendering and cached blits for the same 4K image and
region. Each path has 20 warmups and 220 timed samples at DPR 1.

| Dirty region | Direct source median ms | Cached median ms |
|---|---:|---:|
| 32×32 | 0.0414 | 0.0067 |
| 160×80 | 0.0633 | 0.0105 |
| 600×300 | 0.2744 | 0.0650 |

This is about **4.2–6.2× faster for this raster step alone**. It excludes event
delivery, object geometry, overlays and desktop composition, and is not a
whole-application speedup.

### Reproduce / evidence

```powershell
.\.venv\Scripts\python.exe -m scripts.screenshot_performance --frames 40 --repeats 3 --output verification/screenshot-after.json --profile verification/screenshot-profile-after.txt
.\.venv\Scripts\python.exe -m scripts.screenshot_performance --native --frames 30 --repeats 2 --output verification/screenshot-native-after.json --profile verification/screenshot-native-profile-after.txt
.\.venv\Scripts\python.exe -m scripts.raster_cache_check
```

- Native: [before](../verification/screenshot-native-before.json), [after](../verification/screenshot-native-after.json), [before profile](../verification/screenshot-native-profile-before.txt), [after profile](../verification/screenshot-native-profile-after.txt).
- Offscreen: [before](../verification/screenshot-before.json), [after](../verification/screenshot-after.json), [before profile](../verification/screenshot-profile-before.txt), [after profile](../verification/screenshot-profile-after.txt).
- [Paired raster results](../verification/screenshot-raster-comparison.json), [verification and limitations](TEST_RESULTS.md).

## Historical initial Version 1.1 measurements — before screenshot refinement

The same 21 workloads were rerun with Smart Guides enabled and Grid Snap off.
The previous release measurements below are retained as historical evidence.
All 21 new medians were lower than the previous recorded medians. This is a
short local comparison, sensitive to machine load and caches; it shows no
regression in these fixtures and does not establish a guaranteed speedup.

**500-object document, 100 objects selected for group operations:**

| Operation | Previous median ms | Version 1.1 median ms | Version 1.1 p95 ms | Mean painted area |
|---|---:|---:|---:|---:|
| Circular erase | 2.543 | 1.481 | 2.722 | 0.15% |
| Whole-stroke erase | 0.931 | 0.463 | 0.843 | 0.13% |
| Marquee | 0.688 | 0.359 | 0.797 | 0% |
| Move one | 1.550 | 0.811 | 1.096 | 0.14% |
| Move 100 | 10.288 | 6.370 | 9.802 | 17.35% |
| Resize 100 | 9.138 | 5.806 | 7.529 | 18.07% |
| Rotate 100 | 12.675 | 8.708 | 10.055 | 30.85% |

The 500-object marquee release took 9.056 ms to select objects/build the frame.
Pointer movement itself required no document repaint. All 10/100/500 rows,
commit times and paint fractions are in
[performance-v11.json](../verification/performance-v11.json); the independent
[profile-v11.txt](../verification/profile-v11.txt) records cProfile results.

### Large image and clipboard workload

`scripts.v11_performance` uses a **3840×2160** image with gradient/text and 100
vector annotations, a 1280×820 board, 24 pointer updates per case and Smart Guides
enabled. Image source is 724,374 PNG bytes. Initial PNG encoding took **368.826 ms**
once; painting and affine previews reused the decoded QImage. An instrumented
assertion verified **zero image decodes during every transform sample**.

| Image operation | Median event ms | p95 event ms | Mean painted area |
|---|---:|---:|---:|
| Move | 5.712 | 7.005 | 73.96% |
| Resize | 6.326 | 7.082 | 76.93% |
| Rotate | 9.506 | 10.584 | 92.99% |

Large images cover most of the board, so most document pixels legitimately need
repainting. Source pixels are never permanently resampled during these operations.

Clipboard creation includes JSON encoding and the rendered image representation:

| Selection | Median of 3 copies | First copy |
|---|---:|---:|
| 4K image + 100 annotations | 19.812 ms | 19.812 ms |
| 500 mixed vector objects | 57.938 ms | 166.989 ms |

The first 500-object copy also creates geometry/layout caches. Clipboard work
happens only on commands. Measurements cover payload/image preparation, not
another application's paste time. Large imported images and first copies can
pause briefly; these tests do not measure prolonged native frame delivery.

Implementation additions preserve prior optimisations: sorted bounds targets
captured only when a move/resize starts; nearby binary-search queries; sparse
object previews; shared immutable PNG bytes; decode/paint caches; dirty-region
painting; separate guides; no extra high-frequency timers or clipboard polling.

Reproduce:

```powershell
.\.venv\Scripts\python.exe -m scripts.performance_check --frames 16 --output verification/performance-v11.json --profile verification/profile-v11.txt
.\.venv\Scripts\python.exe -m scripts.v11_performance
```

Raw image/copy results:
[performance-images-v11.json](../verification/performance-images-v11.json).

## Previous polish baseline — development label 1.2.0

The following historical results describe the earlier polish update. The user
requested the new release label **1.1**; all of those optimisations are retained.

Measured 2026-09-29, Windows 11, Python 3.12.14, PySide6 6.11.2.

## Method and limits

The same `scripts.performance_check` workload ran before production edits and
against the final source. Qt's offscreen backend processes actual gestures and
paint events on the GUI thread. Each case has 16 pointer updates. Timings include
`update_gesture` and `processEvents`; release/commit is measured separately in JSON.
The cProfile pass uses 8 updates per case and is separate from the timing pass.

Fixtures contain 10, 100 or 500 mixed objects: 120-point freehand strokes, shapes,
and text. Every fourth object has a partial-erasure mask. Group operations select
all objects at 10/100 and **100 selected objects within the 500-object document**.
The board outer size is 1280 × 820 logical pixels. Its usable area increased with
the requested inset change. These are short, reproducible local measurements,
not native display FPS, prolonged-use guarantees, or statistical confidence bounds.

Paint fractions are the mean actual document paint-event area, including the
release update, divided by canvas area. Cursor/marquee/handle overlay painting is
included in event timing but excluded from document-area fractions. Marquee
release selects objects and builds the frame; the final 500-object release cost
was 10.787 ms even though pointer updates needed no document repaint.

## Recorded timings

| Objects | Operation | Before median ms | After median ms | After p95 ms | Mean document area repainted |
|---|---|---:|---:|---:|---:|
| 10 | Circular erase | 4.400 | 2.102 | 8.570 | 0.14% |
| 10 | Whole-stroke erase | 2.526 | 0.348 | 1.809 | 0.13% |
| 10 | Marquee | 3.945 | 0.509 | 1.044 | 0.00% |
| 10 | Move one | 3.807 | 0.739 | 1.763 | 0.14% |
| 10 | Move group | 3.735 | 1.457 | 2.746 | 1.93% |
| 10 | Resize group | 3.641 | 1.603 | 2.283 | 1.95% |
| 10 | Rotate group | 3.894 | 1.839 | 2.617 | 6.08% |
| 100 | Circular erase | 12.417 | 1.751 | 7.631 | 0.15% |
| 100 | Whole-stroke erase | 11.532 | 0.428 | 1.058 | 0.13% |
| 100 | Marquee | 11.051 | 0.730 | 1.616 | 0.00% |
| 100 | Move one | 12.608 | 0.897 | 1.255 | 0.14% |
| 100 | Move group | 11.385 | 7.272 | 8.096 | 17.42% |
| 100 | Resize group | 11.084 | 8.207 | 9.501 | 17.93% |
| 100 | Rotate group | 11.592 | 9.067 | 11.819 | 30.85% |
| 500 | Circular erase | 52.397 | 2.543 | 3.501 | 0.15% |
| 500 | Whole-stroke erase | 41.035 | 0.931 | 2.831 | 0.13% |
| 500 | Marquee | 45.426 | 0.688 | 1.648 | 0.00% |
| 500 | Move one | 40.035 | 1.550 | 1.939 | 0.14% |
| 500 | Move group | 41.378 | 10.288 | 14.190 | 17.42% |
| 500 | Resize group | 40.547 | 9.138 | 11.068 | 17.93% |
| 500 | Rotate group | 40.705 | 12.675 | 17.328 | 30.85% |

All 21 recorded final median timings were lower than the corresponding baseline.
The baseline repainted 100% of the document on every update. The final 500-object
cases repaint about 0.13–0.15% for erasing/single movement, 17–31% for the group
transforms, and none during marquee movement. A selection covering the entire
canvas can still legitimately require a full repaint.

## Profile findings and implementation

- Baseline: full-canvas/all-object painting dominated. The cProfile workload took
  about 5.13 seconds; canvas painting accounted for about 4.24 seconds and invoked
  `paint_object` 42,511 times.
- Final profile: about 1.62 seconds, canvas painting about 0.68 seconds, 10,892
  `paint_object` calls. This is roughly 74% fewer object paint calls in that pass.
- Each immutable scene record keeps full surviving painted bounds, hit bounds and
  reusable local paint data. Bounds scans run before detailed geometry; a spatial
  tree was unnecessary in the measured workload.
- Gesture sources are captured once. Only affected preview records change, and
  the full after-state tuple is assembled at commit. Source stroke-point tuples,
  masks and unrelated objects are shared throughout a transform.
- Dirty regions cover old/new affected artwork plus 3 px antialias padding. Dense
  regions are coalesced beyond 16 rectangles to avoid expensive fragmented clips.
  Boundary clipping is applied only to objects that need it.
- Cached round-cap/join stroke outlines are filled directly, avoiding repeated
  stroking of every curve on each frame. Text keeps Qt's shaped document renderer.
  Local geometry/masks remain reusable across affine transform changes.
- Erasing queries swept bounds, then tests candidate surviving ink. Analytic
  capsules cover fast motion without generating many tiny interpolation samples.
  Local vector masks reuse prior unions; there is no full-board raster mask.
- One passive tool surface paints cursor, marquee and handles independently of
  document repaint. Its extent is bounded near the viewport, even when selected
  objects extend far beyond the visible canvas.

An intermediate version regressed 100-object group transforms. Subsequent
profiling identified repeated stroke raster work, fragmented dirty regions and
recomputed paint data. The final cache/outline changes above removed that regression.
No GUI worker threads, spatial tree, production logging, or higher timer rates
were introduced.

## Reproduce and raw evidence

```powershell
.\.venv\Scripts\python.exe -m scripts.performance_check --frames 16 --output .test-artifacts/performance.json --profile .test-artifacts/profile.txt
```

- [Before timings](../verification/performance-before.json)
- [After timings, p95, commit costs and paint areas](../verification/performance-after.json)
- [Before profile](../verification/profile-before.txt)
- [After profile](../verification/profile-after.txt)
