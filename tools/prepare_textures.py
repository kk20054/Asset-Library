import sys,json,hashlib,re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
work=Path(sys.argv[1]);src=json.loads((work/'audit/extracted_source.json').read_text(encoding='utf-8'));out=work/'cache/web_textures';out.mkdir(parents=True,exist_ok=True)
def run(e):
 p=work/'cache/source'/e['relative_path'];name=p.stem
 role='normal' if re.search(r'_N$',name,re.I) else 'orm' if re.search(r'_ORM$',name,re.I) else 'mask' if re.search(r'_(OP|R|Mask|Masks|M|Opacity)$',name,re.I) else 'color'
 limit=2048 if role=='color' else 1024
 with Image.open(p) as im:
  original=list(im.size);im.thumbnail((limit,limit),Image.Resampling.LANCZOS)
  has_alpha=im.mode=='RGBA' and im.getchannel('A').getextrema()[0]<255
  if role=='color' and not has_alpha:
   dest=out/(e['guid']+'.jpg');im.convert('RGB').save(dest,'JPEG',quality=92,subsampling=0,optimize=True)
  else:
   dest=out/(e['guid']+'.png');im.save(dest,'PNG',compress_level=3)
  return e['guid'],{'path':dest.name,'source':e['path'],'source_sha256':e['sha256'],'original_dimensions':original,'dimensions':list(im.size),'role':role,'has_alpha':has_alpha,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
entries=[e for e in src['assets'] if Path(e['path']).suffix.lower()=='.png']
with ThreadPoolExecutor(max_workers=4) as pool:results=dict(pool.map(run,entries))
(work/'audit/web_textures.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps({'complete':True,'texture_count':len(results),'bytes':sum(e['bytes'] for e in results.values()),'color_max_dimension':2048,'data_max_dimension':1024}),flush=True)
