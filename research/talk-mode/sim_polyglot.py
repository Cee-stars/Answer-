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

# ===================== polyglot extension =====================
# 追加仮定(明示):
#  F 自動化(即答できる度合い) f in [0,1]: 手がかりなしで自力産出に成功すると伸びる。
#    時間制限つき(timed)なら kf、なしなら kf*untimed_ratio。ヒント付き成功は kf*0.15。f は30日スケールでゆっくり減衰。
#    「瞬時に言える」= 14日後の想起確率>0.7 かつ f>0.5。
#  SH シャドーイング(聞く→まねる): 新出時に音声を聞いて2回まねる。記憶の土台 m を b*sh だけ上げる(S は伸びない=想起ではない)、f を少し上げる。
#  ASR 音声入力の判定: 正しく言えたのに不合格 fr(日本人の発音で10-25%)、間違いを合格 fa(3-10%)。不合格時は「聞き直して判定」ボタン→自己判定に戻る(そのとき甘さ overconf*0.5)。
#  時間コスト(秒): タイル30(+ヒント1段8) / 入力25 / 口頭+自己評価12 / 口頭ASR 8(+ヒント1段4) / 返事4択10 / シャドーイング12。
#  budget: 1日の練習時間を V0 の10ターン相当の平均秒数に揃えた比較も行う(公平比較)。
def sample_extra(rng):
    return dict(kf=rng.uniform(0.15,0.35), untimed=rng.uniform(0.3,0.7), sh=rng.uniform(0.2,0.6),
                fr=rng.uniform(0.10,0.25), fa=rng.uniform(0.03,0.10), Sf=rng.uniform(20,60))

def runP(variant,P,seed):
    rng=random.Random(seed)
    items=[Item(LEVELS[i],SCENES[i]) for i in range(N_ITEMS)]
    F=[0.0]*N_ITEMS; Flast=[0.0]*N_ITEMS; idx={id(it):i for i,it in enumerate(items)}
    turns=variant.get('turns',TURNS); budget=variant.get('budget'); dnew=variant.get('new',DAILY_NEW)
    reask=variant.get('reask',False); reply_prod=variant.get('reply_prod',False)
    secs_total=0; prod_total=0
    def decayF(i,t): return F[i]*math.exp(-max(0,t-Flast[i])/P['Sf'])
    for day in range(DAYS):
        if rng.random()>P['attend']: continue
        newc=0; t=day+0.5; queue=[]; used=0; turn=0
        while True:
            if budget is None and turn>=turns: break
            if budget is not None and used>=budget: break
            t+=1/1440*2
            if turn%3==2 and not reply_prod:
                used+=10; secs_total+=10; turn+=1; continue
            due=[it for it in items if it.seen and it.due<=t]
            due.sort(key=lambda it:it.s)
            if queue and queue[0][0]<=turn: it=queue.pop(0)[1]
            elif due: it=due[0]
            else:
                fresh=[it for it in items if not it.seen]
                if fresh and newc<dnew: it=fresh[0]; newc+=1
                else:
                    rest=[it for it in items if it.seen]
                    if not rest: turn+=1; continue
                    it=min(rest,key=lambda x:x.due)
            i=idx[id(it)]; new=not it.seen
            mode=variant['policy'](it,P,new)
            cost=mode['cost']
            if new and mode.get('shadow'):
                # listen & imitate before first retrieval: encoding without retrieval
                it.m+=P['b']*P['sh']*(1-it.m); it.seen=True; it.last=t; F[i]=decayF(i,t)+0.05*(1-F[i]); Flast[i]=t
                cost+=12
            q=p0(it,t)
            ok,sup=attempt(rng,q,mode['cues'])
            nh=0 if sup<0.01 and ok else (len(mode['cues']) if not ok else max(1,round(sup*len(mode['cues']))))
            cost+=nh*mode.get('hintcost',8)
            g=mode['grade']
            if g=='self':
                seen_ok = ok or rng.random()<P['overconf']
                graded = 'good' if seen_ok and sup<0.01 else ('soso' if seen_ok else 'bad')
            elif g=='asr':
                if ok: rec = rng.random()>P['fr'] or rng.random()<0.5  # 不合格→聞き直しで半分は救済
                else: rec = rng.random()<P['fa'] or rng.random()<P['overconf']*0.5*0.5
                graded = 'good' if rec and sup<0.01 else ('soso' if rec else 'bad')
            else:
                graded = 'good' if ok and sup<0.01 else ('soso' if ok else 'bad')
                if mode.get('lenient') and ok: graded='good'
            learn(it,t,P,ok,sup)
            fi=decayF(i,t)
            if ok and sup<0.01: fi+=P['kf']*(1 if mode.get('timed') else P['untimed'])*(1-fi)
            elif ok: fi+=P['kf']*0.15*(1-fi)
            F[i]=fi; Flast[i]=t
            if mode.get('spoken'): prod_total+=1
            used+=cost; secs_total+=cost
            if new:
                it.s=0; it.due=t; queue.append((turn+2,it))
                if reask: queue.append((turn+5,it))
            elif graded=='good': it.s=min(5,it.s+1); it.due=t+INTERVALS[it.s]
            elif graded=='soso':
                it.due=t+INTERVALS[1]
                if reask: queue.append((turn+3,it))   # ヒントで言えた→セット内でもう一度自力で
            else: it.s=max(0,it.s-2); it.due=t; queue.append((turn+3,it))
            queue.sort(key=lambda x:x[0])
            turn+=1
    T1=DAYS; T2=DAYS+DELAY
    r2=st.mean(p0(it,T2) for it in items)
    solid=sum(1 for it in items if p0(it,T2)>0.7)
    fluent=sum(1 for k,it in enumerate(items) if p0(it,T2)>0.7 and decayF(k,T2)>0.5)
    return r2,solid,fluent,secs_total/max(1,DAYS*P['attend']),prod_total/ (DAYS*P['attend'])

C=lambda P:P['ans']+(1-P['ans'])*P['tile']
def pV0(it,P,new):
    if new or it.s<3: return dict(cues=[C(P)],grade='typed',lenient=True,cost=30,hintcost=0)
    return dict(cues=[P['ans']],grade='self',cost=12,hintcost=0,spoken=True)
def pA(it,P,new):
    if new or it.s<3: return dict(cues=[P['pat'],P['first'],P['ans'],P['tile']],grade='typed',cost=22)
    return dict(cues=[P['pat'],P['first'],P['ans']],grade='self',cost=12,spoken=True)
# 提案: 聞く→まねる→自力で言う(声・ASR)。新出はシャドーイングから。ヒントは段階式で全部「音声」も付く。
def pS(timed):
    def f(it,P,new):
        cues=[P['pat'],P['first'],P['ans']] + ([P['tile']] if it.s<2 else [])
        return dict(cues=cues,grade='asr',cost=8,hintcost=4,shadow=True,timed=timed and not new and it.s>=1,spoken=True)
    return f
def pSself(it,P,new):  # 声に出す→答えを聞いて自己評価(音声認識なし)
    m=pS(True)(it,P,new); m['grade']='self'; m['cost']=10; return m
def pA_timed(it,P,new):
    m=pA(it,P,new); m['timed']=not new and it.s>=1; return m

def build():
    V={}
    V['V0 今の方式(10ターン)']=dict(policy=pV0)
    V['A 段階ヒント(10ターン)']=dict(policy=pA)
    V['A+時間制限']=dict(policy=pA_timed)
    V['P1 聞く→まねる→言う(声,制限なし)']=dict(policy=pS(False))
    V['P2 P1+5秒即答']=dict(policy=pS(True))
    V['P3 P2+セット内で言い直し']=dict(policy=pS(True),reask=True)
    V['P4 P3+返事ターンも発話に']=dict(policy=pS(True),reask=True,reply_prod=True)
    return V

if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 150
    rng=random.Random(1); params=[sample_params(rng) for _ in range(NP)]
    rng2=random.Random(2); [P.update(sample_extra(rng2)) for P in params]
    def report(title,V,mod=None):
        ps=[dict(P) for P in params]
        if mod: r3=random.Random(5); [mod(P,r3) for P in ps]
        res={k:[runP(v,P,i) for i,P in enumerate(ps)] for k,v in V.items()}
        base=list(res.values())[0]
        print('==',title)
        for k,r in res.items():
            win=sum(1 for x,y in zip(r,base) if x[0]>y[0])/len(r)
            print(f"  {k:30s} 2週間後{st.mean(x[0] for x in r)*100:5.1f}% 確実{st.mean(x[1] for x in r):5.1f}問 瞬時{st.mean(x[2] for x in r):5.1f}問 "
                  f"1日{st.mean(x[3] for x in r)/60:4.1f}分 発話{st.mean(x[4] for x in r):4.1f}回 V0に勝つ{win*100:4.0f}%")
        return res
    V=build()
    res=report('同じ10ターン',V)
    bud=st.mean(x[3] for x in res['V0 今の方式(10ターン)'])
    print('V0の1日平均秒',round(bud))
    VB={'V0 今の方式(10ターン)':V['V0 今の方式(10ターン)'],'A 段階ヒント(10ターン)':V['A 段階ヒント(10ターン)']}
    for k in ['P2 P1+5秒即答','P3 P2+セット内で言い直し','P4 P3+返事ターンも発話に']:
        VB[k+' 同時間']=dict(V[k],budget=bud)
    VB['P4s P4だが自己評価(ASRなし) 同時間']=dict(policy=pSself,reask=True,reply_prod=True,budget=bud)
    VB['P5 P4同時間+新出8']=dict(V['P4 P3+返事ターンも発話に'],budget=bud,new=8)
    VB['P6 P4 1.5倍時間+新出8']=dict(V['P4 P3+返事ターンも発話に'],budget=bud*1.5,new=8)
    VB['P7 P4 同時間+新出3']=dict(V['P4 P3+返事ターンも発話に'],budget=bud,new=3)
    report('同じ練習時間(V0と同じ秒数)',VB)
    key=['V0 今の方式(10ターン)','A 段階ヒント(10ターン)','P4 P3+返事ターンも発話に 同時間']
    VK={k:VB[k] for k in key}
    report('感度: 時間制限の効果が小さい(untimed≈timed)',VK,lambda P,r:P.update(untimed=r.uniform(0.85,1.0)))
    report('感度: シャドーイング効果ほぼ無し',VK,lambda P,r:P.update(sh=r.uniform(0,0.05)))
    report('感度: 音声認識が日本人発音に厳しい(fr 30-45%)',VK,lambda P,r:P.update(fr=r.uniform(0.3,0.45),fa=r.uniform(0.08,0.15)))
    report('感度: 自己評価が正直な人',VK,lambda P,r:P.update(overconf=r.uniform(0,0.05)))
