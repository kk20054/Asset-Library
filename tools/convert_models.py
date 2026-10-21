"""Convert all inspected FBX modules into self-contained GLB assets, using real Prefab material slots."""
import bpy,json,sys,re,struct,hashlib,time
from pathlib import Path
from mathutils import Vector
work=Path(sys.argv[sys.argv.index('--')+1]);sys.path.insert(0,str(work/'tools'))
from portable_materials import MaterialFactory,patch_material_metadata
source=json.loads((work/'audit/extracted_source.json').read_text(encoding='utf-8'));mapping=json.loads((work/'audit/unity_mapping.json').read_text());specs=json.loads((work/'audit/pbr_specs.json').read_text());factory=MaterialFactory(specs)
repo=work/'repository';out=repo/'models';out.mkdir(parents=True,exist_ok=True)
by_name={}
for guid,s in specs.items():by_name.setdefault(s['name'].lower(),[]).append(guid)
def find_guid(name):
 name=re.sub(r'\.\d{3}$','',name).lower();choices=by_name.get(name,[])
 return max(choices,key=lambda k:bool(specs[k]['base'])) if choices else None

def patch_glb(path):
 data=path.read_bytes();jlen,jtype=struct.unpack_from('<II',data,12);gltf=json.loads(data[20:20+jlen]);tail=data[20+jlen:];patch_material_metadata(gltf,specs)
 raw=json.dumps(gltf,separators=(',',':')).encode();raw+=b' '*((-len(raw))%4);path.write_bytes(struct.pack('<III',0x46546c67,2,12+8+len(raw)+len(tail))+struct.pack('<II',len(raw),0x4e4f534a)+raw+tail)
 return gltf
assets=[];failures=[]
models=sorted([e for e in source['assets'] if e['path'].lower().endswith('.fbx')],key=lambda e:e['path'])
limit=int(sys.argv[-1]) if sys.argv[-1].isdigit() else len(models)
for ei,e in enumerate(models[:limit]):
 try:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  for me in list(bpy.data.meshes):
   if me.users==0:bpy.data.meshes.remove(me)
  before=set(bpy.data.materials);bpy.ops.import_scene.fbx(filepath=str(work/'cache/source'/e['relative_path']),use_custom_normals=True)
  excluded=[]
  for o in list(bpy.context.scene.objects):
   if o.type=='MESH' and (re.search(r'(convexhull|^UCX_|^UBX_|^UCP_|collision)',o.name,re.I) or re.search(r'(?:^|[_ .])LOD[_ ]?[1-9]\d*',o.name,re.I)):
    excluded.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
  meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
  if not meshes:raise ValueError('No renderable mesh remains')
  overrides=mapping['renderer_overrides'].get(e['guid'],{})
  for o in meshes:
   original=list(o.data.materials);slots=overrides.get(o.name,[])
   for i,old in enumerate(original):
    guid=slots[i] if i<len(slots) else find_guid(old.name if old else '')
    o.data.materials[i]=factory.make(guid,old.name if old else o.name)
  conflicts=[c for c in mapping['renderer_override_conflicts'] if c['fbx_guid']==e['guid']]
  variants=[None] if not conflicts else conflicts[0]['material_choices']
  for vi,variant in enumerate(variants):
   if variant:
    mesh=next(o for o in meshes if o.name==conflicts[0]['mesh_name'])
    for si,guid in enumerate(variant):mesh.data.materials[si]=factory.make(guid)
   stem=Path(e['path']).stem;suffix='' if not conflicts else '_variant_'+str(vi+1);asset_id=stem+suffix
   category=Path(e['path']).parent.name if Path(e['path']).parent.name!='Meshes' else 'Props'
   target=out/category/(asset_id+'.glb');target.parent.mkdir(parents=True,exist_ok=True)
   for o in bpy.context.scene.objects:o.select_set(True)
   bpy.ops.export_scene.gltf(filepath=str(target),export_format='GLB',use_selection=True,export_animations=False,export_cameras=False,export_lights=False,export_extras=True,export_materials='EXPORT',export_yup=True,export_image_format='AUTO',export_tangents=False)
   gltf=patch_glb(target)
   mins=[float('inf')]*3;maxs=[float('-inf')]*3
   for obj in meshes:
    for corner in obj.bound_box:
     v=obj.matrix_world@Vector(corner);pos=(v.x,v.z,-v.y)
     for i in range(3):mins[i]=min(mins[i],pos[i]);maxs[i]=max(maxs[i],pos[i])
   triangles=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)
   record={'id':asset_id,'name':asset_id,'path':target.relative_to(repo).as_posix(),'category':category,'source':e['path'],'source_guid':e['guid'],'source_sha256':e['sha256'],'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'triangles':triangles,'mesh_count':len(gltf.get('meshes',[])),'material_count':len(gltf.get('materials',[])),'texture_count':len(gltf.get('images',[])),'bounds':{'min':mins,'max':maxs},'excluded_helpers_and_lower_lods':excluded,'material_variant':variant,'self_contained':all('uri' not in im for im in gltf.get('images',[])) and all('uri' not in b for b in gltf.get('buffers',[]))}
   assets.append(record);print('ASSET_DONE',json.dumps({'index':ei+1,'total':len(models),'id':asset_id,'bytes':record['bytes']}),flush=True)
  for mat in list(bpy.data.materials):
   if mat not in before and mat.users==0 and mat not in factory.cache.values():bpy.data.materials.remove(mat)
 except Exception as exc:
  failures.append({'source':e['path'],'error':str(exc)});print('ASSET_ERROR',json.dumps(failures[-1]),flush=True)
 (work/'audit/conversion_progress.json').write_text(json.dumps({'assets':assets,'failures':failures,'completed_sources':ei+1,'source_count':len(models),'complete':ei+1==len(models),'unmatched_material_names':sorted(set(factory.missing))},indent=2),encoding='utf-8')
print('CONVERSION_COMPLETE',json.dumps({'assets':len(assets),'failures':len(failures),'bytes':sum(a['bytes'] for a in assets)}),flush=True)
