---
title: Progressive deep-zoom globe geography without tile tokens
tags: [flaneur, maps, canvas, gestures, lod, playwright]
---

# Progressive deep-zoom globe geography

## Symptom
A canvas orthographic globe looked correct at world scale but compact places became marker dots or disappeared when zooming. Touch routing also treated every vertical one-finger gesture as page scroll, and drag sensitivity divided by zoom made deep rotation effectively immobile.

## Repair pattern
- Keep the permanent overview/detail country layers painted while loading another tier.
- Generate a topology-clean `keep-shapes` high LOD from the canonical Natural Earth 1:10m source, preserve D3 spherical ring winding, and lazy-load it only after an effective zoom threshold.
- Cache a successful fetch. Abort an unfinished request after returning well below its threshold. Never blank the current geometry while waiting or on error.
- Cull by spherical feature cap before projecting. Use a finite zoom ceiling tied to source scale; for this atlas 72× is enough to distinguish Monaco while remaining honest about 1:10m—not street-level—detail.
- Hide small-place centroids once polygon geometry is large enough. Distinguish a named place such as Hawaii from a sovereign/jurisdiction boundary in search copy.
- Let one-finger vertical movement remain native page scroll at overview, then switch the canvas to `touch-action:none` after zooming so both axes rotate the globe. Keep yaw unbounded; clamp only pitch just shy of the poles.
- Anchor wheel/pinch zoom by preserving the geographic coordinate under the pointer/midpoint through iterative projection correction.
- Expose canvas state (`data-zoom`, `data-rotation`, `data-lod`, `data-visible-features`) for deterministic tests, not production controls.

## Verification
- Test painted pixels, not only DOM state.
- Assert cumulative yaw exceeds 360° after successive drags at overview and deep zoom.
- Exercise 320px and 390px trusted CDP pinch, vertical drag, pointer cancel, and overview page scroll.
- Capture settled Hawaii, Hong Kong, and Monaco frames and assert the high LOD is active.
- Repeat performance/correctness suites serially; parallel browser suites create false p95 failures through host contention.
