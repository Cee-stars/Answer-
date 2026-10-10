# sim_ling3b.py -- 第2回会議 FINAL3 の検証(言語学者)。sim_ling3.py の記憶モデルを使う。
# 単語プール: bands.json(339語, 帯1-5)＋フレーズ69(帯2相当)。帯→難度 d: 1:-1.2 2:0 3:1.0 4:1.8 5:2.5
# バトル10分(600秒)＋おまけ2分(120秒, 日替わり: 言い換え/例文空所/スピード/しりとり早押し)。おまけは★を上げない。
# 追加の仮定:
#  言い換え(アンカー方式): 類義・対義グループの語で、相手が既知/★3以上のときだけ出題。3択(関係)を客観採点。
#     意味が出れば自力想起として学習(×(1+rel))、dueを残り間隔の50%だけ延ばす。×は due=今(次のバトルで要確認)。8秒/問。
#  例文空所(★3以上): 3秒頭に浮かべる(産出: q*prodpen)→4択(推測で当たる率0.4, 手がかり扱い)。失敗→10分後に再確認、★は下げない。10秒/問。
#  スピード: 既知・★3以上の語を含む文、6秒で2語。即答度F↑、S×1.08。
#  しりとり早押し: 期限が来た語/★1以上。意味＋頭文字→英語を想起(産出, 頭文字ヒントで+0.2)→4択確認。6秒/問。
#     正解: 即答度↑(時間制限つき)・記憶も学習、★不変。誤答: ★-1。
#  継続効果 v: おまけのある方式だけ、休む日が v の割合で減る。
#  別解×: 言い換えで正しいのに×になる率 alt=0.1-0.25(要確認として次のバトルへ=時間の無駄＋自信低下は未モデル)。
import random, math, statistics as st, sys, json, os
import sim_ling3 as S
from sim_ling3 import learn, bumpF, known_p, interf, pk, Fv, INTERVALS
HERE=os.path.dirname(os.path.abspath(__file__))
bands=json.load(open(os.path.join(HERE,'bands.json')))
DMAP={1:-1.2,2:0.0,3:1.0,4:1.8,5:2.5}
S.BAND=[DMAP[b] for b in bands.values()]+[0.0]*69
S.NWORDS=len(S.BAND)
DAYS=60; DELAY=14

def run2(V,P,seed):
    rng=random.Random(seed); ws=S.build(rng,P)
    groups={}
    for w in ws:
        if w.g>=0: groups.setdefault(w.g,[]).append(w)
    order=sorted(ws,key=lambda w:w.d)   # アプリは易しい順に出す想定
    flu0=sum(1 for w in ws if w.known0 and w.m>0.7 and w.F0>0.5)
    att=P['attend']
    if V.get('extra'): att=att+P['v']*(1-att)
    rot=V.get('extra',[])
    days=0; gl={}
    for day in range(DAYS):
        if rng.random()>att: continue
        days+=1; t=day+0.5; used=0; newc=0
        if V.get('diag') and days==1:
            used+=90
            th=P['theta']+rng.gauss(0,P['sigma'])
            for w in ws:
                if pk(th,w.d)>0.85:
                    w.seen=True; w.s=3; w.due=day+rng.uniform(1,14)
                    if w.known0: w.m=0.95; w.S=2000; w.last=0
                    else: w.m=0.0; w.S=0.3; w.last=0
            order=sorted([w for w in ws if not w.seen],key=lambda w:-pk(th,w.d))
        # ---- バトル ----
        B=V['battle']; queue=[]; turn=0
        dues=sorted([w for w in ws if w.seen and w.due<=t+0.01],key=lambda w:(w.s,w.due)); di=0
        while used<B:
            t+=1/1440
            if queue and queue[0][0]<=turn: w=queue.pop(0)[1]
            elif di<len(dues): w=dues[di]; di+=1
            else:
                fw=next((x for x in order if not x.seen),None) if newc<10 else None
                if fw is not None: w=fw; newc+=1
                else:
                    rest=[x for x in ws if x.seen]
                    if not rest: break
                    w=min(rest,key=lambda x:x.due)
            if not w.seen:
                I=interf(w,ws,groups,t,P); used+=8; turn+=1
                if w.known0 and rng.random()<known_p(w,t):
                    w.seen=True; w.last=t; w.lastp=t; w.s=1; w.due=t+INTERVALS[1]
                else:
                    w.m=0.35*(1-I)+(P['ctxb'] if V.get('ctx') else 0); w.S=0.8; w.seen=True; w.last=t; w.lastp=t
                    w.s=0; w.due=t; queue.append((turn+2,w))
                continue
            q0=known_p(w,t); I=interf(w,ws,groups,t,P)
            ok=rng.random()<q0*(1-I); cost=6; mult=1.0
            if not ok:
                if V.get('ctx'): cost+=7; mult=1+P['ctxb']*1.5
                else: cost+=3
            seen_ok=ok or rng.random()<P['overconf']
            learn(w,t,P,ok,0.0,q0,mult)
            if ok: bumpF(w,t,P,P['kf'])
            if seen_ok: w.s=min(5,w.s+1); w.due=t+INTERVALS[w.s]
            else: w.s=max(0,w.s-2); w.due=t; queue.append((turn+3,w))
            queue.sort(key=lambda x:x[0]); used+=cost; turn+=1
        # ---- おまけ(2分) ----
        if not rot: continue
        mode=rot[days%len(rot)]; u=0; E=120
        strong=lambda o:(o.known0 and not o.seen) or (o.seen and o.s>=3)
        if mode=='syn':
            cands=[w for w in ws if w.g>=0 and w.seen and 1<=w.s<=4 and any(strong(o) for o in groups[w.g] if o is not w)]
            rng.shuffle(cands); usedg=set()
            for w in cands:
                if u>=E: break
                if w.g in usedg or t-gl.get(w.g,-9)<3: continue
                usedg.add(w.g); gl[w.g]=t; t+=8/86400; u+=8
                o=next(o for o in groups[w.g] if o is not w and strong(o))
                q0=known_p(w,t); I=interf(w,ws,groups,t,P,partner=o)
                know=rng.random()<q0*(1-I)
                rel_ok=know or rng.random()<1/3
                if V.get('altx') and rel_ok and rng.random()<P['alt']: rel_ok=False
                learn(w,t,P,know,0.0 if know else 0.8,q0,(1+P['rel'])*(1-I) if know else 1.0)
                bumpF(o,t,P,P['kf']*0.4)
                if rel_ok and know: w.due=w.due+0.5*max(0,w.due-t)
                elif not rel_ok: w.due=t
        elif mode=='cloze':
            cands=sorted([w for w in ws if w.seen and w.s>=3],key=lambda w:w.due)
            for w in cands:
                if u>=E: break
                t+=10/86400; u+=10
                q0=known_p(w,t); I=interf(w,ws,groups,t,P)
                rec=rng.random()<q0*P['prodpen']*(1-I)
                if rec:
                    learn(w,t,P,True,0.0,q0,1+P['ctxb']*2,1+P['gen']); bumpF(w,t,P,P['kf']*0.6)
                else:
                    g=rng.random()<0.4+0.6*q0
                    learn(w,t,P,g,0.8 if g else 1.0,q0,1+P['ctxb'])
                    w.due=min(w.due,t+INTERVALS[1])
        elif mode=='speed':
            pool=[w for w in ws if strong(w)]
            while u<E and pool:
                t+=6/86400; u+=6
                for w in rng.sample(pool,min(2,len(pool))):
                    if rng.random()<known_p(w,t):
                        bumpF(w,t,P,P['kf']*0.6)
                        if w.seen: w.S*=1.08
        elif mode=='shiri':
            cands=sorted([w for w in ws if w.seen and (w.due<=t+1 or w.s>=1)],key=lambda w:w.due)
            for w in cands:
                if u>=E: break
                t+=6/86400; u+=6
                q0=known_p(w,t); I=interf(w,ws,groups,t,P)
                q=q0*P['prodpen']*(1-I); q=q+(1-q)*0.2*q0
                ok=rng.random()<q
                learn(w,t,P,ok,0.0,q0)
                if ok: bumpF(w,t,P,P['kf'])
                else: w.s=max(0,w.s-1); w.due=min(w.due,t+INTERVALS[1])
    T2=DAYS+DELAY
    unk=[w for w in ws if not w.known0]
    ret=st.mean(known_p(w,T2) for w in unk) if unk else 0
    solid=sum(1 for w in unk if known_p(w,T2)>0.7)
    flu=sum(1 for w in ws if known_p(w,T2)>0.7 and Fv(w,T2,P)>0.5)-flu0
    return ret,solid,flu,days

ROT=['syn','cloze','speed','shiri']
F3=dict(battle=600,extra=ROT,diag=True,ctx=True)
def minus(**kw): d=dict(F3); d.update(kw); return d
VARS={
 'V0 バトル10分':dict(battle=600),
 'FINAL3 10分+おまけ2分':F3,
 'FINAL3-time バトル12分(診断+例文)':dict(battle=720,diag=True,ctx=True),
 'V0-12 今のバトル12分':dict(battle=720),
 '-診断':minus(diag=False),
 '-言い換え':minus(extra=[m for m in ROT if m!='syn']),
 '-例文(空所も初見例文も)':minus(extra=[m for m in ROT if m!='cloze'],ctx=False),
 '-スピード':minus(extra=[m for m in ROT if m!='speed']),
 '-しりとり早押し':minus(extra=[m for m in ROT if m!='shiri']),
 '言い換えだけ毎日2分':minus(extra=['syn']),
}
def params(NP,mod=None):
    rng=random.Random(1); ps=[]
    for _ in range(NP):
        P=S.sample_params(rng); P.update(v=0.0,alt=rng.uniform(0.1,0.25)); ps.append(P)
    if mod:
        r=random.Random(9)
        for P in ps: mod(P,r)
    return ps
def main(NP,title,mod=None,keys=None,extra_vars=None):
    ps=params(NP,mod); V=dict(VARS); V.update(extra_vars or {})
    keys=keys or list(VARS)
    res={k:[run2(V[k],P,i) for i,P in enumerate(ps)] for k in keys}
    b=res[keys[0]]
    print('==',title)
    print('| 方式 | 未知語の14日後保持 | 定着語 | 即答+ | 練習日数 | V0に勝つ |')
    print('|---|---|---|---|---|---|')
    for k,r in res.items():
        m=[st.mean(x[j] for x in r) for j in range(4)]
        win=sum(1 for x,y in zip(r,b) if x[0]>y[0])/len(r)
        print(f"| {k} | {m[0]*100:.1f}% | {m[1]:.1f} | {m[2]:.1f} | {m[3]:.1f} | {win*100:.0f}% |")
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 100
    main(NP,'基本(継続効果 v=0)')
    K=['V0 バトル10分','FINAL3 10分+おまけ2分','FINAL3-time バトル12分(診断+例文)','-言い換え']
    main(NP,'感度: 継続効果 v=0.3',lambda P,r:P.update(v=0.3),K)
    main(NP,'感度: 干渉強め I=0.35-0.5',lambda P,r:P.update(I=r.uniform(0.35,0.5)),K+['言い換えだけ毎日2分'])
    main(NP,'感度: 別解を×にする',None,['V0 バトル10分','FINAL3 10分+おまけ2分','言い換えだけ毎日2分','言い換えだけ(別解×)'],
         {'言い換えだけ(別解×)':minus(extra=['syn'],altx=True)})
    KD=['V0 バトル10分','FINAL3 10分+おまけ2分','-診断']
    main(NP,'感度: 初級者 θ=-1〜0',lambda P,r:P.update(theta=r.uniform(-1,0)),KD)
    main(NP,'感度: 上級寄り θ=1〜2',lambda P,r:P.update(theta=r.uniform(1,2)),KD)
    main(NP,'感度: 診断の誤差大 σ=0.8-1.2',lambda P,r:P.update(sigma=r.uniform(0.8,1.2)),KD)
