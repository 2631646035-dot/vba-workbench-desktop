"""Sprite playback with aligned feet and a common scale for every frame."""
from pathlib import Path
from PySide6.QtCore import Qt,QRect
from PySide6.QtGui import QPixmap, QRegion, QTransform, QPainter,QImage

ASSETS=Path(__file__).parent/'assets'
OUTFITS=('通勤','泰式休闲','海岛度假')
ACTORS=('小马','腊肠犬','猴子','小猫')

def sprite_regions(atlas):
    """Find nine silhouettes, not nominal cells: generated poses can cross grids."""
    image=atlas.toImage().scaled(251,251,Qt.IgnoreAspectRatio,Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888)
    data=bytes(image.constBits()); stride=image.bytesPerLine(); size=251
    remaining={y*size+x for y in range(size) for x in range(size) if data[y*stride+x*4+3]>48}
    groups=[]
    while remaining:
        seed=remaining.pop(); stack=[seed]; group=[seed]
        while stack:
            value=stack.pop(); x=value%size; y=value//size
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                xx=x+dx; yy=y+dy; neighbor=yy*size+xx
                if 0<=xx<size and 0<=yy<size and neighbor in remaining:
                    remaining.remove(neighbor); stack.append(neighbor); group.append(neighbor)
        if len(group)>70:
            xs=[i%size for i in group]; ys=[i//size for i in group]
            groups.append((len(group),min(xs),min(ys),max(xs),max(ys)))
    groups=sorted(groups,reverse=True)[:9]
    if len(groups)!=9: return []
    groups.sort(key=lambda g:(g[2]+g[4])/2)
    ordered=[]
    for row in range(3): ordered.extend(sorted(groups[row*3:row*3+3],key=lambda g:g[1]))
    sx=atlas.width()/size; sy=atlas.height()/size
    return [QRect(round(x0*sx)-3,round(y0*sy)-3,round((x1-x0+1)*sx)+6,round((y1-y0+1)*sy)+6).intersected(atlas.rect()) for _,x0,y0,x1,y1 in ordered]

class MascotAnimation:
    def __init__(self):
        self.atlases={}; self.cache={}; self.actions={}
        for key,name in [('小马','horse_office_v4.png'),('腊肠犬','dog_office_v4.png'),('猴子','monkey_office_v4.png')]:
            atlas=QPixmap(str(ASSETS/name)); frames=[]
            if not atlas.isNull():
                for i in range(6):
                    left=round((i%3)*atlas.width()/3); top=round((i//3)*atlas.height()/2)
                    right=round((i%3+1)*atlas.width()/3); bottom=round((i//3+1)*atlas.height()/2)
                    frame=atlas.copy(left,top,right-left,bottom-top)
                    rect=QRegion(frame.mask()).boundingRect() if frame.hasAlphaChannel() else frame.rect()
                    frames.append(frame.copy(rect) if not rect.isEmpty() else frame)
                factor=min(86/max(f.height() for f in frames),100/max(f.width() for f in frames))
                frames=[f.scaled(max(1,round(f.width()*factor)),max(1,round(f.height()*factor)),Qt.IgnoreAspectRatio,Qt.SmoothTransformation) for f in frames]
            self.atlases[key]=frames
        for actor,name in zip(ACTORS,('horse','dog','monkey','cat')):
            atlas=QPixmap(str(ASSETS/(name+'_wardrobe_v2.png' if name=='cat' else name+'_wardrobe_v1.png'))); poses=[]
            if not atlas.isNull():
                regions=sprite_regions(atlas)
                for row in range(3):
                    raw=[]
                    for col in range(3):
                        cell=atlas.copy(regions[row*3+col]) if regions else atlas.copy(round(col*atlas.width()/3),round(row*atlas.height()/3),round((col+1)*atlas.width()/3)-round(col*atlas.width()/3),round((row+1)*atlas.height()/3)-round(row*atlas.height()/3))
                        rect=QRegion(cell.mask()).boundingRect()
                        raw.append(cell.copy(rect) if not rect.isEmpty() else cell)
                    # One scale for standing/seated/reclining preserves body size.
                    factor=min(82/max(f.height() for f in raw),112/max(f.width() for f in raw))
                    poses.extend(f.scaled(max(1,round(f.width()*factor)),max(1,round(f.height()*factor)),Qt.IgnoreAspectRatio,Qt.SmoothTransformation) for f in raw)
            self.actions[actor]=poses
        if self.actions.get('小猫'):
            cat=self.actions['小猫'][0]
            self.atlases['小猫']=[cat]*6
        self.fallback=QPixmap(str(ASSETS/'farm_pony.png')).scaled(72,72,Qt.KeepAspectRatio,Qt.SmoothTransformation)

    @staticmethod
    def frame_index(seconds,moving,mood='idle',animated=True):
        if mood=='happy': return 4
        if moving and animated: return int(seconds*8)%4
        return 5 if mood in ('tired','panic') else 1

    def frame(self,actor,seconds,moving,mood='idle',left=False,animated=True):
        frames=self.atlases.get(actor) or self.atlases.get('小马'); index=self.frame_index(seconds,moving,mood,animated)
        if not frames: return self.fallback,index
        key=(actor,index,left)
        if key not in self.cache:
            self.cache[key]=frames[index].transformed(QTransform().scale(-1,1)) if left else frames[index]
        return self.cache[key],index

    def smooth_frame(self,actor,seconds,moving,mood='idle',left=False,animated=True):
        if actor not in ('腊肠犬','猴子','小马') or mood=='happy' or not moving or not animated or not self.atlases.get(actor):
            return self.frame(actor,seconds,moving,mood,left,animated)
        cycle=seconds*10; index=int(cycle)%4
        key=('steady-body',actor,index,left)
        if key not in self.cache:
            frames=self.atlases[actor]; current=frames[index]; body=frames[0]
            canvas=QPixmap(max(f.width() for f in frames[:4]),max(f.height() for f in frames[:4])); canvas.fill(Qt.transparent)
            painter=QPainter(canvas)
            painter.drawPixmap((canvas.width()-current.width())//2,canvas.height()-current.height(),current)
            # Never fade the entire dog's body: generated pose silhouettes differ.
            # Keep the head/torso identical while only the lower leg area changes.
            cut=round(canvas.height()*.70); painter.setClipRect(0,0,canvas.width(),cut)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(0,0,canvas.width(),cut,Qt.transparent)
            painter.drawPixmap((canvas.width()-body.width())//2,canvas.height()-body.height(),body)
            painter.end()
            self.cache[key]=canvas.transformed(QTransform().scale(-1,1)) if left else canvas
        return self.cache[key],index

    def action_frame(self,actor,outfit='通勤',pose='stand',left=False):
        row=OUTFITS.index(outfit) if outfit in OUTFITS else 0
        col={'stand':0,'sit':1,'rest':2}.get(pose,0)
        frames=self.actions.get(actor)
        if not frames: return self.frame(actor,0,False)[0]
        key=('action',actor,row,col,left)
        if key not in self.cache:
            pix=frames[row*3+col]
            self.cache[key]=pix.transformed(QTransform().scale(-1,1)) if left else pix
        return self.cache[key]

    def dressed_frame(self,actor,outfit,seconds,moving,mood='idle',left=False,animated=True):
        if outfit=='通勤' and actor!='小猫':
            return self.smooth_frame(actor,seconds,moving,mood,left,animated)
        return self.action_frame(actor,outfit,'stand',left),0
