import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { disposeTempleGLTF } from './load-model.js';

const $ = id => document.getElementById(id);
const query = new URLSearchParams(location.search);
const base = new URL(query.get('base') || '../', import.meta.url);
if (!base.pathname.endsWith('/')) base.pathname += '/';
const events = new AbortController();
const world = new THREE.Scene();
world.background = new THREE.Color(0x9aafb9);
const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000);
const lights = new THREE.Group();
lights.add(new THREE.HemisphereLight(0xe4eff5, 0x67745c, 2));
lights.add(new THREE.AmbientLight(0xffffff, 0.8));
const sun = new THREE.DirectionalLight(0xffedcf, 2.5);
sun.position.set(-80, 140, 90);
lights.add(sun); world.add(lights, sun.target);
let renderer, controls, observer, records = [], current = null, currentRecord = null, box = null;
let token = 0, closed = false, busy = false, lastMetrics = 0, structure = null, views = [];
let lightDescription = 'Viewer directional and ambient lighting; static approximation';
$('scene-index').href = new URL('scenes/index.json', base).href;
const library = new URL('../', import.meta.url);
if (query.has('base')) library.searchParams.set('base', base.href);
$('library-link').href = library.href;

function status(message, error = false) {
  $('status').textContent = message;
  $('status').dataset.error = String(error);
}
function resize() {
  const viewport = $('viewport'), width = viewport.clientWidth, height = viewport.clientHeight;
  if (!renderer || !width || !height) return;
  camera.aspect = width / height; camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
}
function initializeRenderer() {
  renderer = new THREE.WebGLRenderer({ canvas: $('scene-canvas'), antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  observer = new ResizeObserver(resize); observer.observe($('viewport')); resize();
  renderer.setAnimationLoop(time => {
    if (closed || document.hidden) return;
    controls.update(); renderer.render(world, camera);
    if (time - lastMetrics > 500) { updateMetrics(); lastMetrics = time; }
  });
}
function vector(value) { return Array.isArray(value) && value.length === 3 && value.every(Number.isFinite); }
function readViews(record) {
  const legacy = record.camera?.overview || record.camera;
  const input = record.views?.length ? record.views : [
    { id: 'fullOverview', label: 'Complete layout' },
    ...(vector(legacy?.position) ? [{ ...legacy, id: 'legacyCamera', label: 'Legacy local camera view' }] : [])
  ];
  if (!Array.isArray(input)) throw new Error('Camera views must be an array.');
  const ids = new Set();
  return input.map(view => {
    if (!view.id || ids.has(view.id)) throw new Error('Invalid or duplicate camera view ID.');
    ids.add(view.id);
    for (const key of ['position', 'target']) if (view[key] !== undefined && !vector(view[key])) throw new Error('Invalid camera ' + key + ' in view ' + view.id);
    for (const key of ['near', 'far']) if (view[key] !== undefined && !(Number.isFinite(view[key]) && view[key] > 0)) throw new Error('Invalid camera ' + key + ' in view ' + view.id);
    if (view.near !== undefined && view.far !== undefined && view.far <= view.near) throw new Error('Camera far must exceed near in view ' + view.id);
    return { ...view, label: view.label || view.id };
  });
}
function currentView() { return views.find(view => view.id === $('view-select').value) || views[0] || {}; }
function applyLight(record) {
  const light = record.light;
  sun.color.set(0xffedcf); sun.intensity = 2.5;
  sun.position.set(-80, 140, 90); sun.target.position.set(0, 0, 0);
  if (!light) { lightDescription = 'Viewer directional and ambient lighting; static approximation'; return; }
  if (vector(light.color)) sun.color.setRGB(...light.color);
  if (Number.isFinite(light.intensity) && light.intensity >= 0) sun.intensity = light.intensity;
  if (vector(light.direction)) {
    const direction = new THREE.Vector3().fromArray(light.direction);
    if (direction.lengthSq() > 0) sun.position.copy(direction.normalize()).multiplyScalar(-Math.max(box.getSize(new THREE.Vector3()).length(), 100));
  }
  lightDescription = 'Source directional parameters with viewer hemisphere and ambient fill; static approximation';
}
function resetCamera() {
  if (!box || !controls) return;
  const center = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.length() / 2, 0.1);
  const authored = currentView();
  camera.fov = Number.isFinite(authored.fov) && authored.fov >= 10 && authored.fov <= 120 ? authored.fov : 45;
  const vertical = THREE.MathUtils.degToRad(camera.fov / 2);
  const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
  const distance = radius / Math.sin(Math.min(vertical, horizontal)) * 1.1;
  camera.up.fromArray(vector(authored.up) ? authored.up : [0, 1, 0]);
  controls.target.copy(center);
  if (vector(authored.target)) controls.target.fromArray(authored.target);
  if (vector(authored.position)) camera.position.fromArray(authored.position);
  else camera.position.copy(center).add(new THREE.Vector3(1, 0.8, 1).normalize().multiplyScalar(distance));
  camera.near = authored.near ?? Math.max(radius / 10000, 0.001);
  camera.far = authored.far ?? Math.max(radius * 100, camera.position.distanceTo(center) * 4, camera.near * 2, 100);
  camera.updateProjectionMatrix();
  controls.minDistance = Math.max(radius * 0.001, 0.01);
  controls.maxDistance = Math.max(radius * 50, distance * 2);
  controls.update();
  $('view-label').textContent = 'Current view: ' + authored.label + ' · camera only; original layout retained.';
}
function inspect(root) {
  root.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(root), materials = new Set(), geometries = new Set(), textures = new Set();
  let meshes = 0, triangles = 0, authoredLights = 0;
  root.traverse(node => {
    if (node.isLight) authoredLights++;
    if (!node.isMesh) return;
    meshes++;
    const geometry = node.geometry, position = geometry?.getAttribute('position');
    if (!position?.count) throw new Error('A scene mesh has no position vertices.');
    geometries.add(geometry);
    triangles += (geometry.index?.count ?? position.count) / 3 * (node.isInstancedMesh ? node.count : 1);
    for (const material of [node.material].flat().filter(Boolean)) materials.add(material);
  });
  if (!meshes || bounds.isEmpty() || ![...bounds.min.toArray(), ...bounds.max.toArray()].every(Number.isFinite)) throw new Error('The authored scene has no finite mesh bounds.');
  for (const material of materials) for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
  for (const texture of textures) {
    const image = texture.source?.data;
    if (!((image?.width ?? image?.naturalWidth) > 0 && (image?.height ?? image?.naturalHeight) > 0)) throw new Error('A scene texture has no decoded image.');
  }
  return { bounds, meshes, triangles, materials: materials.size, geometries: geometries.size, textures: textures.size, authoredLights };
}
function updateMetrics() {
  if (!renderer || !structure || !currentRecord) return;
  const info = renderer.info, dimensions = box.getSize(new THREE.Vector3()).toArray().map(value => value.toLocaleString('en', { maximumFractionDigits: 2 })).join(' × ');
  $('metrics').textContent = [
    'Scene: ' + currentRecord.id + ' | source-author layout',
    'View: ' + currentView().label + ' | near / far: ' + camera.near + ' / ' + camera.far,
    lightDescription,
    'Meshes: ' + structure.meshes + ' | source triangles: ' + structure.triangles.toLocaleString('en'),
    'Unique geometry / materials / textures: ' + structure.geometries + ' / ' + structure.materials + ' / ' + structure.textures,
    'Bounds (m): ' + dimensions,
    'Draw calls: ' + info.render.calls + ' | submitted triangles: ' + info.render.triangles,
    'Renderer allocations: ' + info.memory.geometries + ' geometries, ' + info.memory.textures + ' textures',
    'Portable static PBR | shadows OFF | resource counts are not memory bytes'
  ].join('\n');
}
function showRecord(record) {
  $('description').textContent = record.description || 'The exported scene hierarchy is displayed without random placement or model rescaling.';
  for (const [id, path] of [['model-link', record.model], ['layout-link', record.layout]]) {
    $(id).hidden = !path;
    if (path) $(id).href = new URL(path, base).href;
  }
  const omitted = record.omittedUnityEffects || record.omitted_unity_effects || record.omitted_features || [];
  $('omissions').replaceChildren(...(Array.isArray(omitted) ? omitted : [omitted]).map(text => {
    const item = document.createElement('li'); item.textContent = String(text); return item;
  }));
  const previews = Array.isArray(record.previews) ? record.previews : [];
  const links = previews.map((preview, index) => {
    const path = typeof preview === 'string' ? preview : preview?.path || preview?.url;
    if (!path) return null;
    const label = typeof preview === 'string' ? 'Source reference ' + (index + 1) : preview.label || preview.caption || preview.name || 'Source reference ' + (index + 1);
    const link = document.createElement('a'); link.href = new URL(path, base).href;
    link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = label;
    const image = document.createElement('img'); image.src = link.href; image.alt = label; image.loading = 'lazy'; link.append(image);
    return link;
  }).filter(Boolean);
  $('references').replaceChildren(...links); $('reference-panel').hidden = !links.length;
}
async function loadScene(record) {
  const request = ++token;
  busy = true; $('retry').disabled = true; $('reset').disabled = true; $('view-select').disabled = true;
  status('Loading complete scene: ' + record.name + '…');
  const failures = [], manager = new THREE.LoadingManager();
  manager.onError = url => failures.push(url);
  let document = null;
  try {
    document = await new GLTFLoader(manager).loadAsync(new URL(record.model, base).href, progress => {
      if (request !== token || closed) return;
      status('Loading complete scene: ' + record.name + '…' + (progress.total ? '\nScene file: ' + Math.round(progress.loaded / progress.total * 100) + '%' : '') + '\nShared model and texture dependencies may still be loading.');
    });
    if (closed || request !== token) { disposeTempleGLTF(document); return; }
    if (failures.length) throw new Error('Resource failed: ' + failures.join(', '));
    const report = inspect(document.scene), nextViews = readViews(record);
    if (current) disposeTempleGLTF(current);
    current = document; document = null; currentRecord = record; structure = report; box = report.bounds;
    world.add(current.scene); sun.visible = report.authoredLights === 0;
    views = nextViews;
    $('view-select').replaceChildren(...views.map(view => new Option(view.label, view.id)));
    $('view-select').value = views[0].id; $('view-select').disabled = false;
    applyLight(record); resetCamera(); showRecord(record);
    const url = new URL(location.href); url.searchParams.set('scene', record.id); history.replaceState(null, '', url);
    status('Loaded ' + record.name + '.\nSource-author layout · portable static PBR.');
    $('reset').disabled = false;
    updateMetrics();
  } catch (error) {
    if (document) disposeTempleGLTF(document);
    if (closed || request !== token) return;
    status('Could not load ' + record.name + ': ' + error.message + '\nUse Retry loading to try again.', true);
    $('reset').disabled = !current; $('view-select').disabled = !current;
  } finally {
    if (request === token && !closed) { busy = false; $('retry').disabled = false; }
  }
}
async function loadIndex() {
  busy = true; $('retry').disabled = true;
  status('Loading authored scene index…');
  try {
    const response = await fetch(new URL('scenes/index.json', base), { cache: 'no-store', signal: events.signal });
    if (!response.ok) throw new Error('Scene index HTTP ' + response.status);
    const index = await response.json(), scenes = Array.isArray(index) ? index : index.scenes;
    if (!Array.isArray(scenes) || !scenes.length) throw new Error('The scene index has no scenes.');
    const ids = new Set();
    records = scenes.map(record => {
      if (!record.id || ids.has(record.id) || typeof record.model !== 'string') throw new Error('Invalid or duplicate authored scene record.');
      ids.add(record.id); return { ...record, name: record.name || record.id };
    });
    if (closed) return;
    $('scene-select').replaceChildren(...records.map(record => new Option(record.name, record.id)));
    $('scene-select').disabled = false;
    const desired = query.get('scene') || 'overview';
    const selected = records.find(record => record.id === desired) || records[0];
    $('scene-select').value = selected.id;
    await loadScene(selected);
    if (!ids.has(desired) && !closed && currentRecord?.id === selected.id) status('Unknown scene ID "' + desired + '". Showing ' + selected.name + '.');
  } catch (error) {
    if (!closed) status('Could not load the authored scene index: ' + error.message + '\nUse Retry loading to try again.', true);
  } finally { if (!closed && !records.length) { busy = false; $('retry').disabled = false; } }
}
$('scene-select').addEventListener('change', () => {
  const record = records.find(record => record.id === $('scene-select').value);
  if (record) loadScene(record);
}, { signal: events.signal });
$('view-select').addEventListener('change', () => { resetCamera(); updateMetrics(); }, { signal: events.signal });
$('reset').addEventListener('click', resetCamera, { signal: events.signal });
$('retry').addEventListener('click', () => {
  if (busy || closed) return;
  if (!renderer || !controls) { location.reload(); return; }
  const record = records.find(record => record.id === $('scene-select').value);
  if (record) loadScene(record); else loadIndex();
}, { signal: events.signal });
window.addEventListener('pagehide', event => {
  if (event.persisted) return;
  closed = true; token++; events.abort(); observer?.disconnect();
  renderer?.setAnimationLoop(null); controls?.dispose();
  if (current) disposeTempleGLTF(current);
  renderer?.dispose();
}, { signal: events.signal });
try { initializeRenderer(); await loadIndex(); }
catch (error) { busy = false; $('retry').disabled = false; status('Scene viewer could not start: ' + error.message, true); }
