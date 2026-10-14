"""Export the app's existing layered artwork and rig dimensions for Blender."""
import os,sys,json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from mascot_animation import MascotAnimation,ACTORS,OUTFITS
from character_motion import PROFILES
from leg_rig import layers,LEG_PROPORTIONS

def main():
    app=QApplication.instance() or QApplication([])
    mascot=MascotAnimation(); target=ROOT/'animation_studio'/'textures'; target.mkdir(parents=True,exist_ok=True)
    for item in LEG_PROPORTIONS.values(): item['hip_gap']*=4
    models=[]
    for actor_index,actor in enumerate(ACTORS):
        for outfit_index,outfit in enumerate(OUTFITS):
            original=mascot.action_frame(actor,outfit,'stand')
            # Extend only the monkey's legs, preserving its head and torso size.
            extension=8 if actor=='猴子' else 0
            large=original.scaled(original.width()*4,(original.height()+extension)*4,Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
            body,legs,definitions=layers(mascot,actor,outfit,large,leg_extension=extension*4)
            key=f'{actor_index}_{outfit_index}'
            textures=[]
            for part,pix in zip(('body','far','near'),(body,*legs)):
                filename=f'{key}_{part}.png'; pix.save(str(target/filename)); textures.append('textures/'+filename)
            models.append(dict(id=key,actor=actor,outfit=outfit,width=original.width(),height=original.height()+extension,
                textures=textures,legs=definitions,step=PROFILES[actor]['step'],period=PROFILES[actor]['period']))
    (ROOT/'animation_studio'/'models.json').write_text(json.dumps(models,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Prepared {len(models)} editable character/outfit rigs.')

if __name__=='__main__': main()
