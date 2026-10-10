# sim_round2.py -- ablation of the integrated design (round2_design.md) on top of sim_linguist.py
# merges: linguist (rule/chunk/selection skills, cue types), polyglot (time cost, shadowing, ASR, fluency),
#         translator (ambiguity -> valid alternative answers; ja rewrite; alternative-answer judge)
import random, math, statistics as st, sys, json, os
import sim_linguist as L
from sim_linguist import STAGE, FAMS, p0, INTERVALS, DAYS, DELAY, TURNS, DAILY_NEW, cue_vec, Learner, learn_item, learn_rule, build_items

HERE=os.path.dirname(os.path.abspath(__file__))
_A={1,4,7,9,10,17,19,25,26,27,32,34,37,40,41,43,46,58,60,61,62,63,65,67,68,74,75,77,78,80,81,82,85,87,88,89,90,91}
_B={0,2,3,5,6,8,11,15,18,23,24,29,31,35,36,44,47,48,49,51,53,55,64,83,84,93,95,98}
_C={28,33,50,54,56,57,59,70,73}
CLS=['A' if i in _A else 'B' if i in _B else 'C' if i in _C else 'D' for i in range(len(L.RAW))]
REWR={x['idx'] for x in json.load(open(os.path.join(HERE,'translator_rewrites.json')))}

def sample_params(rng):
    P=L.sample_params(rng)
    P.update(sh=rng.uniform(0.2,0.6), fr=rng.uniform(0.10,0.25), fa=rng.uniform(0.03,0.10),
             kf=rng.uniform(0.15,0.35), untimed=rng.uniform(0.3,0.7), Sf=rng.uniform(20,60),
             ambA=rng.uniform(0.35,0.6), ambB=rng.uniform(0.15,0.3), ambC=rng.uniform(0.25,0.45),
             rwkeep=rng.uniform(0.25,0.55), synfix=rng.uniform(0.6,0.85), ansfix=rng.uniform(0.6,0.8),
             frust=rng.uniform(0.0,0.006))
    return P

def attempt(rng,it,lr,t,cues,primed,pre=()):
    """pre: cues given before the attempt (e.g. partner's answer in reply turn). returns ok,support,rule_credit,n_hints_used"""
    P=lr.P; pi=p0(it,t); F=lr.F(it,primed); Lx=lr.L(it); F0,L0=F,Lx
    for c in pre:
        cf,cl=cue_vec(c,it,P); F=F+(1-F)*cf; Lx=Lx+(1-Lx)*cl
    qbase=1-(1-pi)*(1-F0*L0); q=1-(1-pi)*(1-F*Lx)
    if rng.random()<q:
        if not pre:
            src='item' if rng.random()<pi/max(q,1e-9) else 'gen'
            return True,0.0,(0.5 if src=='item' else 1.0),0
        sup=(q-qbase)/q; fs=(F-F0)/max(F,1e-9); return True,sup,max(0,1-fs),0
    Fc,Lc=F,Lx
    for k,c in enumerate(cues):
        cf,cl=cue_vec(c,it,P); Fc=Fc+(1-Fc)*cf; Lc=Lc+(1-Lc)*cl
        ps=1-(1-pi)*(1-Fc*Lc)
        if rng.random()<(ps-q)/(1-q):
            return True,(ps-qbase)/ps,max(0.0,1-(Fc-F0)/max(Fc,1e-9)),k+1
        q=ps
    return False,1.0,0.0,len(cues)

def amb(it,P,cfg,ans_shown):
    base={'A':P['ambA'],'B':P['ambB'],'C':P['ambC'],'D':0.03}[CLS[it.idx]]
    if ans_shown: base*=1-P['ansfix']
    if cfg.get('rewrite'): base*= (P['rwkeep'] if CLS[it.idx] in 'AC' else 0.7) if it.idx in REWR else 1.0
    if cfg.get('judge') and CLS[it.idx] in 'BC': base*=1-P['synfix']
    return base

def run(cfg,P,seed,budget):
    rng=random.Random(seed); items=build_items(); lr=Learner(P)
    for i,it in enumerate(items): it.idx=i
    Fl=[0.0]*len(items); Flast=[0.0]*len(items)
    def dF(i,t): return Fl[i]*math.exp(-max(0,t-Flast[i])/P['Sf'])
    order=cfg.get('order','data')
    if order=='mixed':
        by={f:[it for it in items if it.fam==f] for f in FAMS}; items_new=[]
        while any(by.values()):
            for f in sorted(FAMS,key=lambda f:STAGE[f]):
                if by[f]: items_new.append(by[f].pop(0))
    else: items_new=list(items)
    attend=P['attend']; spoken=0; secs=0; dayson=0
    for day in range(DAYS):
        lr.decay()
        if rng.random()>attend: continue
        dayson+=1; newc=0; t=day+0.5; queue=[]; prev=None; used=0; turn=0
        while used<budget:
            t+=1/1440*2
            reply = turn%3==2
            if reply and not cfg.get('reply_prod'):
                used+=10; secs+=10; turn+=1; prev=None; continue
            due=[it for it in items if it.seen and it.due<=t]; due.sort(key=lambda it:it.s)
            if queue and queue[0][0]<=turn and not reply: it=queue.pop(0)[1]
            elif due: it=due[0]
            elif reply:   # reply-production turn uses an already-seen item
                rest=[it for it in items if it.seen]
                if not rest: used+=10; turn+=1; continue
                it=min(rest,key=lambda x:x.due)
            else:
                fresh=[it for it in items_new if not it.seen]
                if cfg.get('gated'):
                    fr2=[x for x in fresh if lr.ready(x.fam)>=0.8]; fresh=fr2 or fresh
                if fresh and newc<DAILY_NEW: it=fresh[0]; newc+=1
                else:
                    rest=[it for it in items if it.seen]
                    if not rest: used+=10; turn+=1; continue
                    it=min(rest,key=lambda x:x.due)
            i=it.idx; new=not it.seen; primed = prev==it.fam
            # ---- mode for this turn
            if cfg['name']=='V0':
                if new or it.s<3: cues=['ans','tile']; grade='lenient'; cost=30; hc=0; oral=False
                else: cues=['ans']; grade='self'; cost=12; hc=0; oral=True
                pre=('ans',); ans_shown=True
            else:
                cues=list(cfg['cues'])
                if not (new or it.s<3) and 'tile' in cues: cues.remove('tile')
                oral=cfg.get('oral',False)
                if oral: grade='asr'; cost=P.get('oralcost',8); hc=P.get('oralhint',4)
                else: grade='typed'; cost=30 if (new or it.s<3) else 25; hc=8
                pre=('ans',) if reply else (); ans_shown=reply
                if reply and 'ans' in cues: cues.remove('ans')
            if new and cfg.get('shadow'):
                it.m+=P['b']*P['sh']*(1-it.m); it.seen=True; it.last=t
                lr.h[it.frame]=lr.h.get(it.frame,0)+P['rh']*0.3*P['sh']*(1-lr.h.get(it.frame,0))
                Fl[i]=dF(i,t)+0.05*(1-dF(i,t)); Flast[i]=t; cost+=12
            # V0: answer visible -> attempt already cued; for comparability with earlier sims keep first unaided draw
            if cfg['name']=='V0': pre=()
            # ---- alternative valid answer (ambiguity)
            q=1-(1-p0(it,t))*(1-lr.F(it,primed)*lr.L(it))
            handled=False
            if cfg['name']!='V0' and rng.random()<q and rng.random()<amb(it,P,cfg,ans_shown):
                handled=True
                if cfg.get('judge'):
                    ok=True; sup=0.3; rc=0.8; nh=1; graded='soso'; cost+=4
                else:
                    attend*=1-P['frust']
                    ok,sup,rc,nh=attempt(rng,it,lr,t,cues[1:] or ['tile'],primed)
                    if ok: sup=max(sup,0.5)
                    graded='soso' if ok else 'bad'; nh+=1
            if not handled:
                ok,sup,rc,nh=attempt(rng,it,lr,t,cues,primed,pre)
                if grade=='self':
                    sok=ok or rng.random()<P['overconf']
                    graded='good' if sok and sup<0.01 else ('soso' if sok else 'bad')
                elif grade=='lenient': graded='good' if ok else 'bad'
                else:
                    if grade=='asr':
                        rec=(rng.random()>P['fr'] or rng.random()<0.5) if ok else (rng.random()<P['fa'] or rng.random()<P['overconf']*0.25)
                    else: rec=ok
                    graded='good' if rec and sup<0.01 else ('soso' if rec else 'bad')
            cost+=nh*hc; used+=cost; secs+=cost
            if primed: rc*=1-P['prime']
            learn_item(it,t,P,ok,sup); learn_rule(lr,it,ok,rc,primed); prev=it.fam
            fi=dF(i,t)
            if ok and sup<0.01: fi+=P['kf']*(1 if oral else P['untimed']*0.5)*(1-fi)
            elif ok: fi+=P['kf']*0.15*(1-fi)
            Fl[i]=fi; Flast[i]=t
            if oral: spoken+=1
            if reply and not new:   # reply turn: does not move stars except failure
                if graded=='bad': it.due=t
            elif new: it.s=0; it.due=t; queue.append((turn+2,it))
            elif graded=='good': it.s=min(5,it.s+1); it.due=t+INTERVALS[it.s]
            elif graded=='soso': it.due=t+INTERVALS[1]
            else: it.s=max(0,it.s-2); it.due=t; queue.append((turn+3,it))
            queue.sort(key=lambda x:x[0]); turn+=1
    for _ in range(DELAY): lr.decay()
    T2=DAYS+DELAY
    def say(it): return 1-(1-p0(it,T2))*(1-lr.F(it,False)*lr.L(it))
    solid=sum(1 for it in items if say(it)>0.7)
    fluent=sum(1 for it in items if say(it)>0.7 and dF(it.idx,T2)>0.5)
    tr={f:lr.sel[f]*lr.g[f]*max(0.1,P['lex']-0.1) for f in FAMS}
    trans=sum(tr[f]*L.FAMCOUNT[f] for f in FAMS)/sum(L.FAMCOUNT.values())
    seen=sum(it.seen for it in items)
    return solid,fluent,trans,seen,secs/max(1,dayson)/60,spoken/max(1,dayson)

KR=['kw','rule','ans','first','tile']; AO=['pat','first','ans','tile']
FINAL=dict(name='FINAL',cues=KR,oral=True,shadow=True,judge=True,rewrite=True,reply_prod=True,order='mixed',gated=True)
def minus(**kw): d=dict(FINAL); d.update(kw); return d
CFG={
 'V0 今の方式':dict(name='V0'),
 'A+C':dict(name='AC',cues=AO,oral=False),
 'FINAL':FINAL,
 '-2 まねる無し':minus(shadow=False),
 '-3 音声→入力':minus(oral=False),
 '-4 ヒント順を元のA順':minus(cues=AO),
 '-5 別解判定なし':minus(judge=False),
 '-6 返事ターンは4択のまま':minus(reply_prod=False),
 '-7 新出はデータ順':minus(order='data',gated=False),
 'FINAL-1 書き換えなし(参考)':minus(rewrite=False),
}
V0BUDGET=None
def main(NP=150,mod=None,title='基本',keys=None):
    rng=random.Random(1); params=[sample_params(rng) for _ in range(NP)]
    if mod: r=random.Random(5); [mod(P,r) for P in params]
    # equalize time: budget = V0's mean seconds per day (V0 run with 10 turns)
    v0=[run(CFG['V0 今の方式'],P,i,budget=10**9 if False else 0) for i,P in enumerate(params[:0])]
    bud=V0_SECS
    res={k:[run(CFG[k],P,i,bud) for i,P in enumerate(params)] for k in (keys or CFG)}
    fin=res.get('FINAL'); base=res[list(res)[0]]
    print('==',title,f'(1日 {bud}秒に揃える)')
    print(f"  {'方式':26s} 確実に言える 即答できる 新しい質問 出会った 1日分 発話/日 対V0 対FINAL")
    for k,r in res.items():
        m=[st.mean(x[j] for x in r) for j in range(6)]
        w=sum(1 for x,y in zip(r,base) if x[0]>y[0])/len(r); wf=sum(1 for x,y in zip(r,fin) if x[0]>y[0])/len(r) if fin else 0
        print(f"  {k:26s} {m[0]:6.1f}問 {m[1]:6.1f}問 {m[2]*100:6.1f}% {m[3]:5.1f}問 {m[4]:4.1f} {m[5]:5.1f} {w*100:4.0f}% {wf*100:4.0f}%")
# V0 with 10 turns: 7 production turns (tiles 30s / self 12s) + 3 reply turns 10s ~ measured below
def v0_secs():
    # approximate V0 per-day seconds: replicate with turn-count limit using big budget not possible; measure directly
    rng=random.Random(1); Ps=[sample_params(rng) for _ in range(60)]; tot=[]
    for i,P in enumerate(Ps):
        # V0 uses ~ 3 reply*10 + 7 production turns; production cost: tiles 30 while s<3 else 12
        tot.append(run_v0_turns(P,i))
    return round(st.mean(tot))
def run_v0_turns(P,seed):
    # run V0 with a huge budget but stop after 10 turns: emulate by temporarily limiting turns
    global _TURNLIMIT
    rng=random.Random(seed); items=build_items(); lr=Learner(P); secs=[];
    for i,it in enumerate(items): it.idx=i
    days=0; total=0
    for day in range(DAYS):
        lr.decay()
        if rng.random()>P['attend']: continue
        days+=1; t=day+0.5; queue=[]; newc=0
        for turn in range(TURNS):
            t+=1/1440*2
            if turn%3==2: total+=10; continue
            due=[it for it in items if it.seen and it.due<=t]; due.sort(key=lambda it:it.s)
            if queue and queue[0][0]<=turn: it=queue.pop(0)[1]
            elif due: it=due[0]
            else:
                fresh=[it for it in items if not it.seen]
                if fresh and newc<DAILY_NEW: it=fresh[0]; newc+=1
                else: it=min([x for x in items if x.seen],key=lambda x:x.due)
            new=not it.seen; lowS=new or it.s<3
            ok,sup,rc,nh=attempt(rng,it,lr,t,['ans','tile'] if lowS else ['ans'],False)
            sok=ok or (not lowS and rng.random()<P['overconf'])
            graded='good' if (ok if lowS else (sok and sup<0.01)) else ('soso' if sok else 'bad')
            total+=30 if lowS else 12
            learn_item(it,t,P,ok,sup); learn_rule(lr,it,ok,rc,False)
            if new: it.s=0; it.due=t; queue.append((turn+2,it))
            elif graded=='good': it.s=min(5,it.s+1); it.due=t+INTERVALS[it.s]
            elif graded=='soso': it.due=t+INTERVALS[1]
            else: it.s=max(0,it.s-2); it.due=t; queue.append((turn+3,it))
    return total/max(1,days)
V0_SECS=None
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 150
    V0_SECS=v0_secs(); print('V0 10ターンの1日平均秒:',V0_SECS)
    main(NP)
    if len(sys.argv)>2:
        ks=['V0 今の方式','A+C','FINAL','-2 まねる無し','-3 音声→入力','-4 ヒント順を元のA順','-5 別解判定なし','-6 返事ターンは4択のまま','-7 新出はデータ順']
        main(NP,lambda P,r:P.update(fr=r.uniform(0.3,0.45),fa=r.uniform(0.08,0.15)),'感度1: 音声認識が厳しい',ks)
        main(NP,lambda P,r:P.update(rg=r.uniform(0.004,0.01),rs=r.uniform(0.003,0.008)),'感度2: 規則はほぼ伸びない(暗記中心)',ks)
        main(NP,lambda P,r:P.update(oralcost=15,oralhint=7),'感度4: 音声1問15秒(言い直し・誤認識込み)',ks)
        main(NP,lambda P,r:P.update(sh=r.uniform(0,0.05),ambA=r.uniform(0.1,0.2),ambB=0.05,ambC=0.1,frust=0.0),'感度3: まねる効果なし・別解が少ない',ks)
