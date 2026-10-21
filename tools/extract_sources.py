import zipfile,tarfile,json,sys,hashlib,shutil,time
from pathlib import Path,PurePosixPath
work=Path(sys.argv[1]);source=Path(sys.argv[2]);index=json.loads((work/'audit/builtin_index.json').read_text(encoding='utf-8'))
root=work/'cache/source';root.mkdir(parents=True,exist_ok=True)
selected={};records=[]
for e in index['assets']:
 p=PurePosixPath(e.get('path',''))
 if p.suffix.lower() not in {'.fbx','.png','.jpg','.jpeg','.tga','.mat','.prefab','.unity','.shadergraph','.txt'}:continue
 assert not p.is_absolute() and '..' not in p.parts
 rel=Path(*p.parts[4:])
 record=dict(e);record['relative_path']=rel.as_posix();records.append(record)
 selected[e['asset_member']]=(root/rel,record,'sha256')
 if e.get('meta_member'):selected[e['meta_member']]=(Path(str(root/rel)+'.meta'),record,'meta_sha256')
count=0
with zipfile.ZipFile(source) as z:
 name=next(n for n in z.namelist() if n.lower().endswith('.unitypackage'))
 with z.open(name) as stream,tarfile.open(fileobj=stream,mode='r|gz') as outer:
  for m in outer:
   if m.name.endswith('/asset') and m.size>1000000000:
    with tarfile.open(fileobj=outer.extractfile(m),mode='r|gz') as inner:
     for im in inner:
      if im.name not in selected:continue
      dest,record,field=selected[im.name];dest.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256()
      with inner.extractfile(im) as inp,open(dest,'wb') as out:
       for b in iter(lambda:inp.read(1024*1024),b''):out.write(b);h.update(b)
      record[field]=h.hexdigest();count+=1
      if count%100==0:print(json.dumps({'extracted_members':count}),flush=True)
    break
assert all('sha256' in e and 'meta_sha256' in e for e in records)
report={'source_zip':source.name,'source_variant':'Built-in','source_root':'Assets/Stylarts/Stylized Chinese Lost Temple','asset_count':len(records),'assets':records}
(work/'audit/extracted_source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'complete':True,'asset_count':len(records),'member_count':count}),flush=True)
