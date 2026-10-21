import sys,json,gzip,tarfile,hashlib
from pathlib import Path,PurePosixPath
work=Path(sys.argv[1]);package=Path(sys.argv[2]);index=json.loads((work/'audit/source_index.json').read_text());root=work/'cache/source';root.mkdir(parents=True,exist_ok=True)
selected={};records=[];allowed={'.fbx','.obj','.tif','.tiff','.png','.jpg','.tga','.mat','.prefab','.asset','.terrainlayer','.unity','.shader','.txt'}
for e in index['entries']:
 p=PurePosixPath(e['path'])
 if not e.get('asset_member') or p.suffix.lower() not in allowed:continue
 assert not p.is_absolute() and '..' not in p.parts
 rel=Path(*p.parts[1:]);r=dict(e);r['relative_path']=rel.as_posix();records.append(r);selected[e['asset_member']]=(root/rel,r,'sha256')
 if e.get('meta_member'):selected[e['meta_member']]=(Path(str(root/rel)+'.meta'),r,'meta_sha256')
count=0
with gzip.open(package,'rb') as g,tarfile.open(fileobj=g,mode='r|') as t:
 for m in t:
  if m.name not in selected:continue
  dest,r,key=selected[m.name];dest.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256()
  with t.extractfile(m) as inp,open(dest,'wb') as out:
   for b in iter(lambda:inp.read(1024*1024),b''):out.write(b);h.update(b)
  r[key]=h.hexdigest();count+=1
  if count%200==0:print(json.dumps({'members':count}),flush=True)
assert all('sha256' in r for r in records)
(work/'audit/extracted_source.json').write_text(json.dumps({'source_package':package.name,'source_variant':'Built-in','assets':records},indent=2),encoding='utf-8')
print(json.dumps({'complete':True,'assets':len(records),'members':count}),flush=True)
