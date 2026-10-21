import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { disposeTempleGLTF } from './load-model.js';

const ui = Object.fromEntries(['world', 'metrics', 'status', 'clone', 'instanced', 'near', 'far', 'retry'].map(id => [id, document.getElementById(id)]));
const query = new URLSearchParams(location.search);
const baseText = query.get('base') || new URL('../', import.meta.url).href;
const base = new URL(baseText.endsWith('/') ? baseText : baseText + '/', location.href);
let mode = query.get('mode') === 'clone' ? 'clone' : 'instanced';
let renderer, controls, ground, view, ready = false, loading = false, destroyed = false;
let cameraLabel = 'near';
let records = [], frames = [], warmup = 30, lastFrame = 0, lastMetrics = 0, modeFrames = 0;
const cache = new Map(), documents = new Set(), reflected = new Map(), groundTextures = new Set();
let groundPromise = null, groundLayerId = '';
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xc8d9df);
const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 1600);
const mirror = new THREE.Matrix4().makeScale(-1, 1, 1);

function status(message, error = false) {
  ui.status.textContent = message;
  ui.status.dataset.error = String(error);
}
function resetSamples() {
  frames = []; warmup = 30; lastFrame = 0; modeFrames = 0;
}
function cameraPreset(far) {
  cameraLabel = far ? 'far' : 'near';
  camera.position.set(...(far ? [240, 220, 260] : [36, 24, 42]));
  controls.target.set(0, 2, 0);
  controls.update();
  resetSamples();
}
function seeded(seed) {
  return () => { seed |= 0; seed = seed + 0x6d2b79f5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t ^= t + Math.imul(t ^ t >>> 7, 61 | t); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
function placements(count, seed, temple) {
  const random = seeded(seed), result = [], dummy = new THREE.Object3D();
  for (let i = 0; i < count; i++) {
    let x = 0, z = 0;
    if (!temple) do { x = (random() - 0.5) * 290; z = (random() - 0.5) * 290; } while (Math.hypot(x, z) < 19);
    const scale = temple ? 1 : 0.8 + random() * 0.4;
    dummy.position.set(x, 0, z); dummy.rotation.set(0, temple ? 0 : random() * Math.PI * 2, 0); dummy.scale.setScalar(scale); dummy.updateMatrix();
    result.push(dummy.matrix.clone());
  }
  return result;
}
function selectAssets(manifest) {
  if (!Array.isArray(manifest.assets)) throw new Error('The manifest has no assets array.');
  const temple = manifest.assets.find(a => a.collection === 'temple' && a.id === 'SM_Temple') || manifest.assets.find(a => a.collection === 'temple' && a.id === 'SM_Temple_BigRoof');
  if (!temple) throw new Error('The unified manifest is missing Temple SM_Temple / SM_Temple_BigRoof.');
  const selected = [{ asset: temple, count: 1, seed: 1, temple: true }];
  const categories = [['Trees', 96, 11], ['Grass', 192, 22], ['Flowers', 64, 33], ['Rocks', 32, 44]];
  for (const [category, count, seed] of categories) {
    let matches = manifest.assets.filter(a => a.collection === 'meadow' && a.category?.toLowerCase() === category.toLowerCase());
    let fallback = false;
    if (category === 'Trees') {
      const trees = matches.filter(a => /tree/i.test(a.id + ' ' + (a.name || '')) && !/bush/i.test(a.id + ' ' + (a.name || '')));
      if (trees.length) matches = trees;
      else fallback = true;
    }
    matches.sort((a, b) => (a.season_priority ?? 2) - (b.season_priority ?? 2) || (a.triangles || Infinity) - (b.triangles || Infinity) || Number(a.id.includes('__')) - Number(b.id.includes('__')) || a.id.localeCompare(b.id));
    if (!matches.length) throw new Error('The unified manifest is missing Meadow category: ' + category);
    const warning = fallback ? 'Tree fallback: no named Tree model without Bush was found; using ' + matches[0].id + '.' : '';
    selected.push({ asset: matches[0], count, seed, temple: false, warning });
  }
  return selected;
}
function loadAsset(asset) {
  const url = new URL(asset.path, base).href;
  if (!cache.has(url)) {
    const failures = [], manager = new THREE.LoadingManager();
    manager.onError = failedURL => failures.push(failedURL);
    cache.set(url, new GLTFLoader(manager).loadAsync(url).then(gltf => {
      if (failures.length) {
        disposeTempleGLTF(gltf);
        throw new Error('Resource failed: ' + failures.join(', '));
      }
      documents.add(gltf);
      return gltf;
    }).catch(error => { cache.delete(url); throw new Error(asset.id + ': ' + error.message); }));
  }
  return cache.get(url);
}
function prepareRecord(item, gltf) {
  const source = gltf.scene;
  source.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(source);
  if (box.isEmpty() || !Number.isFinite(box.min.y)) throw new Error(item.asset.id + ' has no finite renderable bounds.');
  const parts = [];
  source.traverse(mesh => {
    if (!mesh.isMesh) return;
    let parent = mesh;
    while (parent) { if (!parent.visible) return; parent = parent.parent; }
    if (mesh.isSkinnedMesh || mesh.morphTargetInfluences?.some(v => v !== 0)) throw new Error(item.asset.id + ' needs skin/morph baking for this static comparison.');
    parts.push({ geometry: mesh.geometry, material: mesh.material, matrix: mesh.matrixWorld.clone(), renderOrder: mesh.renderOrder });
  });
  if (!parts.length) throw new Error(item.asset.id + ' has no visible meshes.');
  return { ...item, gltf, parts, offset: new THREE.Matrix4().makeTranslation(0, -box.min.y, 0), placements: placements(item.count, item.seed, item.temple) };
}
// Reflected source nodes need corrected winding: InstancedMesh cannot use negative instance scales.
function positivePart(part) {
  if (part.matrix.determinant() >= 0) return part;
  if (!reflected.has(part.geometry)) {
    const geometry = part.geometry.clone().applyMatrix4(mirror);
    if (!geometry.index) geometry.setIndex(Array.from({ length: geometry.attributes.position.count }, (_, i) => i));
    const index = geometry.index.array;
    for (let i = 0; i < index.length; i += 3) [index[i + 1], index[i + 2]] = [index[i + 2], index[i + 1]];
    geometry.index.needsUpdate = true;
    reflected.set(part.geometry, geometry);
  }
  return { ...part, geometry: reflected.get(part.geometry), matrix: part.matrix.clone().multiply(mirror) };
}
function clearView() {
  if (!view) return;
  view.traverse(node => { if (node.isInstancedMesh) node.dispose(); });
  view.removeFromParent();
  view = null;
}
function rebuild(nextMode) {
  clearView(); mode = nextMode; view = new THREE.Group(); view.name = 'Mixed scene ' + mode;
  for (const record of records) {
    if (mode === 'clone') {
      for (const placement of record.placements) {
        const holder = new THREE.Group();
        holder.matrixAutoUpdate = false;
        holder.matrix.copy(placement).multiply(record.offset);
        holder.add(record.gltf.scene.clone(true));
        view.add(holder);
      }
    } else {
      const batches = new Map();
      for (const original of record.parts) {
        const part = positivePart(original);
        const key = part.geometry.uuid + ':' + [part.material].flat().map(m => m.uuid).join(',') + ':' + part.renderOrder;
        if (!batches.has(key)) batches.set(key, { ...part, transforms: [] });
        const batch = batches.get(key);
        for (const placement of record.placements) batch.transforms.push(placement.clone().multiply(record.offset).multiply(part.matrix));
      }
      for (const batch of batches.values()) {
        const mesh = new THREE.InstancedMesh(batch.geometry, batch.material, batch.transforms.length);
        mesh.renderOrder = batch.renderOrder;
        batch.transforms.forEach((matrix, index) => mesh.setMatrixAt(index, matrix));
        mesh.instanceMatrix.needsUpdate = true;
        mesh.computeBoundingBox(); mesh.computeBoundingSphere();
        view.add(mesh);
      }
    }
  }
  scene.add(view);
  ui.clone.setAttribute('aria-pressed', String(mode === 'clone'));
  ui.instanced.setAttribute('aria-pressed', String(mode === 'instanced'));
  const url = new URL(location.href); url.searchParams.set('mode', mode); history.replaceState(null, '', url);
  resetSamples();
  const warnings = records.map(r => r.warning).filter(Boolean);
  status('Loaded only ' + records.length + ' selected assets. Mode: ' + mode + '.\n' + records.map(r => r.asset.id + ' × ' + r.count).join('\n') + (warnings.length ? '\n' + warnings.join('\n') : ''));
}
function loadGround() {
  if (!groundPromise) groundPromise = (async () => {
    const response = await fetch(new URL('collections/meadow/terrain-textures.json', base), { cache: 'no-store' });
    if (!response.ok) throw new Error('Terrain texture manifest HTTP ' + response.status);
    const catalog = await response.json();
    const layers = catalog.layers || [];
    const layer = layers.find(item => item.name === 'ME_Grass_Terrain_Layer') || layers.find(item => /Grass/i.test(item.name || ''));
    if (!layer) throw new Error('Terrain texture manifest has no authored Grass layer.');
    const tile = layer.tileSize, offset = layer.tileOffset;
    if (!(tile?.x > 0 && tile?.y > 0) || !Number.isFinite(layer.normalScale)) throw new Error('Invalid Grass layer tile size or normal scale.');
    const textures = ['diffuse', 'normal'].map(role => {
      const texture = catalog.textures?.find(item => item.id === layer.textures?.[role] && item.role === role);
      if (!texture?.path) throw new Error('Grass layer is missing its ' + role + ' texture.');
      return texture;
    });
    const loader = new THREE.TextureLoader();
    const outcomes = await Promise.allSettled(textures.map(texture => loader.loadAsync(new URL(texture.path, base).href)));
    const loaded = outcomes.filter(result => result.status === 'fulfilled').map(result => result.value);
    const errors = outcomes.filter(result => result.status === 'rejected');
    if (destroyed || errors.length) {
      loaded.forEach(texture => texture.dispose());
      throw new Error(destroyed ? 'Ground loading was closed.' : 'Ground texture failed: ' + errors.map(result => result.reason?.message || result.reason).join('; '));
    }
    const [diffuse, normal] = loaded;
    for (const texture of loaded) {
      texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
      texture.repeat.set(360 / tile.x, 360 / tile.y);
      texture.offset.set((offset?.x || 0) / tile.x, (offset?.y || 0) / tile.y);
      groundTextures.add(texture);
    }
    diffuse.colorSpace = THREE.SRGBColorSpace;
    normal.colorSpace = THREE.NoColorSpace;
    ground.material.color.set(0xffffff);
    ground.material.map = diffuse;
    ground.material.normalMap = normal;
    ground.material.normalScale.set(layer.normalScale, layer.normalScale);
    ground.material.needsUpdate = true;
    groundLayerId = layer.id;
  })().catch(error => { groundPromise = null; throw error; });
  return groundPromise;
}
async function startLoading() {
  if (loading || destroyed) return;
  loading = true; ready = false;
  ui.retry.disabled = true; ui.clone.disabled = true; ui.instanced.disabled = true;
  status('Loading one authored Grass ground layer and five selected assets. Unselected models are not requested.');
  try {
    const response = await fetch(new URL('manifest.json', base), { cache: 'no-store' });
    if (!response.ok) throw new Error('Manifest HTTP ' + response.status);
    const selected = selectAssets(await response.json());
    await loadGround();
    // allSettled keeps a failed request from racing retry/disposal while others are still loading.
    const outcomes = await Promise.allSettled(selected.map(async item => prepareRecord(item, await loadAsset(item.asset))));
    const errors = outcomes.filter(r => r.status === 'rejected');
    if (errors.length) throw new Error(errors.map(r => r.reason.message).join('\n'));
    if (destroyed) { disposeDocuments(); return; }
    records = outcomes.map(r => r.value);
    rebuild(mode); ready = true;
    ui.clone.disabled = false; ui.instanced.disabled = false;
  } catch (error) {
    status('Loading failed. ' + error.message + '\nCheck the base URL, network access, and unified manifest. Retry uses already loaded assets.', true);
  } finally { loading = false; ui.retry.disabled = false; }
}
function quantile(sorted, q) { return sorted[Math.floor((sorted.length - 1) * q)].toFixed(2); }
function metrics() {
  const sorted = [...frames].sort((a, b) => a - b), info = renderer.info;
  const drawSize = renderer.getDrawingBufferSize(new THREE.Vector2());
  const timing = sorted.length >= 120 ? 'p50 ' + quantile(sorted, 0.5) + ' ms | p95 ' + quantile(sorted, 0.95) + ' ms' : 'Collecting: ' + sorted.length + '/120 minimum samples';
  ui.metrics.textContent = [
    'Three.js 0.180.0 | ' + mode + ' | shadows OFF',
    'Draw calls: ' + info.render.calls + ' | submitted triangles: ' + info.render.triangles,
    'Renderer allocations: ' + info.memory.geometries + ' geometries, ' + info.memory.textures + ' textures',
    'Programs: ' + (info.programs?.length || 0) + ' | cached asset documents: ' + documents.size,
    'Last camera preset: ' + cameraLabel,
    'Ground layer: ' + (groundLayerId || 'not loaded') + ' | one tiled material; no terrain blending',
    'Placements: ' + records.reduce((sum, r) => sum + r.count, 0) + ' | loaded sources: ' + records.length,
    'RAF frame intervals: ' + timing,
    'Window: latest 240 samples after 30 warm-up frames; mode frames: ' + modeFrames,
    'Timing includes browser scheduling; it is not isolated GPU time.',
    'Drawing buffer: ' + drawSize.x + ' × ' + drawSize.y + ' | DPR: ' + renderer.getPixelRatio(),
    'Resource counts are counts, not GPU memory bytes.',
    'Base: ' + base.href,
    'UA: ' + navigator.userAgent
  ].join('\n');
}
function resize() {
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix();
  resetSamples();
}
function animate(time) {
  if (destroyed) return;
  controls.update(); renderer.render(scene, camera);
  if (ready) {
    modeFrames++;
    if (warmup > 0) warmup--;
    else if (lastFrame) { frames.push(time - lastFrame); if (frames.length > 240) frames.shift(); }
    lastFrame = time;
  }
  if (time - lastMetrics > 400) { metrics(); lastMetrics = time; }
}
function disposeDocuments() {
  const geometries = new Set(reflected.values()), materials = new Set(), textures = new Set(), images = new Set();
  for (const gltf of documents) for (const source of gltf.scenes || [gltf.scene]) source.traverse(node => {
    if (node.geometry) geometries.add(node.geometry);
    for (const material of [node.material].flat().filter(Boolean)) materials.add(material);
  });
  for (const material of materials) for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
  for (const texture of textures) { for (const image of [texture.source?.data].flat().filter(Boolean)) images.add(image); texture.dispose(); }
  for (const image of images) if (typeof image.close === 'function') image.close();
  for (const material of materials) material.dispose();
  for (const geometry of geometries) geometry.dispose();
  documents.clear(); cache.clear(); reflected.clear();
}
function dispose() {
  if (destroyed) return;
  destroyed = true; ready = false;
  renderer?.setAnimationLoop(null); controls?.dispose(); clearView(); disposeDocuments();
  groundTextures.forEach(texture => texture.dispose()); groundTextures.clear();
  ground?.geometry.dispose(); ground?.material.dispose(); renderer?.dispose();
  window.removeEventListener('resize', resize);
}
try {
  renderer = new THREE.WebGLRenderer({ canvas: ui.world, antialias: true });
  renderer.shadowMap.enabled = false;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  scene.add(new THREE.HemisphereLight(0xd9ebff, 0x71664c, 2));
  const sun = new THREE.DirectionalLight(0xfff0d8, 2.5); sun.position.set(-80, 160, 70); scene.add(sun);
  ground = new THREE.Mesh(new THREE.PlaneGeometry(360, 360), new THREE.MeshStandardMaterial({ color: 0x71815a, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.02; scene.add(ground);
  controls = new OrbitControls(camera, ui.world); controls.enableDamping = true; controls.maxPolarAngle = Math.PI * 0.49; controls.maxDistance = 900;
  cameraPreset(false); resize();
  ui.clone.addEventListener('click', () => { if (ready) rebuild('clone'); });
  ui.instanced.addEventListener('click', () => { if (ready) rebuild('instanced'); });
  ui.near.addEventListener('click', () => cameraPreset(false)); ui.far.addEventListener('click', () => cameraPreset(true));
  ui.retry.addEventListener('click', startLoading);
  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', resetSamples);
  window.addEventListener('pagehide', event => { if (!event.persisted) dispose(); });
  renderer.setAnimationLoop(animate);
  startLoading();
} catch (error) { status('Renderer initialization failed: ' + error.message, true); dispose(); }
