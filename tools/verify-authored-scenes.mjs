#!/usr/bin/env node
// Anonymous authored-scene receipts. JSON is read fully; binary/image GETs are bounded prefixes.
import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import { parseArgs } from 'node:util';

const { values } = parseArgs({ args: process.argv.slice(2), options: { base: { type: 'string' }, output: { type: 'string' }, help: { type: 'boolean' } } });
if (values.help || !values.output) {
  console.log('Usage: node tools/verify-authored-scenes.mjs [--base PUBLIC_REPOSITORY_ROOT/] --output receipt.json');
  process.exit(values.help ? 0 : 1);
}
const base = new URL(values.base || 'https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/');
if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) throw new Error('Use an HTTP(S) directory URL without credentials, query, or fragment.');
if (!base.pathname.endsWith('/')) base.pathname += '/';
const report = {
  base: base.href, started_at: new Date().toISOString(), finished_at: null, complete: false, ok: false,
  policy: { anonymous: true, head_concurrency: 6, timeout_ms: 15000, maximum_attempts: 2, accept_encoding: 'identity', binary_get_prefix_bytes: 64, maximum_json_bytes: 33554432 },
  scenes: [], total_files: 0, passed_files: 0, failed_files: 0,
  head: { passed: 0, failed: 0 }, get: { passed: 0, failed: 0 },
  cors: { passed: 0, failed: 0 }, content_length: { matched: 0, missing: 0, mismatched: 0 },
  receipts: [], failures: [],
};
const files = new Map(), jsonCache = new Map();
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const fail = (url, message) => report.failures.push({ url, message });
function safeURL(path, relative = base.href) {
  if (typeof path !== 'string' || !path) throw new Error('Missing scene resource path.');
  const url = new URL(path, relative);
  if (!url.href.startsWith(base.href) || url.username || url.password || url.search || url.hash) throw new Error('A scene resource escapes the anonymous repository base.');
  return url.href;
}
function add(url, kind, scene, expectedBytes) {
  let file = files.get(url);
  if (!file) { file = { url, kinds: new Set(), scenes: new Set(), expected_bytes: expectedBytes }; files.set(url, file); }
  if (expectedBytes !== undefined) {
    if (!Number.isSafeInteger(expectedBytes) || expectedBytes < 0) throw new Error('Invalid declared byte length for ' + url);
    if (file.expected_bytes !== undefined && file.expected_bytes !== expectedBytes) throw new Error('Conflicting declared byte lengths for ' + url);
    file.expected_bytes = expectedBytes;
  }
  file.kinds.add(kind); if (scene) file.scenes.add(scene);
  return file;
}
function headers(response) {
  const length = response.headers.get('content-length');
  return { status: response.status, cors: response.headers.get('access-control-allow-origin'), content_length: length === null ? null : Number(length), content_range: response.headers.get('content-range'), content_encoding: response.headers.get('content-encoding') };
}
async function request(url, method, prefix = false) {
  let error;
  for (let attempt = 1; attempt <= 2; attempt++) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
    try {
      const requestHeaders = { 'Accept-Encoding': 'identity' };
      if (prefix) requestHeaders.Range = 'bytes=0-63';
      const response = await fetch(url, { method, headers: requestHeaders, redirect: 'follow', cache: 'no-store', signal: controller.signal });
      if (response.status !== 200 && !(prefix && response.status === 206)) { await response.body?.cancel(); throw new Error('HTTP ' + response.status); }
      const result = { ...headers(response), attempts: attempt, body: Buffer.alloc(0) };
      if (method === 'HEAD') return result;
      const reader = response.body.getReader(), chunks = [];
      let received = 0, kept = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          received += value.length;
          if (prefix) {
            const chunk = Buffer.from(value).subarray(0, 64 - kept); chunks.push(chunk); kept += chunk.length;
            if (kept >= 64) { await reader.cancel(); break; }
          } else {
            if (received > 33554432) { await reader.cancel(); throw new Error('JSON exceeded the 32 MiB safety limit.'); }
            chunks.push(Buffer.from(value));
          }
        }
      } finally { reader.releaseLock(); }
      result.body = Buffer.concat(chunks); result.observed_body_bytes = received;
      return result;
    } catch (caught) { error = caught; }
    finally { clearTimeout(timer); }
  }
  throw new Error(error?.name === 'AbortError' ? 'Request timed out after 15000 ms (maximum two attempts).' : String(error?.message || error));
}
function checkCORS(url, result, method) {
  const ok = result.cors === '*'; report.cors[ok ? 'passed' : 'failed']++;
  if (!ok) fail(url, method + ' Access-Control-Allow-Origin must be *.');
  return ok;
}
function rejectPointer(bytes) {
  if (!bytes.length) throw new Error('Empty response body.');
  if (bytes.subarray(0, 200).toString('utf8').includes('version https://git-lfs.github.com/spec/v1')) throw new Error('Git LFS pointer returned instead of payload.');
}
async function loadJSON(url, kind, scene) {
  const file = add(url, kind, scene);
  if (jsonCache.has(url)) return jsonCache.get(url);
  try {
    const response = await request(url, 'GET'); rejectPointer(response.body);
    const data = JSON.parse(response.body.toString('utf8'));
    file.get = { ...response, body: undefined, ok: checkCORS(url, response, 'GET'), mode: 'full JSON', bytes: response.body.length, sha256: digest(response.body) };
    if (response.content_length !== null && response.content_length !== response.body.length) { file.get.ok = false; fail(url, 'GET Content-Length differs from the complete JSON body.'); }
    add(url, kind, scene, response.body.length);
    jsonCache.set(url, data); return data;
  } catch (error) { file.get = { ok: false, mode: 'full JSON', error: error.message }; fail(url, 'GET: ' + error.message); throw error; }
}
function prefixMagic(url, bytes) {
  rejectPointer(bytes);
  if (/\.png$/i.test(url)) {
    if (!bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) throw new Error('Invalid PNG signature.');
    return 'PNG';
  }
  if (/\.jpe?g$/i.test(url)) {
    if (bytes[0] !== 255 || bytes[1] !== 216 || bytes[2] !== 255) throw new Error('Invalid JPEG signature.');
    return 'JPEG';
  }
  if (/\.webp$/i.test(url)) {
    if (bytes.toString('ascii', 0, 4) !== 'RIFF' || bytes.toString('ascii', 8, 12) !== 'WEBP') throw new Error('Invalid WebP signature.');
    return 'WebP';
  }
  return 'Binary prefix; no universal signature';
}
async function probe(file) {
  try {
    const response = await request(file.url, 'HEAD');
    file.head = { ...response, body: undefined, ok: checkCORS(file.url, response, 'HEAD') };
    if (response.content_length === null) report.content_length.missing++;
    else if (!Number.isSafeInteger(response.content_length) || response.content_length < 1 || (file.expected_bytes !== undefined && response.content_length !== file.expected_bytes)) {
      file.head.ok = false; report.content_length.mismatched++; fail(file.url, 'HEAD Content-Length is invalid or differs from declared/full-JSON bytes.');
    } else report.content_length.matched++;
  } catch (error) { file.head = { ok: false, error: error.message }; fail(file.url, 'HEAD: ' + error.message); }
  if (!file.get) try {
    const response = await request(file.url, 'GET', true), signature = prefixMagic(file.url, response.body);
    let ok = checkCORS(file.url, response, 'GET');
    const match = /^bytes 0-\d+\/(\d+)$/.exec(response.content_range || '');
    const total = response.status === 206 ? (match ? Number(match[1]) : null) : response.content_length;
    const expected = file.expected_bytes ?? file.head.content_length;
    if (response.status === 206 && !match) { ok = false; fail(file.url, 'GET partial response has no valid Content-Range total.'); }
    if (total !== null && expected !== undefined && expected !== null && total !== expected) { ok = false; fail(file.url, 'GET full-resource length differs from HEAD or declared length.'); }
    file.get = { ...response, body: undefined, ok, mode: response.status === 206 ? 'range prefix' : 'bounded prefix; server ignored Range', prefix_bytes: response.body.length, prefix_sha256: digest(response.body), signature, full_resource_bytes: total };
  } catch (error) { file.get = { ok: false, mode: 'bounded prefix', error: error.message }; fail(file.url, 'GET: ' + error.message); }
  report.head[file.head.ok ? 'passed' : 'failed']++;
  report.get[file.get.ok ? 'passed' : 'failed']++;
  file.ok = file.head.ok && file.get.ok;
}
async function pool(items, operation) {
  let index = 0;
  await Promise.all(Array.from({ length: Math.min(6, items.length) }, async () => { while (index < items.length) await operation(items[index++]); }));
}
function resourcePath(item) { return typeof item === 'string' ? item : item?.path || item?.url; }
async function verifyPlacementPages(groups, sceneID, summary, indexURL) {
  const seen = new Map();
  for (const group of groups) {
    if (group?.placement_pages === undefined) continue;
    if (!Array.isArray(group.placement_pages)) { fail(indexURL, 'Scene ' + sceneID + ' has an invalid placement_pages array.'); continue; }
    for (const page of group.placement_pages) {
      let url = indexURL;
      try {
        url = safeURL(resourcePath(page));
        if (seen.has(url)) {
          if (seen.get(url) !== page.object_count) fail(url, 'Index and summary placement-page counts disagree.');
          continue;
        }
        seen.set(url, page.object_count); summary.placement_pages++;
        const data = await loadJSON(url, 'placement-page', sceneID);
        if (!Number.isSafeInteger(page.object_count) || page.object_count < 0 || page.object_count > 24) fail(url, 'Placement-page descriptor object_count must be an integer from 0 to 24.');
        if (!Array.isArray(data.objects) || !Number.isSafeInteger(data.object_count) || data.object_count !== data.objects?.length || data.object_count > 24) fail(url, 'Placement-page objects/object_count mismatch or more than 24 objects.');
        if (data.object_count !== page.object_count) fail(url, 'Placement-page object_count differs from its index/summary descriptor.');
      } catch (error) { fail(url, 'Placement-page verification failed: ' + error.message); }
    }
  }
}

try {
  const indexURL = safeURL('scenes/index.json'), index = await loadJSON(indexURL, 'scene-index');
  if (index.schema_version !== 1 || !Array.isArray(index.scenes) || !index.scenes.length) throw new Error('Invalid authored scene index schema.');
  const ids = new Set();
  for (const scene of index.scenes) {
    if (!scene.id || ids.has(scene.id)) throw new Error('Missing or duplicate authored scene ID.');
    ids.add(scene.id);
    const summary = { id: scene.id, name: scene.name || scene.id, groups: 0, placement_pages: 0, previews: 0, external_dependencies: 0 };
    let summaryGroups = [];
    report.scenes.push(summary);
    for (const kind of ['layout', 'summary']) try {
      const data = await loadJSON(safeURL(scene[kind]), kind, scene.id);
      if (data.id !== scene.id) fail(safeURL(scene[kind]), 'Document scene ID differs from the scene index.');
      if (kind === 'summary' && Array.isArray(data.groups)) summaryGroups = data.groups;
    } catch (error) { fail(indexURL, 'Scene ' + scene.id + ' ' + kind + ' verification failed: ' + error.message); }
    if (!Array.isArray(scene.groups)) fail(indexURL, 'Scene ' + scene.id + ' has no groups array.');
    for (const group of Array.isArray(scene.groups) ? scene.groups : []) {
      try { await loadJSON(safeURL(resourcePath(group)), 'group', scene.id); summary.groups++; }
      catch (error) { fail(indexURL, 'Scene ' + scene.id + ' group verification failed: ' + error.message); }
    }
    await verifyPlacementPages([...(Array.isArray(scene.groups) ? scene.groups : []), ...summaryGroups], scene.id, summary, indexURL);
    if (!Array.isArray(scene.previews) || !scene.previews.length) fail(indexURL, 'Scene ' + scene.id + ' has no preview entries.');
    for (const preview of Array.isArray(scene.previews) ? scene.previews : []) {
      try { add(safeURL(resourcePath(preview)), 'preview', scene.id, typeof preview === 'object' ? preview.bytes : undefined); summary.previews++; }
      catch (error) { fail(indexURL, 'Invalid preview for scene ' + scene.id + ': ' + error.message); }
    }
    try {
      const modelURL = safeURL(scene.model), gltf = await loadJSON(modelURL, 'scene-gltf', scene.id);
      if (gltf.asset?.version !== '2.0') throw new Error('Scene model is not glTF 2.0 JSON.');
      const dependencies = new Set();
      for (const [kind, resources] of [['buffer', gltf.buffers || []], ['image', gltf.images || []]]) for (const resource of resources) {
        if (!resource.uri || resource.uri.startsWith('data:')) continue;
        const url = safeURL(resource.uri, modelURL);
        add(url, kind, scene.id, kind === 'buffer' ? resource.byteLength : undefined); dependencies.add(url);
      }
      summary.external_dependencies = dependencies.size;
    } catch (error) { fail(indexURL, 'Scene ' + scene.id + ' model/dependency discovery failed: ' + error.message); }
  }
  report.total_files = files.size;
  await pool([...files.values()], probe);
  report.complete = true;
} catch (error) { fail(base.href, error.message); }
report.receipts = [...files.values()].map(file => ({ url: file.url, kinds: [...file.kinds], scenes: [...file.scenes], expected_bytes: file.expected_bytes ?? null, ok: !!file.ok, head: file.head || null, get: file.get || null })).sort((a, b) => a.url.localeCompare(b.url));
report.passed_files = report.receipts.filter(file => file.ok).length;
report.failed_files = report.receipts.length - report.passed_files;
report.finished_at = new Date().toISOString();
report.ok = report.complete && report.failures.length === 0 && report.failed_files === 0;
await mkdir(dirname(values.output), { recursive: true });
await writeFile(values.output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ base: report.base, ok: report.ok, scenes: report.scenes.length, total_files: report.total_files, passed: report.passed_files, failed: report.failed_files, failures: report.failures.length, binary_get: '64-byte prefixes; cancel after prefix when Range is ignored' }));
process.exitCode = report.ok ? 0 : 1;
