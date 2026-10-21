"""Create small, read-only placement pages for text-based composition inspection."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True,type=Path);a=p.parse_args();repo=a.repo.resolve();index_path=repo/'scenes/index.json';index=json.loads(index_path.read_text())
pages=0
for scene in index['scenes']:
 for group in scene['groups']:
  full=json.loads((repo/group['path']).read_text());items=full['objects'];refs=[]
  for offset in range(0,len(items),24):
   path=Path(group['path']).with_suffix('')/('placements-%02d.json'%(offset//24+1));selected=[]
   for o in items[offset:offset+24]:
    selected.append({k:o.get(k) for k in ['source_renderer_id','instance_id','name','asset_id','builtin_mesh','material_guids','position_unity','world_matrix_gltf','gltf_node_index'] if o.get(k) is not None})
   data={'schema_version':1,'scene':scene['id'],'group_id':group['id'],'name':group['name'],'read_only_placement_summary':True,'complete_group_json':group['path'],'scene_model':scene['model'],'coordinate_contract':full['coordinate_contract'],'instructions':'Read these pages to understand composition. Load scene.gltf for the actual hierarchy; never reapply these world matrices on top of the assembled model. Source IDs are decimal strings.','offset':offset,'total_group_objects':len(items),'object_count':len(selected),'objects':selected}
   target=repo/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(data,separators=(',',':'))+'\n',encoding='utf-8');refs.append({'path':path.as_posix(),'object_count':len(selected)});pages+=1
  group['placement_pages']=refs
 summary_path=repo/scene['summary'];summary=json.loads(summary_path.read_text());summary['groups']=scene['groups'];summary_path.write_text(json.dumps(summary,separators=(',',':'))+'\n',encoding='utf-8')
index_path.write_text(json.dumps(index,separators=(',',':'))+'\n',encoding='utf-8');print(json.dumps({'pages':pages,'maximum_objects_per_page':24}))
