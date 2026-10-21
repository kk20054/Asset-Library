import json,sys,hashlib
from pathlib import Path
from PIL import Image
work=Path(sys.argv[1]);mapping=json.loads((work/'audit/unity_mapping.json').read_text());textures=json.loads((work/'audit/web_textures.json').read_text());root=work/'cache/web_textures';result={}
def pick(m,names):
 for key in names:
  entry=m['textures'].get(key,{})
  if entry.get('guid') in textures:return key,entry
 return None,None
def file(entry):return str(root/textures[entry['guid']]['path']) if entry else None
for guid,m in mapping['materials'].items():
 bk,base=pick(m,['_BaseMap','_Base_Map','_BaseColorMap','_MainTex'])
 nk,normal=pick(m,['_Normal','_NormalMap','_BumpMap'])
 ok,orm=pick(m,['_ORM'])
 mk,mask=pick(m,['_Opacity_Mask','_OpacityMask'])
 floats=m['floats'];colors=m['colors'];basefile=file(base)
 use_mask=bool(mask and floats.get('_UseOpacityMask',floats.get('_Use_Opacity_Mask',0))>0.5)
 alpha_mode='OPAQUE'
 if base and textures[base['guid']]['has_alpha']:alpha_mode='MASK'
 if use_mask and basefile:
  dest=root/('rgba_'+base['guid']+'_'+mask['guid']+'.png')
  if not dest.exists():
   with Image.open(basefile) as b,Image.open(file(mask)) as a:
    rgba=b.convert('RGBA');alpha=a.convert('RGB').getchannel('R').resize(rgba.size,Image.Resampling.LANCZOS);rgba.putalpha(alpha);rgba.save(dest,'PNG',compress_level=3)
  basefile=str(dest);alpha_mode='MASK'
 color=colors.get('_BaseColor_Value',colors.get('_BaseColor',colors.get('_Color',{'r':1,'g':1,'b':1,'a':1})))
 factor=[max(0,min(1,float(color.get(k,1)))) for k in ['r','g','b','a']]
 if 'water' in m['name'].lower():factor[3]=0.65;alpha_mode='BLEND'
 slot=base or {};scale=slot.get('scale',{'x':1,'y':1});offset=slot.get('offset',{'x':0,'y':0})
 result[guid]={'name':m['name'],'base':basefile,'normal':file(normal),'orm':file(orm),'factor':factor,'normal_scale':max(0,float(floats.get('_Normal_Strength',floats.get('_BumpScale',1)))),'roughness':1 if orm else max(0.05,min(1,float(floats.get('_Roughness',1-floats.get('_Smoothness',0.5))))),'metallic':1 if orm else max(0,min(1,float(floats.get('_Metallic',0)))),'alpha_mode':alpha_mode,'alpha_cutoff':max(0,min(1,float(floats.get('_Alpha_Clip_Treshold',floats.get('_Cutoff',0.5))))),'uv_scale':[scale.get('x',1),scale.get('y',1)],'uv_offset':[offset.get('x',0),offset.get('y',0)],'source':m['source'],'mapped_texture_slots':[k for k,v in [(bk,base),(nk,normal),(ok,orm),(mk,mask if use_mask else None)] if v]}
(work/'audit/pbr_specs.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'materials':len(result),'textured':sum(bool(m['base']) for m in result.values()),'masked':sum(m['alpha_mode']=='MASK' for m in result.values())}))
