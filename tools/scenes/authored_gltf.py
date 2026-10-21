"""Compose portable glTF resources without altering authoring geometry or source bytes."""
import copy,json,os,hashlib,struct
from pathlib import Path
import numpy as np

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'))
def matrix_node(node):
 if 'matrix' in node:return np.array(node['matrix'],dtype=float).reshape((4,4),order='F')
 x,y,z,w=node.get('rotation',[0,0,0,1]);length=(x*x+y*y+z*z+w*w)**.5;x,y,z,w=x/length,y/length,z/length,w/length
 r=np.array([[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w],[2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w],[2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]])
 m=np.eye(4);m[:3,:3]=r@np.diag(node.get('scale',[1,1,1]));m[:3,3]=node.get('translation',[0,0,0]);return m

class ResourceMerger:
 def __init__(self,repo,target):
  self.repo=Path(repo);self.target=Path(target);self.doc={'asset':{'version':'2.0','generator':'Authored Unity scene layout conversion / shared Meadow glTF'},'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],'materials':[],'textures':[],'images':[],'samplers':[],'buffers':[],'bufferViews':[],'accessors':[]};self.cache={};self.tables={};self.assets={};self.material_sources={};self.material_guids={};self.meshes={}
  manifest=json.loads((self.repo/'manifest.json').read_text())
  for a in manifest['assets']:
   if a.get('collection')!='meadow':continue
   self.assets[a['id']]=a
   g=json.loads((self.repo/a['path']).read_text())
   for i,m in enumerate(g.get('materials',[])):
    guid=m.get('extras',{}).get('unity_material_guid')
    if guid:self.material_sources.setdefault(guid,(a,i))
 def add(self,key,value):
  signature=canonical(value);table=self.tables.setdefault(key,{})
  if signature not in table:table[signature]=len(self.doc[key]);self.doc[key].append(value)
  return table[signature]
 def dependency_uri(self,src,uri):
  p=(src.parent/uri).resolve()
  if not p.is_relative_to(self.repo.resolve()):raise ValueError('A dependency escapes repository')
  if not p.is_file():raise FileNotFoundError(p)
  return os.path.relpath(p,self.target.parent).replace('\\','/')
 def import_asset(self,asset):
  if asset['id'] in self.cache:return self.cache[asset['id']]
  src=self.repo/asset['path'];g=json.loads(src.read_text());maps={}
  if g.get('skins') or g.get('animations'):raise ValueError('Expected static library asset')
  for key in ['buffers','bufferViews','accessors','samplers','images','textures','materials','meshes']:
   maps[key]={}
   for i,entry in enumerate(g.get(key,[])):
    v=copy.deepcopy(entry)
    if key in ['buffers','images'] and 'uri' in v:v['uri']=self.dependency_uri(src,v['uri'])
    if key=='bufferViews':v['buffer']=maps['buffers'][v['buffer']]
    if key=='accessors':
     if 'bufferView' in v:v['bufferView']=maps['bufferViews'][v['bufferView']]
     if 'sparse' in v:
      for n in ['indices','values']:v['sparse'][n]['bufferView']=maps['bufferViews'][v['sparse'][n]['bufferView']]
    if key=='images' and 'bufferView' in v:v['bufferView']=maps['bufferViews'][v['bufferView']]
    if key=='textures':
     if 'source' in v:v['source']=maps['images'][v['source']]
     if 'sampler' in v:v['sampler']=maps['samplers'][v['sampler']]
     if v.get('extensions'):raise ValueError('Compressed texture extensions need explicit remapping')
    if key=='materials':
     def texture_infos(d):
      if not isinstance(d,dict):return
      for k,value in d.items():
       if k.endswith('Texture') and isinstance(value,dict) and 'index' in value:value['index']=maps['textures'][value['index']]
       else:texture_infos(value)
     texture_infos(v)
    if key=='meshes':
     for p in v['primitives']:
      p['attributes']={k:maps['accessors'][n] for k,n in p['attributes'].items()}
      if 'indices' in p:p['indices']=maps['accessors'][p['indices']]
      if 'material' in p:p['material']=maps['materials'][p['material']]
      if p.get('targets') or p.get('extensions'):raise ValueError('Unexpected morph/compressed primitive')
    maps[key][i]=self.add(key,v)
    if key=='materials':
     guid=v.get('extras',{}).get('unity_material_guid')
     if guid:self.material_guids.setdefault(guid,maps[key][i])
  for ext in g.get('extensionsUsed',[]):
   self.doc.setdefault('extensionsUsed',[])
   if ext not in self.doc['extensionsUsed']:self.doc['extensionsUsed'].append(ext)
  mesh_nodes=[n for n in g['nodes'] if 'mesh' in n]
  if len(mesh_nodes)!=1:raise ValueError('Library contract requires one mesh node per asset')
  n=copy.deepcopy(mesh_nodes[0]);n['mesh']=maps['meshes'][n['mesh']];n.pop('children',None)
  self.cache[asset['id']]=(n,maps);return n,maps
 def material(self,guid,source_materials):
  if guid in self.material_guids:return self.material_guids[guid]
  if guid in self.material_sources:
   asset,i=self.material_sources[guid];self.import_asset(asset);return self.material_guids[guid]
  s=source_materials.get(guid)
  if not s:raise ValueError('No verified material for '+str(guid))
  if any(t.get('guid') for t in s.get('textures',{}).values()):raise ValueError('Material texture conversion is missing: '+s['name'])
  c=s.get('colors',{}).get('_Color',s.get('colors',{}).get('_BaseColor',{}));f=s.get('floats',{})
  v={'name':s['name'],'pbrMetallicRoughness':{'baseColorFactor':[float(c.get(k,1)) for k in ['r','g','b','a']],'metallicFactor':float(f.get('_Metallic',0)),'roughnessFactor':1-float(f.get('_Glossiness',0))},'extras':{'unity_material_guid':guid,'source_path':s['source'],'portable_interpretation':'Serialized built-in material color; static PBR approximation.'}}
  idx=self.add('materials',v);self.material_guids[guid]=idx;return idx
 def model_node(self,asset_id,materials,source_materials):
  native,_=self.import_asset(self.assets[asset_id]);native=copy.deepcopy(native)
  primitives=self.doc['meshes'][native['mesh']]['primitives']
  actual=[self.doc['materials'][p['material']].get('extras',{}).get('unity_material_guid') for p in primitives]
  if sorted(actual)!=sorted(materials):raise ValueError('Selected library asset does not exactly match source renderer materials')
  return native
 def cube_node(self,material,source_materials):
  dest=self.repo/'scenes/_shared/unit-cube.bin';dest.parent.mkdir(parents=True,exist_ok=True)
  faces=[([0,0,1],[[-.5,-.5,.5],[.5,-.5,.5],[.5,.5,.5],[-.5,.5,.5]]),([0,0,-1],[[.5,-.5,-.5],[-.5,-.5,-.5],[-.5,.5,-.5],[.5,.5,-.5]]),([1,0,0],[[.5,-.5,.5],[.5,-.5,-.5],[.5,.5,-.5],[.5,.5,.5]]),([-1,0,0],[[-.5,-.5,-.5],[-.5,-.5,.5],[-.5,.5,.5],[-.5,.5,-.5]]),([0,1,0],[[-.5,.5,.5],[.5,.5,.5],[.5,.5,-.5],[-.5,.5,-.5]]),([0,-1,0],[[-.5,-.5,-.5],[.5,-.5,-.5],[.5,-.5,.5],[-.5,-.5,.5]])]
  positions=[p for normal,points in faces for p in points];normals=[n for n,pts in faces for p in pts];indices=[i*4+j for i in range(6) for j in [0,1,2,0,2,3]]
  raw=struct.pack('<72f',*(x for p in positions for x in p))+struct.pack('<72f',*(x for n in normals for x in n))+struct.pack('<36H',*indices);dest.write_bytes(raw)
  bi=self.add('buffers',{'uri':os.path.relpath(dest,self.target.parent).replace('\\','/'),'byteLength':len(raw)});views=[]
  for off,length,target in [(0,288,34962),(288,288,34962),(576,72,34963)]:views.append(self.add('bufferViews',{'buffer':bi,'byteOffset':off,'byteLength':length,'target':target}))
  pos=self.add('accessors',{'bufferView':views[0],'componentType':5126,'count':24,'type':'VEC3','min':[-.5,-.5,-.5],'max':[.5,.5,.5]});normal=self.add('accessors',{'bufferView':views[1],'componentType':5126,'count':24,'type':'VEC3'});ind=self.add('accessors',{'bufferView':views[2],'componentType':5123,'count':36,'type':'SCALAR'})
  mi=self.add('meshes',{'name':'Unity built-in Cube (unit dimensions)','primitives':[{'attributes':{'POSITION':pos,'NORMAL':normal},'indices':ind,'material':self.material(material,source_materials)}]});return {'mesh':mi,'name':'Unity Cube / source built-in mesh 10202'}
 def write(self):
  self.target.parent.mkdir(parents=True,exist_ok=True)
  for key in list(self.doc):
   if isinstance(self.doc[key],list) and not self.doc[key]:del self.doc[key]
  self.target.write_text(json.dumps(self.doc,separators=(',',':')),encoding='utf-8',newline='\n')
