"""Export authored Meadow TerrainLayer textures and metadata for a static web host."""
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent / '_deps'))
import yaml
from PIL import Image

DEFAULT_BASE = 'https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/'
ROLES = {'diffuse': 'm_DiffuseTexture', 'normal': 'm_NormalMapTexture', 'mask': 'm_MaskMapTexture'}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unity_yaml(path):
    text = path.read_text(encoding='utf-8-sig')
    text = '\n'.join(line for line in text.splitlines() if not line.startswith('%'))
    text = re.sub(r'^--- !u!\d+ &-?\d+.*$', '---', text, flags=re.MULTILINE)
    return yaml.safe_load(text)


def texture_importer(path):
    importer = unity_yaml(path)['TextureImporter']
    settings = importer.get('textureSettings', {})
    return {
        'sRGBTexture': bool(importer['mipmaps']['sRGBTexture']),
        'textureType': importer.get('textureType'),
        'convertToNormalMap': bool(importer['bumpmap']['convertToNormalMap']),
        'flipGreenChannel': bool(importer['bumpmap']['flipGreenChannel']),
        'wrapU': settings.get('wrapU'),
        'wrapV': settings.get('wrapV'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('repository', type=Path)
    parser.add_argument('--base-url', default=DEFAULT_BASE)
    args = parser.parse_args()
    work, repository = args.work.resolve(), args.repository.resolve()
    base = args.base_url.rstrip('/') + '/'
    source = json.loads((work / 'audit/extracted_source.json').read_text(encoding='utf-8'))
    web = json.loads((work / 'audit/web_textures.json').read_text(encoding='utf-8'))
    entries = {entry['guid']: entry for entry in source['assets']}
    layers = sorted((entry for entry in source['assets'] if entry['path'].endswith('.terrainlayer')), key=lambda entry: entry['path'])
    if len(layers) != 6:
        raise ValueError(f'Expected six authored terrain layers, found {len(layers)}')
    target = repository / 'textures/Meadow/Terrain'
    target.mkdir(parents=True, exist_ok=True)
    textures, records, stems = {}, [], {}
    for entry in layers:
        layer_path = work / 'cache/source' / entry['relative_path']
        if sha256(layer_path) != entry['sha256']:
            raise ValueError(f'TerrainLayer source hash mismatch: {entry["path"]}')
        layer = unity_yaml(layer_path)['TerrainLayer']
        references = {}
        for role, field in ROLES.items():
            guid = layer[field].get('guid')
            if not guid:
                raise ValueError(f'Missing {role} reference: {entry["path"]}')
            references[role] = 'MEADOW_TERRAIN_' + Path(entries[guid]['path']).stem
            if guid in textures:
                if textures[guid]['role'] != role:
                    raise ValueError(f'Conflicting texture roles for {guid}')
                continue
            texture_source, portable = entries[guid], web[guid]
            source_path = work / 'cache/source' / texture_source['relative_path']
            importer = texture_importer(Path(str(source_path) + '.meta'))
            stem = source_path.stem
            if not re.fullmatch(r'[A-Za-z0-9_]+', stem):
                raise ValueError(f'Nonportable texture stem: {stem}')
            if stem in stems and stems[stem] != guid:
                raise ValueError(f'Duplicate texture stem: {stem}')
            stems[stem] = guid
            if role == 'mask':
                if sha256(source_path) != texture_source['sha256']:
                    raise ValueError(f'Mask source hash mismatch: {source_path}')
                destination = target / (stem + '.png')
                with Image.open(source_path) as image:
                    original_dimensions, source_mode = list(image.size), image.mode
                    image = image.convert('RGBA')
                    image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                    dimensions = list(image.size)
                    image.save(destination, 'PNG', compress_level=6)
                conversion = 'Source TIFF channels exported as losslessly compressed RGBA PNG; maximum dimension 2048; Lanczos resize; no gamma or channel remapping.'
                color_space = 'linear'
            else:
                portable_path = work / 'cache/web_textures' / portable['path']
                if portable_path.suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
                    raise ValueError(f'Unsupported browser texture: {portable_path}')
                if sha256(portable_path) != portable['sha256']:
                    raise ValueError(f'Portable texture hash mismatch: {portable_path}')
                destination = target / (stem + portable_path.suffix.lower())
                shutil.copyfile(portable_path, destination)
                with Image.open(destination) as image:
                    dimensions = list(image.size)
                    image.verify()
                original_dimensions = portable['original_dimensions']
                source_mode = None
                conversion = 'Byte-identical copy of the existing browser PNG/JPEG conversion.'
                color_space = 'sRGB' if role == 'diffuse' else 'linear'
            relative = destination.relative_to(repository).as_posix()
            textures[guid] = {
                'id': references[role], 'role': role, 'path': relative,
                'url': base + quote(relative, safe='/'),
                'bytes': destination.stat().st_size, 'sha256': sha256(destination),
                'colorSpace': color_space, 'dimensions': dimensions,
                'source_dimensions': original_dimensions,
                'source_guid': guid, 'source': texture_source['path'],
                'source_sha256': texture_source['sha256'],
                'source_mode': source_mode, 'source_importer': importer,
                'conversion': conversion,
                'channel_mapping': None if role == 'mask' else ('RGB normal, source channel convention preserved' if role == 'normal' else 'RGB diffuse'),
            }
        records.append({
            'id': 'MEADOW_' + layer['m_Name'], 'name': layer['m_Name'],
            'source': entry['path'], 'source_guid': entry['guid'], 'source_sha256': entry['sha256'],
            'textures': references,
            'texture_guids': {role: layer[field]['guid'] for role, field in ROLES.items()},
            'tileSize': layer['m_TileSize'], 'tileOffset': layer['m_TileOffset'],
            'normalScale': layer['m_NormalScale'], 'metallic': layer['m_Metallic'],
            'smoothness': layer['m_Smoothness'], 'specular': layer['m_Specular'],
            'diffuseRemapMin': layer['m_DiffuseRemapMin'], 'diffuseRemapMax': layer['m_DiffuseRemapMax'],
            'maskMapRemapMin': layer['m_MaskMapRemapMin'], 'maskMapRemapMax': layer['m_MaskMapRemapMax'],
            'mask_channel_mapping': None,
        })
    ordered_textures = sorted(textures.values(), key=lambda texture: texture['id'])
    output = {
        'schema_version': 1, 'collection': 'meadow', 'title': 'Meadow TerrainLayer Textures',
        'base_url': base, 'layer_count': len(records), 'texture_count': len(ordered_textures),
        'total_texture_bytes': sum(texture['bytes'] for texture in ordered_textures),
        'role_counts': {role: sum(texture['role'] == role for texture in ordered_textures) for role in ROLES},
        'scope': 'TerrainLayer material definitions and portable texture files. These are not terrain meshes, heightfields, splatmaps, colliders, or complete Unity Terrain scenes.',
        'uv_contract': 'Authored tileSize and tileOffset are preserved verbatim; consumers must implement their terrain UV convention.',
        'mask_policy': 'Masks retain their source channels without packing into ORM. Channel semantics are unverified in the inspected TerrainLayer/texture importer records, so channel_mapping is null. Source mask importers set sRGBTexture=true; the portable mask role is linear data and that source setting is recorded separately.',
        'normal_policy': 'RGB normal pixels and source importer flipGreenChannel values are recorded; no independent normal orientation validation or channel conversion is claimed.',
        'layers': records, 'textures': ordered_textures,
    }
    manifest = repository / 'collections/meadow/terrain-textures.json'
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(output, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps({'manifest': str(manifest), 'layers': len(records), 'textures': len(ordered_textures), 'role_counts': output['role_counts'], 'bytes': output['total_texture_bytes']}))


if __name__ == '__main__':
    main()
