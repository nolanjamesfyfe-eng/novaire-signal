import * as THREE from './vendor/three.module.min.js';
import { OrbitControls } from './vendor/OrbitControls.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';

export const BRAIN_STORAGE_KEY = 'novaire-health-energy-checkins-v1';
export const BRAIN_EVENT = 'health:brain-self-report';
export const BRAIN_PARTS = {
  frontal: {
    name: 'Frontal lobe', group: 'Cerebrum', view: 'Anterior',
    description: 'Supports planning, decision-making, voluntary movement and aspects of speech and social behavior. These functions depend on distributed networks rather than this lobe acting alone.'
  },
  parietal: {
    name: 'Parietal lobe', group: 'Cerebrum', view: 'Superior',
    description: 'Integrates touch and body-position signals and helps direct spatial attention. It works with frontal and sensory networks to guide action.'
  },
  temporal: {
    name: 'Temporal lobe', group: 'Cerebrum', view: 'Lateral',
    description: 'Contributes to hearing, language comprehension and recognition, while medial temporal systems support memory formation. These abilities span connected regions in both hemispheres.'
  },
  occipital: {
    name: 'Occipital lobe', group: 'Cerebrum', view: 'Posterior',
    description: 'Carries out early and intermediate visual processing, including features such as edges, color and motion. Perception emerges through its exchange with wider visual networks.'
  },
  cerebellum: {
    name: 'Cerebellum', group: 'Hindbrain', view: 'Posterior / inferior',
    description: 'Fine-tunes movement, balance and motor learning by comparing intended actions with sensory feedback. It also participates in some cognitive timing and prediction networks.'
  },
  brainstem: {
    name: 'Brainstem', group: 'Brainstem', view: 'Inferior',
    description: 'Relays signals between the brain, spinal cord and cerebellum and helps regulate breathing, arousal and other vital functions. Its compact structure contains many distinct pathways and nuclei.'
  }
};

const clamp = (n, a, b) => Math.min(b, Math.max(a, Number(n) || 0));
export function expressiveLevel(entry) {
  const a = entry?.answers;
  if (!a) return null;
  const values = [a.energy, a.focus].filter(Number.isFinite).map(n => clamp(n, 0, 10));
  const sleep = entry?.foundations?.sleepHours ?? a.sleep;
  if (Number.isFinite(sleep)) values.push(Math.min(clamp(sleep, 0, 24) / 8, 1) * 10);
  return values.length ? values.reduce((sum, n) => sum + n, 0) / (values.length * 10) : null;
}
export function latestLocalEntry(storage = globalThis.localStorage) {
  try {
    const entries = JSON.parse(storage?.getItem(BRAIN_STORAGE_KEY) || '[]');
    return Array.isArray(entries) && entries.length
      ? entries.filter(entry => entry?.answers).sort((a, b) => String(a.date).localeCompare(String(b.date))).at(-1) || null
      : null;
  } catch { return null; }
}

const root = typeof document === 'undefined' ? null : document.querySelector('[data-brain-atlas]');
if (root) {
  root.classList.add('brain-atlas');
  root.innerHTML = `
    <div class="brain-atlas__head">
      <div><p class="brain-atlas__eyebrow">HEALTH ATLAS / 02</p><h2>The inner<br><em>command deck</em></h2></div>
      <p class="brain-atlas__intro">Rotate, zoom and select an anatomical structure. Its light is an expressive reflection of today’s self-reported energy, focus and rest—not a scan.</p>
    </div>
    <div class="brain-atlas__deck">
      <div class="brain-atlas__viewport" role="application" tabindex="0" aria-label="Interactive three-dimensional brain. Drag to rotate, pinch or scroll to zoom, and tap a structure to learn its function.">
        <canvas></canvas><div class="brain-atlas__halo" aria-hidden="true"></div>
        <div class="brain-atlas__orientation"><span>SUPERIOR</span><span>INFERIOR</span></div>
        <div class="brain-atlas__loading" role="status">ASSEMBLING ANATOMY</div><div class="brain-atlas__tooltip" role="status"></div>
      </div>
      <aside class="brain-atlas__panel" aria-live="polite">
        <p class="brain-atlas__eyebrow">SELECTED ANATOMY</p><strong class="brain-atlas__number">00</strong>
        <h3>Select a structure</h3><p class="brain-atlas__description">Choose a label or touch the model.</p>
        <dl><div><dt>GROUP</dt><dd>—</dd></div><div><dt>VIEW</dt><dd>—</dd></div></dl>
        <button type="button" data-brain-reset>RESET VIEW</button>
      </aside>
      <nav class="brain-atlas__labels" aria-label="Brain structures">${Object.entries(BRAIN_PARTS).map(([key, part]) => `<button type="button" data-brain-part="${key}" aria-pressed="false"><i></i><span>${part.name}</span></button>`).join('')}</nav>
      <div class="brain-atlas__turn" role="group" aria-label="Turn brain"><button type="button" data-brain-turn="left" aria-label="Turn brain left">↶</button><span>TURN</span><button type="button" data-brain-turn="right" aria-label="Turn brain right">↷</button><button type="button" data-brain-reset aria-label="Reset brain view">RESET</button></div>
      <div class="brain-atlas__zoom"><button type="button" data-brain-zoom="in" aria-label="Zoom in">+</button><span>ZOOM</span><button type="button" data-brain-zoom="out" aria-label="Zoom out">−</button></div>
    </div>
    <div class="brain-atlas__signal"><div><span>EXPRESSIVE LIGHT</span><strong data-brain-signal>NEUTRAL · NO CHECK-IN</strong></div><div class="brain-atlas__meter" aria-hidden="true"><i></i></div><p><b>SELF-REPORT VISUALIZATION</b> Brightness responds uniformly to energy, focus and sleep you explicitly logged. It is <b>not measured brain activity, a diagnosis, regional function, or inferred neuroscience.</b></p></div>
    <p class="brain-atlas__source">Cortical surface: FreeSurfer fsaverage5 pial template distributed with Nilearn. Broad external lobe labels are educational approximations, not clinical segmentation.</p>`;

  const canvas = root.querySelector('canvas');
  const viewport = root.querySelector('.brain-atlas__viewport');
  const tooltip = root.querySelector('.brain-atlas__tooltip');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let renderer, scene, camera, controls, brain, selected = null, hovered = null, level = null, pulsePhase = 0;
  let magentaWave, cyanWave;
  const pickables = [];
  const pointers = new Map();
  let gesture = null;
  const palette = { frontal: 0x8522c7, parietal: 0x6920a8, temporal: 0x541783, occipital: 0x40115f, cerebellum: 0x17131f, brainstem: 0x120f18 };

  function material(key, left = false) {
    const color = new THREE.Color(palette[key]);
    if (left) color.offsetHSL(.008, -.05, .045);
    const lower = key === 'cerebellum' || key === 'brainstem';
    return new THREE.MeshStandardMaterial({ color, roughness: lower ? .86 : .48, metalness: 0, emissive: lower ? new THREE.Color(0x090711) : color.clone(), emissiveIntensity: lower ? .035 : .08 });
  }
  async function buildBrain() {
    brain = new THREE.Group();
    brain.rotation.set(-.035, 0, 0);
    brain.scale.set(.728, .7, .672);
    scene.add(brain);
    const gltf = await new GLTFLoader().loadAsync(new URL('./models/brain-fsaverage5.glb', import.meta.url).href);
    gltf.scene.traverse(object => {
      if (!object.isMesh) return;
      const key = object.name.includes('cerebellum') ? 'cerebellum' : object.name === 'brainstem' ? 'brainstem' : Object.keys(BRAIN_PARTS).find(k => object.name.endsWith(`_${k}`));
      if (!key) return;
      object.geometry.deleteAttribute('normal');
      object.geometry.computeVertexNormals();
      const isLeftCortex = object.name.startsWith('left_') && key !== 'cerebellum';
      object.material = material(key, isLeftCortex);
      object.material.side = THREE.DoubleSide;
      object.userData.key = key;
      pickables.push(object);
      if (key !== 'brainstem') {
        const edge = new THREE.Mesh(object.geometry, new THREE.MeshBasicMaterial({ color: key === 'cerebellum' ? 0xaeeaff : 0xe1c4ff, side: THREE.BackSide, transparent: true, opacity: key === 'cerebellum' ? .14 : .3, depthWrite: false }));
        edge.position.copy(object.position); edge.quaternion.copy(object.quaternion); edge.scale.copy(object.scale).multiplyScalar(1.012); object.parent.add(edge);
      }
      if (isLeftCortex) {
        const wire = new THREE.Mesh(object.geometry, new THREE.MeshBasicMaterial({ color: 0xf0dcff, wireframe: true, transparent: true, opacity: .46, depthWrite: false }));
        wire.position.copy(object.position); wire.quaternion.copy(object.quaternion); wire.scale.copy(object.scale).multiplyScalar(1.004); object.parent.add(wire);
      }
    });
    brain.add(gltf.scene);
  }
  async function init() {
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
      renderer.setPixelRatio(Math.min(devicePixelRatio, matchMedia('(max-width: 640px)').matches ? 1.35 : 1.75));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.06;
      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(31, 1, .1, 30);
      camera.position.set(0, .12, 7.15);
      controls = new OrbitControls(camera, canvas);
      controls.enableDamping = !reducedMotion.matches;
      controls.dampingFactor = .095;
      controls.rotateSpeed = 1.35;
      controls.zoomSpeed = 1.1;
      controls.enablePan = false;
      controls.minDistance = 4.75;
      controls.maxDistance = 12;
      controls.target.set(0, -.05, 0);
      scene.add(new THREE.HemisphereLight(0xb79ae8, 0x010208, .72));
      const key = new THREE.DirectionalLight(0xf2ddff, 2.25); key.position.set(-3, 5, 6); scene.add(key);
      const rim = new THREE.DirectionalLight(0x78a7ff, 1.5); rim.position.set(4, -1, -4); scene.add(rim);
      const violet = new THREE.PointLight(0x9f4fff, .74, 10); violet.position.set(-2, 0, 3); scene.add(violet);
      magentaWave = new THREE.PointLight(0xff2fc8, 1.2, 4.3, 1.6); scene.add(magentaWave);
      cyanWave = new THREE.PointLight(0x36e7ff, .95, 3.8, 1.7); scene.add(cyanWave);
      await buildBrain(); resize(); bind(); readSignal(latestLocalEntry());
      root.querySelector('.brain-atlas__loading').hidden = true; root.dataset.ready = 'true'; animate();
      window.__HEALTH_BRAIN__ = {
        ready: true, select, reset, zoom, turn, readSignal,
        get selected() { return selected; }, get level() { return level; },
        get cameraDistance() { return camera.position.distanceTo(controls.target); },
        get projectedBounds() {
          brain.updateMatrixWorld(true);
          const box = new THREE.Box3().setFromObject(brain), corners = [];
          for (let i = 0; i < 8; i++) corners.push(new THREE.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z).project(camera));
          const xs = corners.map(p => p.x), ys = corners.map(p => p.y);
          return { width: (Math.max(...xs) - Math.min(...xs)) / 2 * viewport.clientWidth, height: (Math.max(...ys) - Math.min(...ys)) / 2 * viewport.clientHeight };
        },
        get cameraPose() { return { position: camera.position.toArray(), target: controls.target.toArray() }; },
        get pulsePhase() { return pulsePhase; },
        get modelStats() { return { meshes: pickables.length, materials: pickables.map(m => ({ name: m.name, key: m.userData.key, color: m.material.color.getHexString(), emissive: m.material.emissive.getHexString(), intensity: m.material.emissiveIntensity })) }; },
        findHitPoint(key) { return findHitPoint(key); }
      };
    } catch (error) {
      console.error(error); root.dataset.ready = 'false'; root.querySelector('.brain-atlas__loading').textContent = '3D UNAVAILABLE · USE STRUCTURE LABELS'; bindLabels();
    }
  }
  function resize() { const w = viewport.clientWidth, h = viewport.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
  function hit(x, y) { const r = canvas.getBoundingClientRect(), ray = new THREE.Raycaster(); ray.setFromCamera(new THREE.Vector2((x - r.left) / r.width * 2 - 1, -(y - r.top) / r.height * 2 + 1), camera); return ray.intersectObjects(pickables, false)[0]?.object || null; }
  function findHitPoint(key) {
    const r = canvas.getBoundingClientRect();
    for (let y = .18; y <= .82; y += .025) for (let x = .18; x <= .82; x += .025) { const clientX = r.left + r.width * x, clientY = r.top + r.height * y; if (hit(clientX, clientY)?.userData.key === key) return { x: clientX, y: clientY }; }
    return null;
  }
  function select(key) {
    const part = BRAIN_PARTS[key]; if (!part) return;
    selected = key;
    root.querySelector('.brain-atlas__number').textContent = String(Object.keys(BRAIN_PARTS).indexOf(key) + 1).padStart(2, '0');
    root.querySelector('.brain-atlas__panel h3').textContent = part.name;
    root.querySelector('.brain-atlas__description').textContent = part.description;
    const dd = root.querySelectorAll('.brain-atlas__panel dd'); dd[0].textContent = part.group.toUpperCase(); dd[1].textContent = part.view.toUpperCase();
    root.querySelectorAll('[data-brain-part]').forEach(button => { const on = button.dataset.brainPart === key; button.classList.toggle('active', on); button.setAttribute('aria-pressed', String(on)); });
  }
  function clearSelection() {
    selected = null; root.querySelector('.brain-atlas__number').textContent = '00'; root.querySelector('.brain-atlas__panel h3').textContent = 'Select a structure'; root.querySelector('.brain-atlas__description').textContent = 'Choose a label or touch the model.';
    root.querySelectorAll('.brain-atlas__panel dd').forEach(d => d.textContent = '—'); root.querySelectorAll('[data-brain-part]').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
  }
  function reset() { clearSelection(); camera.position.set(0, .12, 7.15); controls.target.set(0, -.05, 0); controls.update(); brain.rotation.set(-.035, 0, 0); }
  function settleCamera(action) { const damping = controls.enableDamping; controls.enableDamping = false; controls.update(); action(); controls.update(); controls.enableDamping = damping; }
  function zoom(direction) { settleCamera(() => { const offset = camera.position.clone().sub(controls.target), distance = THREE.MathUtils.clamp(offset.length() + (direction === 'in' ? -.8 : .8), controls.minDistance, controls.maxDistance); camera.position.copy(controls.target).addScaledVector(offset.normalize(), distance); }); }
  function turn(direction) { settleCamera(() => { const angle = direction === 'left' ? -.34 : .34; camera.position.sub(controls.target).applyAxisAngle(new THREE.Vector3(0, 1, 0), angle).add(controls.target); }); }
  function readSignal(entry) {
    level = expressiveLevel(entry); const neutral = level == null;
    root.classList.toggle('has-signal', !neutral); root.style.setProperty('--brain-signal', neutral ? '0' : level.toFixed(3));
    root.querySelector('[data-brain-signal]').textContent = neutral ? 'NEUTRAL · NO CHECK-IN' : `${Math.round(level * 100)}% · SELF-REPORTED`;
    root.querySelector('.brain-atlas__meter i').style.width = `${neutral ? 0 : Math.round(level * 100)}%`;
    root.dispatchEvent(new CustomEvent(BRAIN_EVENT, { detail: { level, source: neutral ? 'neutral' : 'local-checkin' } }));
  }
  function bindLabels() { root.querySelectorAll('[data-brain-part]').forEach(button => button.addEventListener('click', () => select(button.dataset.brainPart))); }
  function bind() {
    addEventListener('resize', resize); bindLabels();
    root.querySelectorAll('[data-brain-reset]').forEach(button => button.addEventListener('click', reset));
    root.querySelectorAll('[data-brain-zoom]').forEach(button => button.addEventListener('click', () => zoom(button.dataset.brainZoom)));
    root.querySelectorAll('[data-brain-turn]').forEach(button => button.addEventListener('click', () => turn(button.dataset.brainTurn)));
    canvas.addEventListener('pointerdown', event => {
      pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (!gesture) gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, maxMove: 0, multi: false };
      if (pointers.size > 1) gesture.multi = true;
    });
    canvas.addEventListener('pointermove', event => {
      const start = pointers.get(event.pointerId);
      if (start && gesture) gesture.maxMove = Math.max(gesture.maxMove, Math.hypot(event.clientX - start.x, event.clientY - start.y));
      if (event.buttons || pointers.size) { tooltip.hidden = true; return; }
      hovered = hit(event.clientX, event.clientY); tooltip.textContent = hovered ? BRAIN_PARTS[hovered.userData.key].name.toUpperCase() : ''; tooltip.hidden = !hovered;
      if (hovered) { const r = viewport.getBoundingClientRect(); tooltip.style.left = `${event.clientX - r.left}px`; tooltip.style.top = `${event.clientY - r.top}px`; }
    });
    const endPointer = event => {
      const isTap = gesture && event.pointerId === gesture.id && !gesture.multi && gesture.maxMove < 7 && Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) < 7;
      pointers.delete(event.pointerId);
      if (isTap) { const target = hit(event.clientX, event.clientY); if (target) select(target.userData.key); else clearSelection(); }
      if (!pointers.size) gesture = null;
      else if (gesture?.id === event.pointerId) { const [id, remaining] = pointers.entries().next().value; gesture = { id, x: remaining.x, y: remaining.y, maxMove: 8, multi: true }; }
    };
    canvas.addEventListener('pointerup', endPointer); canvas.addEventListener('pointercancel', endPointer);
    document.addEventListener('pointerdown', event => { if (!root.contains(event.target)) clearSelection(); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') clearSelection(); });
    document.addEventListener('health:checkin', event => readSignal(event.detail));
    addEventListener('storage', event => { if (event.key === BRAIN_STORAGE_KEY) readSignal(latestLocalEntry()); });
  }
  function animate() {
    requestAnimationFrame(animate); const now = performance.now(), moving = !reducedMotion.matches;
    pulsePhase = moving ? (now * .00022) % 1 : .18;
    const signal = level == null ? 0 : .25 + level * 1.35;
    if (magentaWave && cyanWave) {
      const a = pulsePhase * Math.PI * 2;
      magentaWave.position.set(Math.cos(a) * 2.25, .35 + Math.sin(a * 1.7) * .7, Math.sin(a) * 1.65 + .35);
      cyanWave.position.set(Math.cos(a + Math.PI) * 2.05, -.2 + Math.sin(a * 1.35 + 1) * .62, Math.sin(a + Math.PI) * 1.45 + .2);
      magentaWave.intensity = moving ? 1.05 + signal * .34 : .68;
      cyanWave.intensity = moving ? .82 + signal * .3 : .55;
    }
    for (const mesh of pickables) {
      const active = mesh.userData.key === selected, over = mesh === hovered, lower = mesh.userData.key === 'cerebellum' || mesh.userData.key === 'brainstem';
      const wave = moving ? .5 + .5 * Math.sin(now * .00165 + mesh.position.x * 2.8 + mesh.position.y * 1.7 + pickables.indexOf(mesh) * .83) : .56;
      mesh.material.emissive.setHex(lower ? (wave > .66 ? 0x123444 : 0x110b1d) : (wave > .52 ? 0x7e1bc0 : 0x153f70));
      mesh.material.emissiveIntensity = (lower ? .025 + wave * .055 : .055 + wave * .12 + signal * .075) + (active ? .24 : over ? .1 : 0);
    }
    controls.update(); renderer.render(scene, camera);
  }
  init();
}
