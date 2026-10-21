"""Publish complete static author layouts, exact hierarchy JSON, and shared-resource scenes."""
import argparse,json,sys,hashlib,copy,math,re
from pathlib import Path
import numpy as np
from authored_gltf import ResourceMerger,matrix_node
p=argparse.ArgumentParser();p.add_argument('--work',required=True);p.add_argument('--repo',required=True);args=p.parse_args();work=Path(args.work);repo=Path(args.repo)
materials=json.loads((work/'audit/unity_mapping.json').read_text())['materials']
def save(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8',newline='\n')
def mat(v):return np.array(v,dtype=float).reshape((4,4),order='F')
def flat(v):return np.asarray(v).flatten(order='F').tolist()
def bbox_merge(a,b):return b if a is None else (np.minimum(a[0],b[0]),np.maximum(a[1],b[1]))
def safe(s):return re.sub('[^A-Za-z0-9_-]+','_',s).strip('_').lower()
def geometry_box(doc,node,world):
 m=world@matrix_node(node);result=None
 for primitive in doc['meshes'][node['mesh']]['primitives']:
  ac=doc['accessors'][primitive['attributes']['POSITION']];lo=ac['min'];hi=ac['max'];pts=np.array([(m@np.array([x,y,z,1]))[:3] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]]);result=bbox_merge(result,(pts.min(axis=0),pts.max(axis=0)))
 return result

def view_box(id,label,bbox,scale=1.7):
 lo,hi=bbox;center=(lo+hi)/2;direction=np.array([.25,1.05,1.4]);direction/=np.linalg.norm(direction);forward=-direction;right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward);tv=math.tan(math.radians(25));th=tv*1.2;distance=1
 for x in [lo[0],hi[0]]:
  for y in [lo[1],hi[1]]:
   for z in [lo[2],hi[2]]:
    delta=np.array([x,y,z])-center;depth=np.dot(delta,direction);distance=max(distance,abs(np.dot(delta,right))/th+depth,abs(np.dot(delta,up))/tv+depth)
 pos=center+direction*distance*1.12;radius=max(np.linalg.norm(hi-lo)/2,1)
 return {'id':id,'label':label,'position':pos.tolist(),'target':center.tolist(),'fov':50,'near':max(radius/10000,.01),'far':max(radius*20,1000),'framing':'Conservative bounds-based inspection view; only source-camera is the author camera.'}

def source_camera(layout):
 c=next(c for c in layout['cameras'] if c['active_in_hierarchy'] and c['enabled']);u=mat(c['world_matrix_unity']);H=mat(layout['coordinate_contract']['unity_to_gltf_basis']);position=(H@u@np.array([0,0,0,1]))[:3];forward=(H@u@np.array([0,0,1,0]))[:3];forward/=np.linalg.norm(forward);up=(H@u@np.array([0,1,0,0]))[:3];up/=np.linalg.norm(up);right=np.cross(forward,up);right/=np.linalg.norm(right);up=np.cross(right,forward);m=np.eye(4);m[:3,:3]=np.column_stack([right,up,-forward]);m[:3,3]=position
 props=c['properties'];return {'id':'source-camera','label':'Original source camera (local view)','position':position.tolist(),'target':(position+forward*30).tolist(),'up':up.tolist(),'fov':props['field of view'],'near':props['near clip plane'],'far':props['far clip plane'],'source_component_id':c['source_component_id'],'matrix_gltf':flat(m)}

index={'schema_version':1,'title':'Meadow authored scene layouts','source_package':'Meadow Environment - Stylized Pack1.6','scope':'Complete authored static mesh placements, hierarchy and material selection; portable PBR, not a Unity runtime conversion.','scenes':[]}
reports=[]
for sid in ['overview','diorama']:
 layout=json.loads((work/f'audit/scene_layouts/{sid}.json').read_text());out=repo/'scenes'/sid;target=out/'scene.gltf';merger=ResourceMerger(repo,target);doc=merger.doc
 groups={g['id']:g for g in layout['groups']};instances={i['id']:i for i in layout['prefab_instances']};roots={g:i['id'] for i in instances.values() for g in i['root_group_ids']};node_ids={}
 for group in groups.values():
  extras={'source_layout_group_id':group['id'],'source_transform_id':group['source_transform_id'],'source_instance_id':group.get('instance_id'),'source_is_prefab_root':group['id'] in roots,'source_active_in_hierarchy':group['active_in_hierarchy']}
  if group['id'] in roots:extras['source_prefab_guid']=instances[roots[group['id']]]['source_prefab_guid']
  node_ids[group['id']]=len(doc['nodes']);doc['nodes'].append({'name':group['name'],'matrix':group['local_matrix_gltf'],'extras':extras})
 for group in groups.values():
  n=node_ids[group['id']];parent=group['parent_id']
  if parent:doc['nodes'][node_ids[parent]].setdefault('children',[]).append(n)
  else:doc['scenes'][0]['nodes'].append(n)
 total_box=None;group_boxes={};draw=[];object_nodes={};used=set();triangle_total=0
 for obj in layout['objects']:
  if not obj.get('draw'):continue
  if obj.get('builtin_mesh'):native=merger.cube_node(obj['material_guids'][0],materials)
  else:
   if not obj.get('asset_id'):raise ValueError('Unresolved visible static object: '+obj['id'])
   native=merger.model_node(obj['asset_id'],obj['material_guids'],materials);used.add(obj['asset_id'])
  native.setdefault('extras',{}).update({'source_layout_object_id':obj['id'],'source_renderer_id':obj['source_renderer_id'],'source_transform_id':obj['source_transform_id'],'source_instance_id':obj['instance_id'],'library_asset_id':obj.get('asset_id'),'author_layout_preserved':True})
  ni=len(doc['nodes']);doc['nodes'].append(native);doc['nodes'][node_ids[obj['parent_id']]].setdefault('children',[]).append(ni);object_nodes[obj['id']]=ni
  bounds=geometry_box(doc,native,mat(obj['world_matrix_gltf']));total_box=bbox_merge(total_box,bounds)
  parent=obj['parent_id']
  while parent:group_boxes[parent]=bbox_merge(group_boxes.get(parent),bounds);parent=groups[parent]['parent_id']
  entry={k:obj.get(k) for k in ['id','name','parent_id','instance_id','source_renderer_id','source_transform_id','source_prefab_guid','source_prefab_path','fbx_guid','mesh_file_id','mesh_name','material_guids','asset_id','builtin_mesh','world_matrix_gltf']};entry['position_unity']=mat(obj['world_matrix_unity'])[:3,3].tolist();entry['gltf_node_index']=ni;draw.append(entry)
  for prim in doc['meshes'][native['mesh']]['primitives']:triangle_total+=doc['accessors'][prim['indices']]['count']//3 if 'indices' in prim else doc['accessors'][prim['attributes']['POSITION']]['count']//3
 doc['scenes'][0]['name']=layout['name'];doc['scenes'][0]['extras']={'source_scene_guid':layout['source']['guid'],'source_sha256':layout['source']['sha256'],'layout_json':'layout.json','static_draw_objects':len(draw),'source_transforms_preserved':True,'unported_effects':'Particle systems, wind, source sky/postprocessing and custom Unity shader behavior are metadata, not runtime effects.'}
 src_cam=source_camera(layout);ci=len(doc['nodes']);doc['cameras']=[{'name':'Original source camera','type':'perspective','perspective':{'yfov':math.radians(src_cam['fov']),'znear':src_cam['near'],'zfar':src_cam['far']}}];doc['nodes'].append({'name':'Original source camera / forward adapted','matrix':src_cam['matrix_gltf'],'camera':0,'extras':{'source_component_id':src_cam['source_component_id'],'camera_forward_adapted':True}});doc['scenes'][0]['nodes'].append(ci);merger.write()
 # Public hierarchy excludes verbose raw Unity component blobs, never transforms or visible static objects.
 public_groups=[{k:g.get(k) for k in ['id','parent_id','name','instance_id','source_transform_id','local_position_unity','local_rotation_unity','local_scale_unity','local_matrix_gltf','active_in_hierarchy']} for g in groups.values()]
 rootgroups=[g for g in groups.values() if g['parent_id'] is None and g['id'] in group_boxes];rootgroups.sort(key=lambda g:(group_boxes[g['id']][0][0],g['name']))
 particle_objects=[o for o in layout['objects'] if o['type']=='ParticleSystemRenderer'];fx=[{'id':o['id'],'parent_id':o['parent_id'],'name':o['name'],'instance_id':o['instance_id'],'source_prefab_guid':o.get('source_prefab_guid'),'world_matrix_gltf':o['world_matrix_gltf'],'status':'Original effect anchor preserved; Unity particle behavior is not ported.'} for o in particle_objects]
 public={'schema_version':1,'id':sid,'name':layout['name'],'source':layout['source'],'coordinate_contract':layout['coordinate_contract'],'groups':public_groups,'objects':draw,'effect_anchors':fx,'source_camera':src_cam,'source_lights':layout['lights'],'source_counts':layout['source_counts'],'unresolved':layout['unresolved'],'limitations':layout['limitations'],'runtime_scope':'All retained authored static meshes and original hierarchy; no procedural scatter or placement offsets.'}
 save(out/'layout.json',public)
 views=[view_box('complete-layout','Complete authored layout',total_box,2.0),src_cam];chunks=[]
 for j,g in enumerate(rootgroups):
  ancestor_ids=set();members=[]
  for o in draw:
   x=o['parent_id'];chain=[]
   while x:chain.append(x);x=groups[x]['parent_id']
   if g['id'] in chain:members.append(o);ancestor_ids.update(chain[:chain.index(g['id'])+1])
  slug=f'{j+1:02d}_'+safe(g['name']);chunk_path=f'scenes/{sid}/groups/{slug}.json';chunk={'schema_version':1,'scene':sid,'group_id':g['id'],'name':g['name'],'coordinate_contract':layout['coordinate_contract'],'source':layout['source'],'groups':[v for v in public_groups if v['id'] in ancestor_ids],'objects':members,'object_count':len(members)};save(repo/chunk_path,chunk)
  b=group_boxes[g['id']];chunks.append({'id':g['id'],'name':g['name'],'object_count':len(members),'path':chunk_path,'bounds':{'min':b[0].tolist(),'max':b[1].tolist()}});views.append(view_box(slug,g['name']+' / authored group',b,2.0))
 light=next(l for l in layout['lights'] if l['enabled']);lu=mat(light['world_matrix_unity']);H=mat(layout['coordinate_contract']['unity_to_gltf_basis']);ld=(H@lu@np.array([0,0,1,0]))[:3];props=light['properties'];lightdata={'color':[props['m_Color'][k] for k in ['r','g','b']],'intensity':props['m_Intensity'],'direction':ld.tolist(),'scope':'Source directional values; sky, indirect light and postprocessing remain portable-preview approximations.'}
 source_counts=layout['source_counts'];summary={'schema_version':1,'id':sid,'name':layout['name'],'source':layout['source'],'source_counts':source_counts,'static_objects':len(draw),'library_assets_used':len(used),'triangle_instances':triangle_total,'groups':chunks,'source_camera':src_cam,'bounds':{'min':total_box[0].tolist(),'max':total_box[1].tolist()},'effect_anchor_count':len(fx),'unresolved':layout['unresolved'],'limitations':layout['limitations']};save(out/'summary.json',summary)
 record={'id':sid,'name':layout['name'],'model':f'scenes/{sid}/scene.gltf','layout':f'scenes/{sid}/layout.json','summary':f'scenes/{sid}/summary.json','groups':chunks,'bounds':summary['bounds'],'views':views,'light':lightdata,'static_objects':len(draw),'effect_anchor_count':len(fx),'library_assets_used':len(used),'previews':[]};index['scenes'].append(record)
 reports.append({'id':sid,'source_counts':source_counts,'draw_objects':len(draw),'gltf_nodes':len(doc['nodes']),'unique_meshes':len(doc['meshes']),'unique_materials':len(doc['materials']),'triangles':triangle_total,'gltf_bytes':target.stat().st_size,'layout_bytes':(out/'layout.json').stat().st_size,'bounds':summary['bounds'],'group_names':[g['name'] for g in chunks]})
save(repo/'scenes/index.json',index);save(work/'audit/scene_assembly.json',{'scenes':reports});print(json.dumps(reports),flush=True)
