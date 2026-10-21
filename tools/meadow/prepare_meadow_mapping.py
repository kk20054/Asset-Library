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
    sys.path.insert(0, str(work.parent / 'ChineseLostTemple_20261021' / 'tools' / '_deps'))
    import yaml

    index = json.loads((work / 'audit' / 'extracted_source.json').read_text('utf-8'))
    assets = index['assets']
    by_guid = {a['guid']: a for a in assets}
    source = work / 'cache' / 'source'
    warnings = []
    materials = {}
    prefabs = []
    mesh_names = {}
    fbx_model_names = {}
    mesh_name_evidence = {}
    prefab_documents = {}
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
        # Empty Unity internalID tables are common in this vendor package.
        # This is evidence from actual FBX Model records, not filename guessing.
        fbx_model_names[a['guid']] = set(x.decode('utf-8', 'replace') for x in re.findall(
            rb'([A-Za-z_][A-Za-z0-9_. -]*)\x00\x01Model', actual(a).read_bytes()))

    for a in assets:
        if not a['path'].lower().endswith('.prefab'):
            continue
        docs = documents(actual(a).read_text('utf-8-sig'), a['path'])
        prefab_documents[a['guid']] = docs
        gos = {d['id']: d['data'] for d in docs if d['type'] == 'GameObject'}
        for d in docs:
            if d['type'] not in ('MeshFilter', 'SkinnedMeshRenderer'):
                continue
            mesh = reference(d['data'].get('m_Mesh'))
            guid = mesh.get('guid')
            file_id = str(mesh.get('fileID', 0))
            go_id = reference(d['data'].get('m_GameObject')).get('fileID')
            name = gos.get(go_id, {}).get('m_Name')
            method = 'explicit MeshFilter fileID + GameObject name exact match to source FBX Model record'
            # Seven vendor RockGroup prefabs retain an older plural spelling.
            # Normalize only this documented literal and require actual FBX match.
            canonical = re.sub(r'^SM_RocksGroup_(\d+_LOD\d+)$', r'SM_RockGroup_\1', name or '')
            if name not in fbx_model_names.get(guid, set()) and canonical in fbx_model_names.get(guid, set()):
                method = 'explicit MeshFilter fileID + documented vendor RocksGroup/RockGroup spelling normalization + source FBX Model exact match'
                name = canonical
            if name not in fbx_model_names.get(guid, set()):
                continue
            old = mesh_names[guid].get(file_id)
            if old is not None and old != name:
                raise ValueError(f'Contradictory FBX mesh name evidence: {guid}/{file_id}: {old} vs {name}')
            mesh_names[guid][file_id] = name
            mesh_name_evidence.setdefault(guid, {}).setdefault(file_id, []).append({
                'mesh_name': name, 'prefab': a['path'], 'game_object_id': str(go_id),
                'method': 'explicit MeshFilter fileID + GameObject name exact match to source FBX Model record'})

    shader_properties = {}
    shader_names = {}
    for a in assets:
        if not a['path'].lower().endswith('.shader'):
            continue
        text = actual(a).read_text('utf-8-sig')
        # Unity generated shader Properties blocks appear before SubShader.
        block = text.split('SubShader', 1)[0]
        shader_properties[a['guid']] = list(dict.fromkeys(re.findall(
            r'^\s*(?:\[[^\]]+\]\s*)*(_\w+)\s*\(', block, re.M)))
        match = re.search(r'Shader\s+"([^"]+)"', text)
        shader_names[a['guid']] = match[1] if match else None

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
                                'tags': mat.get('stringTagMap', {}),
                                'shader_name': shader_names.get(shader_guid),
                                'active_properties': shader_properties.get(shader_guid, []),
                                'active_property_source': by_guid.get(shader_guid, {}).get('path'),
                                'evidence_note': 'All saved properties retained; only active_properties are declared by current local shader.'}
        if shader_guid not in shader_properties:
            warn(f'No local shader Properties whitelist for {a["path"]}; active_properties empty, saved values evidence only.')

    for a in assets:
        if not a['path'].lower().endswith('.prefab'):
            continue
        docs = prefab_documents[a['guid']]
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

    def season_priority(path):
        low = path.lower()
        if 'summer' in low:
            return 0 if 'drysummer' not in low else 1
        if 'autumn' in low:
            return 3
        if 'winter' in low:
            return 4
        return 2

    variant_groups = defaultdict(dict)
    for prefab in prefabs:
        # Each candidate is the exact simultaneous assignment in one prefab.
        # Never combine independent material choices by Cartesian product.
        grouped = defaultdict(dict)
        blocked = set()
        for row in prefab['renderers']:
            guid = row['fbx_guid']
            name = row['mesh_name']
            mats = row['material_guids']
            if not guid or not name or guid not in mesh_names:
                continue
            if not mats or any(not mat or mat not in materials for mat in mats):
                warn(f'Unresolved material prevents export variant: {prefab["path"]}, mesh {name}.')
                blocked.add(guid)
                continue
            old = grouped[guid].get(name)
            if old is not None and old != mats:
                warn(f'Multiple simultaneous assignments for the same FBX mesh in {prefab["path"]}: {guid}/{name}; no invented variant.')
                blocked.add(guid)
            grouped[guid][name] = mats
        for guid, assignments in grouped.items():
            if guid in blocked or not assignments:
                continue
            key = json.dumps(assignments, sort_keys=True, separators=(',', ':'))
            row = variant_groups[guid].get(key)
            if row is None:
                row = {'name': prefab['name'], 'source_prefabs': [],
                       'source_prefab_guids': [], 'assignments': assignments,
                       'mapped_mesh_count': len(assignments),
                       'total_source_mesh_count': len(mesh_names.get(guid, {})),
                       'season_priority': season_priority(prefab['path'])}
                variant_groups[guid][key] = row
            row['source_prefabs'].append(prefab['path'])
            row['source_prefab_guids'].append(prefab['guid'])
            if (season_priority(prefab['path']), prefab['name']) < (row['season_priority'], row['name']):
                row['name'] = prefab['name']
                row['season_priority'] = season_priority(prefab['path'])

    export_variants = {}
    overrides = {}
    conflicts = []
    for guid, groups in variant_groups.items():
        ordered = sorted(groups.values(), key=lambda row: (
            row['season_priority'], -row['mapped_mesh_count'], row['name']))
        for row in ordered:
            row['source_prefabs'] = sorted(row['source_prefabs'])
            row['source_prefab_guids'] = sorted(row['source_prefab_guids'])
            row['coverage'] = 'all_source_meshes' if row['mapped_mesh_count'] == row['total_source_mesh_count'] else 'prefab_subset_only'
        export_variants[guid] = ordered
        # Backward-compatible converter input uses one coherent actual prefab.
        overrides[guid] = ordered[0]['assignments']
        if len(ordered) > 1:
            conflicts.append({'fbx_guid': guid, 'variant_count': len(ordered),
                              'selected_default_variant': ordered[0]['name'],
                              'resolution': 'ordered actual prefab assignment variants; no Cartesian product'})
    warn('Material properties are preserved without inventing shader style or channel semantics.')
    warn('Unity ShaderGraph, foliage wind, water, particles, colliders, and LOD behavior require '
         'separate runtime implementation; this mapping does not reproduce them.')
    warn('This mapping covers extracted materials and explicit prefab renderers; '
         'the complete Unity scene has not been reconstructed.')
    result = {'schema_version': 1, 'source_variant': index.get('source_variant'),
              'materials': materials, 'renderer_overrides': overrides,
              'renderer_override_conflicts': conflicts, 'export_variants': export_variants,
              'shader_properties': shader_properties, 'mesh_name_evidence': mesh_name_evidence,
              'prefabs': prefabs, 'fbx_mesh_names': mesh_names,
              'warnings': list(dict.fromkeys(warnings))}
    output = work / 'audit' / 'unity_mapping.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', 'utf-8')
    print(json.dumps({'output': str(output), 'materials': len(materials),
                      'prefabs': len(prefabs), 'mapped_fbxs': len(overrides),
                      'mapped_renderers': sum(len(v) for v in overrides.values()),
                      'conflicts': len(conflicts), 'export_variant_count': sum(len(v) for v in export_variants.values()), 'warnings': len(result['warnings'])}))


if __name__ == '__main__':
    main()
