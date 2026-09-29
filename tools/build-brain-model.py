#!/usr/bin/env python3
"""Build the public brain atlas GLB from Nilearn's FreeSurfer fsaverage5 pial mesh."""
from pathlib import Path
import nibabel as nib
import numpy as np
import trimesh
from nilearn import datasets

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "health/models/brain-fsaverage5.glb"
fs = datasets.fetch_surf_fsaverage(mesh="fsaverage5")
scene = trimesh.Scene()
colors = {
    "frontal": [116, 38, 178, 255], "parietal": [128, 48, 183, 255],
    "temporal": [102, 34, 150, 255], "occipital": [84, 29, 126, 255],
}

def region_for(c):
    # FreeSurfer RAS: +Y anterior, +Z superior. Broad surface-lobe approximation.
    y, z = c[:, 1], c[:, 2]
    return np.where(y > 12, "frontal", np.where(y < -48, "occipital", np.where((z < 4) & (y < 25), "temporal", "parietal")))

for side in ("left", "right"):
    img = nib.load(fs[f"pial_{side}"])
    verts = np.asarray(img.darrays[0].data, dtype=np.float32)
    faces = np.asarray(img.darrays[1].data, dtype=np.int64)[:, [0, 2, 1]]  # axis swap reverses handedness
    # Convert mm RAS to the atlas' x-horizontal/y-superior/z-anterior coordinates.
    verts = np.column_stack((verts[:, 0], verts[:, 2], verts[:, 1])) / 67.0
    centroids_ras = np.asarray(img.darrays[0].data)[faces].mean(axis=1)
    regions = region_for(centroids_ras)
    for region, rgba in colors.items():
        part = trimesh.Trimesh(vertices=verts, faces=faces[regions == region], process=False)
        part.visual = trimesh.visual.ColorVisuals(mesh=part, face_colors=rgba)
        scene.add_geometry(part, node_name=f"{side}_{region}", geom_name=f"{side}_{region}")

# A continuous, corrugated cerebellar surface with paired hemispheres.
def cerebellum(side):
    nu, nv = 80, 42
    u = np.linspace(0, 2*np.pi, nu, endpoint=False)
    v = np.linspace(-np.pi/2, np.pi/2, nv)
    U, V = np.meshgrid(u, v)
    corr = 1 + .07*np.cos(16*V + .8*np.sin(3*U))
    x = side*.42 + .52*np.cos(V)*np.cos(U)*corr
    y = -.76 + .38*np.sin(V)*corr
    z = -.43 + .44*np.cos(V)*np.sin(U)*corr
    vertices = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    faces=[]
    for j in range(nv-1):
        for i in range(nu):
            a=j*nu+i;b=j*nu+(i+1)%nu;c=(j+1)*nu+i;d=(j+1)*nu+(i+1)%nu
            faces.extend(((a,c,b),(b,c,d)))
    mesh=trimesh.Trimesh(vertices=vertices,faces=np.asarray(faces),process=False)
    mesh.visual=trimesh.visual.ColorVisuals(mesh=mesh,face_colors=[39,76,145,255])
    return mesh
for side,name in [(-1,"left_cerebellum"),(1,"right_cerebellum")]:
    scene.add_geometry(cerebellum(side),node_name=name,geom_name=name)
stem=trimesh.creation.capsule(radius=.18,height=.86,count=[24,24])
stem.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0]))
stem.apply_translation([0,-1.16,-.18])
stem.visual=trimesh.visual.ColorVisuals(mesh=stem,face_colors=[49,89,155,255])
scene.add_geometry(stem,node_name="brainstem",geom_name="brainstem")
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_bytes(scene.export(file_type="glb"))
print(f"wrote {OUT} ({OUT.stat().st_size} bytes), {sum(len(g.faces) for g in scene.geometry.values())} triangles")
