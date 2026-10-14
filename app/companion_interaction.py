"""Read-only companion reactions shared by the main view and floating list."""
import math
import time
from PySide6.QtCore import Qt,QPointF,QRectF,QTimer
from PySide6.QtGui import QColor,QFont,QPen,QPainter
from PySide6.QtWidgets import QWidget
from mascot_animation import MascotAnimation
from character_motion import draw_character

class CompanionInteraction:
    def __init__(self):
        self.rect=QRectF(); self.card_rect=QRectF(); self.hovered=False
        self.until=0.; self.started=0.; self.kind=''; self.task=None; self.selection=0

    def active(self): return time.monotonic()<self.until

    def react(self,kind,pending):
        self.kind=kind; self.started=time.monotonic(); self.until=self.started+(6 if kind=='offer' else 2)
        self.task=None; self.card_rect=QRectF()
        if kind=='offer':
            ranked=sorted(pending,key=lambda t:({'高':0,'中':1,'低':2}.get(t.get('priority'),1),t.get('title','')))
            if ranked:
                self.task=ranked[self.selection%len(ranked)]; self.selection+=1

    def mood(self,default):
        return 'happy' if self.hovered or (self.active() and self.kind=='tickle') else default

    def draw(self,p,bounds,animated=True):
        self.card_rect=QRectF()
        if not self.active(): return
        offer=self.kind=='offer'; width=min(255,max(100,bounds.width()-16)); height=108 if offer and self.task else 36
        target=QRectF(min(max(8,self.rect.center().x()-width/2),max(8,bounds.width()-width-8)),max(8,self.rect.top()-height-12),width,height)
        progress=min(1,(time.monotonic()-self.started)/.75) if animated else 1
        # Toss a little task card out of the character, ending at a readable bubble.
        origin=QPointF(self.rect.center().x()-width/2,self.rect.top())
        position=origin+(target.topLeft()-origin)*progress+QPointF(0,-math.sin(progress*math.pi)*38)
        card=QRectF(position,target.size()); self.card_rect=card if offer and self.task and progress>=1 else QRectF()
        p.save(); p.translate(card.center()); p.rotate(math.sin(progress*math.pi)*-16 if offer else 0)
        scale=.25+.75*progress if offer else 1; p.scale(scale,scale); card=QRectF(-width/2,-height/2,width,height)
        p.setPen(Qt.NoPen); p.setBrush(QColor(28,62,48,24)); p.drawRoundedRect(card.translated(0,4),12,12)
        p.setPen(QPen(QColor('#80AD9C'),1)); p.setBrush(QColor('#FFFFFF')); p.drawRoundedRect(card,10,10)
        p.setPen(QColor('#284F40')); p.setFont(QFont('Microsoft YaHei UI',9,QFont.Bold))
        if offer and self.task:
            priority=self.task.get('priority','中'); color={'高':'#DD796E','中':'#D5AC55','低':'#54AFA1'}.get(priority,'#D5AC55')
            p.setPen(Qt.NoPen); p.setBrush(QColor(color)); p.drawEllipse(QPointF(card.x()+17,card.y()+17),4,4)
            p.setPen(QColor('#66877A')); p.setFont(QFont('Microsoft YaHei UI',8)); p.drawText(QPointF(card.x()+28,card.y()+21),'待做任务 · '+priority+'优先')
            p.setPen(QColor('#284F40')); p.setFont(QFont('Microsoft YaHei UI',10,QFont.Bold))
            title=p.fontMetrics().elidedText(self.task['title'],Qt.ElideRight,int(width-24))
            p.drawText(card.adjusted(12,33,-12,-38),Qt.AlignTop|Qt.TextWordWrap,title)
            p.setPen(QColor('#7B948A')); p.setFont(QFont('Microsoft YaHei UI',8))
            estimate=str(self.task.get('minutes',0))+' 分钟' if self.task.get('minutes') else '未估时'
            p.drawText(QPointF(card.x()+12,card.bottom()-29),estimate+' · '+('周期任务' if self.task.get('repeat') else '普通任务'))
            p.setPen(QPen(QColor('#DDE8E2'),1)); p.drawLine(QPointF(card.x()+12,card.bottom()-22),QPointF(card.right()-12,card.bottom()-22))
            p.setPen(QColor('#398C73')); p.drawText(card.adjusted(12,height-21,-12,-2),Qt.AlignVCenter|Qt.AlignHCenter,'快去干这个 → 点击查看')
        else:
            title='今天清空了，先歇会儿。' if offer else '嘿，痒！别闹啦。'
            p.drawText(card.adjusted(10,4,-10,-4),Qt.AlignTop|Qt.AlignHCenter,title)
        p.restore()

class FloatingCompanion(QWidget):
    def __init__(self,store,page,parent=None):
        super().__init__(parent); self.store=store; self.page=page; self.setMouseTracking(True); self.setFixedHeight(196)
        self.interaction=CompanionInteraction(); self.mascot=MascotAnimation(); self.started=time.monotonic()
        self.timer=QTimer(self); self.timer.setInterval(16); self.timer.timeout.connect(self.animate)
        self.setToolTip('悬停：开心 · 点击：挠痒 · 右键：抛一个待做任务')

    def animate(self):
        if self.isVisible() and not self.window().isMinimized(): self.update()

    def showEvent(self,event):
        super().showEvent(event)
        if self.store.setting('motion','yes')=='yes': self.timer.start()
    def hideEvent(self,event):
        if hasattr(self,'timer'): self.timer.stop()
        super().hideEvent(event)
    def pending(self):
        from datetime import date
        return [t for t,done in self.store.today(date.today().isoformat()) if not done]
    def mouseMoveEvent(self,event):
        self.interaction.hovered=self.interaction.rect.contains(event.position()); self.update()
    def leaveEvent(self,event): self.interaction.hovered=False; self.update()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and self.interaction.card_rect.contains(event.position()) and self.interaction.task:
            current=next((t for t in self.pending() if t['id']==self.interaction.task['id']),None)
            if current: self.page.open_plot(current)
            self.window().refresh(); return
        if self.interaction.rect.contains(event.position()) and event.button() in (Qt.LeftButton,Qt.RightButton):
            self.interaction.react('offer' if event.button()==Qt.RightButton else 'tickle',self.pending()); self.update()
            QTimer.singleShot(6100 if event.button()==Qt.RightButton else 2100,self.update)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        elapsed=time.monotonic()-self.started; animated=self.timer.isActive(); mood=self.interaction.mood('idle')
        sprite,_=self.mascot.dressed_frame(self.page.actor,getattr(self.page,'outfit','通勤'),elapsed,False,mood)
        x=(self.width()-sprite.width())/2; y=self.height()-sprite.height()-3
        self.interaction.rect=QRectF(x,y,sprite.width(),sprite.height())
        tickled=animated and self.interaction.active() and self.interaction.kind=='tickle'
        self.interaction.rect=draw_character(p,self.mascot,self.page.actor,getattr(self.page,'outfit','通勤'),self.width()/2,self.height()-3,elapsed,
            gesture='tickle' if tickled else '',animated=animated,mood=mood)
        self.interaction.draw(p,self.rect(),animated); p.end()
