#!/usr/bin/env node
/** Validate all Meadow glTF assets and their actual local dependencies. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const work = path.resolve(process.env.MEADOW_WORK || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'));
const validatorPath = path.resolve(work, '../ChineseLostTemple_20261021/tools/_node_deps/gltf-validator/index.js');
let validator;
try { validator = require(validatorPath); } catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND') throw error;
  validator = require('gltf-validator');
}
const args = process.argv.slice(2);
const repositoryIndex = args.indexOf('--repository');
if (repositoryIndex < 0 || !args[repositoryIndex + 1]) {
  throw new Error('Usage: node validate_assets.mjs --repository <repository>');
}
const repository = await fs.realpath(path.resolve(args[repositoryIndex + 1]));
const modelRoot = path.resolve(repository, 'models', 'Meadow');
const output = path.resolve(work, 'audit', 'gltf_validation.json');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const relative = absolute => path.relative(repository, absolute).split(path.sep).join('/');
function isInside(absolute) {
  const rel = path.relative(repository, absolute);
  return rel !== '..' && !rel.startsWith('..' + path.sep) && !path.isAbsolute(rel);
}
async function listModels(directory) {
  const files = [];
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) {
      const target = await fs.realpath(file);
      if (!isInside(target)) throw new Error('Model symlink escapes repository: ' + relative(file));
      const stat = await fs.stat(file);
      if (stat.isDirectory()) throw new Error('Symbolic model directories are not traversed: ' + relative(file));
      if (stat.isFile() && entry.name.toLowerCase().endsWith('.gltf')) files.push(file);
    } else if (entry.isDirectory()) {
      files.push(...await listModels(file));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.gltf')) {
      files.push(file);
    }
  }
  return files.sort();
}
const fileCache = new Map();
async function localDependency(asset, uri) {
  if (typeof uri !== 'string' || !uri || /[\\\x00]/.test(uri) || /[?#]/.test(uri)) {
    throw new Error('External URI must be a plain relative path: ' + JSON.stringify(uri));
  }
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(uri) || uri.startsWith('//')) {
    throw new Error('External URI must not have a scheme or authority: ' + uri);
  }
  let decoded;
  try { decoded = decodeURIComponent(uri); } catch { throw new Error('Malformed percent encoding in URI: ' + uri); }
  if (/[\\\x00]/.test(decoded) || path.isAbsolute(decoded) || path.win32.isAbsolute(decoded)) {
    throw new Error('External URI must be relative: ' + uri);
  }
  const candidate = path.resolve(path.dirname(asset), decoded);
  if (!isInside(candidate)) throw new Error('External URI escapes repository: ' + uri);
  const real = await fs.realpath(candidate);
  if (!isInside(real)) throw new Error('External URI symlink escapes repository: ' + uri);
  const stat = await fs.stat(real);
  if (!stat.isFile()) throw new Error('External URI is not a regular file: ' + uri);
  if (!fileCache.has(real)) {
    const bytes = await fs.readFile(real);
    fileCache.set(real, { bytes, byte_length: bytes.length, sha256: hash(bytes), path: relative(real) });
  }
  return fileCache.get(real);
}
function embeddedDependency(uri) {
  const match = /^data:([^,]*),(.*)$/s.exec(uri);
  if (!match) throw new Error('Malformed data URI.');
  const bytes = /;base64(?:;|$)/i.test(match[1]) ? Buffer.from(match[2], 'base64') : Buffer.from(decodeURIComponent(match[2]));
  return { bytes, byte_length: bytes.length, sha256: hash(bytes), mime_type: match[1].split(';')[0] || null };
}
const started = new Date().toISOString();
const results = [];
const models = await listModels(modelRoot);
for (const asset of models) {
  const row = { path: relative(asset), byte_length: null, sha256: null, dependencies: [], dependency_errors: [], validator_report: null, passed: false };
  try {
    const realAsset = await fs.realpath(asset);
    if (!isInside(realAsset)) throw new Error('Model resolves outside repository.');
    const bytes = await fs.readFile(asset);
    row.byte_length = bytes.length;
    row.sha256 = hash(bytes);
    const document = JSON.parse(bytes.toString('utf8'));
    for (const type of ['buffers', 'images']) {
      for (const [index, item] of (document[type] || []).entries()) {
        if (!item.uri) continue; // Images may reference a validated bufferView.
        try {
          const embedded = item.uri.startsWith('data:');
          const dependency = embedded ? embeddedDependency(item.uri) : await localDependency(asset, item.uri);
          const entry = { type, index, uri: embedded ? '[embedded data URI]' : item.uri,
            embedded, path: dependency.path || null, byte_length: dependency.byte_length, sha256: dependency.sha256 };
          if (type === 'buffers') {
            entry.declared_byte_length = item.byteLength;
            entry.byte_length_matches = dependency.byte_length === item.byteLength;
            if (!entry.byte_length_matches) row.dependency_errors.push('Buffer ' + index + ' byteLength differs from actual bytes.');
          }
          row.dependencies.push(entry);
        } catch (error) {
          row.dependency_errors.push(type + '[' + index + ']: ' + error.message);
        }
      }
    }
    row.validator_report = await validator.validateBytes(new Uint8Array(bytes), {
      uri: row.path, format: 'gltf', maxIssues: 0, writeTimestamp: false,
      externalResourceFunction: async uri => new Uint8Array((await localDependency(asset, uri)).bytes)
    });
    row.passed = row.dependency_errors.length === 0 && row.validator_report.issues.numErrors === 0;
  } catch (error) {
    row.dependency_errors.push(error.message);
  }
  results.push(row);
}
const summary = {
  assets: results.length,
  passed: results.filter(row => row.passed).length,
  failed: results.filter(row => !row.passed).length,
  validator_errors: results.reduce((sum, row) => sum + (row.validator_report?.issues.numErrors || 0), 0),
  validator_warnings: results.reduce((sum, row) => sum + (row.validator_report?.issues.numWarnings || 0), 0),
  dependency_errors: results.reduce((sum, row) => sum + row.dependency_errors.length, 0),
  unique_external_dependencies: fileCache.size,
  unique_external_dependency_bytes: [...fileCache.values()].reduce((sum, item) => sum + item.byte_length, 0)
};
const report = {
  schema_version: 1, validator: 'Khronos glTF Validator', validator_version: validator.version(),
  repository, model_root: relative(modelRoot), started_at: started, completed_at: new Date().toISOString(),
  scope: 'All models/Meadow/**/*.gltf, official glTF validation with external resource loading, relative URI containment, actual dependency byte lengths and SHA-256.',
  passed: results.length > 0 && summary.failed === 0, summary,
  limitations: ['This checks format and resource integrity, not visual fidelity, gameplay, runtime performance or redistribution rights.'],
  assets: results
};
await fs.mkdir(path.dirname(output), { recursive: true });
await fs.writeFile(output, JSON.stringify(report, null, 2) + '\n', 'utf8');
console.log(JSON.stringify({ output, passed: report.passed, ...summary }));
if (!report.passed) process.exitCode = 1;
