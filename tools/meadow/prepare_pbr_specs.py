"""Bake supported static shader inputs into portable glTF metallic/roughness textures."""
import sys,json,hashlib,re
from pathlib import Path
import numpy as np
from PIL import Image
work=Path(sys.argv[1]);mapping=json.loads((work/'audit/unity_mapping.json').read_text());textures=json.loads((work/'audit/web_textures.json').read_text());root=work/'cache/web_textures';out=work/'cache/pbr';out.mkdir(parents=True,exist_ok=True);result={}
def choose(m,keys):
 active=set(m.get('active_properties',[]))
 for key in keys:
  t=m['textures'].get(key,{})
  if (key in active or not m.get('shader_guid')) and t.get('guid') in textures:return key,t
 return None,None
def actual(t):return root/textures[t['guid']]['path'] if t else None
def linear(a):return np.where(a<=0.04045,a/12.92,((a+0.055)/1.055)**2.4)
def srgb(a):return np.where(a<=0.0031308,a*12.92,1.055*np.maximum(a,0)**(1/2.4)-0.055)
for guid,m in mapping['materials'].items():
 f=m['floats'];c=m['colors'];active=set(m.get('active_properties',[]));bk,base=choose(m,['_BaseAlbedo','_Albedo','_MainTex']);nk,normal=choose(m,['_BaseNormal','_BumpMap']);dk,data=choose(m,['_BaseSMAE','_BaseSSE','_BaseSMA','_SMAE']);base_path=None;alpha_mode='OPAQUE';orm_path=None;emission_path=None;used=[k for k,v in [(bk,base),(nk,normal),(dk,data)] if v]
 if base:
  with Image.open(actual(base)) as image:
   arr=np.asarray(image.convert('RGBA'),dtype=np.float32)/255;rgb=linear(arr[:,:,:3]);color=c.get('_BaseAlbedoColor',c.get('_Color',{'r':0.5,'g':0.5,'b':0.5}));blend=np.array([color.get(k,0.5) for k in ['r','g','b']],dtype=np.float32)
   desat=np.clip(f.get('_BaseAlbedoDesaturation',0),0,1);gray=np.sum(rgb*np.array([0.299,0.587,0.114]),axis=2,keepdims=True);sample=(rgb*(1-desat)+gray*desat)*f.get('_BaseAlbedoBrightness',1)
   overlay=np.clip(np.where(blend>0.5,1-2*(1-blend)*(1-sample),2*blend*sample),0,1);mix=np.clip(f.get('_BaseLerpBetweenColorandTexture',1),0,1) if '_BaseLerpBetweenColorandTexture' in active else 1;rgb=blend*(1-mix)+overlay*mix;arr[:,:,:3]=np.clip(srgb(np.maximum(rgb,0)),0,1)
   alpha=arr[:,:,3].min()<0.999;alpha_mode='MASK' if alpha and ('_OpacityCutoff' in active or '_Cutoff' in active or '_CutOff' in active or '/Leaves/' in m['source'] or '/Plants/' in m['source'] or '/Grass/' in m['source'] or '/Flowers/' in m['source']) else 'OPAQUE'
   base_path=out/(guid+('.png' if alpha_mode=='MASK' else '.jpg'));pixels=Image.fromarray(np.uint8(np.clip(arr*255+0.5,0,255)),'RGBA')
   if base_path.suffix=='.jpg':pixels.convert('RGB').save(base_path,quality=92,subsampling=0,optimize=True)
   else:pixels.save(base_path,compress_level=3)
 if data:
  with Image.open(actual(data)) as image:
   d=np.asarray(image.convert('RGBA'),dtype=np.float32)/255;leaf=dk=='_BaseSSE';s0=f.get('_BaseSmoothnessMin',0);s1=f.get('_BaseSmoothnessMax',1);rough=1-np.clip(s0+(s1-s0)*d[:,:,0],0,1);metal=np.zeros_like(rough) if leaf else np.clip(d[:,:,1]*f.get('_BaseMetallicIntensity',0),0,1);aostrength=f.get('_BaseAOIntensity',f.get('_BaseBarkAOIntensity',0));ao=np.ones_like(rough) if leaf else np.clip(1+(d[:,:,2]-1)*aostrength,0,1);orm=np.stack([ao,rough,metal],axis=2);orm_path=out/(guid+'_orm.png');Image.fromarray(np.uint8(orm*255+0.5),'RGB').save(orm_path,compress_level=3)
   emission=c.get('_BaseEmissiveColor',{});ef=np.array([emission.get(k,0) for k in ['r','g','b']]);strength=f.get('_BaseEmissiveIntensity',0)
   if ef.max()>0 and strength>0:
    mask=d[:,:,2] if leaf else d[:,:,3];mask=np.clip((mask-0.5)*f.get('_BaseEmissiveMaskContrast',1)+0.5,0,1);emit=srgb(mask[:,:,None]*np.clip(ef,0,1));emission_path=out/(guid+'_emission.png');Image.fromarray(np.uint8(np.clip(emit,0,1)*255+0.5),'RGB').save(emission_path,compress_level=3)
 t=base or {};scale=t.get('scale',{'x':1,'y':1});offset=t.get('offset',{'x':0,'y':0});not_ported=[k for k in ['_EnableWind','_EnableTopLayerBlend','_EnableBottomColor','_EnableTintColor','_EnableTintVariationColor'] if k in active and f.get(k,0)>0.5]
 result[guid]={'name':m['name'],'source':m['source'],'base':str(base_path) if base_path else None,'normal':str(actual(normal)) if normal else None,'orm':str(orm_path) if orm_path else None,'factor':[1,1,1,1],'normal_scale':max(0,float(f.get('_BaseNormalIntensity',f.get('_BumpScale',1)))),'roughness':1 if data else float(np.clip(1-f.get('_SmoothnessIntensity',f.get('_Glossiness',0.25)),0,1)),'metallic':1 if data else 0,'alpha_mode':alpha_mode,'alpha_cutoff':float(np.clip(f.get('_OpacityCutoff',f.get('_Cutoff',f.get('_CutOff',0.5))),0,1)),'uv_scale':[scale.get('x',1),scale.get('y',1)],'uv_offset':[offset.get('x',0),offset.get('y',0)],'emission':str(emission_path) if emission_path else None,'emission_strength':float(f.get('_BaseEmissiveIntensity',1)),'mapped_texture_slots':used,'unported_shader_controls':not_ported}
(work/'audit/pbr_specs.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'materials':len(result),'textured':sum(bool(m['base']) for m in result.values()),'masked':sum(m['alpha_mode']=='MASK' for m in result.values()),'emissive':sum(bool(m['emission']) for m in result.values())}),flush=True)
