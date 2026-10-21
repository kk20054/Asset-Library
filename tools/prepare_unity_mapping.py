#!/usr/bin/env python3
"""Read extracted Unity materials/prefabs and preserve their GUID mappings.

This tool does not modify source assets, process images, or export geometry.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    work = args.work.resolve()
    sys.path.insert(0, str(work / 'tools' / '_deps'))
    import yaml

    index = json.loads((work / 'audit' / 'extracted_source.json').read_text('utf-8'))
    assets = index['assets']
    by_guid = {a['guid']: a for a in assets}
    source = work / 'cache' / 'source'
    warnings = []
    materials = {}
    prefabs = []
    mesh_names = {}
    candidates = defaultdict(lambda: defaultdict(set))
    evidence = defaultdict(lambda: defaultdict(list))

    def warn(message):
        warnings.append(message)

    def actual(a):
        p = (source / a['relative_path']).resolve()
        if source.resolve() not in p.parents:
            raise ValueError('Source path escapes the extracted source directory.')
        return p

    def documents(text, path):
        matches = list(re.finditer(r'^--- !u!(\d+) &(-?\d+)(?: stripped)?\s*$', text, re.M))
        result = []
        for i, match in enumerate(matches):
            body = text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)]
            try:
                parsed = yaml.safe_load(body) or {}
            except yaml.YAMLError as error:
                warn(f'Cannot parse Unity document {match[2]} in {path}: {error}')
                continue
            if not isinstance(parsed, dict) or len(parsed) != 1:
                warn(f'Unexpected Unity document structure in {path}, file ID {match[2]}.')
                continue
            typename, data = next(iter(parsed.items()))
            result.append({'class_id': int(match[1]), 'id': int(match[2]),
                           'type': typename, 'data': data or {}})
        return result

    def reference(value):
        return value if isinstance(value, dict) else {}

    def entries(value):
        result = {}
        for item in value or []:
            if isinstance(item, dict):
                result.update(item)
        return result

    for a in assets:
        if not a['path'].lower().endswith('.fbx'):
            continue
        meta_path = Path(str(actual(a)) + '.meta')
        if not meta_path.exists():
            warn(f'FBX metadata is missing: {a["path"]}.')
            continue
        meta = yaml.safe_load(meta_path.read_text('utf-8-sig')) or {}
        names = {}
        for item in meta.get('ModelImporter', {}).get('internalIDToNameTable', []) or []:
            for category, file_id in (item.get('first', {}) or {}).items():
                if str(category) == '43':
                    names[str(file_id)] = item.get('second', '')
        mesh_names[a['guid']] = names

    for a in assets:
        if not a['path'].lower().endswith('.mat'):
            continue
        docs = documents(actual(a).read_text('utf-8-sig'), a['path'])
        mat = next((d['data'] for d in docs if d['type'] == 'Material'), None)
        if mat is None:
            warn(f'No Material document found: {a["path"]}.')
            continue
        props = mat.get('m_SavedProperties', {}) or {}
        textures = {}
        for prop, data in entries(props.get('m_TexEnvs')).items():
            data = data or {}
            ref = reference(data.get('m_Texture'))
            guid = ref.get('guid')
            texture = by_guid.get(guid, {})
            textures[prop] = {'guid': guid, 'path': texture.get('path'),
                              'relative_path': texture.get('relative_path'),
                              'file_id': ref.get('fileID', 0),
                              'scale': data.get('m_Scale'), 'offset': data.get('m_Offset')}
            if guid and not texture and not guid.startswith('0000000000000000'):
                warn(f'Unresolved texture GUID {guid} in {a["path"]}, property {prop}; '
                     'the saved property may be unused shader residue.')
        shader_guid = reference(mat.get('m_Shader')).get('guid')
        if shader_guid and shader_guid not in by_guid and not shader_guid.startswith('0000000000000000'):
            warn(f'Shader GUID {shader_guid} is external or absent for {a["path"]}.')
        materials[a['guid']] = {'name': mat.get('m_Name') or Path(a['path']).stem,
                                'source': a['path'], 'relative_path': a['relative_path'],
                                'textures': textures, 'floats': entries(props.get('m_Floats')),
                                'ints': entries(props.get('m_Ints')),
                                'colors': entries(props.get('m_Colors')),
                                'shader_guid': shader_guid,
                                'shader_file_id': reference(mat.get('m_Shader')).get('fileID'),
                                'render_queue': mat.get('m_CustomRenderQueue'),
                                'keywords': mat.get('m_ValidKeywords', []),
                                'tags': mat.get('stringTagMap', {})}

    for a in assets:
        if not a['path'].lower().endswith('.prefab'):
            continue
        docs = documents(actual(a).read_text('utf-8-sig'), a['path'])
        game_objects = {d['id']: d['data'] for d in docs if d['type'] == 'GameObject'}
        filters = {reference(d['data'].get('m_GameObject')).get('fileID'): d['data']
                   for d in docs if d['type'] == 'MeshFilter'}
        renderers = []
        nested = [d for d in docs if d['type'] == 'PrefabInstance']
        if nested:
            warn(f'Nested prefab instances are not expanded in {a["path"]}; '
                 'only explicit renderer documents are mapped.')
        if any(d['type'].startswith('ParticleSystem') for d in docs):
            warn(f'Unity particle-system behavior is not converted in {a["path"]}.')
        for d in docs:
            if d['type'] not in ('MeshRenderer', 'SkinnedMeshRenderer'):
                continue
            data = d['data']
            go_id = reference(data.get('m_GameObject')).get('fileID')
            name = game_objects.get(go_id, {}).get('m_Name', '')
            mesh = reference(data.get('m_Mesh') if d['type'] == 'SkinnedMeshRenderer'
                             else filters.get(go_id, {}).get('m_Mesh'))
            fbx_guid = mesh.get('guid')
            mesh_id = mesh.get('fileID', 0)
            mesh_name = mesh_names.get(fbx_guid, {}).get(str(mesh_id))
            material_refs = [reference(r) for r in data.get('m_Materials', []) or []]
            material_guids = [r.get('guid') for r in material_refs]
            row = {'name': name, 'mesh_name': mesh_name, 'fbx_guid': fbx_guid,
                   'file_id': mesh_id, 'renderer_id': d['id'], 'game_object_id': go_id,
                   'renderer_type': d['type'], 'material_guids': material_guids,
                   'material_file_ids': [r.get('fileID', 0) for r in material_refs],
                   'enabled': data.get('m_Enabled', 1)}
            renderers.append(row)
            if not fbx_guid or fbx_guid not in mesh_names:
                warn(f'Renderer {name or d["id"]} has no resolved FBX mesh in {a["path"]}.')
                continue
            if not mesh_name:
                warn(f'Mesh file ID {mesh_id} has no FBX metadata name in {a["path"]}; '
                     'the GameObject name is retained but not used as a guessed mesh name.')
                continue
            for guid in material_guids:
                if guid and guid not in materials:
                    warn(f'Unresolved material GUID {guid} for renderer {name} in {a["path"]}.')
            candidates[fbx_guid][mesh_name].add(tuple(material_guids))
            evidence[fbx_guid][mesh_name].append({'prefab_guid': a['guid'],
                                                'renderer_id': d['id'], 'name': name})
        prefabs.append({'guid': a['guid'], 'name': Path(a['path']).stem,
                        'path': a['path'], 'relative_path': a['relative_path'],
                        'fbx_guids': sorted({r['fbx_guid'] for r in renderers if r['fbx_guid']}),
                        'renderers': renderers, 'nested_prefab_count': len(nested)})

    overrides = {}
    conflicts = []
    for guid, meshes in candidates.items():
        clean = {}
        for mesh_name, choices in meshes.items():
            if len(choices) == 1:
                clean[mesh_name] = list(next(iter(choices)))
            else:
                choices_list = [list(c) for c in choices]
                conflicts.append({'fbx_guid': guid, 'mesh_name': mesh_name,
                                  'material_choices': choices_list,
                                  'evidence': evidence[guid][mesh_name]})
                warn(f'Conflicting prefab material assignments for FBX {guid}, mesh {mesh_name}; '
                     'no global renderer override is selected.')
        if clean:
            overrides[guid] = clean
    warn('Material properties are preserved without inventing shader style or channel semantics.')
    warn('Unity ShaderGraph, foliage wind, water, particles, colliders, and LOD behavior require '
         'separate runtime implementation; this mapping does not reproduce them.')
    warn('This mapping covers extracted materials and explicit prefab renderers; '
         'the complete Unity scene has not been reconstructed.')
    result = {'schema_version': 1, 'source_variant': index.get('source_variant'),
              'materials': materials, 'renderer_overrides': overrides,
              'renderer_override_conflicts': conflicts,
              'prefabs': prefabs, 'fbx_mesh_names': mesh_names,
              'warnings': list(dict.fromkeys(warnings))}
    output = work / 'audit' / 'unity_mapping.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', 'utf-8')
    print(json.dumps({'output': str(output), 'materials': len(materials),
                      'prefabs': len(prefabs), 'mapped_fbxs': len(overrides),
                      'mapped_renderers': sum(len(v) for v in overrides.values()),
                      'conflicts': len(conflicts), 'warnings': len(result['warnings'])}))


if __name__ == '__main__':
    main()
