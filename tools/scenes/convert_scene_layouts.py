#!/usr/bin/env python3
"""Resolve author Overview/Diorama Unity scene layouts without editing source/models."""
import argparse,copy,hashlib,json,re,sys
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

def ref(v):return v if isinstance(v,dict) else {}
def fid(v):return int(ref(v).get('fileID',0))
def safe(v,key=''):
 if isinstance(v,dict):return {str(k):safe(x,str(k)) for k,x in v.items()}
 if isinstance(v,list):return [safe(x,key) for x in v]
 if key=='fileID' or isinstance(v,int) and abs(v)>9007199254740991:return str(v)
 return v

def mat(data):
 p=data.get('m_LocalPosition',{});q=data.get('m_LocalRotation',{});s=data.get('m_LocalScale',{})
 x,y,z,w=[float(q.get(k,1 if k=='w' else 0)) for k in 'xyzw'];n=x*x+y*y+z*z+w*w
 if not n:raise ValueError('Zero quaternion')
 k=2/n;r=np.array([[1-k*(y*y+z*z),k*(x*y-z*w),k*(x*z+y*w),0],[k*(x*y+z*w),1-k*(x*x+z*z),k*(y*z-x*w),0],[k*(x*z-y*w),k*(y*z+x*w),1-k*(x*x+y*y),0],[0,0,0,1.]])
 r[:3,:3]=r[:3,:3]@np.diag([float(s.get(a,1)) for a in 'xyz']);r[:3,3]=[float(p.get(a,0)) for a in 'xyz'];return r

def flat(m):return [float(x) for x in m.flatten(order='F')]
def gltf_matrix(node):
 if 'matrix' in node:return np.array(node['matrix'],dtype=float).reshape((4,4),order='F')
 return mat({'m_LocalPosition':dict(zip('xyz',node.get('translation',[0,0,0]))),'m_LocalRotation':dict(zip('xyzw',node.get('rotation',[0,0,0,1]))),'m_LocalScale':dict(zip('xyz',node.get('scale',[1,1,1])))})

def set_property(data,path,value,reference):
 tokens=re.findall(r'[^.\[\]]+',path.replace('.Array.data[','[').replace('.Array.size','.size'))
 target=data
 for token in tokens[:-1]:target=target[int(token)] if isinstance(target,list) else target[token]
 key=tokens[-1]
 if key=='size' and isinstance(target,list):
  size=int(value);target[:]=target[:size]+[{'fileID':0} for _ in range(max(0,size-len(target)))];return
 if isinstance(reference,dict) and int(reference.get('fileID',0))!=0:new=copy.deepcopy(reference)
 else:
  old=target[int(key)] if isinstance(target,list) else target.get(key)
  if isinstance(old,dict) and 'fileID' in old:new=copy.deepcopy(reference or {'fileID':0})
  elif isinstance(old,str):new=str(value)
  elif isinstance(old,bool):new=bool(int(value))
  elif isinstance(old,(int,float)):new=float(value) if isinstance(value,float) or any(c in str(value).lower() for c in '.e') else int(value)
  else:
   try:new=float(value) if any(c in str(value).lower() for c in '.e') else int(value)
   except (TypeError,ValueError):new=value
 if isinstance(target,list):target[int(key)]=new
 else:target[key]=new

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',required=True,type=Path);ap.add_argument('--repository','--repo',dest='repo',required=True,type=Path);args=ap.parse_args();work=args.work.resolve();repo=args.repo.resolve()
 sys.path.insert(0,str(work/'tools/_deps'));import yaml
 loader=getattr(yaml,'CSafeLoader',yaml.SafeLoader)
 index=json.loads((work/'audit/extracted_source.json').read_text('utf-8'));by={a['guid']:a for a in index['assets']};mapping=json.loads((work/'audit/unity_mapping.json').read_text('utf-8'));manifest=json.loads((repo/'manifest.json').read_text('utf-8'));assets=[a for a in manifest['assets'] if a.get('collection')=='meadow'];cache={};H=np.diag([-1.,1.,1.,1.]);E=np.eye(4)
 def documents(guid):
  if guid in cache:return cache[guid]
  a=by[guid];text=(work/'cache/source'/a['relative_path']).read_text('utf-8-sig');marks=list(re.finditer(r'^--- !u!(\d+) &(-?\d+)( stripped)?\s*$',text,re.M));docs={}
  for i,m in enumerate(marks):
   body=yaml.load(text[m.end():marks[i+1].start() if i+1<len(marks) else len(text)],Loader=loader) or {};typ,data=next(iter(body.items()));docs[int(m[2])]={'id':int(m[2]),'class_id':int(m[1]),'stripped':bool(m[3]),'type':typ,'data':data or {}}
  cache[guid]=docs;return docs
 library=defaultdict(list)
 for a in assets:
  doc=json.loads((repo/a['path']).read_text('utf-8'));worlds={}
  def visit(n,parent):
   world=parent@gltf_matrix(doc['nodes'][n]);worlds[n]=world
   for child in doc['nodes'][n].get('children',[]):visit(child,world)
  for n in doc['scenes'][doc.get('scene',0)]['nodes']:visit(n,E)
  for n,world in worlds.items():
   node=doc['nodes'][n]
   if 'mesh' not in node:continue
   name=node['name'];variants=[v for v in mapping['export_variants'].get(a['source_guid'],[]) if v['name']==a.get('material_variant')];assignments=next((v['assignments'].get(name) for v in variants if name in v['assignments']),None)
   library[(a['source_guid'],name)].append({'id':a['id'],'path':a['path'],'node_name':name,'native_node_matrix_gltf':flat(world),'material_guids':assignments,'source_prefabs':a.get('source_prefabs',[])})
 scenes=[a for a in index['assets'] if re.search(r'_(04_DioramaExample|05_Overview)\.unity$',a['path'])];outdir=work/'audit/scene_layouts';outdir.mkdir(parents=True,exist_ok=True)
 for scene in scenes:
  sg=scene['guid'];docs=documents(sg);prefix=sg+'/scene:';groups={};aliases={};components=[];instances=[];unresolved=[];unsupported=[];definitions={};override_count=Counter();lod_groups=[];source_instances=[]
  def key(scope,num):return scope+'/transform:'+str(num)
  def add_context(source_guid,source_docs,scope,instance=None,external_parent=None):
   transforms={i:d for i,d in source_docs.items() if d['type']=='Transform' and not d['stripped']};gos={i:d['data'] for i,d in source_docs.items() if d['type']=='GameObject'};roots=[]
   for i,d in transforms.items():
    data=d['data'];go=fid(data.get('m_GameObject'));parent=fid(data.get('m_Father'));node=key(scope,i);parent_id=key(scope,parent) if parent else external_parent
    if not parent:roots.append(node)
    if sum(float(data.get('m_LocalRotation',{}).get(a,1 if a=='w' else 0))**2 for a in 'xyzw')==0:raise ValueError('Zero quaternion at '+source_guid+'/'+str(i)+' instance '+str(instance)+' data '+str(data))
    groups[node]={'id':node,'parent_id':parent_id,'name':gos.get(go,{}).get('m_Name','Transform '+str(i)),'source_guid':source_guid,'source_transform_id':str(i),'source_game_object_id':str(go),'instance_id':str(instance) if instance is not None else None,'active_self':bool(gos.get(go,{}).get('m_IsActive',1)),'local_position_unity':[float(data.get('m_LocalPosition',{}).get(a,0)) for a in 'xyz'],'local_rotation_unity':[float(data.get('m_LocalRotation',{}).get(a,1 if a=='w' else 0)) for a in 'xyzw'],'local_scale_unity':[float(data.get('m_LocalScale',{}).get(a,1)) for a in 'xyz'],'local_matrix_unity':flat(mat(data)),'local_matrix_gltf':flat(H@mat(data)@H)}
   go_transform={fid(d['data'].get('m_GameObject')):key(scope,i) for i,d in transforms.items()}
   for i,d in source_docs.items():
    if d['type'] not in ['GameObject','Transform','PrefabInstance']:
     components.append({'source_guid':source_guid,'scope':scope,'instance':instance,'id':i,'type':d['type'],'class_id':d['class_id'],'data':d['data'],'group':go_transform.get(fid(d['data'].get('m_GameObject'))),'root':roots[0] if len(roots)==1 else None})
    if d['type']=='LODGroup':lod_groups.append({'id':scope+'/component:'+str(i),'group_id':go_transform.get(fid(d['data'].get('m_GameObject'))),'source_guid':source_guid,'properties':safe(d['data'])})
   return roots
  # First reserve all aliases, including stripped prefab child transforms.
  for i,d in docs.items():
   if d['type']=='Transform':
    if d['stripped']:
     data=d['data'];aliases[key(prefix,i)]=key(sg+'/instance:'+str(fid(data.get('m_PrefabInstance'))),fid(data.get('m_CorrespondingSourceObject')))
    else:aliases[key(prefix,i)]=key(prefix,i)
  add_context(sg,{i:d for i,d in docs.items() if d['type']!='PrefabInstance'},prefix)
  for i,d in docs.items():
   if d['type']!='PrefabInstance':continue
   data=d['data'];pg=str(ref(data.get('m_SourcePrefab')).get('guid',''));scope=sg+'/instance:'+str(i);mod=data.get('m_Modification',{});parent=fid(mod.get('m_TransformParent'));parent_id=aliases.get(key(prefix,parent),key(prefix,parent)) if parent else None
   record={'id':str(i),'source_prefab_guid':pg,'source_prefab_path':by.get(pg,{}).get('path'),'parent_id':parent_id,'modifications':safe(mod.get('m_Modifications',[]))};source_instances.append(record)
   if pg not in by:unresolved.append({'instance_id':str(i),'reason':'Source Prefab GUID missing','guid':pg});continue
   pd=copy.deepcopy(documents(pg))
   for change in mod.get('m_Modifications',[]):
    target=ref(change.get('target'));tid=fid(target);tg=str(target.get('guid',pg));path=change.get('propertyPath','');override_count[path]+=1
    if tg!=pg or tid not in pd:unresolved.append({'instance_id':str(i),'reason':'Override target not in resolved Prefab','modification':safe(change)});continue
    try:set_property(pd[tid]['data'],path,change.get('value'),change.get('objectReference'))
    except (KeyError,IndexError,TypeError,ValueError) as exc:unresolved.append({'instance_id':str(i),'reason':'Cannot apply property override: '+str(exc),'modification':safe(change)})
   for kind in ['m_RemovedComponents','m_RemovedGameObjects','m_AddedGameObjects','m_AddedComponents']:
    if mod.get(kind):unsupported.append({'instance_id':str(i),'type':kind,'reason':'Structural Prefab overrides require explicit expansion','properties':safe(mod[kind])})
   if any(x['type']=='PrefabInstance' for x in pd.values()):unsupported.append({'instance_id':str(i),'reason':'Nested source PrefabInstance requires further expansion','source_guid':pg})
   roots=add_context(pg,pd,scope,i,parent_id);record['root_group_ids']=roots;instances.append((scope,pg,pd,roots))
  # Resolve ordinary scene parent references through stripped Transform aliases.
  for group in groups.values():
   if group['parent_id'] in aliases:group['parent_id']=aliases[group['parent_id']]
  memo={};visiting=set()
  def world(gid):
   if gid in memo:return memo[gid]
   if gid in visiting:raise ValueError('Transform cycle: '+gid)
   visiting.add(gid);g=groups[gid];parent=g['parent_id'];local=np.array(g['local_matrix_unity']).reshape((4,4),order='F')
   if parent and parent not in groups:unresolved.append({'group_id':gid,'reason':'Missing parent Transform','parent_id':parent});return None
   pw=world(parent) if parent else E
   if pw is None:return None
   result=pw@local;memo[gid]=result;visiting.remove(gid);g['world_matrix_unity']=flat(result);g['world_matrix_gltf']=flat(H@result@H);g['active_in_hierarchy']=g['active_self'] and (groups[parent].get('active_in_hierarchy',False) if parent else True);return result
  for gid in groups:world(gid)
  objects=[];cameras=[];lights=[];counts=Counter();filters={(c['scope'],fid(c['data'].get('m_GameObject'))):c for c in components if c['type']=='MeshFilter'}
  prefab_paths={pg:by[pg]['path'] for _,pg,_,_ in instances}
  for c in components:
   typ=c['type'];counts[typ]+=1;gid=c['group'];data=c['data'];cid=c['scope']+'/component:'+str(c['id']);definition=c['scope']+'/component:'+str(c['id'])
   base={'id':cid,'parent_id':gid,'source_component_id':str(c['id']),'source_guid':c['source_guid'],'instance_id':str(c['instance']) if c['instance'] is not None else None,'type':typ,'name':groups.get(gid,{}).get('name',typ),'active_in_hierarchy':groups.get(gid,{}).get('active_in_hierarchy',False),'enabled':bool(data.get('m_Enabled',1)),'world_matrix_unity':groups.get(gid,{}).get('world_matrix_unity'),'world_matrix_gltf':groups.get(gid,{}).get('world_matrix_gltf')}
   if typ in ['Camera','Light']:
    (cameras if typ=='Camera' else lights).append(base|{'properties':safe(data)});continue
   if typ in ['MeshRenderer','SkinnedMeshRenderer','ParticleSystemRenderer']:
    mesh=ref(data.get('m_Mesh')) if typ!='MeshRenderer' else ref(filters.get((c['scope'],fid(data.get('m_GameObject'))),{}).get('data',{}).get('m_Mesh'))
    fg=str(mesh.get('guid',''));mi=str(mesh.get('fileID',0));name=mapping['fbx_mesh_names'].get(fg,{}).get(mi);materials=[str(ref(v).get('guid','')) or None for v in data.get('m_Materials',[])];level=re.search(r'(?:^|[_ .])LOD[_ ]?(\d+)',name or '',re.I);lod=int(level[1]) if level else None
    row=base|{'id':c['scope']+'/renderer:'+str(c['id']),'source_renderer_id':str(c['id']),'source_transform_id':groups.get(gid,{}).get('source_transform_id'),'source_prefab_guid':c['source_guid'] if c['instance'] is not None else None,'source_prefab_path':prefab_paths.get(c['source_guid']),'fbx_guid':fg or None,'mesh_file_id':mi,'mesh_name':name,'material_guids':materials,'renderer_enabled':bool(data.get('m_Enabled',1)),'selected_lod':lod,'retained':False,'asset_id':None,'asset_candidates':[]}
    root=c['root']
    if root and gid in memo and root in memo:row['prefab_root_to_renderer_matrix_unity']=flat(np.linalg.inv(memo[root])@memo[gid])
    if typ=='ParticleSystemRenderer':row['exclusion_reason']='Unity particle runtime is unsupported; mesh metadata retained'
    elif mi=='10202' and (not fg or fg.startswith('0000000000000000')):row.update(builtin_mesh={'file_id':mi,'shape':'cube','size':[1,1,1]},retained=True)
    elif (fg,name) in library:
     choices=[a for a in library[(fg,name)] if a['material_guids']==materials]
     choices.sort(key=lambda a:(row['source_prefab_path'] not in a['source_prefabs'],a['id']))
     row['asset_candidates']=choices;row['asset_id']=choices[0]['id'] if choices else None;row['retained']=True
     if not choices:row['requires_material_variant']=True;unresolved.append({'renderer_id':row['id'],'reason':'No exact library material assignment; static geometry exists','fbx_guid':fg,'mesh_name':name,'material_guids':materials})
    elif lod is not None and lod>0:row['exclusion_reason']='Lower LOD intentionally excluded to match current library'
    elif c['source_guid'] in by and '/ASP Global Settings/' in by[c['source_guid']]['path']:row['exclusion_reason']='ASP editor helper mesh is intentionally excluded'
    else:row['exclusion_reason']='Mesh is not resolved to current library';unresolved.append({'renderer_id':row['id'],'reason':row['exclusion_reason'],'mesh_reference':safe(mesh)})
    if not row['active_in_hierarchy'] or not row['renderer_enabled']:row['draw']=False
    else:row['draw']=row['retained']
    row['renderer_properties']=safe({k:v for k,v in data.items() if k not in ['m_GameObject','m_CorrespondingSourceObject','m_PrefabInstance','m_PrefabAsset']});objects.append(row);continue
   if typ in ['MeshFilter','LODGroup']:continue
   if typ in ['RenderSettings','LightmapSettings','OcclusionCullingSettings','NavMeshSettings']:continue
   reason='Collision only; no visible geometry' if 'Collider' in typ else 'Unity component behavior is preserved as metadata, not implemented'
   definitions[definition]={'type':typ,'class_id':c['class_id'],'source_guid':c['source_guid'],'source_component_id':str(c['id']),'properties':safe(data)}
   unsupported.append(base|{'reason':reason,'definition_id':definition})
  environment={d['type']:safe(d['data']) for d in docs.values() if d['type'] in ['RenderSettings','LightmapSettings','OcclusionCullingSettings','NavMeshSettings']}
  tag='overview' if '_05_' in scene['path'] else 'diorama';result={'schema_version':1,'id':'meadow_author_'+tag,'name':Path(scene['path']).stem,'source':{'path':scene['path'],'guid':sg,'sha256':scene['sha256']},'coordinate_contract':{'matrix_layout':'column-major; Matrix4.fromArray compatible','unity_to_gltf_basis':flat(H),'basis_name':'flip X: H = diag(-1, 1, 1, 1)','basis_reference':'https://github.com/KhronosGroup/UnityGLTF/issues/290','basis_scope':'Coordinate representation changes only; original Unity authored placement values and hierarchy are preserved. Existing library mesh vertices/native nodes are unchanged.','units':'Unity meters; existing glTF mesh-node scale 0.01 converts its raw centimeter vertices','assembly':'Preserve groups local TRS hierarchy. Attach selected library single mesh-node beneath the renderer parent_id. Keep complete native library node matrix including scale 0.01 and any pivot translation; do not multiply root-to-renderer or world matrix again.','world_matrices':'Audit evidence only; do not flatten hierarchy because nonuniform scale plus child rotations can produce shear.','library_native_pivots':'Flower09_01 and three Leaves FBX nodes have native translations absent from Unity Prefab mesh-local transforms; retain them once.'},'groups':list(groups.values()),'objects':objects,'prefab_instances':source_instances,'cameras':cameras,'lights':lights,'environment':environment,'lod_groups':lod_groups,'unsupported':unsupported,'unsupported_definitions':definitions,'unresolved':unresolved,'source_counts':{'scene_documents':len(docs),'prefab_instances':len(source_instances),'ordinary_scene_transforms':sum(d['type']=='Transform' and not d['stripped'] for d in docs.values()),'resolved_groups':len(groups),'renderers':len(objects),'retained_renderers':sum(r['retained'] for r in objects),'draw_renderers':sum(r['draw'] for r in objects),'builtin_cubes':sum('builtin_mesh' in r for r in objects),'component_types':dict(counts),'override_property_counts':dict(override_count),'unresolved':len(unresolved),'unsupported_records':len(unsupported)},'limitations':['Unity runtime particles, custom postprocessing/shaders and collisions are preserved as unsupported metadata rather than reproduced.','Source alpha, wind and material approximations remain those of the current portable asset library.']}
  target=outdir/(tag+'.json');target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf-8');print(json.dumps({'output':str(target),'id':result['id'],'counts':result['source_counts'],'unresolved_examples':unresolved[:5]},ensure_ascii=False))
if __name__=='__main__':main()
