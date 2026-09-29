---
title: Public-domain quotation corpus quality gates
tags: [quotes, provenance, public-domain, curation]
---

# Public-domain quotation corpus quality gates

A public-domain book is not automatically a usable quote corpus. Treat legality, attribution, and card quality as separate gates.

- Pin the exact edition and translation, jurisdiction, catalog URL, and rights statement before extraction.
- Keep an exact excerpt hash and a stable source anchor for every retained card.
- Exclude quotation marks, footnotes, indexes, editor matter, case histories, and nearby attribution verbs before ranking prose.
- Historical surveys are especially dangerous: the narrator frequently quotes or compresses another thinker. Do not bulk-publish those sentences under the narrator's name.
- OCR can silently alter words and line-break hyphens. Reject a source when reliable line-level recovery would require editorial reconstruction.
- Rank for self-contained meaning, then manually inspect representatives and reject technical mechanics, obsolete prescriptions, discriminatory claims, and context-dependent fragments.
- Stop below a requested round number when the remaining material is weak. A smaller audited corpus is better than a padded one that falsifies authorship.
- Test the rotation against the actual pool size for at least three complete cycles, not a fixed calendar duration that may cease to cover multiple cycles after expansion.
