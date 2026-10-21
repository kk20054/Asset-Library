# Stylized Chinese Lost Temple

Three.js-ready conversions of the user-supplied Unity environment pack: **134 source FBX files, 135 self-contained GLB files**, approximately 355.7 MB in total. The extra GLB preserves a second source material variant for SM_Base_02. Every GLB contains its geometry, materials, and used image textures.

## Start here

- [Interactive asset viewer](https://kk20054.github.io/Stylized-Chinese-Lost-Temple/)
- [Instructions for Claude and other coding assistants](CLAUDE_USAGE.md)
- [Compact asset index for text-based tools](https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/asset-index.json)
- [Public JSON manifest](https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/manifest.json)
- [Reusable Three.js loading helper](examples/load-model.js)
- [Source inventory](source-catalog.json), [Prefab renderer assignments](source-prefabs.json), and [material mapping](source-materials.json)

All assets are ordinary Git files. **No Git LFS checkout, Unity installation, authentication, API key, or Draco/KTX2 decoder is required to load them.** Use the manifest URLs or the Pages viewer, rather than GitHub blob-page URLs.

## Load a model in Three.js

Use the same Three.js version for the core library and its addons. The included viewer uses version 0.180.0.

~~~js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const base = 'https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/';
const manifest = await fetch(base + 'manifest.json').then(r => {
  if (!r.ok) throw new Error('Manifest HTTP ' + r.status);
  return r.json();
});
const asset = manifest.assets.find(item => item.id === 'SM_Temple_BigRoof');
if (!asset) throw new Error('Unknown asset ID');
const gltf = await new GLTFLoader().loadAsync(new URL(asset.path, base).href);
scene.add(gltf.scene);
gltf.scene.position.set(0, 0, 0);
~~~

Models preserve their source pivots and import scale. glTF uses meters, a right-handed coordinate system, and +Y up. Sizes and triangle counts are available per asset in the manifest. Many files are modular building pieces, not complete standalone temples; assemble them as reusable objects. Character and panda meshes are included as static props only.

For reproducible projects, replace main in the base URL with a full commit SHA. Copy examples/load-model.js into your application, or import it from the Pages host. GitHub raw is appropriate for model and JSON data, but its JavaScript MIME type is not an ES-module hosting guarantee.

## Conversion details

The original ZIP files contain nested Unity packages. Built-in was selected because all 134 Built-in and URP FBX hashes matched. Original archives and full-resolution source images remain unchanged in the local source library and are not duplicated into this repository.

- Actual Prefab renderer/material GUID assignments were used, rather than untextured FBX defaults.
- Base color, normal, ORM, and enabled opacity-mask inputs were rebuilt as portable metallic/roughness PBR materials.
- Base-color images are at most 2048 pixels on their longest side. Normal/data images are at most 1024 pixels. Opaque colors use quality-92 JPEG; alpha and data images use PNG.
- Only highest-detail render meshes are exported. Lower LODs and collision helper meshes are excluded and listed in the manifest. No additional mesh decimation was performed.
- SM_Base_02_variant_1 and SM_Base_02_variant_2 preserve the two original Prefab material choices.

The water plane uses the source water color and a static normal map, with inactive legacy wood-texture properties excluded.

Unity ShaderGraph code, foliage wind, particles, water distortion, terrain/moss blending, scene lighting, and Unity runtime components are **not** converted into equivalent Three.js behaviors. This is a portable asset library, not a reconstruction of the complete Unity demo scene. Source Prefab and material metadata is included to support further work. One material slot in the source SM_Character_Merged Prefab is unassigned; that slot retains a neutral fallback.

## Validation

All 135 files passed the official Khronos glTF Validator with zero specification errors, zero container errors, and zero external-resource references. See [validation summary](validation/gltf-summary.json). The retained portability warnings concern runtime-generated normal-map tangent space; different renderers may produce small shading differences.

The browser viewer also has an explicit full-library load check at [?validate=1](https://kk20054.github.io/Stylized-Chinese-Lost-Temple/?validate=1). Results are displayed on the page, including failed resources and decoded image dimensions. Public-access and browser test receipts are recorded under validation after publication. These checks prove public HTTP access and Three.js loading; they do not claim an untested third-party chat account has parsed binary geometry as text.

To view a local checkout, serve this folder over HTTP; do not open index.html through a file URL:

~~~sh
python -m http.server 8080
~~~

## Source and rights

Source identity: the user-provided Stylized Chinese Lost Temple package, using the Assets/Stylarts namespace. Source hashes and mappings are retained for traceability. The user requested this repository publication on 2026-10-21. Conversion does not change the original assets' ownership or license terms, and this repository does not grant a new permissive license for third-party models or textures. Use the assets under the rights attached to your original source package. The third-party Three.js library and Khronos validator retain their own licenses.
