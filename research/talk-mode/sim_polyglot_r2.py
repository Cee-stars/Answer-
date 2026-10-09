# sim_polyglot_r2.py -- 第2回(多言語実践者担当): FINAL案の要素別寄与。元ファイルは変更しない。
# 土台: pg_ling.py(=sim_linguist.pyの写し: 型の規則/チャンク/準備度/プライミング/転移, 手がかりは(文型,内容))
# 追加: pg_trans.py(=sim_translator.pyの写し)の 意図あいまい→別解(分類A-D, ja書き換え, 別解判定)
#       sim_polyglot.py の 自動化f / まねる(シャドーイング) / 音声認識の誤判定と「合ってた」ボタン / 秒数 / 同時間比較
import random, math, statistics as st, sys
import pg_ling as L, pg_trans as TR
from pg_ling import build_items, Learner, attempt, learn_item, learn_rule, STAGE, FAMS, FAMCOUNT, INTERVALS, DAYS, DELAY
from sim import p0
CLS=[('A' if i in TR._A else 'B' if i in TR._B else 'C' if i in TR._C else 'D') for i in range(len(L.RAW))]

def sample_all(rng):
    P=L.sample_params(rng)
    P.update(ambA=rng.uniform(0.35,0.6), ambB=rng.uniform(0.15,0.3), ambC=rng.uniform(0.25,0.45),
             rwkeep=rng.uniform(0.25,0.55), synfix=rng.uniform(0.6,0.85), ansfix=rng.uniform(0.6,0.8), frust=rng.uniform(0.0,0.006),
             kf=rng.uniform(0.15,0.35), untimed=rng.uniform(0.3,0.7), soft=rng.uniform(0.5,0.9),
             sh=rng.uniform(0.2,0.6), fr=rng.uniform(0.10,0.25), fa=rng.uniform(0.03,0.10),
             okbtn=rng.uniform(0.4,0.8), Sf=rng.uniform(20,60))
    return P

def run(V,P,seed,budget):
    rng=random.Random(seed); items=build_items(); lr=Learner(P)
    CL={id(it):CLS[i] for i,it in enumerate(items)}
    if V.get('order')=='mixed':
        by={f:[it for it in items if it.fam==f] for f in FAMS}; items_new=[]
        while any(by.values()):
            for f in sorted(FAMS,key=lambda f:STAGE[f]):
                if by[f]: items_new.append(by[f].pop(0))
    else: items_new=list(items)
    F={id(it):0.0 for it in items}; Fl={id(it):0.0 for it in items}
    dF=lambda it,t: F[id(it)]*math.exp(-max(0,t-Fl[id(it)])/P['Sf'])
    attend=P['attend']; secs=0; prods=0; days=0
    for day in range(DAYS):
        lr.decay()
        if rng.random()>attend: continue
        days+=1; newc=0; t=day+0.5; queue=[]; prev=None; used=0; turn=0
        while (turn<V['turns']) if V.get('turns') else (used<budget):
            t+=1/1440*2
            if turn%3==2 and not V.get('reply_prod'):
                used+=10; turn+=1; prev=None; continue
            due=sorted([it for it in items if it.seen and it.due<=t],key=lambda it:it.s)
            if queue and queue[0][0]<=turn: it=queue.pop(0)[1]
            elif due: it=due[0]
            else:
                fresh=[it for it in items_new if not it.seen]
                if fresh and newc<5: it=fresh[0]; newc+=1
                else: it=min([x for x in items if x.seen],key=lambda x:x.due)
            primed=prev is not None and prev==it.fam
            new=not it.seen; m=V['policy'](it,new); cost=m['cost']
            if new and V.get('shadow'):
                it.m+=P['b']*P['sh']*(1-it.m); it.seen=True; it.last=t
                F[id(it)]=0.05; Fl[id(it)]=t; cost+=12
            c=CL[id(it)]; amb={'A':P['ambA'],'B':P['ambB'],'C':P['ambC'],'D':0.03}[c]
            if m.get('tile_only'): amb=0
            if V.get('ans_shown'): amb*=1-P['ansfix']
            if V.get('rewrite'): amb*=P['rwkeep'] if c in 'AC' else 0.7
            if V.get('judge') and c in 'BC': amb*=1-P['synfix']
            ok,sup,rc=attempt(rng,it,lr,t,m['cues'],primed)
            alt=False
            if ok and sup<0.01 and rng.random()<amb:   # 正しいが別の言い方をした
                alt=True
                if V.get('judge'): sup=0.3; graded='soso'       # ◯通じる→型で言い直し
                elif m['grade']=='self': sup=0.5; graded='soso'
                else:                                           # 完全一致で×→次のヒントへ
                    attend*=1-P['frust']
                    ok,sup,rc=attempt(rng,it,lr,t,m['cues'][1:],primed)
                    if ok: sup=max(sup,0.5)
                    graded='soso' if ok else 'bad'
            nh=0 if (ok and sup<0.01) else (len(m['cues']) if not ok else max(1,round(sup*len(m['cues']))))
            cost+=nh*m.get('hc',8)
            if not alt:
                g=m['grade']
                if g=='self': so=ok or rng.random()<P['overconf']
                elif g=='asr':
                    if ok:
                        so=rng.random()>P['fr']
                        if not so: cost+=5; so=rng.random()<P['okbtn']        # 誤って不合格→「合ってた」
                    else: so=rng.random()<P['fa'] or rng.random()<P['overconf']*P['okbtn']*0.5
                else: so=ok
                graded='good' if so and sup<0.01 else ('soso' if so else 'bad')
                if m.get('lenient') and ok: graded='good'
            if primed: rc*=1-P['prime']
            learn_item(it,t,P,ok,sup); learn_rule(lr,it,ok,rc,primed)
            fi=dF(it,t)
            if ok and sup<0.01: fi+=P['kf']*(P['soft'] if m.get('timed') else P['untimed'])*(1-fi)
            elif ok: fi+=P['kf']*0.15*(1-fi)
            F[id(it)]=fi; Fl[id(it)]=t
            if m.get('spoken'): prods+=1
            prev=it.fam; used+=cost
            if new: it.s=0; it.due=t; queue.append((turn+2,it))
            elif graded=='good': it.s=min(5,it.s+1); it.due=t+INTERVALS[it.s]
            elif graded=='soso': it.due=t+INTERVALS[1]
            else: it.s=max(0,it.s-2); it.due=t; queue.append((turn+3,it))
            queue.sort(key=lambda x:x[0]); turn+=1
        secs+=used
    for _ in range(DELAY): lr.decay()
    T2=DAYS+DELAY
    say=lambda it:1-(1-p0(it,T2))*(1-lr.F(it,False)*lr.L(it))
    rec=st.mean(say(it) for it in items); solid=sum(1 for it in items if say(it)>0.7)
    flu=sum(1 for it in items if say(it)>0.7 and dF(it,T2)>0.5)
    tr={f:lr.sel[f]*lr.g[f]*max(0.1,P['lex']-0.1) for f in FAMS}
    trans=sum(tr[f]*FAMCOUNT[f] for f in FAMS)/sum(FAMCOUNT.values())
    return rec,solid,flu,trans,secs/max(1,days),prods/max(1,days)

def V0pol(it,new):
    if new or it.s<3: return dict(cues=['ans','tile'],grade='typed',lenient=True,tile_only=True,cost=30,hc=0)
    return dict(cues=['ans'],grade='self',cost=12,hc=0,spoken=True)
LADDER=['kw','rule','ans','first','tile']
def fin(grade='asr',hints=True):
    def pol(it,new):
        cues=(LADDER if it.s<2 else LADDER[:4]) if hints else []
        if grade=='asr': return dict(cues=cues,grade='asr',cost=8,hc=4,timed=not new,spoken=True)
        return dict(cues=cues,grade='self',cost=10,hc=4,timed=not new,spoken=True)
    return pol
def P4pol(it,new):
    cues=['pat','first','ans']+(['tile'] if it.s<2 else [])
    return dict(cues=cues,grade='asr',cost=8,hc=4,timed=not new,spoken=True)
FULL=dict(policy=fin(),shadow=True,rewrite=True,judge=True,reply_prod=True,order='mixed')
def minus(**kw): d=dict(FULL); d.update(kw); return d
VARS={
 'V0 今の方式':dict(policy=V0pol,ans_shown=True,turns=10),
 'P4 第1回案':dict(policy=P4pol,shadow=True,reply_prod=True),
 'FINAL':FULL,
 '-1 ja書き換え無し':minus(rewrite=False),
 '-2 まねる無し':minus(shadow=False),
 '-3 ASR無し(自己評価)':minus(policy=fin('self')),
 '-4 ヒント無し(失敗→答え)':minus(policy=fin(hints=False)),
 '-4b ヒント順=第1回A順':minus(policy=P4pol),
 '-5 別解判定無し':minus(judge=False),
 '-6 返事ターン4択のまま':minus(reply_prod=False),
 '-7 新出順そのまま':minus(order='data'),
}
def main(NP,title,mod=None,keys=None):
    rng=random.Random(1); ps=[sample_all(rng) for _ in range(NP)]
    if mod: r=random.Random(9); [mod(P,r) for P in ps]
    b0=[run(VARS['V0 今の方式'],P,i,0) for i,P in enumerate(ps)]
    res={'V0 今の方式':b0}
    for k in (keys or VARS):
        if k!='V0 今の方式': res[k]=[run(VARS[k],P,i,b[4]) for i,(P,b) in enumerate(zip(ps,b0))]  # 人ごとにV0と同じ秒数
    fr=st.mean(x[0] for x in res['FINAL'])
    print('==',title)
    for k,r in res.items():
        m=[st.mean(x[j] for x in r) for j in range(6)]
        w0=sum(1 for x,y in zip(r,b0) if x[0]>y[0])/len(r)
        wf=sum(1 for x,y in zip(r,res['FINAL']) if x[0]>y[0])/len(r)
        print(f"  {k:22s} 言える{m[0]*100:5.1f}% FINAL比{(m[0]-fr)*100:+5.1f} 確実{m[1]:5.1f}問 瞬時{m[2]:5.1f}問 新しい質問{m[3]*100:5.1f}% {m[4]/60:3.1f}分 発話{m[5]:4.1f} 対V0{w0*100:4.0f}% 対FINAL{wf*100:4.0f}%")
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 150
    main(NP,'基本(人ごとにV0の10ターンと同じ1日の秒数)')
    K=['V0 今の方式','FINAL','-3 ASR無し(自己評価)','-5 別解判定無し']
    main(NP,'感度A: ASR厳しめ(不合格30-45%,誤合格8-15%),「合ってた」40-80%',lambda P,r:P.update(fr=r.uniform(0.3,0.45),fa=r.uniform(0.08,0.15)),K)
    main(NP,'感度B: 同上+「合ってた」をあまり押さない10-30%',lambda P,r:P.update(fr=r.uniform(0.3,0.45),fa=r.uniform(0.08,0.15),okbtn=r.uniform(0.1,0.3)),K)
    main(NP,'感度C: 同上+「合ってた」を押しすぎ(常に押す,甘さ1.8倍)',lambda P,r:P.update(fr=r.uniform(0.3,0.45),fa=r.uniform(0.08,0.15),okbtn=1.0,overconf=min(0.9,P['overconf']*1.8)),K)
