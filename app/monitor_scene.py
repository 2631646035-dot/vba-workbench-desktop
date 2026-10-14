"""Quiet computer-screen tasks with a small, purposeful horse patrol."""
import math
from pathlib import Path
from datetime import date
from PySide6.QtCore import Qt,QTimer,QPointF,QRectF,QElapsedTimer
from PySide6.QtGui import QPainter,QColor,QFont,QPen,QPixmap,QPainterPath
from PySide6.QtWidgets import QWidget,QMenu
from task_store import crop_status,timer_state
from workstation_activity import WorkstationActivity,task_activity
from character_motion import draw_character,DistanceGait,PROFILES
from mascot_animation import MascotAnimation
from companion_interaction import CompanionInteraction
BACKGROUNDS={'light':{'雾白':'#EDF2EF','青绿':'#E3EFEB','暖砂':'#F4EDDF','浅蓝':'#E6EEF8'},
             'dark':{'雾白':'#0F202C','青绿':'#132D25','暖砂':'#2A2624','浅蓝':'#142739'}}

def walking_path(origin,target,aisle):
    path=QPainterPath(origin); delta=target-origin
    if abs(delta.y())<1:
        path.cubicTo(origin+QPointF(delta.x()*.3,5),target-QPointF(delta.x()*.3,5),target)
        return path
    points=[origin,QPointF(aisle,origin.y()),QPointF(aisle,target.y()),target]
    points=[pt for i,pt in enumerate(points) if not i or (pt-points[i-1]).manhattanLength()>.01]
    for i in range(1,len(points)-1):
        before=points[i]-points[i-1]; after=points[i+1]-points[i]
        a=math.hypot(before.x(),before.y()); b=math.hypot(after.x(),after.y()); radius=min(25,a/3,b/3)
        path.lineTo(points[i]-before*(radius/a)); path.quadTo(points[i],points[i]+after*(radius/b))
    path.lineTo(target); return path

class MonitorWorld(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setMouseTracking(True); self.setMinimumHeight(400)
        self.items=[]; self.station_rects=[]; self.phase=3.; self.hover=-1; self.actor='小马'; self.open_task=None
        self.selected_id=None; self.reward_until=0.; self.theme='light'; self.active_index=-1; self.horse_position=QPointF()
        self.background_choice='雾白'
        self.overloaded=False; self.panic_anchor=None; self.panic_cycle=-1
        self.interaction=CompanionInteraction()
        self.outfit='通勤'; self.day=date.today().isoformat(); self.activity=WorkstationActivity()
        self.timer_task=None; self.task_menu=None
        self.stepper=DistanceGait(); self.motion_phase=None; self.walk_state=None; self.frame_dt=1/60; self.work_speed=0.
        self.pony=QPixmap(str(Path(__file__).parent/'assets'/'farm_pony.png'))
        self.mascot=MascotAnimation(); self.done_today=0; self.all_done=False; self.last_position=None; self.facing_left=False; self.frame_index=1; self.reward_delay=0.
        self.clock=QElapsedTimer(); self.clock.start()
        self.timer=QTimer(self); self.timer.setTimerType(Qt.PreciseTimer); self.timer.setInterval(16); self.timer.timeout.connect(self.tick)
    def tick(self):
        elapsed=min(.05,max(0.,self.clock.restart()/1000.))
        if self.isVisible() and not self.window().isMinimized():
            self.phase+=elapsed
            self.frame_dt=elapsed
            if self.phase<self.reward_until or self.interaction.hovered or self.interaction.active(): self.reward_delay+=elapsed
            self.update()
    def set_items(self,items):
        self.items=items; cols=max(1,int(max(320,self.width())/330))
        self.setMinimumHeight(max(400,self.layout_stations(cols,True))); self.update()
    def layout_stations(self,cols,height_only=False):
        width=self.width()/cols; y=55; rects=[]
        for offset in range(0,len(self.items),cols):
            row=self.items[offset:offset+cols]
            heights=[260 if task_activity(task,self.day,done)=='working' else 175 for task,done in row]
            rects.extend(QRectF(i*width+35,y,width-70,height) for i,height in enumerate(heights))
            y+=max(heights)+110
        return y if height_only else rects
    def resizeEvent(self,event): super().resizeEvent(event); self.set_items(self.items)
    def mouseMoveEvent(self,event):
        self.interaction.hovered=self.interaction.rect.contains(event.position())
        self.hover=next((i for i,r in enumerate(self.station_rects) if r.contains(event.position())),-1)
        interactive=self.interaction.hovered or self.interaction.card_rect.contains(event.position())
        self.setCursor(Qt.PointingHandCursor if self.hover>=0 or interactive else Qt.ArrowCursor)
        self.setToolTip('悬停：开心 · 点击：挠痒 · 右键：抛一个待做任务' if interactive else self.items[self.hover][0]['title']+' · 点击查看任务' if self.hover>=0 else '')
        self.update()
    def leaveEvent(self,event): self.hover=-1; self.interaction.hovered=False; self.update()
    def mousePressEvent(self,event):
        pending=[t for t,done in self.items if not done]
        if event.button()==Qt.LeftButton and self.interaction.card_rect.contains(event.position()) and self.interaction.task:
            task=next((t for t in pending if t['id']==self.interaction.task['id']),None)
            if task and self.open_task: self.open_task(task)
            return
        if self.interaction.rect.contains(event.position()) and event.button() in (Qt.LeftButton,Qt.RightButton):
            self.interaction.react('offer' if event.button()==Qt.RightButton else 'tickle',pending)
            self.update(); QTimer.singleShot(6100 if event.button()==Qt.RightButton else 2100,self.update); return
        index=next((i for i,r in enumerate(self.station_rects) if r.contains(event.position())),-1)
        if event.button()==Qt.RightButton and index>=0 and not self.items[index][1] and self.timer_task:
            task=self.items[index][0]; state=timer_state(task,self.day)
            self.task_menu=QMenu(self)
            action=self.task_menu.addAction('开始处理' if not state['started'] else '继续处理' if state['paused'] or state['finished'] else '暂停处理')
            action.triggered.connect(lambda checked=False,t=task:self.timer_task(t))
            self.task_menu.popup(event.globalPosition().toPoint()); return
        if event.button()==Qt.LeftButton and index>=0:
            self.selected_id=self.items[index][0]['id']
            if self.open_task: self.open_task(self.items[index][0])
    def patrol(self):
        pending=[i for i,(_,done) in enumerate(self.items) if not done]
        if not pending: self.active_index=-1; return self.last_position or QPointF(self.width()/2,300),False
        if self.phase<self.reward_until and self.last_position is not None: return QPointF(self.last_position),False
        if (self.interaction.hovered or self.interaction.active()) and self.last_position is not None: return QPointF(self.last_position),False
        # Stay with the real in-progress task instead of leaving it to patrol.
        working=[i for i in pending if task_activity(self.items[i][0],self.day)=='working']
        if working:
            current=next((i for i in working if self.items[i][0]['id']==self.selected_id),working[0]); self.active_index=current
            target=QPointF(self.station_rects[current].center().x(),self.station_rects[current].bottom()-74)
            if self.last_position is None or not self.timer.isActive(): return target,False
            distance=target-self.last_position
            if math.hypot(distance.x(),distance.y())<2: return target,False
            if abs(distance.y())>2:
                aisle=16 if target.x()+self.last_position.x()<self.width() else self.width()-16
                waypoint=QPointF(aisle,self.last_position.y()) if abs(self.last_position.x()-aisle)>2 else QPointF(aisle,target.y())
                distance=waypoint-self.last_position
            length=math.hypot(distance.x(),distance.y()); speed=PROFILES[self.actor]['speed']
            self.work_speed=min(speed,self.work_speed+200*self.frame_dt,math.sqrt(400*length))
            return self.last_position+distance*(min(length,self.work_speed*self.frame_dt)/max(length,.001)),True
        if self.actor=='猴子' and self.overloaded and self.timer.isActive():
            cycle=int(self.phase/16); burst=self.phase%16
            if burst<4:
                if self.panic_cycle!=cycle or self.panic_anchor is None:
                    self.panic_cycle=cycle
                    self.panic_anchor=QPointF(self.last_position or QPointF(self.station_rects[pending[0]].center().x(),self.station_rects[pending[0]].bottom()+63))
                # A bounded short burst, returning to its origin rather than jumping.
                radius=min(65,max(0,min(self.panic_anchor.x()-60,self.width()-60-self.panic_anchor.x())))
                return self.panic_anchor+QPointF(radius*math.sin(burst*math.pi*2),0),True
        self.work_speed=0.
        journey=self.phase-self.reward_delay; slot=int(journey/16)
        current=pending[slot%len(pending)]; previous=pending[(slot-1)%len(pending)]; self.active_index=current
        target=QPointF(self.station_rects[current].center().x(),self.station_rects[current].bottom()+63)
        origin=QPointF(self.station_rects[previous].center().x(),self.station_rects[previous].bottom()+63)
        if (target-origin).manhattanLength()<.01: return target,False
        aisle=16 if origin.x()+target.x()<self.width() else self.width()-16
        path=walking_path(origin,target,aisle); length=path.length()
        duration=min(9,max(1,length/PROFILES[self.actor]['speed']+.45)); progress=(journey%16)/duration
        if progress>=1 or not self.timer.isActive(): return target,False
        progress=progress*progress*(3-2*progress)
        return path.pointAtPercent(path.percentAtLength(length*progress)),True
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform); dark=self.theme=='dark'
        background=BACKGROUNDS[self.theme].get(self.background_choice,BACKGROUNDS[self.theme]['雾白']); foreground='#ECF2EF' if dark else '#253D34'; muted='#ABC0B6' if dark else '#7B8F85'
        p.fillRect(self.rect(),QColor(background)); p.setPen(QColor(muted)); p.setFont(QFont('Microsoft YaHei UI',9))
        p.drawText(24,27,'角色：悬停开心 · 左键挠痒 · 右键抛任务（仅提醒，不执行）')
        cols=max(1,int(self.width()/330)); self.station_rects=self.layout_stations(cols)
        position,moving=self.patrol(); self.horse_position=position
        if self.motion_phase is None or self.phase!=self.motion_phase:
            dt=self.frame_dt if self.motion_phase is None else min(.05,max(0,self.phase-self.motion_phase))
            self.walk_state=self.stepper.update(position,dt,self.actor,moving and self.timer.isActive()); self.motion_phase=self.phase
        for i,(task,done) in enumerate(self.items):
            rect=self.station_rects[i]; active=i==self.active_index; hover=i==self.hover; late=crop_status(task,date.today().isoformat(),done)=='late'
            if not event.rect().intersects(rect.toAlignedRect().adjusted(-5,-5,5,25)): continue
            p.setPen(Qt.NoPen); p.setBrush(QColor('#132936' if dark else '#DCE5DF')); p.drawRoundedRect(rect.translated(0,5),13,13)
            p.setBrush(QColor('#1A3442' if dark else '#FFFFFF')); p.setPen(QPen(QColor('#489E88' if active or hover else '#385461' if dark else '#C9D5CE'),2 if active or hover else 1)); p.drawRoundedRect(rect,13,13)
            colors={'高':'#DA7B72','中':'#C5A451','低':'#60A593'}
            p.setPen(Qt.NoPen); p.setBrush(QColor(colors.get(task.get('priority','中'),'#C5A451'))); p.drawEllipse(QRectF(rect.x()+17,rect.y()+16,7,7))
            p.setPen(QColor(muted)); p.setFont(QFont('Microsoft YaHei UI',9)); p.drawText(QPointF(rect.x()+31,rect.y()+24),task.get('priority','中')+'优先')
            status=task_activity(task,self.day,done)
            paused=timer_state(task,self.day)['paused']
            p.drawText(QRectF(rect.right()-85,rect.y()+10,70,22),Qt.AlignRight|Qt.AlignVCenter,'已完成' if done else '进行中' if status=='working' else '已暂停' if paused else '已超时' if late else '待处理')
            p.setPen(QColor(foreground)); p.setFont(QFont('Microsoft YaHei UI',12,QFont.Bold)); p.drawText(QRectF(rect.x()+17,rect.y()+44,rect.width()-34,57),Qt.TextWordWrap,task['title'])
            p.setPen(QColor(muted)); p.setFont(QFont('Microsoft YaHei UI',9)); note=task.get('note','').replace('\n',' ') or ('周期任务' if task.get('repeat') else '普通任务')
            p.drawText(QRectF(rect.x()+17,rect.y()+103,rect.width()-34,20),Qt.AlignVCenter,p.fontMetrics().elidedText(note,Qt.ElideRight,int(rect.width()-34)))
            if status=='working':
                p.setPen(Qt.NoPen); p.setBrush(QColor('#213D45' if dark else '#F0F6F2'))
                p.drawRoundedRect(QRectF(rect.x()+12,rect.y()+130,rect.width()-24,95),9,9)
            p.setPen(QColor(muted))
            p.drawText(QPointF(rect.x()+17,rect.bottom()-13),str(task.get('minutes',0))+' 分钟' if task.get('minutes') else '未估时')
            label=('正在处理' if status=='working' else '前往工位' if moving else '休息工位') if active else '点击查看 →'
            p.setPen(QColor('#398C73' if active else muted)); p.drawText(QRectF(rect.right()-110,rect.bottom()-32,93,23),Qt.AlignRight|Qt.AlignVCenter,label)
            p.setPen(QPen(QColor('#71867C'),3)); p.drawLine(QPointF(rect.center().x(),rect.bottom()+3),QPointF(rect.center().x(),rect.bottom()+16))
            p.setPen(Qt.NoPen); p.setBrush(QColor('#9AAC9F')); p.drawRoundedRect(QRectF(rect.center().x()-28,rect.bottom()+14,56,5),2,2)
        if self.items:
            if self.last_position is not None and abs(position.x()-self.last_position.x())>.2:
                self.facing_left=position.x()<self.last_position.x()
            self.last_position=QPointF(position)
            mood='happy' if self.phase<self.reward_until or self.all_done else 'tired' if self.done_today>=4 else 'idle'
            if mood!='happy' and self.actor=='猴子' and self.overloaded: mood='panic'
            mood=self.interaction.mood(mood)
            animated=self.timer.isActive()
            pixmap,self.frame_index=self.mascot.dressed_frame(self.actor,self.outfit,self.phase,moving,mood,self.facing_left,animated)
            bob=abs(math.sin(self.phase*12))*1.2 if moving and animated else math.sin(self.phase*2)*.5 if animated else 0
            if mood=='happy' and animated: bob=abs(math.sin(self.phase*5))*8
            x=position.x()-pixmap.width()/2; y=position.y()+36-pixmap.height()-bob
            self.interaction.rect=QRectF(x,y,pixmap.width(),pixmap.height())
            activity_allowed=not moving and self.active_index>=0 and mood not in ('happy','panic') and not self.interaction.active() and not self.interaction.hovered
            if activity_allowed:
                self.interaction.rect=self.activity.draw(p,position,self.items[self.active_index][0],self.day,self.phase,self.mascot,self.actor,self.outfit,animated)
            else:
                if moving: self.activity.key=None
                tickled=animated and self.interaction.active() and self.interaction.kind=='tickle'
                self.interaction.rect=draw_character(p,self.mascot,self.actor,self.outfit,position.x(),position.y()+36,self.phase,
                    moving=moving,gesture='tickle' if tickled else '',left=self.facing_left,
                    angle=math.sin(self.phase*24)*3 if tickled else 0,animated=animated,mood=mood,walk=self.walk_state)
            if mood=='happy':
                p.setPen(QColor('#C7A04B')); p.setFont(QFont('Segoe UI',12)); p.drawText(int(position.x()+pixmap.width()/2+2),int(position.y()-20),'★')
            self.interaction.draw(p,self.rect(),animated)
        else:
            self.interaction.rect=QRectF(); self.interaction.card_rect=QRectF()
            p.setPen(QColor(muted)); p.setFont(QFont('Microsoft YaHei UI',13)); p.drawText(24,90,'没有匹配的任务。新增任务，或换个筛选看看。')
        if self.phase<self.reward_until:
            p.setPen(QColor('#398C73')); p.setFont(QFont('Microsoft YaHei UI',10,QFont.Bold)); p.drawText(24,46,'任务完成 ＋1 份奖励')
        p.end()
