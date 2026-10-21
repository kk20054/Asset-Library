"""Index actual rendered PNGs with hashes for anonymous Claude/browser access."""
import argparse,hashlib,json,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True,type=Path);a=p.parse_args();repo=a.repo.resolve();index_path=repo/'scenes/index.json';index=json.loads(index_path.read_text())
for scene in index['scenes']:
 records=[]
 for view in scene['views']:
  path=repo/'scenes'/scene['id']/'previews'/(view['id']+'.png');raw=path.read_bytes()
  if raw[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Invalid PNG: '+str(path))
  width,height=struct.unpack('>II',raw[16:24])
  if (width,height)!=(1600,900):raise ValueError('Unexpected reference size')
  records.append({'path':path.relative_to(repo).as_posix(),'label':view['label'],'view_id':view['id'],'width':width,'height':height,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'caption':'Rendered from converted original author placements with Blender Eevee; portable static PBR, not an original Unity screenshot.'})
 scene['previews']=records
 receipt={'scene_id':scene['id'],'input_scene_sha256':hashlib.sha256((repo/scene['model']).read_bytes()).hexdigest(),'renderer':'Blender 5.2.2 LTS / Eevee','source_camera_preserved':True,'original_unity_capture':False,'previews':records}
 (repo/'scenes'/scene['id']/'preview-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
index_path.write_text(json.dumps(index,separators=(',',':'))+'\n',encoding='utf-8');print(json.dumps({'scenes':len(index['scenes']),'previews':sum(len(s['previews']) for s in index['scenes'])}))
