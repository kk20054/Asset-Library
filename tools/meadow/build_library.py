#!/usr/bin/env python3
"""Build the shared library indexes after complete Meadow conversion; models are read only."""
import argparse,copy,json,re,shutil,sys
from pathlib import Path,PurePosixPath
from collections import Counter
from urllib.parse import quote
BASE='https://raw.githubusercontent.com/kk20054/ThreeJS-Stylized-World-Assets/main/'
VIEWER='https://kk20054.github.io/ThreeJS-Stylized-World-Assets/'
LOCAL=re.compile(r'(?:[A-Za-z]:[/\\]|file://|^\\\\|^/(?:Users|home|tmp|private|mnt)/)',re.I)
def load(p):return json.loads(p.read_text('utf-8-sig'))
def write(p,v,compact=False):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False,indent=None if compact else 2,separators=(',',':') if compact else None)+'\n','utf-8')
def actual(repo,name):
 if PurePosixPath(name).is_absolute() or '\\' in name or re.match(r'^[A-Za-z]:',name):raise ValueError('Not a relative repository path: '+name)
 p=(repo/name).resolve(strict=True)
 if not p.is_relative_to(repo) or not p.is_file():raise ValueError('Payload escapes repository or is not a file: '+name)
 return p
def extras_paths(node,pointer='',inside=False):
 found=[]
 if isinstance(node,str) and inside and LOCAL.search(node):found.append({'pointer':pointer,'value':node})
 elif isinstance(node,dict):
  for k,v in node.items():found+=extras_paths(v,pointer+'/'+str(k),inside or k=='extras')
 elif isinstance(node,list):
  for i,v in enumerate(node):found+=extras_paths(v,pointer+'/'+str(i),inside)
 return found
def compact(a):
 return {k:a.get(k) for k in ['id','name','collection','category','path','url','triangles','bytes','format','self_contained']}|{'variant':a.get('material_variant')}
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--work',type=Path,required=True)
 parser.add_argument('--repo','--repository',dest='repo',type=Path,required=True)
 args=parser.parse_args();work=args.work.resolve();repo=args.repo.resolve(strict=True)
 old=load(repo/'manifest.json');progress=load(work/'audit/conversion_progress.json');extracted=load(work/'audit/extracted_source.json')
 if not progress.get('complete') or progress.get('failures'):raise ValueError('Conversion must be complete with zero failures.')
 source_assets=extracted['assets'];fbxs={a['guid']:a for a in source_assets if a['path'].lower().endswith('.fbx')}
 meadow=copy.deepcopy(progress['assets']);exported={a['source_guid'] for a in meadow};excluded={a.get('guid') or a.get('source_guid'):a for a in progress['excluded_sources']}
 if (len(fbxs),len(exported),len(excluded))!=(151,144,7):raise ValueError('Expected source partition 151 = 144 exported + 7 excluded.')
 if exported&set(excluded) or exported|set(excluded)!=set(fbxs):raise ValueError('Exported/excluded GUIDs do not partition actual source FBXs.')
 if progress.get('source_count')!=151:raise ValueError('Conversion source_count is not 151.')
 temple=copy.deepcopy([a for a in old['assets'] if a.get('collection')!='meadow'])
 if len(temple)!=135:raise ValueError('Original Temple asset count is not 135.')
 for a in temple:a.update(collection='temple',format='glb')
 for a in meadow:
  a.update(collection='meadow',format='gltf')
  if a.get('self_contained') is not False:raise ValueError('Meadow models must explicitly declare shared dependencies.')
  if a['source_guid'] not in fbxs or a['source_sha256']!=fbxs[a['source_guid']]['sha256']:raise ValueError('Meadow source GUID/hash disagrees with extraction evidence.')
 assets=temple+meadow
 if len({a['id'] for a in assets})!=len(assets) or len({a['path'] for a in assets})!=len(assets):raise ValueError('Duplicate asset ID or path.')
 payload={};meadow_payload={};findings=[]
 for a in assets:
  for item in [a]+a.get('dependencies',[]):
   p=actual(repo,item['path']);size=p.stat().st_size
   if size!=item['bytes']:raise ValueError('Actual byte length disagrees with evidence: '+item['path'])
   payload[p]=size
   if a['collection']=='meadow':meadow_payload[p]=size
  a['url']=BASE+quote(a['path'],safe='/')
  if a['format']=='gltf':
   findings += [{'asset':a['path'],**f} for f in extras_paths(load(actual(repo,a['path'])))]
 if findings:
  print(json.dumps({'status':'blocked','reason':'Local machine paths found in glTF extras; models were not modified.','findings':findings},ensure_ascii=False),file=sys.stderr)
  raise SystemExit(2)
 terrain_name='collections/meadow/terrain-textures.json';terrain=repo/terrain_name;terrain_files=[]
 if terrain.exists():
  load(terrain)
  for p in sorted((repo/'textures/Meadow/Terrain').rglob('*')):
   if p.is_file():
    real=actual(repo,p.relative_to(repo).as_posix());terrain_files.append(real);payload[real]=meadow_payload[real]=real.stat().st_size
 old_collections=old.get('collections',{})
 if isinstance(old_collections,list):old_collections={c['id']:c for c in old_collections}
 ts=copy.deepcopy(old_collections.get('temple',{}))
 if not ts:
  for k in ['source_fbx_count','texture_policy','material_policy','validation','known_limits']:
   if k in old:ts[k]=copy.deepcopy(old[k])
 ts.update(id='temple',name='Stylized Chinese Lost Temple',title='Stylized Chinese Lost Temple',format='glb',asset_count=135,unique_model_count=len({a['source_guid'] for a in temple}),total_glb_bytes=sum(a['bytes'] for a in temple),asset_index='collections/temple/asset-index.json')
 ms={'title':'Meadow Environment - Stylized Pack','format':'gltf','asset_count':len(meadow),'unique_model_count':144,'source_fbx_count':151,'exported_source_fbx_count':144,'excluded_source_fbx_count':7,'conversion_failures':0,'categories':dict(sorted(Counter(a['category'] for a in meadow).items())),'total_payload_bytes':sum(meadow_payload.values()),'asset_index':'collections/meadow/asset-index.json','source_catalog':'collections/meadow/source-catalog.json','self_contained':False,'texture_policy':'Shared external PNG/JPEG textures and content-addressed BIN buffers; keep relative paths.','material_policy':'Static portable PBR approximations of actual Unity Prefab variants.','known_limits':['Wind, particle behavior, global season blending, terrain height/splat data, SSS and procedural vertex masks are not ported.']}
 ms.update(id='meadow',name='Meadow Environment - Stylized Pack 1.6')
 if terrain.exists():ms.update(terrain_texture_index=terrain_name,terrain_texture_file_count=len(terrain_files))
 manifest=copy.deepcopy(old)
 manifest.update(schema_version=2,title='Three.js Stylized World Assets',format='glTF 2.0: self-contained GLB and shared-resource glTF',base_url=BASE,viewer_url=VIEWER,collections=[ts,ms],asset_count=len(assets),unique_model_count=len({(a['collection'],a['source_guid']) for a in assets}),total_payload_bytes=sum(payload.values()),payload_file_count=len(payload),total_glb_bytes=ts['total_glb_bytes'],total_glb_bytes_scope='temple collection only; use total_payload_bytes for the entire library',assets=assets)
 for k in ['source_variant','source_fbx_count','texture_policy','material_policy','validation']:manifest.pop(k,None)
 manifest['known_limits']=list(dict.fromkeys(ts.get('known_limits',[])+ms['known_limits']))
 catalog=[]
 for a in source_assets:
  guid=a['guid'];row={k:a[k] for k in ['path','guid','sha256','bytes']}
  if guid in exported:row['status']='exported_static_model'
  elif guid in excluded:row.update(status='excluded',exclusion_reason=excluded[guid]['reason'])
  else:row['status']='source_support_resource'
  catalog.append(row)
 source_catalog={'schema_version':2,'collection':'meadow','source_package':Path(extracted['source_package']).name,'source_fbx_count':151,'exported_source_fbx_count':144,'excluded_source_fbx_count':7,'conversion_failures':0,'assets':catalog}
 index={'schema_version':2,'title':manifest['title'],'base_url':BASE,'viewer_url':VIEWER,'asset_count':len(assets),'unique_model_count':manifest['unique_model_count'],'total_payload_bytes':manifest['total_payload_bytes'],'collections':manifest['collections'],'assets':[compact(a) for a in assets]}
 write(repo/'manifest.json',manifest);write(repo/'asset-index.json',index,True)
 for name,items in [('temple',temple),('meadow',meadow)]:write(repo/'collections'/name/'asset-index.json',{'schema_version':2,'collection':name,'base_url':BASE,'asset_count':len(items),'assets':[compact(a) for a in items]},True)
 write(repo/'collections/meadow/source-catalog.json',source_catalog)
 target=repo/'tools/meadow';target.mkdir(parents=True,exist_ok=True);copied=[]
 for p in sorted((work/'tools').iterdir()):
  if p.is_file() and p.suffix in ('.py','.mjs'):
   shutil.copy2(p,target/p.name);copied.append(p.name)
 source_index=load(work/'audit/source_index.json');source_index['source_package']=Path(source_index['source_package']).name
 write(target/'source_index.json',source_index)
 readme='''# Meadow conversion tools

Exact conversion scripts used for this collection. Original Unity assets are not bundled.
Install Python dependencies: python -m pip install PyYAML Pillow numpy. Install gltf-validator with npm for official validation. Set MEADOW_WORK to your work folder when running the copied validator. Blender supplies bpy/mathutils.
Use a separate work folder with tools/, audit/, cache/. Source indexing streams the original gzip+tar package and records GUID/asset/pathname entries; pathname uses its first text line. Restore the included source_index.json to audit/source_index.json before extraction.
Commands: extract_sources.py <work> <original-package>; prepare_meadow_mapping.py --work <work>; prepare_textures.py <work>; prepare_pbr_specs.py <work>; Blender --background --python convert_meadow.py -- <work> <repository>.
Run build_library.py --work <work> --repo <repository> only after complete conversion with 144 exported sources and seven excluded sources. No runtime caches or installed dependencies are copied here.
Keep shared images/BIN paths together with Meadow glTF. Unity wind, particles, terrain shape/splat maps and procedural shaders are not reproduced.
'''
 (target/'README.md').write_text(readme,'utf-8')
 print(json.dumps({'status':'complete','asset_count':len(assets),'temple_assets':135,'meadow_assets':len(meadow),'unique_model_count':manifest['unique_model_count'],'meadow_source_partition':{'source':151,'exported':144,'excluded':7},'total_payload_bytes':manifest['total_payload_bytes'],'payload_file_count':len(payload),'terrain_texture_file_count':len(terrain_files),'copied_tools':copied},ensure_ascii=False))
if __name__=='__main__':main()
