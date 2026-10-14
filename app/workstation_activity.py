"""Read-only species-specific choreography with attached, textured props."""
import math
from pathlib import Path
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QColor,QPen,QFont,QPainterPath,QPixmap,QRegion
from task_store import timer_state
from character_motion import draw_character,span,DistanceGait

def task_activity(task,day,done=False):
    state=timer_state(task,day)
    return 'done' if done else 'working' if state['started'] and not state['paused'] and not state['finished'] else 'resting'

REST_NAMES={'腊肠犬':('拉来狗窝','整理狗窝','钻进狗窝'),'小猫':('拖来软垫','踩踩软垫','蜷进软垫'),
            '小马':('展开草席','抚平草席','躺上草席'),'猴子':('搬来吊床','打开吊床','试坐吊床')}

def rest_stage(actor,t):
    labels=REST_NAMES.get(actor,REST_NAMES['小马'])
    return labels[0] if t<1.6 else labels[1] if t<2.5 else labels[2] if t<3.15 else '躺下' if t<4.15 else '休息'

class WorkstationActivity:
    _props=None
    def __init__(self):
        self.key=None; self.since=0.; self.stage=''; self.rest_stepper=DistanceGait(); self.rest_time=None
        if WorkstationActivity._props is None:
            props={}
            for actor,name in zip(('小马','腊肠犬','猴子','小猫'),('horse','dog','monkey','cat')):
                image=QPixmap(str(Path(__file__).parent/'assets'/(name+'_rest_prop_v1.png')))
                if not image.isNull():
                    image=image.copy(QRegion(image.mask()).boundingRect()).scaled(148,86,Qt.KeepAspectRatio,Qt.SmoothTransformation)
                props[actor]=image
            WorkstationActivity._props=props
        self.props=WorkstationActivity._props

    def draw(self,p,position,task,day,phase,mascot,actor,outfit,animated=True):
        state=task_activity(task,day); key=(task['id'],state)
        if key!=self.key:
            self.key=key; self.since=phase; self.rest_stepper=DistanceGait(); self.rest_time=None
        elapsed=max(0,phase-self.since) if animated else 6
        return self.work(p,position,elapsed,mascot,actor,outfit,animated) if state=='working' else self.rest(p,position,elapsed,mascot,actor,outfit,animated)

    def prop(self,p,actor,x,floor,scale_y=1,clip=None):
        image=self.props.get(actor)
        if image is None or image.isNull(): return
        p.save()
        if clip is not None: p.setClipRect(clip,Qt.IntersectClip)
        p.translate(x,floor); p.scale(1,scale_y); p.drawPixmap(-image.width()//2,-image.height(),image); p.restore()

    def rest(self,p,position,t,mascot,actor,outfit,animated):
        self.stage=rest_stage(actor,t); x=position.x(); floor=position.y()+36
        supply=span(t,0,1.6); arrange=span(t,1.6,2.5); settle=span(t,3.15,4.15)
        prop_x=x-85*(1-supply); char_x=prop_x+85
        p.save(); p.setPen(Qt.NoPen); p.setBrush(QColor(63,83,67,18)); p.drawEllipse(QRectF(x-65,floor-5,130,9))
        if actor=='小马':
            end=x-73+146*supply
            self.prop(p,actor,x,floor,clip=QRectF(x-74,floor-86,max(1,146*supply),87))
            if supply<1:
                p.setPen(QPen(QColor('#A88B52'),1.3)); p.setBrush(QColor('#D6BB7C')); p.drawRoundedRect(QRectF(end-8,floor-32,16,27),7,7)
                p.drawEllipse(QRectF(end-6,floor-18,12,12)); p.drawArc(QRectF(end-3,floor-15,6,6),0,270*16); char_x=end-27
        elif actor=='猴子':
            p.save(); p.translate(prop_x,floor); p.rotate(-12*(1-supply)); p.translate(-prop_x,-floor)
            self.prop(p,actor,prop_x,floor,.28+.72*span(t,1.15,2.5)); p.restore()
        elif actor=='小猫':
            knead=math.sin(t*8)**2*.09 if 1.6<t<2.5 and animated else 0
            self.prop(p,actor,prop_x,floor,1-knead)
        else: self.prop(p,actor,prop_x,floor)
        if actor in ('腊肠犬','小猫') and t<1.6:
            p.setPen(QPen(QColor('#B4A17B'),1.7)); path=QPainterPath(QPointF(prop_x+50,floor-32)); path.quadTo(QPointF(char_x-8,floor-22),QPointF(char_x+10,floor-43)); p.drawPath(path)
        if t<2.5:
            offset=25 if actor=='小猫' else -18 if actor=='小马' else 32
            if t>=1.6: char_x=x+(46 if actor=='小马' else 85)*(1-arrange)+offset*arrange
            dt=max(0,t-self.rest_time) if self.rest_time is not None else 0
            if self.rest_time is not None and t<self.rest_time: self.rest_stepper=DistanceGait()
            walk=self.rest_stepper.update(QPointF(char_x,floor-6),min(.05,dt),actor,animated)
            self.rest_time=t
            rect=draw_character(p,mascot,actor,outfit,char_x,floor-6,t,'stand',True,'pull' if t<1.6 else 'pat',left=actor!='小马',angle=-7*arrange,animated=animated,walk=walk)
        elif t<3.15:
            seat=span(t,2.5,3.15)
            offset=25 if actor=='小猫' else -18 if actor=='小马' else 32
            # The old seated artwork has outstretched typing arms. Never use it
            # in the sleep pipeline: crouch/lean using the standing rig instead.
            rect=draw_character(p,mascot,actor,outfit,x+offset*(1-seat),floor-6+seat*4,t,
                'stand',gesture='settle',left=True,angle=-18*seat,scale=1-.15*seat,animated=animated)
        else:
            prop_height={'小猫':25,'小马':13,'猴子':33,'腊肠犬':18}.get(actor,20)
            breathe=math.sin(t*1.65)*.45 if animated else 0
            sway=math.sin((t-4.15)*2)*math.exp(-max(0,t-4.15)*.7)*2 if actor=='猴子' and animated else 0
            char_x=x-13 if actor=='腊肠犬' else x
            if actor=='腊肠犬':
                p.save(); entrance=QPainterPath(); entrance.addRoundedRect(QRectF(x-62,floor-64,69,60),25,25); p.setClipPath(entrance,Qt.IntersectClip)
            rect=draw_character(p,mascot,actor,outfit,char_x,floor-prop_height-12*(1-settle)-breathe,t,'rest',gesture='sleep',angle=-16*(1-settle)+sway,animated=animated)
            if actor=='腊肠犬':
                p.restore(); rect=rect.intersected(QRectF(x-62,floor-64,69,60)); p.setPen(QPen(QColor('#C4AE85'),2)); p.drawLine(QPointF(x-59,floor-7),QPointF(x+6,floor-7))
            if t>=4.15:
                p.setPen(QColor('#719084')); p.setFont(QFont('Segoe UI',8)); drift=(t%2.5)*4 if animated else 0; p.drawText(QPointF(x+47,floor-54-drift),'z')
        p.restore(); return rect

    def work(self,p,position,t,mascot,actor,outfit,animated):
        x=position.x(); floor=position.y()+36; setup=span(t,0,1.4); self.stage='拉办公椅' if setup<1 else '涂鸦' if t%18>=12 else '打字'
        p.save(); p.setPen(QPen(QColor('#608778'),2)); p.setBrush(QColor('#BCD8CE')); slide=(1-setup)*45; cx=x-12-slide
        p.drawRoundedRect(QRectF(cx-22,floor-67,9,34),4,4); p.drawRoundedRect(QRectF(cx-20,floor-40,42,9),4,4)
        p.drawLine(QPointF(cx,floor-31),QPointF(cx,floor-8)); p.drawLine(QPointF(cx-18,floor-5),QPointF(cx+18,floor-5))
        for dx in (-16,16):
            p.drawEllipse(QPointF(cx+dx,floor-3),3,3)
            if animated and setup<1: p.drawLine(QPointF(cx+dx,floor-3),QPointF(cx+dx+math.cos(t*15)*2,floor-3+math.sin(t*15)*2))
        rect=draw_character(p,mascot,actor,outfit,x-8,floor-12,t,'sit',gesture='pull' if setup<1 else 'doodle' if self.stage=='涂鸦' else 'type',angle=-4*(1-setup),animated=animated)
        p.setPen(QPen(QColor('#608778'),2)); p.setBrush(QColor('#EFF6F2')); p.drawRoundedRect(QRectF(x+9,floor-42,61,7),3,3); p.drawLine(QPointF(x+61,floor-35),QPointF(x+61,floor-3))
        if self.stage=='涂鸦':
            paper=QRectF(x+20,floor-55,35,12); p.setPen(QPen(QColor('#AAC6BA'),1)); p.setBrush(QColor('white')); p.drawRoundedRect(paper,2,2)
            tip_t=t*3 if animated else 0; ink=QPainterPath(QPointF(x+24,floor-48))
            for i in range(1,round(4+20*((t%6)/6))): ink.lineTo(x+24+i,floor-48+math.sin(i*.8)*2)
            p.setPen(QPen(QColor('#7292AF'),1)); p.drawPath(ink); tip=QPointF(x+34+math.sin(tip_t)*9,floor-48+math.cos(tip_t)*2)
            p.setPen(QPen(QColor('#B78E46'),3)); p.drawLine(tip,tip+QPointF(7,-15))
        else:
            p.setPen(QPen(QColor('#90AA9E'),1)); p.setBrush(QColor('#D5E6DF')); p.drawRoundedRect(QRectF(x+20,floor-48,34,5),2,2)
            for i in range(7): p.drawLine(QPointF(x+23+i*4,floor-47),QPointF(x+23+i*4,floor-44))
        p.restore(); return rect
