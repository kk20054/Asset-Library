"""Native Unreal source -> self-contained portable GLB/PNG/EXR/WAV.
Execute through UnrealEditor-Cmd -ExecutePythonScript with SOSTYLIZED_EXPORT_CONFIG.
The source archive stays untouched. JSONL receipts make interrupted batches resumable.
"""
import collections
import json
import os
from pathlib import Path
import time
import traceback
import unreal

config_path = Path(os.environ['SOSTYLIZED_EXPORT_CONFIG'])
config = json.loads(config_path.read_text(encoding='utf8'))
work = Path(config['work'])
output = work / 'native'
output.mkdir(parents=True, exist_ok=True)
source_catalog = json.loads((work / 'native_catalog.json').read_text(encoding='utf8'))
allowed = {'StaticMesh', 'Texture2D', 'SoundWave'}
assets = [a for a in source_catalog['assets'] if a['class'] in allowed]
selected = config.get('selected')
if selected is not None:
    wanted = set(selected)
    assets = [a for a in assets if a['package'] in wanted]
# Environment models first; demo helpers/effect geometry remain labelled utility assets.
assets.sort(key=lambda a: (a['class'] != 'StaticMesh', '/Environment/' not in a['package'], a['package']))
records_path = work / 'export_records.jsonl'
previous = {}
if records_path.is_file():
    for line in records_path.read_text(encoding='utf8').splitlines():
        row = json.loads(line)
        previous[row['source']['package']] = row

def safe_property(obj, name):
    try:
        value = obj.get_editor_property(name)
        if isinstance(value, (bool, int, float, str)):
            return value
        return str(value)
    except Exception:
        return None

def glb_options():
    options = unreal.GLTFExportOptions()
    options.set_editor_property('bake_material_inputs', unreal.GLTFMaterialBakeMode.USE_MESH_DATA)
    size = unreal.GLTFMaterialBakeSize()
    size.set_editor_property('x', config.get('bake_pixels', 1024))
    size.set_editor_property('y', config.get('bake_pixels', 1024))
    size.set_editor_property('auto_detect', False)
    options.set_editor_property('default_material_bake_size', size)
    options.set_editor_property('default_level_of_detail', 0)
    options.set_editor_property('export_source_model', False)
    options.set_editor_property('export_vertex_colors', False)
    options.set_editor_property('export_uniform_scale', 0.01)
    options.set_editor_property('texture_image_format', unreal.GLTFTextureImageFormat.PNG)
    return options

def write_asset(row):
    source = row['source']
    obj = unreal.load_asset(source['package'])
    if obj is None:
        raise RuntimeError('Native asset load returned null')
    relative = source['package'].removeprefix('/Game/SoStylized/')
    if source['class'] == 'StaticMesh':
        row['relative_path'] = 'Models/' + relative + '.glb'
        target = output / row['relative_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        row['lod_count'] = unreal.EditorStaticMeshLibrary.get_lod_count(obj)
        row['exported_lods'] = [0]
        row['material_slots'] = [{'slot': str(x.material_slot_name),
            'path': x.material_interface.get_path_name() if x.material_interface else None}
            for x in obj.static_materials]
        messages = unreal.GLTFExporter.export_to_gltf(obj, str(target), glb_options(), set())
        row['export_messages'] = {name: [str(x) for x in getattr(messages, name)]
                                  for name in ('suggestions', 'warnings', 'errors')}
        if row['export_messages']['errors']:
            raise RuntimeError('Native glTF export reported errors')
    else:
        relative_root = "Textures/" if source["class"] == "Texture2D" else "Audio/"
        extensions = (".png", ".exr") if source["class"] == "Texture2D" else (".wav",)
        if source["class"] == "Texture2D":
            row["srgb"] = safe_property(obj, "srgb")
            row["compression_settings"] = safe_property(obj, "compression_settings")
            row["flip_green_channel"] = safe_property(obj, "flip_green_channel")
            row["channel_mapping"] = None
        row["format_attempts"] = []
        for extension in extensions:
            row["relative_path"] = relative_root + relative + extension
            target = output / row["relative_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            task = unreal.AssetExportTask()
            task.object = obj
            task.automated = True
            task.prompt = False
            task.replace_identical = False
            task.filename = str(target)
            # Native FindExporter checks actual Texture.Source pixel format.
            # CompressionSettings can say HDR for an 8-bit source; forcing EXR asserts.
            accepted = unreal.Exporter.run_asset_export_task(task)
            valid = accepted and target.is_file() and target.stat().st_size >= 16
            row["format_attempts"].append({"extension": extension, "succeeded": valid})
            if valid:
                break
        else:
            raise RuntimeError("No native exporter produced a valid source image/audio")
        row["export_messages"] = {"errors": [], "warnings": [], "suggestions": []}
    if not target.is_file() or target.stat().st_size < 16:
        raise RuntimeError('Native export did not create a nonempty file')
    row['bytes'] = target.stat().st_size
    return obj

stats = collections.Counter()
start = time.time()
for index, source in enumerate(assets):
    old = previous.get(source['package'])
    if old and old.get('status') == 'exported':
        file = output / old['relative_path']
        if file.is_file() and file.stat().st_size == old.get('bytes'):
            stats['reused'] += 1
            continue
    row = {'source': source, 'status': 'started', 'engine': unreal.SystemLibrary.get_engine_version()}
    active_path = work / 'active_asset.json'
    active_path.write_text(json.dumps(row, indent=2), encoding='utf8')
    asset_start = time.time()
    try:
        obj = write_asset(row)
        row['status'] = 'exported'
        stats['exported'] += 1
        del obj
    except Exception:
        row['status'] = 'failed'
        row['error'] = traceback.format_exc()
        stats['failed'] += 1
    row['seconds'] = round(time.time() - asset_start, 3)
    with records_path.open('a', encoding='utf8') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + chr(10))
    progress = {'total': len(assets), 'index': index + 1, 'counts': dict(stats),
                'current': source['package'], 'elapsed_seconds': round(time.time() - start, 1)}
    (work / 'export_progress.json').write_text(json.dumps(progress, indent=2), encoding='utf8')
    print('SO_STYLIZED_EXPORT_PROGRESS ' + json.dumps(progress), flush=True)
    if (index + 1) % 8 == 0:
        unreal.SystemLibrary.collect_garbage()
summary = {'total': len(assets), 'counts': dict(stats), 'engine': unreal.SystemLibrary.get_engine_version(),
           'scope': 'Native LOD0 static models, source Texture2D and SoundWave; no Blueprint/world-runtime conversion',
           'seconds': round(time.time() - start, 1)}
(work / 'export_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
print('SO_STYLIZED_EXPORT_DONE ' + json.dumps(summary), flush=True)
