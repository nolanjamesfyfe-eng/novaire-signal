# Health check-in implementation contract

- `/health/` presents Novaire’s Muscle System and a daily self-report wellbeing battery; it is not a medical measurement or diagnostic tool.
- Daily score components are sleep (full at 8+ hours), energy, focus/clarity, inverse stress, calm, happiness, and movement adherence. Movement states `done`, `planned`, `recovery`, and `none` remain distinct; done/planned/recovery may satisfy adherence without claiming strenuous exercise improves physiological energy.
- Day/week/month views use only real local check-ins and display coverage. Legacy scores remain intact and are marked legacy rather than being silently recalculated.
- Check-ins remain in browser LocalStorage unless separately authorized persistence is introduced.
- The head overlay is symbolic and maps answers to stylized regions; it must never claim measured activation, diagnosis, or neuroscience inference.
- Preserve the existing 3D anatomy implementation as an independent module. Preserve canonical globe and bolt geometry/navigation.
- The main-page health battery link belongs in `signal_brand.py` and the main generator invocation, not only generated `index.html`.
