"""Continuous local deformation of one texture: no whole-body frame swapping."""
import math
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QTransform,QPainterPath,QPainter
from leg_rig import layers,solve_legs,draw_leg

def ease(value):
    value=max(0.,min(1.,value)); return value*value*(3-2*value)

def span(time,start,end): return ease((time-start)/(end-start))

PROFILES={
    '小马':dict(period=.78,stride=5.5,bounce=.6,sway=.35,step=15,speed=65),
    '腊肠犬':dict(period=.55,stride=4.3,bounce=.4,sway=.3,step=12,speed=60),
    '猴子':dict(period=.88,stride=6.,bounce=.7,sway=.5,step=17,speed=64),
    '小猫':dict(period=1.32,stride=3.6,bounce=.35,sway=.3,step=12,speed=43),
}

def foot_contact(phase,step):
    phase%=1
    if phase<.5: return step*(.5-2*phase),0.,True
    q=(phase-.5)*2
    return step*(-.5-q+6*q*q-4*q*q*q),6*math.sin(q*math.pi)**2,False

class DistanceGait:
    """Steps follow actual travelled distance, including acceleration and stops."""
    def __init__(self):
        self.position=None; self.distance=0.; self.weight=0.; self.heading=QPointF(1,0); self.facing=1.; self.actor=None
    def update(self,position,dt,actor,moving=True):
        if actor!=self.actor: self.__init__(); self.actor=actor
        delta=position-self.position if self.position is not None else QPointF(); self.position=QPointF(position)
        dt=max(0,min(.05,dt)); travelled=math.hypot(delta.x(),delta.y())
        if travelled>40: travelled=0 # resized / reloaded scene, not a 40px footstep
        genuine=moving and travelled>.005 and dt>0
        if genuine:
            self.distance+=travelled
            blend=1-math.exp(-dt/.10); direction=delta/max(travelled,.001)
            self.heading+= (direction-self.heading)*blend
            if abs(direction.x())>.15:
                wanted=-1 if direction.x()<0 else 1
                self.facing+=(wanted-self.facing)*(1-math.exp(-dt/.09))
        wanted=1 if genuine else 0
        self.weight+=(wanted-self.weight)*(1-math.exp(-dt/.09))
        profile=PROFILES.get(actor,PROFILES['小马']); phase=self.distance/(2*profile['step'])
        return dict(phase=phase,weight=self.weight,heading=QPointF(self.heading),facing=self.facing)

def gait(actor,time,moving,animated=True):
    profile=PROFILES.get(actor,PROFILES['小马']); t=time if animated else 0
    cycle=t*2*math.pi/profile['period']; foot=math.sin(cycle)
    hop=0.
    if moving and animated and actor=='猴子':
        local=t%7.2
        if 3.8<local<4.5: hop=11*math.sin((local-3.8)/.7*math.pi)**2
    return dict(cycle=cycle,foot=foot if moving and animated else 0.,
        lift=(profile['bounce']*(1-math.cos(cycle*2))*.5+hop) if moving and animated else 0.,
        sway=profile['sway']*math.sin(cycle) if moving and animated else 0.,hop=hop,
        stride=profile['stride'] if moving and animated else 0.)

def deform(u,v,width,height,actor,time,moving=False,gesture='',animated=True,walk=None):
    """Smooth weights prevent torn hips and flickering silhouettes."""
    t=time if animated else 0.; motion=gait(actor,t,moving,animated)
    x=u*width; y=v*height
    leg=ease((v-.66)/.32); side=math.tanh((u-.49)*11)
    if walk is not None and animated:
        step=PROFILES[actor]['step']; mix=(1+side)/2; weight=walk['weight']
        first=foot_contact(walk['phase'],step); second=foot_contact(walk['phase']+.5,step)
        offset=(first[0]*(1-mix)+second[0]*mix)*weight
        lift=(first[1]*(1-mix)+second[1]*mix)*weight
        heading=walk['heading']; sign=-1 if walk['facing']<0 else 1
        if not walk.get('independent_legs'):
            x+=leg*offset*heading.x()*sign
            y+=leg*(offset*heading.y()-lift+walk.get('body_lift',motion['lift']*weight))
        arm=ease((u-.50)/.35)*math.exp(-((v-.54)/.18)**2)
        x+=arm*math.sin(walk['phase']*2*math.pi+math.pi)*3*weight
    else:
        x+=leg*side*motion['foot']*motion['stride']
        y-=leg*max(0,side*math.cos(motion['cycle']))*(3 if moving and animated else 0)
    torso=math.exp(-((v-.55)/.23)**2)
    x+=torso*math.sin(t*1.8)*(.6 if actor=='小猫' else .25) if animated else 0
    # Tail/ear lag, offset from the feet; the head remains almost still.
    trailing=ease((.32-u)/.25)*ease((v-.3)/.25)*(1-ease((v-.76)/.2))
    y+=trailing*math.sin(t*5-.6)*(1.8 if actor=='腊肠犬' else .8) if animated else 0
    hand=ease((u-.51)/.3)*math.exp(-((v-.53)/.15)**2)
    if gesture in ('type','pat','pull','doodle','tickle') and animated:
        frequency={'type':17,'pat':8,'pull':7,'doodle':4,'tickle':20}[gesture]
        y+=hand*math.sin(t*frequency+u*7)*({'pat':3,'pull':2,'type':1.5,'doodle':2,'tickle':3}[gesture])
        x+=hand*math.cos(t*frequency)*(.8 if gesture=='type' else 2)
    if gesture=='sleep' and animated:
        chest=math.exp(-((u-.54)/.26)**2)*ease((1-v)/.6)
        y-=chest*(.55+.55*math.sin(t*1.65))
    return QPointF(x,y)

def affine(src,dst):
    s0,s1,s2=src; d0,d1,d2=dst
    ax=s1.x()-s0.x(); ay=s1.y()-s0.y(); bx=s2.x()-s0.x(); by=s2.y()-s0.y(); det=ax*by-ay*bx
    ux=d1.x()-d0.x(); uy=d1.y()-d0.y(); vx=d2.x()-d0.x(); vy=d2.y()-d0.y()
    a=(ux*by-vx*ay)/det; c=(vx*ax-ux*bx)/det
    b=(uy*by-vy*ay)/det; d=(vy*ax-uy*bx)/det
    return QTransform(a,b,c,d,d0.x()-a*s0.x()-c*s0.y(),d0.y()-b*s0.x()-d*s0.y())

def draw_character(p,mascot,actor,outfit,center,floor,time,pose='stand',moving=False,
                   gesture='',left=False,angle=0,scale=1,animated=True,mood='idle',walk=None):
    from blender_motion import draw_blender_character
    baked=draw_blender_character(p,actor,outfit,center,floor,time,pose,moving,gesture,left,angle,scale,animated,mood,walk,affine)
    if baked is not None: return baked
    pix=mascot.action_frame(actor,outfit,pose); width=pix.width(); height=pix.height()
    motion=gait(actor,time,moving,animated)
    if walk is not None and animated:
        synced=gait(actor,walk['phase']*PROFILES[actor]['period'],True,True)
        motion['lift']=(synced['lift']-synced['hop'])*walk['weight']+motion['hop']*walk['weight']
        motion['sway']=synced['sway']*walk['weight']
    happy=3*(1-math.cos(time*5)) if animated and mood=='happy' else 0
    origin=QPointF(center-width*scale/2,floor-height*scale-motion['lift']-happy)
    facing=(-1 if left else 1)
    if walk is not None and animated: facing=(-1 if walk['facing']<0 else 1)*max(.25,abs(walk['facing']))
    p.save(); p.translate(center,floor-motion['lift']-happy); p.rotate(angle+motion['sway']); p.scale(facing*scale,scale); p.translate(-width/2,-height)
    transform=p.worldTransform(); columns=6; rows=9
    separate=pose=='stand'
    if separate:
        if walk is None: walk=dict(phase=time/PROFILES[actor]['period'] if animated else 0,weight=1 if moving and animated else 0,heading=QPointF(1,0),facing=1)
        if not animated: walk=dict(walk,weight=0,phase=0)
        walk=dict(walk,body_lift=motion['lift'],step=PROFILES[actor]['step'],independent_legs=True)
        pix,legs,definitions=layers(mascot,actor,outfit,pix)
        bones=solve_legs(actor,width,height,walk,foot_contact,definitions)
        # Near/far legs keep their depth while passing one another.
        order=(0,1)
        draw_leg(p,legs[order[0]],bones[order[0]],affine)
        draw_leg(p,legs[order[1]],bones[order[1]],affine)
    src=[[QPointF(width*i/columns,height*j/rows) for i in range(columns+1)] for j in range(rows+1)]
    if walk is not None: walk=dict(walk,body_lift=motion['lift'])
    dst=[[deform(i/columns,j/rows,width,height,actor,time,moving,gesture,animated,walk) for i in range(columns+1)] for j in range(rows+1)]
    p.setRenderHint(QPainter.Antialiasing,False)
    for j in range(rows):
        for i in range(columns):
            for indices in (((j,i),(j,i+1),(j+1,i+1)),((j,i),(j+1,i+1),(j+1,i))):
                source=[src[r][c] for r,c in indices]; target=[dst[r][c] for r,c in indices]
                # Slightly overlapping clip edges prevent transparent seams.
                mid=sum((pt for pt in target),QPointF())/3
                path=QPainterPath(); points=[mid+(pt-mid)*1.035 for pt in target]
                path.moveTo(points[0]); path.lineTo(points[1]); path.lineTo(points[2]); path.closeSubpath()
                p.save(); p.setClipPath(path,Qt.IntersectClip); p.setWorldTransform(affine(source,target),True); p.drawPixmap(0,0,pix); p.restore()
    rect=transform.mapRect(QRectF(-4,-4,width+8,height+8)); p.restore()
    return rect
