import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// Copy this module into your app, or import it from the published Pages site.
// GitHub raw serves JavaScript as text; use raw only as the asset base below.
// Use the same Three.js import map as index.html, or your own Three.js 0.180.0 build.
// The default base resolves to this repository's root on any static HTTP host.
const DEFAULT_BASE = new URL('../', import.meta.url).href;

function directoryURL(baseURL) {
  const value = String(baseURL);
  return new URL(value.endsWith('/') ? value : value + '/');
}

export async function loadTempleManifest(baseURL = DEFAULT_BASE) {
  const url = new URL('manifest.json', directoryURL(baseURL));
  const response = await fetch(url);
  if (!response.ok) throw new Error('Asset manifest HTTP ' + response.status + ': ' + url);
  const manifest = await response.json();
  if (!Array.isArray(manifest.assets)) throw new Error('The manifest must contain an assets array.');
  return manifest;
}

// Example usage inside a module:
// const baseURL = 'https://raw.githubusercontent.com/kk20054/Asset-Library/COMMIT_SHA/';
// const manifest = await loadTempleManifest(baseURL);
// const model = await loadTempleModel(manifest.assets[0].id, { baseURL, manifest });
// scene.add(model.object);
// model.object.position.set(0, 0, 0);
// Call model.dispose() when the model is removed permanently.
// Replace COMMIT_SHA with a real commit for reproducible content, or use main.
// A public raw base URL must return real GLB bytes and permit cross-origin requests.
export async function loadTempleModel(assetId, {
  baseURL = DEFAULT_BASE,
  manifest = null,
  manager = undefined,
  onProgress = undefined,
} = {}) {
  const catalog = manifest || await loadTempleManifest(baseURL);
  const asset = catalog.assets.find((item) => item.id === assetId);
  if (!asset) throw new Error('Unknown asset ID: ' + assetId);
  const url = new URL(asset.path, directoryURL(baseURL)).href;
  const gltf = await new GLTFLoader(manager).loadAsync(url, onProgress);
  let disposed = false;
  return {
    asset,
    url,
    gltf,
    object: gltf.scene,
    dispose() {
      if (disposed) return;
      disposed = true;
      disposeTempleGLTF(gltf);
    },
  };
}

// This disposes every scene in the document, including shared resources only once.
// Do not call it while another object still uses this document's resources.
export function disposeTempleGLTF(gltf) {
  const geometries = new Set(), materials = new Set(), textures = new Set(), images = new Set(), skeletons = new Set();
  const scenes = gltf.scenes?.length ? gltf.scenes : [gltf.scene];
  for (const root of scenes) {
    if (!root) continue;
    root.removeFromParent();
    root.traverse((node) => {
      if (node.geometry) geometries.add(node.geometry);
      if (node.skeleton) skeletons.add(node.skeleton);
      for (const material of [node.material].flat().filter(Boolean)) materials.add(material);
    });
  }
  for (const material of materials) {
    for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    for (const uniform of Object.values(material.uniforms || {})) {
      for (const value of [uniform.value].flat()) if (value?.isTexture) textures.add(value);
    }
  }
  for (const texture of textures) {
    for (const image of [texture.source?.data].flat().filter(Boolean)) images.add(image);
    texture.dispose();
  }
  for (const image of images) if (typeof image.close === 'function') image.close();
  for (const material of materials) material.dispose();
  for (const geometry of geometries) geometry.dispose();
  for (const skeleton of skeletons) skeleton.dispose();
}
