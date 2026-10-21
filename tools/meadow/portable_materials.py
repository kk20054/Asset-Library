"""Build portable materials from inspected Unity assignments; source files remain untouched."""
import bpy,re
from pathlib import Path
class MaterialFactory:
 def __init__(self,specs):self.specs=specs;self.cache={};self.images={};self.missing=[]
 def image(self,path,data=False):
  key=(path,data)
  if key not in self.images:
   im=bpy.data.images.load(path,check_existing=False);im.colorspace_settings.name='Non-Color' if data else 'sRGB';self.images[key]=im
  return self.images[key]
 def make(self,guid,fallback='Unassigned'):
  if guid in self.cache:return self.cache[guid]
  s=self.specs.get(guid)
  if s is None:
   self.missing.append(fallback);m=bpy.data.materials.new(fallback+'_fallback');m.diffuse_color=(.6,.6,.6,1);m.use_nodes=True;return m
  m=bpy.data.materials.new(s['name']);m.use_nodes=True;m['unity_material_guid']=guid;m['source_path']=s['source'];m['portable_alpha_mode']=s['alpha_mode'];m['portable_alpha_cutoff']=s['alpha_cutoff']
  nodes=m.node_tree.nodes;links=m.node_tree.links;bs=nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=s['factor'];bs.inputs['Roughness'].default_value=s['roughness'];bs.inputs['Metallic'].default_value=s['metallic'];bs.inputs['Alpha'].default_value=s['factor'][3]
  coords=nodes.new('ShaderNodeTexCoord');mapping=nodes.new('ShaderNodeMapping');mapping.inputs['Scale'].default_value=(s['uv_scale'][0],s['uv_scale'][1],1);mapping.inputs['Location'].default_value=(s['uv_offset'][0],s['uv_offset'][1],0);links.new(coords.outputs['UV'],mapping.inputs['Vector'])
  def tex(path,data=False):
   n=nodes.new('ShaderNodeTexImage');n.image=self.image(path,data);links.new(mapping.outputs['Vector'],n.inputs['Vector']);return n
  if s['base']:
   n=tex(s['base']);links.new(n.outputs['Color'],bs.inputs['Base Color'])
   if s['alpha_mode']!='OPAQUE':links.new(n.outputs['Alpha'],bs.inputs['Alpha'])
  if s['normal']:
   n=tex(s['normal'],True);nm=nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=s['normal_scale'];links.new(n.outputs['Color'],nm.inputs['Color']);links.new(nm.outputs['Normal'],bs.inputs['Normal'])
  if s['orm']:
   n=tex(s['orm'],True);sep=nodes.new('ShaderNodeSeparateColor');links.new(n.outputs['Color'],sep.inputs['Color']);links.new(sep.outputs['Green'],bs.inputs['Roughness']);links.new(sep.outputs['Blue'],bs.inputs['Metallic'])
  if s.get('emission'):
   n=tex(s['emission']);links.new(n.outputs['Color'],bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=1
  if s['alpha_mode']!='OPAQUE':m.surface_render_method='DITHERED'
  m.use_backface_culling=False;self.cache[guid]=m;return m

def patch_material_metadata(gltf,specs):
 for mat in gltf.get('materials',[]):
  guid=mat.get('extras',{}).get('unity_material_guid');s=specs.get(guid)
  if not s:continue
  mat['alphaMode']=s['alpha_mode'];mat['doubleSided']=True
  if s['alpha_mode']=='MASK':mat['alphaCutoff']=s['alpha_cutoff']
  pbr=mat.get('pbrMetallicRoughness',{});pbr['baseColorFactor']=s['factor']
  if s['orm'] and 'metallicRoughnessTexture' in pbr:mat['occlusionTexture']=dict(pbr['metallicRoughnessTexture'])
