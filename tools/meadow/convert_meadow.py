"""Export inspected static Meadow modules to shared-resource glTF; originals are read-only."""
import bpy,json,sys,re,hashlib,os,time
from pathlib import Path
from mathutils import Vector
work=Path(sys.argv[sys.argv.index('--')+1]);repo=Path(sys.argv[sys.argv.index('--')+2])
sys.path.insert(0,str(work/'tools'))
from portable_materials import MaterialFactory,patch_material_metadata
source=json.loads((work/'audit/extracted_source.json').read_text(encoding='utf-8'))
mapping=json.loads((work/'audit/unity_mapping.json').read_text(encoding='utf-8'))
specs=json.loads((work/'audit/pbr_specs.json').read_text(encoding='utf-8'))
factory=MaterialFactory(specs);out=repo/'models/Meadow';out.mkdir(parents=True,exist_ok=True)
by_name={}
for guid,s in specs.items():by_name.setdefault(s['name'].lower(),[]).append(guid)
def clean(name):return re.sub(r'\.\d{3}$','',name)
def find_guid(name):
 choices=by_name.get(clean(name).lower(),[])
 return max(choices,key=lambda k:bool(specs[k]['base'])) if choices else None
def safe(name):return re.sub(r'[^A-Za-z0-9_-]+','_',name).strip('_')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def lod(name):
 m=re.search(r'(?:^|[_ .])LOD[_ ]?(\d+)',name,re.I)
 return int(m.group(1)) if m else None

def share_gltf(stage,target):
 gltf=json.loads(stage.read_text(encoding='utf-8'));patch_material_metadata(gltf,specs);deps=[]
 for key,kind in [('buffers','buffers'),('images','textures')]:
  for item in gltf.get(key,[]):
   uri=item.get('uri')
   if not uri:continue
   original=(stage.parent/uri).resolve()
   if not original.is_relative_to(stage.parent.resolve()):raise ValueError('Unexpected staged dependency path')
   raw=original.read_bytes();sha=hashlib.sha256(raw).hexdigest();ext=original.suffix.lower()
   dest=out/'_shared'/kind/(sha+ext);dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():dest.write_bytes(raw)
   item['uri']=os.path.relpath(dest,target.parent).replace('\\','/')
   deps.append({'path':dest.relative_to(repo).as_posix(),'bytes':len(raw),'sha256':sha,'kind':kind})
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(gltf,separators=(',',':')),encoding='utf-8',newline='\n')
 return gltf,list({d['path']:d for d in deps}.values())

assets=[];failures=[];excluded_sources=[]
models=sorted([e for e in source['assets'] if e['path'].lower().endswith('.fbx')],key=lambda e:e['path'])
only=sys.argv[sys.argv.index('--only')+1] if '--only' in sys.argv else None
if only:models=[e for e in models if Path(e['path']).stem==only]
for ei,e in enumerate(models):
 try:
  if e['guid'] not in mapping['export_variants']:
   excluded_sources.append({'source':e['path'],'guid':e['guid'],'reason':'Particle-system-only mesh or editor helper; no static Prefab renderer assignment.'});continue
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  for mesh in list(bpy.data.meshes):
   if mesh.users==0:bpy.data.meshes.remove(mesh)
  bpy.ops.import_scene.fbx(filepath=str(work/'cache/source'/e['relative_path']),use_custom_normals=True)
  all_meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];excluded=[]
  levels=[lod(o.name) for o in all_meshes if lod(o.name) is not None];highest=min(levels) if levels else None
  for o in all_meshes:
   level=lod(o.name)
   if re.search(r'(convexhull|^UCX_|^UBX_|^UCP_|collision)',o.name,re.I) or (level is not None and level!=highest):
    excluded.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
  meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
  if not meshes:raise ValueError('No renderable highest-detail mesh remains')
  # Unity vertex channels encode wind and tint masks, not glTF diffuse colors.
  for o in meshes:
   for attr in list(o.data.color_attributes):o.data.color_attributes.remove(attr)
  originals={o.name:[m.name if m else '' for m in o.data.materials] for o in meshes}
  variants=[];known={}
  for variant in mapping['export_variants'][e['guid']]:
   assignments={};unmatched=[]
   for o in meshes:
    slots=variant['assignments'].get(clean(o.name)) or variant['assignments'].get(o.name)
    if slots is None:unmatched.append(o.name);continue
    assignments[o.name]=slots
   # Prefab-subset variants are valid only when they cover every retained mesh.
   if unmatched:continue
   signature=json.dumps(assignments,sort_keys=True,separators=(',',':'))
   if signature in known:
    known[signature]['source_prefabs']+=variant['source_prefabs'];continue
   v=dict(variant);v['retained_assignments']=assignments;v['source_prefabs']=list(variant['source_prefabs']);known[signature]=v;variants.append(v)
  if not variants:raise ValueError('No actual Prefab variant covers the retained highest-detail mesh set')
  mins=[float('inf')]*3;maxs=[float('-inf')]*3
  for obj in meshes:
   for corner in obj.bound_box:
    v=obj.matrix_world@Vector(corner);p=(v.x,v.z,-v.y)
    for axis in range(3):mins[axis]=min(mins[axis],p[axis]);maxs[axis]=max(maxs[axis],p[axis])
  triangles=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
  for vi,v in enumerate(variants):
   missing=[]
   for o in meshes:
    slots=v['retained_assignments'][o.name]
    used_indices={p.material_index for p in o.data.polygons}
    for i in range(len(o.data.materials)):
     if i not in used_indices:
      o.data.materials[i]=None;continue
     guid=slots[i] if i<len(slots) else find_guid(originals[o.name][i])
     if not guid:raise ValueError('An actually used material slot has no verified assignment: '+o.name+' / '+str(i))
     o.data.materials[i]=factory.make(guid,originals[o.name][i] or o.name)
   stem=Path(e['path']).stem;asset_id='MEADOW_'+stem+('' if vi==0 else '__'+safe(v['name']))
   category=Path(e['path']).parent.name;target=out/category/(asset_id+'.gltf')
   stage_dir=work/'cache/gltf_stage'/asset_id;stage_dir.mkdir(parents=True,exist_ok=True);stage=stage_dir/'asset.gltf'
   for o in bpy.context.scene.objects:o.select_set(True)
   bpy.ops.export_scene.gltf(filepath=str(stage),export_format='GLTF_SEPARATE',use_selection=True,export_animations=False,export_cameras=False,export_lights=False,export_extras=True,export_materials='EXPORT',export_yup=True,export_image_format='AUTO',export_tangents=False)
   gltf,deps=share_gltf(stage,target)
   controls=sorted({control for slots in v['retained_assignments'].values() for guid in slots for control in specs.get(guid,{}).get('unported_shader_controls',[])})
   record={'id':asset_id,'name':stem+' / '+v['name'],'collection':'meadow','format':'gltf','path':target.relative_to(repo).as_posix(),'category':category,'source':e['path'],'source_guid':e['guid'],'source_sha256':e['sha256'],'bytes':target.stat().st_size,'sha256':digest(target),'triangles':triangles,'mesh_count':len(gltf.get('meshes',[])),'material_count':len(gltf.get('materials',[])),'texture_count':len(gltf.get('images',[])),'bounds':{'min':mins,'max':maxs},'excluded_helpers_and_lower_lods':excluded,'material_variant':v['name'],'source_prefabs':sorted(set(v['source_prefabs'])),'season_priority':v['season_priority'],'self_contained':False,'dependencies':deps,'warnings':['Static PBR approximation; Unity wind, global season blending and vertex-mask shading are not ported.']+(['Missing material slots: '+', '.join(missing)] if missing else []),'unported_shader_controls':controls}
   assets.append(record);print('ASSET_DONE',json.dumps({'source_index':ei+1,'total_sources':len(models),'id':asset_id,'triangles':triangles}),flush=True)
  for mat in list(bpy.data.materials):
   if mat.users==0 and mat not in factory.cache.values():bpy.data.materials.remove(mat)
 except Exception as exc:
  failures.append({'source':e['path'],'error':str(exc)});print('ASSET_ERROR',json.dumps(failures[-1]),flush=True)
 finally:
  report={'assets':assets,'failures':failures,'excluded_sources':excluded_sources,'completed_sources':ei+1,'source_count':len(models),'complete':ei+1==len(models),'unmatched_material_names':sorted(set(factory.missing))}
  (work/('audit/conversion_probe.json' if only else 'audit/conversion_progress.json')).write_text(json.dumps(report,indent=2),encoding='utf-8',newline='\n')
print('CONVERSION_COMPLETE',json.dumps({'assets':len(assets),'failures':len(failures),'sources':len(models)}),flush=True)
if failures:sys.exit(1)
