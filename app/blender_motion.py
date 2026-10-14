"""Play Blender-evaluated artwork meshes; no runtime IK or leg stretching."""
import gzip,json,math
from collections import OrderedDict
from pathlib import Path
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QPixmap,QPainter,QPainterPath,QColor

ROOT=Path(__file__).resolve().parent/'animation_studio'

class BlenderMotion:
    def __init__(self):
        self.stamp=None; self.models={}; self.textures={}; self.cache=OrderedDict(); self.error=''
    def reload(self):
        path=ROOT/'baked_motion.json.gz'
        stamp=path.stat().st_mtime_ns if path.exists() else 0
        if stamp==self.stamp: return
        self.stamp=stamp
        if not stamp: return
        try:
            with gzip.open(path,'rt',encoding='utf-8') as f: data=json.load(f)
            if data.get('schema')!=1 or not str(data.get('producer','')).startswith('Blender '): raise ValueError('Unsupported animation export')
            models={(m['actor'],m['outfit']):m for m in data['models'].values()}
            for model in models.values():
                for part in model['parts'].values():
                    texture=(ROOT/part['texture']).resolve()
                    if not texture.is_relative_to(ROOT.resolve()) or not texture.is_file(): raise ValueError('Missing or invalid texture')
                    for clip in ('idle','walk','happy'):
                        frames=part['frames'][clip]
                        if not frames or any(len(frame)!=len(part['source']) for frame in frames): raise ValueError('Invalid animation geometry')
                        if not all(math.isfinite(c) for frame in frames for point in frame for c in point): raise ValueError('Invalid animation coordinates')
            self.models=models; self.textures.clear(); self.cache.clear(); self.error=''
        except (OSError,ValueError,KeyError,TypeError,EOFError) as exc:
            self.error=str(exc) # Keep the last successfully loaded set.
    def model(self,actor,outfit):
        self.reload(); return self.models.get((actor,outfit))
    def geometry(self,part,clip,phase):
        frames=part['frames'][clip]; position=(phase%1)*len(frames); i=int(position); mix=position-i
        first=frames[i]; second=frames[(i+1)%len(frames)]
        return [[a[0]+(b[0]-a[0])*mix,a[1]+(b[1]-a[1])*mix] for a,b in zip(first,second)]
    def paint_mesh(self,p,model,clip,phase,weight,idle_phase,affine):
        w=model['width']; h=model['height']
        p.setRenderHint(QPainter.SmoothPixmapTransform,True)
        for name in ('far','near','body'):
            part=model['parts'][name]; path=part['texture']
            if path not in self.textures: self.textures[path]=QPixmap(str(ROOT/path))
            texture=self.textures[path]; target=self.geometry(part,clip,phase)
            if clip=='walk' and weight<.995:
                idle=self.geometry(part,'idle',idle_phase)
                target=[[a[0]+(b[0]-a[0])*weight,a[1]+(b[1]-a[1])*weight] for a,b in zip(idle,target)]
            for triangle in part['triangles']:
                source=[QPointF(*part['source'][i]) for i in triangle]; points=[QPointF(*target[i]) for i in triangle]
                center=sum(points,QPointF())/3; expanded=[center+(point-center)*1.012 for point in points]
                polygon=QPainterPath(expanded[0]); polygon.lineTo(expanded[1]); polygon.lineTo(expanded[2]); polygon.closeSubpath()
                p.save(); p.setClipPath(polygon,Qt.IntersectClip); p.setWorldTransform(affine(source,points),True)
                p.drawPixmap(QRectF(0,0,w,h),texture,QRectF(texture.rect())); p.restore()
    def draw(self,p,model,clip,phase,weight,idle_phase,affine):
        # Cache whole rendered poses. Full playback then needs one pixmap draw.
        use_cache=clip!='walk' or weight>=.995
        if not use_cache:
            self.paint_mesh(p,model,clip,phase,weight,idle_phase,affine); return
        frame=int((phase%1)*60)%60; key=(model['actor'],model['outfit'],clip,frame)
        if key not in self.cache:
            pix=QPixmap(model['width']+16,model['height']+16); pix.fill(Qt.transparent)
            painter=QPainter(pix); painter.translate(8,8)
            self.paint_mesh(painter,model,clip,frame/60,1,idle_phase,affine); painter.end(); self.cache[key]=pix
            while len(self.cache)>240: self.cache.popitem(last=False)
        else: self.cache.move_to_end(key)
        p.drawPixmap(-8,-8,self.cache[key])

player=BlenderMotion()

def draw_blender_character(p,actor,outfit,center,floor,time,pose,moving,gesture,left,angle,scale,animated,mood,walk,affine):
    if pose!='stand': return None
    model=player.model(actor,outfit)
    if model is None: return None
    w=model['width']; h=model['height']; idle_phase=time/3.0 if animated else 0
    weight=walk['weight'] if walk is not None and animated else (1 if moving and animated else 0)
    clip='walk' if weight>.002 else 'idle'; phase=walk['phase'] if walk is not None else time/model['period']
    if clip=='idle': phase=idle_phase
    if animated and mood=='happy' and weight<.1: clip='happy'; phase=time/1.25
    sign=-1 if left else 1
    if walk is not None and animated: sign=-1 if walk['facing']<0 else 1
    p.save(); p.translate(center,floor); p.rotate(angle); p.scale(sign*scale,scale); p.translate(-w/2,-h)
    player.draw(p,model,clip,phase,weight,idle_phase,affine)
    rect=p.worldTransform().mapRect(QRectF(-8,-8,w+16,h+16)); p.restore(); return rect
