# Anatomy model attribution

The anatomy meshes in `health/models/bodyparts3d.glb` and `health/models/muscle-completion.glb` are derived from **BodyParts3D / Anatomography 4.3**.

- Data copyright: Database Center for Life Science (DBCLS)
- License: [Creative Commons Attribution-ShareAlike 2.1 Japan](https://creativecommons.org/licenses/by-sa/2.1/jp/)
- Source project: https://lifesciencedb.jp/bp3d/
- Versioned manifest/downloader reference: https://doi.org/10.5281/zenodo.22727172
- `muscle-completion.glb` is a transformed and Meshopt-compressed derivative containing 53 BodyParts3D components selected for superficial neck, back, forearm, hand, thigh, lower-leg, and foot coverage. It is redistributed under the same CC BY-SA 2.1 Japan terms.
- Muscle-view head, hand, and foot closure surfaces are localized triangle subsets extracted at runtime from the licensed `FJ2810` skin surface in `bodyparts3d.glb`; no third-party primitive or unlicensed model is introduced.

The skeleton bundle remains subject to its existing repository provenance and licensing records.
