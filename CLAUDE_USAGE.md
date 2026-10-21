# Using these assets with Claude

## Text entry points

Read these public text files first:

1. https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/asset-index.json (compact asset list)
2. https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/manifest.json (full metadata)
3. https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/README.md
4. https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/examples/load-model.js

The manifest provides exact asset IDs, GLB paths and URLs, source identity, categories, sizes, triangle counts, hashes, and conversion limitations. Do not guess filenames. The GLB files are binary resources for GLTFLoader; a chat document parser does not need to decode their geometry as text.

## Prompt to copy into Claude

> Build a Three.js scene using the public asset library at https://github.com/kk20054/Stylized-Chinese-Lost-Temple . First fetch the raw manifest.json and use only asset IDs and paths present in it. Load models with GLTFLoader from https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/ . The GLBs include their textures and need no Unity runtime or compression decoder. Preserve +Y-up meters and source pivots, assemble modular building pieces, show loading errors visibly, and dispose resources when removing models. Refer to the source Prefab/material metadata for original renderer assignments. Custom Unity shader effects and a complete assembled demo scene are not included. Use the same pinned Three.js version for the core and addons. Do not use github.com/blob URLs as model URLs.

## Minimal asset selection

~~~js
const baseURL = 'https://raw.githubusercontent.com/kk20054/Stylized-Chinese-Lost-Temple/main/';
const response = await fetch(new URL('manifest.json', baseURL));
if (!response.ok) throw new Error('Manifest HTTP ' + response.status);
const { assets } = await response.json();
const roofs = assets.filter(asset => /roof/i.test(asset.name));
const gltf = await loader.loadAsync(new URL(roofs[0].path, baseURL).href);
scene.add(gltf.scene);
~~~

GitHub repository pages are for browsing, raw URLs are for data, and the Pages site hosts the interactive viewer and importable JavaScript helper. A client with restricted network access may require permission to reach raw.githubusercontent.com and the selected Three.js CDN. Never add a GitHub token to browser code for this public library.

For a quick visual check, open https://kk20054.github.io/Stylized-Chinese-Lost-Temple/?asset=SM_Temple_BigRoof . For a cross-origin check from a local HTTP viewer, use its base query parameter with the public raw root URL.
