import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { disposeTempleGLTF } from './examples/load-model.js';

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const repoBase = new URL(params.get('base') || './', import.meta.url);
if (!repoBase.pathname.endsWith('/')) repoBase.pathname += '/';
$('manifest').href = new URL('manifest.json', repoBase).href;
const events = new AbortController();
const viewport = $('viewport');
const scene = new THREE.Scene();
scene.background = new THREE.Color('#151b23');
const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000);
const renderer = new THREE.WebGLRenderer({ canvas: $('viewer'), antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
const hemisphere = new THREE.HemisphereLight(0xe3efff, 0x726858, 2.5);
const sun = new THREE.DirectionalLight(0xffeddb, 3);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.normalBias = 0.03;
scene.add(hemisphere, sun, sun.target);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshStandardMaterial({ color: 0x263140, roughness: 1 }));
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
const grid = new THREE.GridHelper(1, 20, 0x728297, 0x435063);
scene.add(floor, grid);
floor.visible = grid.visible = false;
let assets = [], collections = [], current = null, currentDocument = null, currentBox = null, request = 0, closed = false;

function status(message, state = 'ready') {
  $('status').textContent = message;
  $('status').dataset.state = state;
}

function resize() {
  const width = viewport.clientWidth, height = viewport.clientHeight;
  if (!width || !height) return;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
}
const observer = new ResizeObserver(resize);
observer.observe(viewport);
resize();
renderer.setAnimationLoop(() => {
  if (closed || document.hidden) return;
  controls.update();
  renderer.render(scene, camera);
});

function resources(root) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  root.traverse((node) => {
    if (node.geometry) geometries.add(node.geometry);
    for (const material of [node.material].flat().filter(Boolean)) materials.add(material);
  });
  for (const material of materials) {
    for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    for (const uniform of Object.values(material.uniforms || {})) {
      for (const value of [uniform.value].flat()) if (value?.isTexture) textures.add(value);
    }
  }
  return { geometries, materials, textures };
}

function dispose(root) {
  if (!root) return;
  const { geometries, materials, textures } = resources(root), images = new Set();
  for (const texture of textures) {
    for (const image of [texture.source?.data].flat().filter(Boolean)) images.add(image);
    texture.dispose();
  }
  for (const image of images) if (typeof image.close === 'function') image.close();
  for (const material of materials) material.dispose();
  for (const geometry of geometries) geometry.dispose();
  root.removeFromParent();
}

function inspect(root) {
  root.updateMatrixWorld(true);
  const { geometries, materials, textures } = resources(root);
  let meshes = 0, triangles = 0;
  const errors = [];
  root.traverse((node) => {
    if (!node.isMesh) return;
    meshes++;
    const position = node.geometry?.getAttribute('position');
    if (!position?.count) errors.push('A mesh has no position vertices.');
    triangles += ((node.geometry?.index?.count ?? position?.count ?? 0) / 3) * (node.isInstancedMesh ? node.count : 1);
  });
  const box = new THREE.Box3().setFromObject(root);
  if (!meshes || box.isEmpty()) errors.push('The asset has no visible mesh bounds.');
  if (![...box.min.toArray(), ...box.max.toArray()].every(Number.isFinite)) errors.push('The model bounds are not finite.');
  const textureImages = [...textures].map((texture) => {
    const image = texture.source?.data;
    const width = image?.width ?? image?.naturalWidth ?? 0;
    const height = image?.height ?? image?.naturalHeight ?? 0;
    if (!(width > 0 && height > 0)) errors.push('A material texture has no decoded image: ' + (texture.name || texture.uuid));
    return { name: texture.name || '(unnamed)', width, height };
  });
  return { meshes, geometries: geometries.size, materials: materials.size, triangles, textures: textures.size, textureImages, bounds: { min: box.min.toArray(), max: box.max.toArray() }, errors };
}

function frame(box = currentBox) {
  if (!box) return;
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const radius = Math.max(size.length() / 2, 0.05);
  const vertical = THREE.MathUtils.degToRad(camera.fov / 2);
  const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
  const distance = radius / Math.sin(Math.min(vertical, horizontal)) * 1.2;
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(1, 0.65, 1).normalize().multiplyScalar(distance));
  camera.near = Math.max(radius / 1000, 0.001);
  camera.far = Math.max(radius * 2000, 100);
  camera.updateProjectionMatrix();
  controls.minDistance = radius * 0.05;
  controls.maxDistance = radius * 50;
  controls.update();
}

function prepareStage(box) {
  const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  const span = Math.max(size.x, size.y, size.z, 0.1);
  floor.position.set(center.x, box.min.y - span * 0.001, center.z);
  floor.scale.setScalar(span * 8);
  grid.position.set(center.x, box.min.y, center.z);
  grid.scale.setScalar(span * 4);
  floor.visible = grid.visible = true;
  sun.position.copy(center).add(new THREE.Vector3(-1, 2, 1).multiplyScalar(span * 2));
  sun.target.position.copy(center);
  Object.assign(sun.shadow.camera, { left: -span * 2, right: span * 2, top: span * 2, bottom: -span * 2, near: span * 0.01, far: span * 12 });
  sun.shadow.camera.updateProjectionMatrix();
  sun.shadow.normalBias = span * 0.002;
}

async function load(asset) {
  const token = ++request;
  status('Loading ' + asset.name + '…', 'loading');
  $('frame').disabled = true;
  const failures = [], manager = new THREE.LoadingManager();
  manager.onError = (url) => failures.push(url);
  let loaded = null, loadedDocument = null;
  try {
    loadedDocument = await new GLTFLoader(manager).loadAsync(new URL(asset.path, repoBase).href);
    loaded = loadedDocument.scene;
    if (closed || token !== request) { disposeTempleGLTF(loadedDocument); return; }
    const report = inspect(loaded);
    if (failures.length || report.errors.length) throw new Error([...report.errors, ...failures.map((url) => 'Resource failed: ' + url)].join(' '));
    if (currentDocument) disposeTempleGLTF(currentDocument);
    currentDocument = loadedDocument;
    loadedDocument = null;
    current = loaded;
    loaded = null;
    scene.add(current);
    current.traverse((node) => { if (node.isMesh) node.castShadow = node.receiveShadow = true; });
    currentBox = new THREE.Box3().setFromObject(current);
    prepareStage(currentBox);
    frame();
    const size = currentBox.getSize(new THREE.Vector3());
    $('dimensions').textContent = size.toArray().map((n) => n.toLocaleString('en', { maximumFractionDigits: 2 })).join(' × ');
    $('triangles').textContent = report.triangles.toLocaleString('en');
    $('bytes').textContent = Number(asset.bytes).toLocaleString('en') + ' bytes';
    $('structure').textContent = report.meshes + ' / ' + report.materials;
    $('frame').disabled = false;
    $('download').href = new URL(asset.path, repoBase).href;
    $('download').textContent = asset.self_contained ? 'Download GLB' : 'Open glTF (shared dependencies required)';
    $('download').hidden = false;
    const url = new URL(location.href);
    url.searchParams.set('asset', asset.id);
    history.replaceState(null, '', url);
    status('Loaded ' + asset.name + '.');
  } catch (error) {
    if (loadedDocument) disposeTempleGLTF(loadedDocument);
    if (closed || token !== request) return;
    status('Could not load ' + asset.name + ': ' + error.message, 'error');
    $('frame').disabled = !current;
  }
}

function fillModels(preferred) {
  const category = $('category').value;
  const collection = $('collection').value;
  const matches = assets.filter((asset) => asset.collection === collection && (!category || asset.category === category));
  $('asset').replaceChildren(...matches.map((asset) => new Option(asset.name, asset.id)));
  const selected = matches.find((asset) => asset.id === preferred) || matches[0];
  $('asset').disabled = !selected;
  if (selected) { $('asset').value = selected.id; return load(selected); }
  status('No models in this category.');
}

function fillCategories(preferred) {
  const matches = assets.filter((asset) => asset.collection === $('collection').value);
  const categories = [...new Set(matches.map((asset) => asset.category))].sort();
  $('category').replaceChildren(new Option('All categories', ''), ...categories.map((category) => new Option(category, category)));
  $('category').disabled = !matches.length;
  return fillModels(preferred);
}

async function validateAll() {
  const result = { complete: false, total: assets.length, passed: 0, failed: 0, assets: [] };
  $('validation-panel').hidden = false;
  $('validation-panel').open = true;
  const publish = () => { $('validation-results').textContent = JSON.stringify(result, null, 2); };
  publish();
  for (const asset of assets) {
    if (closed) break;
    $('validation-status').textContent = 'Checking ' + (result.assets.length + 1) + ' / ' + assets.length + ': ' + asset.name;
    const failures = [], manager = new THREE.LoadingManager();
    manager.onError = (url) => failures.push(url);
    let root = null, document = null, entry;
    try {
      document = await new GLTFLoader(manager).loadAsync(new URL(asset.path, repoBase).href);
      root = document.scene;
      const report = inspect(root);
      entry = { id: asset.id, collection: asset.collection, path: asset.path, ...report, resourceErrors: failures };
      entry.ok = report.errors.length === 0 && failures.length === 0;
    } catch (error) { entry = { id: asset.id, collection: asset.collection, path: asset.path, ok: false, error: error.message, resourceErrors: failures }; }
    finally { if (document) disposeTempleGLTF(document); }
    result.assets.push(entry);
    result[entry.ok ? 'passed' : 'failed']++;
    publish();
  }
  result.complete = !closed && result.assets.length === assets.length;
  publish();
  $('validation-status').textContent = result.passed + ' passed · ' + result.failed + ' failed';
  $('validation-status').dataset.state = result.failed ? 'error' : 'ready';
}

$('collection').addEventListener('change', () => fillCategories(), { signal: events.signal });
$('category').addEventListener('change', () => fillModels(), { signal: events.signal });
$('asset').addEventListener('change', () => load(assets.find((asset) => asset.id === $('asset').value)), { signal: events.signal });
$('frame').addEventListener('click', () => frame(), { signal: events.signal });
window.addEventListener('pagehide', (event) => {
  if (event.persisted) return;
  closed = true;
  request++;
  events.abort();
  observer.disconnect();
  renderer.setAnimationLoop(null);
  controls.dispose();
  if (currentDocument) disposeTempleGLTF(currentDocument);
  dispose(floor);
  dispose(grid);
  sun.dispose();
  renderer.dispose();
}, { signal: events.signal });

try {
  const response = await fetch(new URL('manifest.json', repoBase), { cache: 'no-store' });
  if (!response.ok) throw new Error('Manifest HTTP ' + response.status);
  const manifest = await response.json();
  if (!Array.isArray(manifest.assets) || !manifest.assets.length) throw new Error('The manifest has no assets.');
  collections = manifest.collections || [{ id: 'temple', name: 'Stylized Chinese Lost Temple' }];
  if (!Array.isArray(collections) || !collections.length) throw new Error('The manifest has no collections.');
  const collectionIds = new Set();
  for (const collection of collections) {
    if (!collection.id || collectionIds.has(collection.id)) throw new Error('Invalid or duplicate collection.');
    collectionIds.add(collection.id);
  }
  const ids = new Set();
  assets = manifest.assets.map((asset) => {
    const collection = asset.collection || 'temple';
    if (!asset.id || ids.has(asset.id) || !collectionIds.has(collection) || typeof asset.path !== 'string' || !asset.path.startsWith('models/')) throw new Error('Invalid or duplicate manifest entry.');
    ids.add(asset.id);
    return { ...asset, collection, name: asset.name || asset.id, category: asset.category || 'Uncategorized' };
  });
  const title = manifest.title || 'Three.js Stylized World Assets';
  $('library-title').textContent = title;
  document.title = title + ' — Asset Viewer';
  $('collection').replaceChildren(...collections.map((collection) => new Option(collection.name || collection.id, collection.id)));
  $('collection').disabled = false;
  const preferred = params.get('asset') || (ids.has('SM_Temple_BigRoof') ? 'SM_Temple_BigRoof' : assets[0].id);
  const selected = assets.find((asset) => asset.id === preferred) || assets[0];
  $('collection').value = selected.collection;
  await fillCategories(preferred);
  if (preferred && !ids.has(preferred)) status('Unknown asset ID. Showing the first model.', 'error');
  if (params.get('validate') === '1') await validateAll();
} catch (error) { status('Viewer could not start: ' + error.message, 'error'); }
