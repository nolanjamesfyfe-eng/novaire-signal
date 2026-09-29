# brain-fsaverage5.glb provenance

- **Cortical source:** FreeSurfer `fsaverage5` pial surfaces, distributed in the Nilearn Python package (`nilearn.datasets.fetch_surf_fsaverage('fsaverage5')`).
- **Upstream citation:** Fischl, B. et al. (1999), *High-resolution intersubject averaging and a coordinate system for the cortical surface*, Human Brain Mapping 8(4), 272–284.
- **Upstream terms:** FreeSurfer Open Access Software License Agreement — https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSoftwareLicense
- **Nilearn license:** BSD-3-Clause — https://github.com/nilearn/nilearn/blob/main/LICENSE
- **Local processing:** Surface axes normalized for Three.js, hemisphere triangles partitioned into broad external lobe meshes using FreeSurfer RAS anterior/superior coordinates. Cerebellum and brainstem are locally generated illustrative geometry, not FreeSurfer segmentation.
- **Rebuild:** `python tools/build-brain-model.py` (requires `nibabel`, `nilearn`, and `trimesh`).

This model is an educational visualization, not a clinical segmentation or diagnostic asset.
