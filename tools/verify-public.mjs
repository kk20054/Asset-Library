#!/usr/bin/env node
// Bounded anonymous verification: HEAD every declared file, GET only metadata and two model samples.
import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import { parseArgs } from 'node:util';

const { values } = parseArgs({ args: process.argv.slice(2), options: { base: { type: 'string' }, output: { type: 'string' }, help: { type: 'boolean' } } });
if (values.help || !values.base || !values.output) {
  console.log('Usage: node tools/verify-public.mjs --base https://raw.githubusercontent.com/OWNER/REPO/REF/ --output report.json');
  process.exit(values.help ? 0 : 1);
}
const base = new URL(values.base);
if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) throw new Error('Use an HTTP(S) directory URL without credentials, query, or fragment.');
if (!base.pathname.endsWith('/')) base.pathname += '/';
const report = {
  base: base.href, started_at: new Date().toISOString(), finished_at: null, complete: false, ok: false,
  request_policy: { anonymous: true, timeout_ms: 15000, maximum_attempts: 2, head_concurrency: 6, sample_body_limit_bytes: 33554432, total_sample_budget_bytes: 67108864 },
  schema: null, total_files: 0, payload_files: 0, head_passed: 0, head_failed: 0,
  cors: { passed: 0, failed: 0 }, content_length: { checked: 0, missing: 0, mismatched: 0 },
  get_checks: [], head_checks: [], sample_hashes: [], failures: [],
};
const files = new Map(), smallCache = new Map();

function urlFor(path) {
  if (typeof path !== 'string' || !path || path.startsWith('/')) throw new Error('Invalid repository-relative catalog path.');
  const url = new URL(path, base);
  if (!url.href.startsWith(base.href) || url.search || url.hash) throw new Error('A catalog path escapes the public base URL.');
  return url.href;
}
function fail(url, message) { report.failures.push({ url, message }); }
function lfsPointer(bytes) { return bytes.subarray(0, 200).toString('utf8').includes('version https://git-lfs.github.com/spec/v1'); }
function hash(bytes) { return createHash('sha256').update(bytes).digest('hex'); }
function addFile(item, kind) {
  const url = urlFor(item.path), existing = files.get(url);
  if (existing) {
    if (item.bytes !== undefined && existing.bytes !== undefined && item.bytes !== existing.bytes) throw new Error('Conflicting byte counts for ' + url);
    if (item.sha256 && existing.sha256 && item.sha256 !== existing.sha256) throw new Error('Conflicting hashes for ' + url);
    if (item.bytes !== undefined) existing.bytes = item.bytes;
    if (item.sha256) existing.sha256 = item.sha256;
    existing.kinds.add(kind);
  } else files.set(url, { url, bytes: item.bytes, sha256: item.sha256, kinds: new Set([kind]) });
}
async function request(url, method, limit = 8388608) {
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt++) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, { method, headers: { 'Accept-Encoding': 'identity' }, redirect: 'follow', cache: 'no-store', signal: controller.signal });
      if (response.status !== 200) throw new Error('HTTP ' + response.status);
      const chunks = [];
      let size = 0;
      if (method === 'GET') {
        for await (const chunk of response.body) {
          size += chunk.length;
          if (size > limit) { controller.abort(); throw new Error('Response exceeded the bounded download limit.'); }
          chunks.push(chunk);
        }
      }
      return { status: response.status, headers: response.headers, bytes: Buffer.concat(chunks), attempts: attempt };
    } catch (error) { lastError = error; }
    finally { clearTimeout(timer); }
  }
  throw new Error(lastError?.name === 'AbortError' ? 'Request timed out after 15000 ms (maximum two attempts).' : String(lastError?.message || lastError));
}
async function getSmall(path) {
  const url = urlFor(path);
  if (smallCache.has(url)) return smallCache.get(url);
  const entry = { url, ok: false };
  report.get_checks.push(entry);
  try {
    const response = await request(url, 'GET');
    if (!response.bytes.length || lfsPointer(response.bytes)) throw new Error('Empty body or Git LFS pointer instead of public file content.');
    const data = path.endsWith('.json') ? JSON.parse(response.bytes.toString('utf8')) : response.bytes.toString('utf8');
    Object.assign(entry, { ok: true, status: 200, bytes: response.bytes.length, attempts: response.attempts });
    addFile({ path }, 'metadata');
    smallCache.set(url, data);
    return data;
  } catch (error) {
    entry.error = error.message;
    fail(url, error.message);
    throw error;
  }
}
function validatePayload(item) {
  if (!Number.isSafeInteger(item.bytes) || item.bytes < 1 || !/^[a-f0-9]{64}$/i.test(item.sha256 || '')) throw new Error('Invalid payload size/hash for ' + urlFor(item.path));
}
function validateCatalog(manifest) {
  if (manifest.schema_version !== 2 || !Array.isArray(manifest.assets) || !manifest.assets.length || manifest.asset_count !== manifest.assets.length) throw new Error('Manifest schema/count mismatch.');
  if (!Array.isArray(manifest.collections) || !manifest.collections.length) throw new Error('Manifest has no collections.');
  const ids = new Set(), collections = new Set(manifest.collections.map(collection => collection.id));
  if (collections.size !== manifest.collections.length) throw new Error('Duplicate collection IDs.');
  for (const asset of manifest.assets) {
    if (!asset.id || ids.has(asset.id) || !collections.has(asset.collection)) throw new Error('Duplicate asset ID or unknown collection.');
    ids.add(asset.id); validatePayload(asset); addFile(asset, 'model');
    for (const dependency of asset.dependencies || []) { validatePayload(dependency); addFile(dependency, 'dependency'); }
  }
  for (const collection of manifest.collections) {
    if (manifest.assets.filter(asset => asset.collection === collection.id).length !== collection.asset_count) throw new Error('Collection count mismatch for ' + collection.id);
    urlFor(collection.asset_index);
  }
  report.schema = { version: manifest.schema_version, assets: manifest.assets.length, collections: manifest.collections.map(collection => ({ id: collection.id, assets: collection.asset_count })) };
}
async function headFile(file) {
  const entry = { url: file.url, kinds: [...file.kinds], ok: false, expected_bytes: file.bytes ?? null };
  try {
    const response = await request(file.url, 'HEAD');
    entry.status = 200; entry.attempts = response.attempts;
    entry.cors = response.headers.get('access-control-allow-origin');
    entry.cors_ok = entry.cors === '*';
    report.cors[entry.cors_ok ? 'passed' : 'failed']++;
    const length = response.headers.get('content-length');
    entry.content_length = length === null ? null : Number(length);
    entry.content_encoding = response.headers.get('content-encoding');
    if (length === null) report.content_length.missing++;
    else if (file.bytes !== undefined) {
      entry.content_length_ok = Number.isSafeInteger(entry.content_length) && entry.content_length === file.bytes;
      report.content_length.checked++;
      if (!entry.content_length_ok) report.content_length.mismatched++;
    }
    entry.ok = entry.cors_ok && entry.content_length_ok !== false;
    if (!entry.cors_ok) fail(file.url, 'Access-Control-Allow-Origin must be *.');
    if (entry.content_length_ok === false) fail(file.url, 'Content-Length differs from declared bytes.');
  } catch (error) { entry.error = error.message; fail(file.url, error.message); }
  report[entry.ok ? 'head_passed' : 'head_failed']++;
  report.head_checks.push(entry);
}
async function concurrent(items, count, operation) {
  let index = 0;
  await Promise.all(Array.from({ length: Math.min(count, items.length) }, async () => {
    while (index < items.length) await operation(items[index++]);
  }));
}
function magic(bytes, path) {
  if (lfsPointer(bytes)) throw new Error('Git LFS pointer returned instead of payload.');
  if (path.endsWith('.glb')) {
    if (bytes.length < 12 || bytes.toString('ascii', 0, 4) !== 'glTF' || bytes.readUInt32LE(4) !== 2 || bytes.readUInt32LE(8) !== bytes.length) throw new Error('Invalid glTF 2.0 binary magic or length.');
    return 'glTF 2.0 binary';
  }
  if (path.endsWith('.gltf')) {
    if (JSON.parse(bytes.toString('utf8')).asset?.version !== '2.0') throw new Error('Invalid glTF 2.0 JSON.');
    return 'glTF 2.0 JSON';
  }
  if (path.endsWith('.png')) {
    if (!bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) throw new Error('Invalid PNG magic.');
    return 'PNG';
  }
  if (/\.jpe?g$/i.test(path)) {
    if (bytes[0] !== 255 || bytes[1] !== 216 || bytes[2] !== 255) throw new Error('Invalid JPEG magic.');
    return 'JPEG';
  }
  return 'binary buffer (hash verified; no universal magic)';
}
async function sampleFile(item) {
  const url = urlFor(item.path), entry = { url, ok: false, expected_sha256: item.sha256 };
  report.sample_hashes.push(entry);
  try {
    const response = await request(url, 'GET', 33554432);
    entry.bytes = response.bytes.length; entry.sha256 = hash(response.bytes); entry.magic = magic(response.bytes, item.path);
    if (entry.bytes !== item.bytes || entry.sha256 !== item.sha256) throw new Error('Sample size or SHA256 differs from the manifest.');
    entry.ok = true;
    return response.bytes;
  } catch (error) { entry.error = error.message; fail(url, error.message); return null; }
}
async function samples(manifest) {
  const cost = asset => asset.bytes + (asset.dependencies || []).reduce((sum, dependency) => sum + dependency.bytes, 0);
  const temple = manifest.assets.filter(asset => asset.collection === 'temple' && asset.path.endsWith('.glb')).sort((a, b) => cost(a) - cost(b))[0];
  const meadow = manifest.assets.filter(asset => asset.collection === 'meadow' && asset.path.endsWith('.gltf') && asset.dependencies?.some(dependency => /\.(png|jpe?g)$/i.test(dependency.path))).sort((a, b) => cost(a) - cost(b))[0];
  if (!temple || !meadow) throw new Error('Both a Temple GLB and a Meadow glTF sample are required.');
  if (cost(temple) + cost(meadow) > 67108864) throw new Error('The cheapest two model samples exceed the 64 MiB total download budget.');
  await sampleFile(temple);
  const bytes = await sampleFile(meadow);
  if (!bytes) return;
  const gltf = JSON.parse(bytes.toString('utf8')), required = new Set();
  for (const resource of [...(gltf.buffers || []), ...(gltf.images || [])]) {
    if (!resource.uri || resource.uri.startsWith('data:')) continue;
    const url = new URL(resource.uri, urlFor(meadow.path)).href;
    const dependency = (meadow.dependencies || []).find(item => urlFor(item.path) === url);
    if (!dependency) { fail(urlFor(meadow.path), 'glTF references a resource absent from its declared dependencies.'); continue; }
    if (required.has(url)) continue;
    required.add(url);
    await sampleFile(dependency);
  }
  for (const dependency of meadow.dependencies || []) if (!required.has(urlFor(dependency.path))) await sampleFile(dependency);
}

try {
  const manifest = await getSmall('manifest.json');
  validateCatalog(manifest);
  const metadata = new Set(['README.md', 'CLAUDE_USAGE.md', 'FEASIBILITY.md', 'asset-index.json', ...manifest.collections.map(collection => collection.asset_index)]);
  for (const collection of manifest.collections) if (collection.terrain_texture_index) {
    metadata.add(collection.terrain_texture_index);
    const terrain = await getSmall(collection.terrain_texture_index);
    if (!Array.isArray(terrain.textures) || terrain.texture_count !== terrain.textures.length || !Array.isArray(terrain.layers) || terrain.layer_count !== terrain.layers.length) throw new Error('Terrain texture index schema/count mismatch.');
    for (const texture of terrain.textures) { validatePayload(texture); addFile(texture, 'terrain-texture'); }
    if (collection.terrain_texture_file_count !== undefined && collection.terrain_texture_file_count !== terrain.texture_count) throw new Error('Declared terrain texture count mismatch.');
  }
  for (const path of metadata) {
    try {
      const data = await getSmall(path);
      if (path === 'asset-index.json' && (data.asset_count !== manifest.asset_count || data.assets?.length !== manifest.assets.length)) fail(urlFor(path), 'Root asset index count differs from manifest.');
      const collection = manifest.collections.find(item => item.asset_index === path);
      if (collection && (data.asset_count !== collection.asset_count || data.assets?.length !== collection.asset_count)) fail(urlFor(path), 'Collection index count differs from manifest.');
    } catch { /* getSmall already recorded the public URL and failure. */ }
  }
  report.total_files = files.size;
  report.payload_files = [...files.values()].filter(file => [...file.kinds].some(kind => kind !== 'metadata')).length;
  await concurrent([...files.values()], 6, headFile);
  await samples(manifest);
  report.complete = true;
} catch (error) { fail(base.href, error.message); }
report.finished_at = new Date().toISOString();
report.ok = report.complete && report.failures.length === 0 && report.head_passed === report.total_files;
report.head_checks.sort((a, b) => a.url.localeCompare(b.url));
await mkdir(dirname(values.output), { recursive: true });
await writeFile(values.output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ base: report.base, ok: report.ok, total_files: report.total_files, head_passed: report.head_passed, head_failed: report.head_failed, failures: report.failures.length, sample_files: report.sample_hashes.length }));
process.exitCode = report.ok ? 0 : 1;
