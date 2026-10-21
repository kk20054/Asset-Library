import json,sys,re,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
work=Path(sys.argv[1]);source=json.loads((work/'audit/extracted_source.json').read_text());dest=work/'cache/web_textures';dest.mkdir(parents=True,exist_ok=True)
def convert(e):
 p=work/'cache/source'/e['relative_path'];name=p.stem;role='normal' if re.search(r'_N(?:_\d+)?$',name,re.I) else 'data' if re.search(r'_(SMAE?|SSE|RMAE?|ORM|AO|MAO)(?:_\d+)?$',name,re.I) else 'color';limit=2048 if role=='color' else 1024
 with Image.open(p) as im:
  original=list(im.size);im=im.convert('RGBA');im.thumbnail((limit,limit),Image.Resampling.LANCZOS);alpha=im.getchannel('A').getextrema()[0]<255
  target=dest/(e['guid']+('.jpg' if role=='color' and not alpha else '.png'))
  if target.suffix=='.jpg':im.convert('RGB').save(target,quality=92,subsampling=0,optimize=True)
  else:im.save(target,'PNG',compress_level=3)
  return e['guid'],{'path':target.name,'source':e['path'],'role':role,'original_dimensions':original,'dimensions':list(im.size),'has_alpha':alpha,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
entries=[e for e in source['assets'] if Path(e['path']).suffix.lower() in {'.tif','.tiff','.png','.jpg','.tga'}]
with ThreadPoolExecutor(max_workers=4) as pool:out=dict(pool.map(convert,entries))
(work/'audit/web_textures.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps({'complete':True,'textures':len(out),'bytes':sum(i['bytes'] for i in out.values())}),flush=True)
