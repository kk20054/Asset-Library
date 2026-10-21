"""Render reference PNGs from converted source layouts; never substitute a staged model layout."""
import bpy,sys,json,math,time
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];repo=Path(args[0]);sid=args[1];mode=args[2] if len(args)>2 else 'all';index=json.loads((repo/'scenes/index.json').read_text());record=next(s for s in index['scenes'] if s['id']==sid)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(repo/record['model']))
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1600;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.film_transparent=False
scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast' if 'Medium High Contrast' in [x.name for x in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items] else 'None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
world=bpy.data.worlds.new('Portable reference background');world.use_nodes=True;world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.26,.34,.42,1);world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.7;scene.world=world
light=bpy.data.lights.new('Source directional light approximation','SUN');light.color=record['light']['color'];light.energy=record['light']['intensity'];light.angle=math.radians(10);sun=bpy.data.objects.new('Reference Sun',light);scene.collection.objects.link(sun)
def point(p):return Vector((p[0],-p[2],p[1]))
sun.rotation_euler=point(record['light']['direction']).to_track_quat('-Z','Y').to_euler()
camdata=bpy.data.cameras.new('ReferenceCamera');cam=bpy.data.objects.new('ReferenceCamera',camdata);scene.collection.objects.link(cam);scene.camera=cam;camdata.type='PERSP';camdata.sensor_fit='VERTICAL';camdata.sensor_height=24
views=record['views'];selected=views if mode=='all' else [v for v in views if v['id']==mode]
if not selected:raise ValueError('Unknown reference view '+mode)
out=repo/'scenes'/sid/'previews';out.mkdir(parents=True,exist_ok=True);receipts=[]
for v in selected:
 pos=point(v['position']);target=point(v['target']);cam.location=pos;cam.rotation_euler=(target-pos).to_track_quat('-Z','Y').to_euler()
 if v.get('up'):
  forward=(target-pos).normalized();up=point(v['up']).normalized();right=forward.cross(up).normalized();up=right.cross(forward);from mathutils import Matrix;rotation=Matrix((right,up,-forward)).transposed();cam.rotation_euler=rotation.to_euler()
 camdata.lens=12/math.tan(math.radians(v['fov'])/2);camdata.clip_start=v.get('near',.1);camdata.clip_end=v.get('far',10000);dest=out/(v['id']+'.png');scene.render.filepath=str(dest);start=time.time();bpy.ops.render.render(write_still=True)
 if not dest.is_file() or dest.stat().st_size<1000:raise RuntimeError('Render did not produce a usable PNG')
 receipts.append({'view':v['id'],'path':dest.relative_to(repo).as_posix(),'bytes':dest.stat().st_size,'seconds':time.time()-start,'width':1600,'height':900,'renderer':'Blender 5.2 Eevee','source':'Converted original author layout; portable static PBR reference, not an original Unity capture.'});print('PREVIEW_DONE',json.dumps(receipts[-1]),flush=True)
(repo/'scenes'/sid/'preview-receipt.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8',newline='\n')
