"""Independent cutout legs with two-bone IK and explicit depth ordering."""
import math
from pathlib import Path
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QPixmap,QPainter,QPainterPath,QRegion

# Limb silhouettes must balance the torso at the app's small display size.
# The original isolated limbs were scaled by height alone and became spindly.
LEG_PROPORTIONS={
    '小马':dict(width=1.38,hip_gap=7.0),
    '腊肠犬':dict(width=1.30,hip_gap=6.3),
    '猴子':dict(width=1.44,hip_gap=6.2),
    '小猫':dict(width=1.42,hip_gap=8.0),
}

def layers(mascot,actor,outfit,pix,leg_extension=0):
    key=('leg-rig',actor,outfit,pix.width(),pix.height(),leg_extension)
    if key in mascot.cache: return mascot.cache[key]
    from mascot_animation import sprite_regions,OUTFITS
    name={'小马':'horse','腊肠犬':'dog','猴子':'monkey','小猫':'cat'}[actor]
    atlas=QPixmap(str(Path(__file__).parent/'assets'/(name+'_cutout_rig_v2.png' if name=='cat' else name+'_cutout_rig_v1.png')))
    if atlas.isNull(): raise RuntimeError('缺少分层角色素材：'+name)
    regions=sprite_regions(atlas)
    if len(regions)!=9: raise RuntimeError('分层角色素材必须包含 9 个独立部件：'+name)
    row=OUTFITS.index(outfit) if outfit in OUTFITS else 0
    parts=[atlas.copy(regions[row*3+i]) for i in range(3)]
    w=pix.width(); h=pix.height(); body=QPixmap(w,h); body.fill(Qt.transparent); legs=[]; definitions=[]
    ratio=.78 if actor=='猴子' else .74
    upper=parts[0].scaledToHeight(round((h-leg_extension)*ratio),Qt.SmoothTransformation)
    if upper.width()>w: upper=upper.scaledToWidth(w,Qt.SmoothTransformation)
    bx=(w-upper.width())/2
    p=QPainter(body); p.drawPixmap(round(bx),0,upper); p.end()
    # Place the thigh under the hem, not at its bottom edge. This overlap
    # preserves a full-length leg and hides the cut edge of the texture.
    hip_y=upper.height()*.84
    pelvis=bx+upper.width()*{'小马':.63,'腊肠犬':.54,'猴子':.72,'小猫':.60}[actor]
    proportions=LEG_PROPORTIONS[actor]
    for i,part in enumerate(parts[1:]):
        leg=QPixmap(w,h); leg.fill(Qt.transparent)
        leg_height=round(h-hip_y+2)
        leg_width=round(part.width()*leg_height/part.height()*proportions['width'])
        texture=part.scaled(leg_width,leg_height,Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
        hip_x=pelvis+(-.5 if i==0 else .5)*proportions['hip_gap']
        lx=hip_x-texture.width()*.45; ly=hip_y-2
        p=QPainter(leg); p.drawPixmap(round(lx),round(ly),texture); p.end(); legs.append(leg)
        definitions.append((hip_x/w,hip_y/h,(lx+texture.width()*.64)/w,(h-1)/h,[]))
    result=(body,legs,definitions); mascot.cache[key]=result; return result

def solve_legs(actor,w,h,walk,foot_contact,definitions=None):
    result=[]; weight=walk['weight']
    if not definitions or len(definitions)!=2: raise ValueError('需要两条独立腿的连接点')
    for i,(hx,hy,fx,fy,_) in enumerate(definitions):
        source_hip=QPointF(hx*w,hy*h); source_foot=QPointF(fx*w,fy*h)
        offset,lift,stance=foot_contact(walk['phase']+i*.5,walk['step'])
        # Keep travel in the side-view plane. Screen-space vertical travel
        # must never pull a foot through the character's belly.
        lift*=.42
        destination=QPointF(source_foot.x()+offset,h-1+walk.get('body_lift',0)-lift)
        foot=source_foot+(destination-source_foot)*weight; hip=QPointF(source_hip)
        delta=foot-hip; reach=math.hypot(delta.x(),delta.y())
        # The old .67 multiplier created a deep squat on every planted step.
        # The source leg is nearly straight: each bone is half its length.
        length=math.hypot(source_foot.x()-source_hip.x(),source_foot.y()-source_hip.y())*.505
        if reach>length*1.999:
            foot=hip+delta*(length*1.999/reach); delta=foot-hip; reach=length*1.999
        bent=(hip+foot)*.5+QPointF(delta.y(),-delta.x())*(math.sqrt(max(0,length*length-reach*reach/4))/max(.001,reach))
        knee=(source_hip+source_foot)*.5+(bent-(source_hip+source_foot)*.5)*weight
        result.append(dict(hip=hip,knee=knee,foot=foot,source_hip=source_hip,source_foot=source_foot,stance=stance,index=i))
    return result

def leg_point(point,bone):
    sh=bone['source_hip']; sf=bone['source_foot']; sk=(sh+sf)*.5
    t=(point.y()-sh.y())/max(1,sf.y()-sh.y())
    if t<.5:
        q=t*2; source=sh+(sk-sh)*q; target=bone['hip']+(bone['knee']-bone['hip'])*q
    else:
        q=(t-.5)*2; source=sk+(sf-sk)*q; target=bone['knee']+(bone['foot']-bone['knee'])*q
    a0=math.atan2((bone['knee']-bone['hip']).y(),(bone['knee']-bone['hip']).x())-math.atan2((sk-sh).y(),(sk-sh).x())
    a1=math.atan2((bone['foot']-bone['knee']).y(),(bone['foot']-bone['knee']).x())-math.atan2((sf-sk).y(),(sf-sk).x())
    blend=max(0,min(1,(t-.35)/.3)); blend=blend*blend*(3-2*blend); angle=a0*(1-blend)+a1*blend
    # Keep the foot attached to the shin; flattening its angle over a tiny
    # strip used to fold the foot texture back through itself.
    offset=point-source; return target+QPointF(offset.x()*math.cos(angle)-offset.y()*math.sin(angle),offset.x()*math.sin(angle)+offset.y()*math.cos(angle))

def draw_leg(p,pix,bone,affine):
    # Each leg owns its triangles. Passing legs may overlap without folding
    # a single shared torso/leg mesh inside out.
    w=pix.width(); h=pix.height(); bounds=QRegion(pix.mask()).boundingRect()
    x0=bounds.left(); x1=bounds.right()+1; y0=max(0,bone['source_hip'].y()-2); columns=3; rows=6
    p.save(); p.setRenderHint(QPainter.Antialiasing,False)
    for j in range(rows):
        for i in range(columns):
            vertices=[QPointF(x0+(x1-x0)*i/columns,y0+(h-y0)*j/rows),QPointF(x0+(x1-x0)*(i+1)/columns,y0+(h-y0)*j/rows),QPointF(x0+(x1-x0)*(i+1)/columns,y0+(h-y0)*(j+1)/rows),QPointF(x0+(x1-x0)*i/columns,y0+(h-y0)*(j+1)/rows)]
            for indices in ((0,1,2),(0,2,3)):
                source=[vertices[k] for k in indices]; target=[leg_point(pt,bone) for pt in source]
                mid=sum(target,QPointF())/3; expanded=[mid+(pt-mid)*1.035 for pt in target]
                path=QPainterPath(expanded[0]); path.lineTo(expanded[1]); path.lineTo(expanded[2]); path.closeSubpath()
                p.save(); p.setClipPath(path,Qt.IntersectClip); p.setWorldTransform(affine(source,target),True); p.drawPixmap(0,0,pix); p.restore()
    p.restore()
