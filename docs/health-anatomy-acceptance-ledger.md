# Personalized anatomy acceptance ledger

## Visual and interaction acceptance

- [x] Distinct BodyParts3D muscle meshes retained; tendons and internal separations remain visible.
- [x] Muscle surfaces use antique gold `#b59662`, restrained white edge geometry, and a gentle emissive pulse.
- [x] `prefers-reduced-motion` disables pulse animation and camera damping/automatic motion.
- [x] No red atlas materials. The full-body envelope is a low-opacity dark-gold backing in muscular mode, not an opaque cover.
- [x] Tall, lean 193 cm / 80 kg illustrative baseline retained. Copy explicitly says approximation, not scan or exact likeness.
- [x] Front, back, left, right and free 360-degree orbit controls.
- [x] Full-body envelope supplies head, hands and feet in muscular and skin views; skeleton asset supplies complete skull, hands and feet.
- [x] Muscular, skeletal and skin controls change real rendered geometry/material state.
- [x] Muscle, bone and skin meshes are raycast pickable; selected mesh highlights and inspector shows anatomical name.
- [x] Selection dismisses from Close, Escape, or contextual outside click.
- [x] Existing physique width/definition deformation retained for all anatomical groups.
- [x] Existing brain, battery, authentication and journal modules are untouched.
- [x] Private left-clavicle marker is created only from an authenticated `health:record-ready` injury payload. `*`, injury label and saved approximate date are copied from that payload; no personal diagnosis/date is hard-coded.
- [x] Private first-MTP marker and journal event contract retained.

## Evidence

- `tests/health-atlas.mjs`: loading, raycast, selection, orbit, absolute views, zoom/focus/reset, search, keyboard and WebGL fallback.
- `tests/health-physique-browser.mjs`: 193 cm / 80 kg baseline, visible deformation, brain dismissal, desktop/mobile screenshots.
- `tests/health-anatomy-360.mjs`: desktop/mobile × muscular/skeletal/skin × front/back/left/right captures, frame padding, selection dismissal, private clavicle event and reduced-motion state.
- Screenshots: `tests/health-anatomy-360/*.png`, `tests/health-atlas-{desktop,mobile}.png`, `tests/health-physique-{desktop,mobile}.png`.

## Honest limits

- This is an illustrative atlas derived from generic BodyParts3D assets and verified broad proportions, not photogrammetry, a scan, or exact likeness.
- The bundled muscle model contains 14 named muscle groups rather than every muscle in a clinical dissection. The detailed skeleton provides broader individually named pick targets.
- Injury copy depends on the authenticated private record schema/event and is deliberately absent before unlock.
