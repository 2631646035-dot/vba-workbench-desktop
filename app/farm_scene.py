"""Full scene task vegetable plots; mascot stays by its stable unless a plot is selected."""
import math
from pathlib import Path
from datetime import date
from PySide6.QtCore import Qt,QTimer,QPointF,QRectF
from PySide6.QtGui import QPainter,QColor,QFont,QPen,QPixmap,QLinearGradient,QPolygonF
from PySide6.QtWidgets import QWidget
from task_store import crop_status

class FarmWorld(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setMinimumHeight(460); self.setMouseTracking(True)
        self.items=[]; self.station_rects=[]; self.phase=0.; self.hover=-1; self.actor='小马'; self.open_task=None
        self.selected_id=None; self.reward_until=0.; self.pony=QPixmap(str(Path(__file__).parent/'assets'/'farm_pony.png'))
        self.timer=QTimer(self); self.timer.setInterval(40); self.timer.timeout.connect(self.tick)
    def tick(self):
        if self.isVisible(): self.phase+=.035; self.update()
    def set_items(self,items):
        self.items=items; cols=max(1,int(max(400,self.width())/270))
        self.setMinimumHeight(max(460,250+math.ceil(len(items)/cols)*190)); self.update()
    def resizeEvent(self,event): super().resizeEvent(event); self.set_items(self.items)
    def mouseMoveEvent(self,event):
        self.hover=next((i for i,r in enumerate(self.station_rects) if r.contains(event.position())),-1)
        self.setCursor(Qt.PointingHandCursor if self.hover>=0 else Qt.ArrowCursor)
        if self.hover>=0: self.setToolTip(self.items[self.hover][0]['title']+' · 点击管理 / 收割')
        self.update()
    def leaveEvent(self,event): self.hover=-1; self.update()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and self.hover>=0:
            self.selected_id=self.items[self.hover][0]['id']; self.update()
            if self.open_task: self.open_task(self.items[self.hover][0])
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        gradient=QLinearGradient(0,0,0,self.height()); gradient.setColorAt(0,QColor('#DBEDD4')); gradient.setColorAt(1,QColor('#B5D69B'))
        p.fillRect(self.rect(),gradient)
        p.setPen(Qt.NoPen)
        for i in range(0,self.width(),110):
            p.setBrush(QColor('#C8DFAE')); p.drawEllipse(QRectF(i-60,-45,200,140))
        # Pale path: the horse does not roam over the vegetables.
        p.setBrush(QColor('#E6D7B4')); p.drawRoundedRect(QRectF(16,155,self.width()-32,35),15,15)
        p.setPen(QPen(QColor('#B19467'),3))
        for x in range(22,self.width()-22,38): p.drawLine(x,135,x,159)
        p.drawLine(22,145,self.width()-22,145)
        p.setPen(QColor('#365543')); p.setFont(QFont('Microsoft YaHei UI',21,QFont.Bold)); p.drawText(32,50,'今天，种点能收获的事。')
        p.setFont(QFont('Microsoft YaHei UI',10)); p.drawText(32,78,'一件任务一块菜田 · 完成收割 · 超期变色，但随时可以补救')
        p.setFont(QFont('Microsoft YaHei UI',9)); p.drawText(32,111,'珊瑚牌＝高优先   金色牌＝中优先   青绿牌＝低优先')
        # Stable area with original character, gentle idle breathing only.
        x=self.width()-200
        p.setBrush(QColor('#A87955')); p.setPen(Qt.NoPen); p.drawRoundedRect(QRectF(x,75,160,70),8,8)
        p.setBrush(QColor('#6C7A50')); p.drawPolygon(QPolygonF([QPointF(x-12,75),QPointF(x+80,28),QPointF(x+172,75)]))
        p.setBrush(QColor('#5E4936')); p.drawRoundedRect(QRectF(x+55,88,50,57),12,12)
        if not self.pony.isNull():
            pixmap=self.pony.scaled(175,175,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            p.drawPixmap(int(x-20),int(4+math.sin(self.phase*2)*2),pixmap)
        else:
            p.setPen(QColor('#365543')); p.drawText(x+15,125,'小马素材载入中')
        p.setPen(QColor('#365543')); p.setFont(QFont('Microsoft YaHei UI',9,QFont.Bold))
        p.drawText(x+80,115,'收割庆祝！' if self.phase<self.reward_until else '今天已收工' if self.items and all(done for _,done in self.items) else '陪你种完这一天')
        cols=max(1,int(self.width()/270)); colwidth=self.width()/cols; self.station_rects=[]
        for i,(task,done) in enumerate(self.items):
            left=i%cols*colwidth+24; top=i//cols*190+215; rect=QRectF(left,top,colwidth-48,150); self.station_rects.append(rect)
            state=crop_status(task,date.today().isoformat(),done); late=state=='late'; lifted=-4 if self.hover==i else 0
            p.setPen(Qt.NoPen); p.setBrush(QColor('#8DAA76')); p.drawRoundedRect(rect.translated(0,8),14,14)
            p.setBrush(QColor('#A8825E' if late else '#815E43')); p.drawRoundedRect(rect.translated(0,lifted),14,14)
            p.setPen(QPen(QColor('#967153'),2))
            for k in range(3): p.drawLine(QPointF(left+15,top+65+k*20),QPointF(left+rect.width()-15,top+65+k*20))
            # Priority sign is separate from freshness colour.
            priority=task.get('priority','中'); colors={'高':'#D97262','中':'#DAAE4F','低':'#4D9E90'}
            p.setPen(Qt.NoPen); p.setBrush(QColor(colors.get(priority,'#DAAE4F'))); p.drawRoundedRect(QRectF(left+12,top-13+lifted,rect.width()-24,34),8,8)
            p.setPen(QColor('#FFFFFF')); p.setFont(QFont('Microsoft YaHei UI',10,QFont.Bold))
            p.drawText(QRectF(left+22,top-10+lifted,rect.width()-44,28),Qt.AlignVCenter,p.fontMetrics().elidedText(task['title'],Qt.ElideRight,int(rect.width()-44)))
            if done:
                p.setPen(Qt.NoPen); p.setBrush(QColor('#D3A26A')); p.drawRoundedRect(QRectF(left+rect.width()/2-35,top+48,70,38),8,8)
                p.setBrush(QColor('#77A75B'))
                for k in range(4): p.drawEllipse(QRectF(left+rect.width()/2-32+k*16,top+35,24,22))
            else:
                for row in range(2):
                    for col in range(4):
                        cx=left+35+col*(rect.width()-70)/3; cy=top+52+row*36
                        p.setPen(Qt.NoPen); p.setBrush(QColor('#806846' if late else '#82B74E')); p.drawEllipse(QRectF(cx-13,cy-11,27,22))
                        p.setBrush(QColor('#A18A5E' if late else '#A7CD68')); p.drawEllipse(QRectF(cx-6,cy-8,17,18))
                        p.setPen(QPen(QColor('#A59068' if late else '#4E8B47'),1)); p.drawArc(QRectF(cx-7,cy-5,13,12),20*16,280*16)
            p.setPen(QColor('#FFF0D8')); p.setFont(QFont('Microsoft YaHei UI',9))
            status='已收割 · 可以撤销' if done else '超期了 · 菜叶蔫了' if late else '新鲜待办 · 点击照料'
            p.drawText(QRectF(left+8,top+112,rect.width()-16,26),Qt.AlignCenter,status)
        if not self.items:
            p.setPen(QColor('#456349')); p.setFont(QFont('Microsoft YaHei UI',14)); p.drawText(32,245,'暂时没有菜田。新增任务，或者换个筛选看看。')
        if self.phase<self.reward_until:
            p.setPen(QColor('#325B36')); p.setFont(QFont('Microsoft YaHei UI',14,QFont.Bold)); p.drawText(32,175,'收割成功！＋1 份收获')
        p.end()
