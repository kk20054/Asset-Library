import json,sys,re,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from io import BytesIO
import numpy as np
sys.path.insert(0,str(Path(__file__).parent/'_deps'))
import tifffile
work=Path(sys.argv[1]);source=json.loads((work/'audit/extracted_source.json').read_text());dest=work/'cache/web_textures';dest.mkdir(parents=True,exist_ok=True)
def convert(e):
 p=work/'cache/source'/e['relative_path'];name=p.stem;role='normal' if re.search(r'_N(?:_\d+)?$',name,re.I) else 'data' if re.search(r'_(SMAE?|SSE|RMAE?|ORM|AO|MAO)(?:_\d+)?$',name,re.I) else 'color';limit=2048 if role=='color' else 1024
 recovered=False
 if p.suffix.lower() in {'.tif','.tiff'}:
  with tifffile.TiffFile(p) as tf:
   page=tf.pages[0];samples=page.samplesperpixel;array=page.asarray();recovered=samples==4 and tuple(int(x) for x in page.extrasamples)==(0,)
  if array.ndim==3 and array.shape[-1] in {3,4}:
   if array.dtype==np.uint16:array=np.uint8(np.round(array.astype(np.float32)/257))
   if array.dtype!=np.uint8:raise ValueError('Unsupported TIFF sample type: '+str(array.dtype))
   source_image=Image.fromarray(array)
  else:source_image=Image.open(p)
 else:source_image=Image.open(p)
 with source_image as im:
  original=list(im.size);im=im.convert('RGBA');im.thumbnail((limit,limit),Image.Resampling.LANCZOS);alpha=im.getchannel('A').getextrema()[0]<255
  target=dest/(e['guid']+('.jpg' if role=='color' and not alpha else '.png'))
  if target.suffix=='.jpg':im.convert('RGB').save(target,quality=92,subsampling=0,optimize=True)
  else:im.save(target,'PNG',compress_level=3)
  return e['guid'],{'path':target.name,'source':e['path'],'role':role,'original_dimensions':original,'dimensions':list(im.size),'has_alpha':alpha,'source_tiff_extra_alpha_recovered':recovered,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
entries=[e for e in source['assets'] if Path(e['path']).suffix.lower() in {'.tif','.tiff','.png','.jpg','.tga'}]
with ThreadPoolExecutor(max_workers=4) as pool:out=dict(pool.map(convert,entries))
(work/'audit/web_textures.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps({'complete':True,'textures':len(out),'bytes':sum(i['bytes'] for i in out.values())}),flush=True)
