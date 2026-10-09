import random, math, statistics as st, sys
N_ITEMS=97; DAYS=90; DELAY=14; TURNS=10; DAILY_NEW=5
INTERVALS=[0, 10/1440, 1/24, 1, 3, 7]
LEVELS=[1]*35+[2]*40+[3]*22
SCENES=[i%5 for i in range(N_ITEMS)]

def sample_params(rng):
    return dict(a=rng.uniform(1.5,3.5), dd=rng.uniform(0.5,1.5), b=rng.uniform(0.15,0.4),
        tile=rng.uniform(0.6,0.9), ans=rng.uniform(0.25,0.5), pat=rng.uniform(0.15,0.3), first=rng.uniform(0.15,0.3),
        overconf=rng.uniform(0.1,0.45), attend=rng.uniform(0.6,0.95), cuecost=rng.uniform(0.5,1.0))

class Item:
    __slots__=('m','S','last','s','due','seen','lv','sc')
    def __init__(s,lv,sc): s.m=0.05+0.05*(3-lv); s.S=0.2; s.last=0; s.s=0; s.due=0; s.seen=False; s.lv=lv; s.sc=sc

def p0(it,t): return it.m*math.exp(-max(0,t-it.last)/it.S) if it.seen else 0.0

def learn(it,t,P,ok,support):
    # support: share of the success that came from cues (0 = fully self-generated)
    q=p0(it,t)
    if ok:
        e=1-P['cuecost']*support
        it.S*=1+P['a']*e*(1-q)**P['dd']
        it.m+=P['b']*(0.4+0.6*e)*(1-it.m)
    else:
        it.m+=P['b']*0.5*(1-it.m)
        it.S=max(0.2,it.S*0.6)
    it.last=t; it.seen=True

def attempt(rng,q,cues):
    """cues: list of cumulative boosts tried in order (adaptive); returns (ok, support)"""
    if rng.random()<q: return True,0.0
    tot=0.0
    for c in cues:
        tot=tot+(1-tot)*c
        ps=q+(1-q)*tot
        if rng.random()<(ps-q)/(1-q): return True,(ps-q)/ps
    return False,1.0

def run(variant,P,seed):
    rng=random.Random(seed)
    items=[Item(LEVELS[i],SCENES[i]) for i in range(N_ITEMS)]
    order=list(range(N_ITEMS))
    for day in range(DAYS):
        if rng.random()>P['attend']: continue
        newc=0; t=day+0.5
        scene=day%5 if variant.get('block') else None
        queue=[]
        for turn in range(TURNS):
            t+=1/1440*2
            if turn%3==2: continue  # reply turn (receptive), same for all variants
            due=[it for it in items if it.seen and it.due<=t and (scene is None or it.sc==scene)]
            due.sort(key=lambda it:it.s)
            if queue and queue[0][0]<=turn: it=queue.pop(0)[1]
            elif due: it=due[0]
            else:
                fresh=[it for it in items if not it.seen and (scene is None or it.sc==scene)]
                if fresh and newc<DAILY_NEW: it=fresh[0]; newc+=1
                else:
                    rest=[it for it in items if it.seen and (scene is None or it.sc==scene)]
                    if not rest: continue
                    it=min(rest,key=lambda x:x.due)
            q=p0(it,t); new=not it.seen
            mode=variant['policy'](it,P,new)
            ok,sup=attempt(rng,q,mode['cues'])
            # grading seen by the app
            if mode['self']:
                seen_ok = ok or rng.random()<P['overconf']
                graded = 'good' if seen_ok and sup<0.01 else ('soso' if seen_ok else 'bad')
            else:
                graded = 'good' if ok and sup<0.01 else ('soso' if ok else 'bad')
                if mode.get('lenient') and ok: graded='good'
            learn(it,t,P,ok,sup)
            if new: it.s=0; it.due=t; queue.append((turn+2,it))
            elif graded=='good': it.s=min(5,it.s+1); it.due=t+INTERVALS[it.s]
            elif graded=='soso': it.due=t+INTERVALS[1]
            else: it.s=max(0,it.s-2); it.due=t; queue.append((turn+3,it))
    T1=DAYS; T2=DAYS+DELAY
    r1=st.mean(p0(it,T1) for it in items); r2=st.mean(p0(it,T2) for it in items)
    solid=sum(1 for it in items if p0(it,T2)>0.7)
    return r1,r2,solid

def V0(it,P,new):   # current: tiles + answer shown; s>=3 say aloud with answer shown, self-rated
    if new or it.s<3: return dict(cues=[P['ans']+(1-P['ans'])*P['tile']],self=False,lenient=True)
    return dict(cues=[P['ans']],self=True)
def A(it,P,new):    # adaptive hints on demand, answer hidden at first
    if new or it.s<3: return dict(cues=[P['pat'],P['first'],P['ans'],P['tile']],self=False)
    return dict(cues=[P['pat'],P['first'],P['ans']],self=True)
def DC(it,P,new):   # fixed fading by stars, typed from s>=2
    if new or it.s==0: return dict(cues=[P['ans']+(1-P['ans'])*P['tile']],self=False,lenient=True)
    if it.s==1: return dict(cues=[P['pat']+(1-P['pat'])*P['tile']],self=False,lenient=True)
    if it.s==2: return dict(cues=[P['first']],self=False,lenient=True)
    return dict(cues=[],self=False)
def AC(it,P,new):   # adaptive hints + typed (objective) production for s>=3
    if new or it.s<3: return dict(cues=[P['pat'],P['first'],P['ans'],P['tile']],self=False)
    return dict(cues=[P['pat'],P['first'],P['ans']],self=False)
def HYB(it,P,new):  # fading baseline + adaptive extra hints, typed from s>=2
    if new: return dict(cues=[P['ans']+(1-P['ans'])*P['tile']],self=False,lenient=True)
    if it.s<=1: return dict(cues=[P['pat'],P['first'],P['tile']],self=False)
    return dict(cues=[P['pat'],P['first'],P['ans']],self=False)

VARIANTS={'V0 今の方式':dict(policy=V0),'A 段階ヒント':dict(policy=A),'DC 自動で減るヒント':dict(policy=DC),
 'A+C 段階ヒント+入力':dict(policy=AC),'HYB 減るヒント+段階ヒント+入力':dict(policy=HYB),
 'A+C+B 場面固定':dict(policy=AC,block=True)}
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 150
    rng=random.Random(1); params=[sample_params(rng) for _ in range(NP)]
    res={k:[run(v,P,i) for i,P in enumerate(params)] for k,v in VARIANTS.items()}
    base=res['V0 今の方式']
    for k,r in res.items():
        r1=st.mean(x[0] for x in r); r2=st.mean(x[1] for x in r); sol=st.mean(x[2] for x in r)
        win=sum(1 for x,y in zip(r,base) if x[1]>y[1])/len(r)
        print(f"{k:28s} 90日目 {r1*100:5.1f}%  2週間後 {r2*100:5.1f}%  確実に言える {sol:5.1f}問  今の方式に勝つ割合 {win*100:4.0f}%")
