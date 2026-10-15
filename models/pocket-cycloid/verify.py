"""Independent assembly/motion review, operating on the final OCCT components.

Run from any directory: .venv/Scripts/python models/pocket-cycloid/verify.py
Writes evidence/verification.json beside this source. No exports or UI changes.
"""
from itertools import combinations
from hashlib import sha256
import json
from pathlib import Path
import time

from build123d import Pos, Rot
from project import create_project, overlap_volume


def verify():
    started = time.monotonic()
    document = create_project()
    validation = document.validate().to_dict()
    assert validation['passed'], validation['summary']
    s = {k:v.shape for k,v in document.components.items()}
    pairs = []
    for a,b in combinations(s,2):
        volume = overlap_volume(s[a],s[b])
        assert volume < .001, (a,b,volume)
        pairs.append({'a':a,'b':b,'overlap_mm3':volume})

    paths = []
    def insertion(name, moving, fixed, translations):
        worst=0
        for z in translations:
            worst=max(worst,overlap_volume(Pos(0,0,z)*moving,fixed))
        assert worst<.001, (name,worst)
        paths.append({'name':name,'poses':len(translations),'max_overlap_mm3':worst})

    # Rear-side disc installation is checked before the eccentric is in the cage.
    insertion('disc slides on from rear of input', s['cycloid-disc'], s['eccentric-input'], list(range(-30,1)))
    insertion('carrier enters rear frame',s['output-carrier'],s['rear-frame'],list(range(25,-1,-1)))
    insertion('disc and shaft enter cage together',s['cycloid-disc']+s['eccentric-input'],
              s['rear-frame']+s['output-carrier'],list(range(30,-1,-1)))
    insertion('front frame closes over journals and pin tips',s['front-frame'],
              s['rear-frame']+s['eccentric-input']+s['output-carrier']+s['cycloid-disc'],list(range(20,-1,-1)))
    insertion('crank slides over square tang',s['crank'],s['eccentric-input']+s['front-frame']+s['rear-frame'],list(range(15,-1,-1)))

    # Crank/grip/key against all fixed structure at every 5 degrees.
    rotating=s['crank']+s['crank-key']
    stationary=s['front-frame']+s['rear-frame']
    for k in ('frame-key-1','frame-key-2','frame-key-3'): stationary+=s[k]
    minimum=1e6
    for a in range(0,360,5):
        posed=Rot(0,0,a)*rotating
        assert overlap_volume(posed,stationary)<.001, a
        minimum=min(minimum,posed.distance_to(stationary))
    # Analytic radial envelope is inside every frame key/post; the remaining
    # stationary structure ends below the crank with a 0.5 mm axial gap.
    # Extremes of the intended axial float stay disjoint from fixed geometry.
    end_float=[]
    for shift in (-.3,.3):
        for k in ('eccentric-input','cycloid-disc','output-carrier'):
            posed=Pos(0,0,shift)*s[k]
            for frame in ('rear-frame','front-frame'):
                v=overlap_volume(posed,s[frame]); assert v<.001,(k,shift,frame,v)
            end_float.append({'part':k,'shift_mm':shift,'fixed_overlap_mm3':0})
    root=Path(__file__).parent
    result={'source_sha256':{name:sha256((root/name).read_bytes()).hexdigest() for name in ('project.py','verify.py')},
            'component_bounds_mm':{k:{'min':list(v.bounding_box().min),'max':list(v.bounding_box().max)} for k,v in s.items()},
            'validation':validation,'all_assembled_pairs':pairs,'assembly_paths':paths,
            'crank_sweep':{'poses':72,'minimum_stationary_clearance_mm':minimum},
            'axial_float_checks':end_float,'motion':document.metadata['motion_evidence'],
            'elapsed_seconds':time.monotonic()-started,
            'limitations':['Assembly paths sampled at 1 mm; cotters require elastic insertion.',
                           'No print, torque, friction, flexural life or manufacturing error test performed.']}
    out=Path(__file__).parent/'evidence'/'verification.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'checks':validation['summary'],'assembly_paths':paths,
                      'crank_sweep':result['crank_sweep'],'motion':result['motion'],
                      'seconds':result['elapsed_seconds']},indent=2))


if __name__=='__main__':
    verify()
