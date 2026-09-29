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

# Paired cerebellar hemispheres with irregular folia. Avoid the uniform
# corrugated-shell look: fold spacing, depth and phase vary across the surface.
def cerebellum(side):
    nu, nv = 96, 56
    u = np.linspace(0, 2*np.pi, nu, endpoint=False)
    v = np.linspace(-np.pi/2, np.pi/2, nv)
    U, V = np.meshgrid(u, v)
    folia = (.032*np.cos(19*V + 1.35*np.sin(2*U))
             + .014*np.cos(31*V - .7*np.sin(5*U)))
    lobules = 1 + .045*np.sin(3*U + .45*np.sin(4*V)) + folia
    x = side*.40 + .50*np.cos(V)*np.cos(U)*lobules
    y = -.75 + .35*np.sin(V)*lobules + .018*np.sin(5*U)*np.cos(V)**2
    z = -.43 + .41*np.cos(V)*np.sin(U)*lobules
    vertices = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    faces=[]
    for j in range(nv-1):
        for i in range(nu):
            a=j*nu+i;b=j*nu+(i+1)%nu;c=(j+1)*nu+i;d=(j+1)*nu+(i+1)%nu
            faces.extend(((a,c,b),(b,c,d)))
    mesh=trimesh.Trimesh(vertices=vertices,faces=np.asarray(faces),process=False)
    mesh.visual=trimesh.visual.ColorVisuals(mesh=mesh,face_colors=[20,17,28,255])
    return mesh
for side,name in [(-1,"left_cerebellum"),(1,"right_cerebellum")]:
    scene.add_geometry(cerebellum(side),node_name=name,geom_name=name)
# Tapered, asymmetric brainstem: narrower medulla below, subtle pons bulge
# above, and no hemispherical capsule end that reads like a plastic pill.
nu, nv = 48, 36
u = np.linspace(0, 2*np.pi, nu, endpoint=False)
t = np.linspace(0, 1, nv)
U, T = np.meshgrid(u, t)
radius = .10 + .08*T + .075*np.exp(-((T-.68)/.18)**2)
x = radius*np.cos(U)*(1 + .05*np.sin(3*U + 4*T))
z = -.17 + radius*.82*np.sin(U) - .035*T
y = -1.62 + .83*T
verts = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
faces=[]
for j in range(nv-1):
    for i in range(nu):
        a=j*nu+i;b=j*nu+(i+1)%nu;c=(j+1)*nu+i;d=(j+1)*nu+(i+1)%nu
        faces.extend(((a,c,b),(b,c,d)))
stem=trimesh.Trimesh(vertices=verts,faces=np.asarray(faces),process=False)
stem.visual=trimesh.visual.ColorVisuals(mesh=stem,face_colors=[17,14,23,255])
scene.add_geometry(stem,node_name="brainstem",geom_name="brainstem")
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_bytes(scene.export(file_type="glb"))
print(f"wrote {OUT} ({OUT.stat().st_size} bytes), {sum(len(g.faces) for g in scene.geometry.values())} triangles")
