"""Blender 4.5: editable armatures, foot targets and baked mesh animation.

Run with Blender --background --python build_blender.py. Re-export edits with
Blender --background companions.blend --python build_blender.py -- --export-only.
The app plays the evaluated Blender mesh; it does not run its own leg solver.
"""
import bpy,math,json,gzip,sys,os
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
CLIPS={'idle':(1,60),'walk':(81,60),'happy':(161,60)}

def smooth(t):
    t=max(0,min(1,t)); return t*t*(3-2*t)

def foot_path(phase,step):
    phase%=1
    if phase<.5: return step*(.5-2*phase),0.,0.
    t=(phase-.5)*2
    return step*(-.5-t+6*t*t-4*t*t*t),3.0*math.sin(math.pi*t)**2,-.12*math.sin(2*math.pi*t)

def material(path):
    image=bpy.data.images.load(str(path),check_existing=True); image.pack()
    mat=bpy.data.materials.new(path.stem); mat.use_nodes=True
    nodes=mat.node_tree.nodes; nodes.clear()
    texture=nodes.new('ShaderNodeTexImage'); texture.image=image; texture.interpolation='Linear'
    emission=nodes.new('ShaderNodeEmission'); transparent=nodes.new('ShaderNodeBsdfTransparent')
    mix=nodes.new('ShaderNodeMixShader'); output=nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(texture.outputs['Color'],emission.inputs['Color'])
    mat.node_tree.links.new(texture.outputs['Alpha'],mix.inputs[0])
    mat.node_tree.links.new(transparent.outputs[0],mix.inputs[1]); mat.node_tree.links.new(emission.outputs[0],mix.inputs[2])
    mat.node_tree.links.new(mix.outputs[0],output.inputs[0])
    mat.surface_render_method='DITHERED'
    return mat

def mesh_part(model,name,z,collection,armature,leg_index=None):
    w=model['width']; h=model['height']
    if leg_index is None:
        x0,x1,y0,y1=0,w,0,h; cols=8; rows=12
    else:
        hx,hy,fx,fy,_=model['legs'][leg_index]
        # The transparent canvas uses identical coordinates to the app.
        x0,x1,y0,y1=0,w,max(0,hy*h-3),h; cols=4; rows=14
    points=[(x0+(x1-x0)*i/cols,y0+(y1-y0)*j/rows) for j in range(rows+1) for i in range(cols+1)]
    verts=[(x,h-y,z) for x,y in points]; faces=[]
    for j in range(rows):
        for i in range(cols):
            a=j*(cols+1)+i; faces.extend(((a,a+1,a+cols+2),(a,a+cols+2,a+cols+1)))
    mesh=bpy.data.meshes.new(model['id']+'_'+name); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(mesh.name,mesh); collection.objects.link(obj)
    obj.location=armature.location; uv=mesh.uv_layers.new(name='Artwork')
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            x,y=points[mesh.loops[li].vertex_index]; uv.data[li].uv=(x/w,1-y/h)
    obj.data.materials.append(material(ROOT/model['textures'][0 if leg_index is None else leg_index+1]))
    obj['source_xy']=json.dumps(points); obj['model_id']=model['id']; obj['part']=name
    if leg_index is None:
        groups={name:obj.vertex_groups.new(name=name) for name in ('body','head','hand','tail')}
        for index,(x,y) in enumerate(points):
            u=x/w; v=y/h
            head=smooth((.43-v)/.13)
            hand=smooth((u-.57)/.20)*math.exp(-((v-.49)/.13)**2)*(1-head)
            tail=smooth((.33-u)/.18)*math.exp(-((v-.57)/.12)**2)*(1-head)
            remaining=max(0,1-head-hand-tail)
            weights={'body':remaining,'head':head,'hand':hand,'tail':tail}; total=sum(weights.values())
            for name,weight in weights.items():
                if weight>0: groups[name].add([index],weight/total,'REPLACE')
    else:
        prefix=('far','near')[leg_index]; hip_y=hy*h; ankle_y=h-4.0; knee_y=(hip_y+ankle_y)/2
        groups={part:obj.vertex_groups.new(name=prefix+'_'+part) for part in ('thigh','shin','foot')}
        for index,(_,y) in enumerate(points):
            shin=smooth((y-(knee_y-2.5))/5); foot=smooth((y-(ankle_y-2))/3)
            weights={'thigh':1-shin,'shin':shin*(1-foot),'foot':shin*foot}
            for part,weight in weights.items():
                if weight>0: groups[part].add([index],weight,'REPLACE')
    mod=obj.modifiers.new('Blender armature deformation','ARMATURE'); mod.object=armature; mod.use_deform_preserve_volume=True
    return obj

def create_rig(model,index):
    collection=bpy.data.collections.new(model['id']+' · '+model['actor']+' · '+model['outfit']); bpy.context.scene.collection.children.link(collection)
    arm=bpy.data.armatures.new(model['id']+'_skeleton'); rig=bpy.data.objects.new(model['id']+'_Rig',arm); collection.objects.link(rig)
    rig.location=(index%3*145,-(index//3)*125,0); rig.show_in_front=True
    rig['model_id']=model['id']; rig['model_spec']=json.dumps(model,ensure_ascii=False)
    bpy.context.view_layer.objects.active=rig; rig.select_set(True); bpy.ops.object.mode_set(mode='EDIT')
    def bone(name,head,tail,parent=None):
        b=arm.edit_bones.new(name); b.head=head; b.tail=tail
        if parent: b.parent=arm.edit_bones[parent]
        return b
    h=model['height']; w=model['width']
    bone('body',(w*.5,h*.35,0),(w*.5,h*.60,0))
    bone('head',(w*.55,h*.59,0),(w*.55,h*.83,0),'body')
    bone('hand',(w*.60,h*.57,0),(w*.72,h*.36,0),'body')
    bone('tail',(w*.35,h*.45,0),(w*.12,h*.45,0),'body')
    for i,definition in enumerate(model['legs']):
        hx,hy,fx,fy,_=definition; prefix=('far','near')[i]; depth=-.12 if i==0 else -.06
        hip=(hx*w,h-hy*h,depth); knee=(hx*w+1,(h-hy*h+4)/2,depth); ankle=(fx*w,4,depth)
        bone(prefix+'_thigh',hip,knee,'body'); bone(prefix+'_shin',knee,ankle,prefix+'_thigh')
        b=bone(prefix+'_foot',ankle,(fx*w+5,4,depth),prefix+'_shin'); b.use_inherit_rotation=False
    bpy.ops.object.mode_set(mode='OBJECT'); rig.select_set(False)
    for i,definition in enumerate(model['legs']):
        prefix=('far','near')[i]; hx,hy,fx,fy,_=definition
        target=bpy.data.objects.new(model['id']+'_'+prefix+'_FootTarget',None); collection.objects.link(target)
        target.empty_display_type='SPHERE'; target.empty_display_size=1.5; target.location=rig.location+Vector((fx*w,4,-.12 if i==0 else -.06))
        constraint=rig.pose.bones[prefix+'_shin'].constraints.new('IK'); constraint.target=target; constraint.chain_count=2; constraint.use_stretch=False
        rig.pose.bones[prefix+'_thigh'].lock_ik_x=True; rig.pose.bones[prefix+'_thigh'].lock_ik_y=True
        rig.pose.bones[prefix+'_shin'].lock_ik_x=True; rig.pose.bones[prefix+'_shin'].lock_ik_y=True
        for clip,(start,count) in CLIPS.items():
            for n in range(0,count+1,3):
                phase=n/count; foot_phase=phase+i*.5
                offset,lift,roll=foot_path(foot_phase,model['step']) if clip=='walk' else (0,0,0)
                lift*= {'小马':1.05,'腊肠犬':.85,'猴子':1.45,'小猫':.7}[model['actor']]
                jump=3*max(0,math.sin(phase*math.pi*2))**2 if clip=='happy' else 0
                target.location=rig.location+Vector((fx*w+offset,4+lift+jump,-.12 if i==0 else -.06))
                target.keyframe_insert('location',frame=start+n,group=clip)
                foot=rig.pose.bones[prefix+'_foot']; foot.rotation_mode='XYZ'; foot.rotation_euler.z=roll
                foot.keyframe_insert('rotation_euler',frame=start+n,group=clip)
    body=rig.pose.bones['body']; body.rotation_mode='XYZ'
    for clip,(start,count) in CLIPS.items():
        for n in range(0,count+1,3):
            phase=n/count; rise=-1.4+.45*(1-math.cos(phase*4*math.pi)) if clip=='walk' else -.5+.18*math.sin(phase*2*math.pi)
            if clip=='happy': rise+=3*max(0,math.sin(phase*math.pi*2))**2
            body.location=(0,rise,0); body.rotation_euler.z=(.008*math.sin(phase*2*math.pi) if clip=='walk' else .002*math.sin(phase*2*math.pi))
            body.keyframe_insert('location',frame=start+n,group=clip); body.keyframe_insert('rotation_euler',frame=start+n,group=clip)
            for name,amplitude,lag in (('head',.009,-.4),('hand',.055,math.pi),('tail',.035,-.8)):
                part=rig.pose.bones[name]; part.rotation_mode='XYZ'
                gain=1 if clip=='walk' else (1.5 if clip=='happy' else .25)
                part.rotation_euler.z=amplitude*gain*math.sin(phase*2*math.pi+lag)
                part.keyframe_insert('rotation_euler',frame=start+n,group=clip)
    mesh_part(model,'body',0,collection,rig)
    mesh_part(model,'far',-.12,collection,rig,0); mesh_part(model,'near',-.06,collection,rig,1)
    return rig

def bake():
    scene=bpy.context.scene; result={'schema':1,'producer':'Blender '+bpy.app.version_string,'fps':60,'models':{}}
    rigs=[obj for obj in scene.objects if obj.type=='ARMATURE' and obj.get('model_id')]
    if not rigs: raise ValueError('No companion rigs found; previous export was kept')
    for rig in rigs:
        model=json.loads(rig['model_spec']); key=model['id']; parts={}
        meshes=[obj for obj in scene.objects if obj.type=='MESH' and obj.get('model_id')==key]
        for obj in meshes:
            parts[obj['part']]={'source':json.loads(obj['source_xy']),'triangles':[list(p.vertices) for p in obj.data.polygons],
                'texture':model['textures'][{'body':0,'far':1,'near':2}[obj['part']]],'frames':{}}
        for clip,(start,count) in CLIPS.items():
            for obj in meshes: parts[obj['part']]['frames'][clip]=[]
            for n in range(count):
                scene.frame_set(start+n); depsgraph=bpy.context.evaluated_depsgraph_get()
                for obj in meshes:
                    evaluated=obj.evaluated_get(depsgraph); mesh=evaluated.to_mesh()
                    points=[[round(v.co.x,4),round(model['height']-v.co.y,4)] for v in mesh.vertices]
                    if len(points)!=len(parts[obj['part']]['source']): raise ValueError('Mesh topology changed; rebind artwork before export')
                    if not all(math.isfinite(c) for p in points for c in p): raise ValueError('Non-finite rig geometry: '+key)
                    parts[obj['part']]['frames'][clip].append(points); evaluated.to_mesh_clear()
        result['models'][key]={'actor':model['actor'],'outfit':model['outfit'],'width':model['width'],'height':model['height'],
            'step':model['step'],'period':model['period'],'parts':parts}
        print('Baked',model['actor'],model['outfit'],flush=True)
    output=ROOT/'baked_motion.json.gz'; temporary=ROOT/'baked_motion.tmp.gz'
    with gzip.open(temporary,'wt',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,separators=(',',':'))
    os.replace(temporary,output); scene.frame_set(81)
    print('Exported',output,flush=True)

def build():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    models=json.loads((ROOT/'models.json').read_text(encoding='utf-8'))
    for i,model in enumerate(models): create_rig(model,i)
    scene=bpy.context.scene; scene.render.fps=60; scene.frame_start=81; scene.frame_end=140
    for name,(start,count) in CLIPS.items(): scene.timeline_markers.new(name.upper(),frame=start)
    scene['clip_ranges']=json.dumps(CLIPS); scene['help']='Idle 1–60, Walk 81–140, Happy 161–220. Edit foot targets and body keyframes; export via the workbench.'
    scene.world.color=(.35,.40,.38)
    camera_data=bpy.data.cameras.new('PreviewCamera'); camera=bpy.data.objects.new('PreviewCamera',camera_data); scene.collection.objects.link(camera)
    camera.location=(175,-140,650); camera.rotation_euler=(0,0,0); camera_data.type='ORTHO'; camera_data.ortho_scale=530; scene.camera=camera
    scene.render.resolution_x=1000; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'; area.spaces.active.shading.type='MATERIAL'
    scene.frame_set(81)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'companions.blend'))
    bake()

if '--export-only' in sys.argv: bake()
else: build()
