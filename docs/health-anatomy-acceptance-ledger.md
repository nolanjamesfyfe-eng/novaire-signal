# Personalized anatomy acceptance ledger

## Visual and interaction acceptance

- [x] Distinct BodyParts3D muscle meshes retained; tendons and internal separations remain visible.
- [x] Muscle surfaces use shaded terracotta/copper materials, restrained high-angle white edge geometry, and a gentle emissive pulse.
- [x] `prefers-reduced-motion` disables pulse animation and camera damping/automatic motion.
- [x] The full-body envelope is a low-opacity deep tissue backing in muscular mode, not an opaque cover; detailed superficial geometry remains readable over it.
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
- Generated screenshots are intentionally untracked. Current evidence: `/root/.hermes/cache/scratch/output/health-anatomy-360/*.png` and `/root/.hermes/cache/scratch/output/health-anatomy-iteration2/*.png`.

## Human visual approval (not implied by automated tests)

- [ ] Front muscular view aesthetically approved by the user.
- [ ] Back muscular view aesthetically approved by the user.
- [ ] Left/right muscular views aesthetically approved by the user.
- [ ] Skin front/back/side views aesthetically approved by the user.

## Honest limits

- This is an illustrative atlas derived from generic BodyParts3D assets and verified broad proportions, not photogrammetry, a scan, or exact likeness.
- The atlas retains 14 individually named muscle-group pick targets and adds a 53-component BodyParts3D superficial completion mesh for neck, back, forearm, hand, thigh, lower-leg and foot coverage. This is still not every structure in a clinical dissection.
- Injury copy depends on the authenticated private record schema/event and is deliberately absent before unlock.
