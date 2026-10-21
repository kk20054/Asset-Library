#!/usr/bin/env python3
"""Independently audit foliage TIFF alpha recovery and portable alpha cutoffs.

Only writes audit/foliage_alpha_validation.json. Source assets are read only.
"""
import argparse,hashlib,json,zlib
from pathlib import Path
import numpy as np
from PIL import Image

def read_json(p):return json.loads(p.read_text('utf-8-sig'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def decode_tiff_four_samples(path):
 """Independent decoder: raw TIFF strips, Deflate, horizontal Predictor 2."""
 raw=path.read_bytes()
 with Image.open(path) as im:
  t=im.tag_v2;width,height=im.size
  assert t[277]==4 and tuple(t[258])==(8,8,8,8)
  assert t.get(284,1)==1 and t[262]==2
  pieces=[]
  for start,count in zip(t[273],t[279]):
   data=raw[start:start+count]
   if t[259] in (8,32946):data=zlib.decompress(data)
   elif t[259]!=1:raise ValueError('Unsupported source TIFF compression')
   pieces.append(data)
  arr=np.frombuffer(b''.join(pieces),dtype=np.uint8).reshape(height,width,4)
  predictor=t.get(317,1)
  if predictor==2:arr=np.cumsum(arr,axis=1,dtype=np.uint8)
  elif predictor!=1:raise ValueError('Unsupported source TIFF predictor')
  assert t.get(274,1)==1,'Unsupported source TIFF orientation'
  evidence={'source_pillow_mode':im.mode,'samples_per_pixel':4,'bits_per_sample':list(t[258]),
    'extra_samples':list(t.get(338,[])),'compression':t[259],'predictor':predictor,
    'dimensions':[width,height],'source_rgb_matches_pillow':bool(np.array_equal(arr[:,:,:3],np.asarray(im.convert('RGB'))))}
 return arr,evidence,raw

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',required=True,type=Path);args=ap.parse_args();work=args.work.resolve()
 mapping=read_json(work/'audit/unity_mapping.json');index=read_json(work/'audit/source_index.json');extracted=read_json(work/'audit/extracted_source.json');specs=read_json(work/'audit/pbr_specs.json');web=read_json(work/'audit/web_textures.json')
 source_by={a['guid']:a for a in extracted['assets']};inventory={a['guid']:a for a in index['entries']};uses={}
 for guid,mat in mapping['materials'].items():
  if mat.get('shader_name') not in ('ANGRYMESH/Stylized Pack/Grass','ANGRYMESH/Stylized Pack/Tree Leaf'):continue
  if '_BaseAlbedo' not in mat['active_properties']:continue
  tx=mat['textures'].get('_BaseAlbedo',{});tg=tx.get('guid')
  if tg and tg in source_by:uses.setdefault(tg,[]).append((guid,mat))
 textures=[];materials=[];failures=[];decoded={}
 for tg,rows in uses.items():
  source=source_by[tg];path=work/'cache/source'/source['relative_path']
  with Image.open(path) as probe:
   if probe.format!='TIFF' or probe.mode!='RGB' or probe.tag_v2.get(277)!=4 or tuple(probe.tag_v2.get(338,()))!=(0,):continue
  try:
   rgba,evidence,raw=decode_tiff_four_samples(path);alpha=rgba[:,:,3];decoded[tg]=rgba
   meta=Path(str(path)+'.meta');meta_hash=sha(meta.read_bytes());source_hash=sha(raw)
   original_unchanged=source_hash==source['sha256'] and meta_hash==source['meta_sha256'] and len(raw)==inventory[tg]['bytes']
   record={'guid':tg,'source_path':source['path'],'source_sha256':source_hash,'expected_source_sha256':source['sha256'],
     'meta_sha256':meta_hash,'expected_meta_sha256':source['meta_sha256'],'source_unchanged':original_unchanged,
     'independent_raw_decode':evidence,'source_rgba_sha256':sha(rgba.tobytes()),'source_alpha_sha256':sha(alpha.tobytes()),
     'alpha_min':int(alpha.min()),'alpha_max':int(alpha.max()),'alpha_zero_fraction':float(np.mean(alpha==0)),
     'affected_material_count':len(rows),'web':{},'passed':False}
   entry=web[tg];wp=work/'cache/web_textures'/entry['path'];wb=wp.read_bytes()
   with Image.open(wp) as wi:
    wa=np.asarray(wi.convert('RGBA'));web_mode=wi.mode
   record['web']={'path':'cache/web_textures/'+entry['path'],'mode':web_mode,'declared_has_alpha':entry.get('has_alpha'),
     'sha256':sha(wb),'declared_sha256':entry.get('sha256'),'dimensions':[wa.shape[1],wa.shape[0]],
     'rgba_matches_source_raw':bool(wa.shape==rgba.shape and np.array_equal(wa,rgba)),
     'alpha_matches_source_raw':bool(wa.shape==rgba.shape and np.array_equal(wa[:,:,3],alpha)),
     'alpha_sha256':sha(wa[:,:,3].tobytes())}
   record['passed']=bool(original_unchanged and evidence['source_rgb_matches_pillow'] and web_mode=='RGBA' and entry.get('has_alpha') is True and sha(wb)==entry['sha256'] and record['web']['rgba_matches_source_raw'])
   if not record['passed']:failures.append({'source_guid':tg,'reason':'Source integrity or recovered web RGBA check failed'})
   textures.append(record)
   for guid,mat in rows:
    spec=specs[guid];prop='_BaseOpacityCutoff' if mat['shader_name']=='ANGRYMESH/Stylized Pack/Grass' else '_CutOff'
    expected=mat['floats'][prop] if prop in mat['active_properties'] else None
    mr={'guid':guid,'name':mat['name'],'shader_name':mat['shader_name'],'source_texture_guid':tg,
      'expected_cutoff_property':prop,'property_declared_by_active_shader':prop in mat['active_properties'],
      'expected_cutoff':expected,'actual_alpha_mode':spec.get('alpha_mode'),'actual_cutoff':spec.get('alpha_cutoff'),
      'source_bottom_dither':mat['floats'].get('_EnableBottomDither'),'base_path':None,'base_mode':None,'alpha_matches_source_raw':False,'passed':False}
    bp=Path(spec['base']).resolve()
    if not bp.is_relative_to(work):raise ValueError('Portable base texture is outside the work directory')
    mr['base_path']=bp.relative_to(work).as_posix();mr['base_sha256']=sha(bp.read_bytes())
    with Image.open(bp) as bi:
     mr['base_mode']=bi.mode;ba=np.asarray(bi.convert('RGBA'))
    mr['alpha_matches_source_raw']=bool(ba.shape==rgba.shape and np.array_equal(ba[:,:,3],alpha));mr['alpha_sha256']=sha(ba[:,:,3].tobytes())
    mr['passed']=bool(mr['property_declared_by_active_shader'] and expected is not None and spec.get('alpha_mode')=='MASK' and abs(float(spec.get('alpha_cutoff',-1))-float(expected))<1e-9 and mr['base_mode']=='RGBA' and bp.suffix.lower()=='.png' and mr['alpha_matches_source_raw'])
    if not mr['passed']:failures.append({'material_guid':guid,'reason':'Portable alpha mode/cutoff/source alpha mismatch'})
    materials.append(mr)
  except Exception as exc:
   failures.append({'source_guid':tg,'reason':'Audit exception','exception_type':type(exc).__name__})
 summary={'affected_source_textures':len(textures),'affected_materials':len(materials),'source_files_unchanged':sum(t['source_unchanged'] for t in textures),
   'web_rgba_passed':sum(t['passed'] for t in textures),'material_alpha_passed':sum(m['passed'] for m in materials),'failures':len(failures)}
 expected_counts=len(textures)==6 and len(materials)==36
 if not expected_counts:failures.append({'reason':'Expected six affected source TIFFs and 36 source materials; audit may have run before refreshed inputs were ready'})
 summary['failures']=len(failures)
 result={'schema_version':1,'title':'Independent foliage alpha recovery validation','passed':expected_counts and not failures,
   'scope':'Six source RGB TIFFs with four samples and unspecified ExtraSamples=0; all 36 active Grass/Tree Leaf materials referencing them.',
   'method':'Independent raw strip decode and Predictor 2 reversal; no use of the production TIFF alpha-recovery helper.',
   'source_integrity_method':'Actual source TIFF and metadata SHA-256 match extraction evidence; source byte length matches original package inventory.',
   'alpha_contract':'Grass uses _BaseAlbedo.a and active _BaseOpacityCutoff. Tree Leaf uses _BaseAlbedo.a and active _CutOff. Portable PNG alpha must equal the original fourth sample.',
   'summary':summary,'textures':textures,'materials':materials,'failures':failures}
 output=work/'audit/foliage_alpha_validation.json';output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf-8')
 print(json.dumps({'output':'audit/foliage_alpha_validation.json','passed':result['passed'],**summary},ensure_ascii=False))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
