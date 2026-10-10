# sim_poly3b.py -- 第3回・第2会議: ROUND2.md(FINAL3) の検証。sim_poly3.py の記憶モデル/仮定を引き継ぐ。
# 追加仮定:
#  既知語: 学習者はアプリ開始前に Lv1語の50%,Lv2の20%,Lv3の5%を知っている(個人差×0.5-1.5; m=0.75,S=40日)。
#    アプリは知らずに初見として出す(初見15秒+直後の再出)= 新出枠と時間のムダ。
#  診断(1日目,約90秒): 既知語の85%を検出→★3,期日1-14日。うそYes fy=5-15%(擬似語で補正後)の未知語も★3にされ、期日に失敗して学び直し。
#  言い換え(PA): 8問×8秒。目標語(★0-2)とアンカーの関係3択。精緻化 m+=b*0.3、q で弱い想起(支え0.6)。干渉 ifr: q<0.5 のとき確率 ifr で混同(失敗扱い)。
#  例文(CL): ★3以上,8問×10秒。3秒想起→4択。想起成功(q*0.9)は支え0.3,だめなら消去法elimで支え0.8。★は下げない。
#  スピード処理(SP3): 10文×3周(1文の秒数 7/5.25/3.5秒+要旨3択2秒)。周回ごとに圧力↑で F の伸び×pg^(周-1) (pg 1.0-1.3)。
#     SP1: 同じ時間で1周だけ(1文9秒)、文は2.3倍の種類。
#  しりとり早押し(HY): 「卵 / e___」→分かった→4択。期限の語優先。日→英の想起(q*0.85)に頭文字手がかり。
#     自力(手がかりなし)成功→支え0.2を転移tr分で学習+F(時間制限)。頭文字で出た→支え0.5。分からず4択→消去法(支え0.85)。誤答★-1。1問4秒。
#  早押し(HO)・狙い撃ちしりとり(SH+) は sim_poly3 と同じ。
#  別解×(感度): 翻訳者の指摘。日→英の産出(HY/SH+)で別の正しい語を言った時に×になる→ amb=0.15 の確率で成功が失敗扱い(★-1)。
import random, math, statistics as st, sys
sys.path.insert(0,'/home/user/Answer-/research/talk-mode'); sys.path.insert(0,'/tmp/claude-0/-home-user-Answer-/7b95110d-ba08-5cac-b5c8-030a513b1d3f/scratchpad/r3')
from sim_polyglot import p0, learn, attempt, sample_params, sample_extra, INTERVALS
from sim_poly3 import xparams, srs, Fd, bumpF
DAYS=90; DELAY=14; N=600; NEW=10
class W:
    __slots__=('m','S','last','s','due','seen','lv','L','F','Fl','intro')
def mk(i,rng,k):
    w=W(); w.lv=1 if i<200 else 2 if i<450 else 3; w.m=0.05+0.05*(3-w.lv); w.S=0.2; w.last=0; w.s=0; w.due=0
    w.seen=False; w.intro=False; w.L=rng.randrange(20); w.F=0.0; w.Fl=0.0
    if rng.random()<{1:0.5,2:0.2,3:0.05}[w.lv]*k: w.seen=True; w.m=0.75; w.S=40; w.last=0; w.F=0.2
    return w
def pool(ws,smin=0): return [w for w in ws if w.intro and w.s>=smin]

def battle(rng,P,ws,t,budget,D):
    used=0; queue=[]; turn=0; goods=0
    while used<budget:
        t+=1/1440
        due=[w for w in ws if w.intro and w.due<=t]
        if queue and queue[0][0]<=turn: w=queue.pop(0)[1]
        elif due: w=min(due,key=lambda x:x.s)
        else:
            fresh=[w for w in ws if not w.intro]
            if fresh and D['new']<NEW: w=fresh[0]; D['new']+=1
            else:
                pl=pool(ws)
                if not pl: break
                w=min(pl,key=lambda x:x.due)
        new=not w.intro; q=p0(w,t)
        if new:
            ok,sup=attempt(rng,q,[P['ans']+(1-P['ans'])*P['tile']]); learn(w,t,P,ok,max(sup,0.7) if sup>0 or not ok else 0.3); used+=15
            w.intro=True; w.s=0; w.due=t; queue.append((turn+2,w))
        else:
            ok,sup=attempt(rng,q,[P['pat'],P['first'],P['ans']]); nh=0 if ok and sup<0.01 else (3 if not ok else max(1,round(sup*3)))
            used+=8+4*nh
            so=ok or rng.random()<P['overconf']
            g='good' if so and sup<0.01 else ('soso' if so else 'bad')
            learn(w,t,P,ok,sup)
            if ok and sup<0.01: bumpF(w,t,P,P['kf']*P['soft'])     # 今のrecallは10秒タイマー付き
            srs(w,t,g)
            if g=='bad': queue.append((turn+3,w))
            if g=='good':
                goods+=1
                if goods%3==0: used+=6; q2=p0(w,t); learn(w,t,P,rng.random()<q2+(1-q2)*P['elim'],0.8)
        queue.sort(key=lambda x:x[0]); turn+=1
    return t

def para(rng,P,ws,t,budget,D):
    pl=[w for w in pool(ws) if w.s<=2] or pool(ws)
    used=0
    while pl and used<budget:
        w=rng.choice(pl); t+=1/1440/8; q=p0(w,t)
        if q<0.5 and rng.random()<P['ifr']: learn(w,t,P,False,1.0); w.due=min(w.due,t)
        else:
            w.m+=P['b']*0.3*(1-w.m)
            if rng.random()<q: learn(w,t,P,True,0.6); w.due+=0.2*(w.due-t) if w.due>t else 0
        used+=8
    return t
def cloze(rng,P,ws,t,budget,D):
    pl=pool(ws,3); used=0
    while pl and used<budget:
        w=rng.choice(pl); t+=1/1440/6; q=p0(w,t)*0.9
        if rng.random()<q: learn(w,t,P,True,0.3); bumpF(w,t,P,P['kf']*0.5)
        elif rng.random()<P['elim']: learn(w,t,P,True,0.8)
        else: learn(w,t,P,False,1.0)
        used+=10
    return t
def speed(rng,P,ws,t,budget,D,passes):
    known=pool(ws,2) or pool(ws)
    if len(known)<3: return t
    used=0
    per=[7,5.25,3.5][:passes] if passes==3 else [9]
    while used<budget:
        sents=[rng.sample(known,3) for _ in range(10)]
        for pi,sec in enumerate(per):
            for s in sents:
                if used>=budget: break
                t+=1/1440/6
                for w in s:
                    q=min(1,p0(w,t)*P['ctx'])
                    if rng.random()<q: learn(w,t,P,True,0.5); bumpF(w,t,P,P['kf']*P['kfr']*P['pg']**pi)
                    else: w.m+=P['b']*P['inc']*(1-w.m)
                used+=sec+2
    return t
def hybrid(rng,P,ws,t,budget,D,amb=0.0):
    used=0
    while used<budget:
        pl=pool(ws,1) or pool(ws)
        if not pl: break
        due=[w for w in pl if w.due<=t]
        w=rng.choice(due) if due else min(pl,key=lambda x:x.due)
        t+=1/1440/15; q=p0(w,t)*0.85
        if rng.random()<q: ok,sup=True,0.0
        elif rng.random()<P['first']: ok,sup=True,0.5
        else: ok=False
        if ok and rng.random()<amb: learn(w,t,P,True,1-P['tr']*(1-sup)); w.s=max(0,w.s-1); w.due=t   # 別解で×
        elif ok:
            learn(w,t,P,True,1-P['tr']*(1-sup))
            if sup==0: bumpF(w,t,P,P['kf']*P['tr'])
        elif rng.random()<P['elim']: learn(w,t,P,True,0.85)
        else: learn(w,t,P,False,1.0); w.s=max(0,w.s-1); w.due=t
        used+=4
    return t
def hayaoshi(rng,P,ws,t,budget,D):
    pl=sorted(pool(ws,1),key=lambda x:x.due); used=0; k=0
    while pl and used<budget:
        w=pl[k%len(pl)]; k+=1; t+=1/1440/15; q=p0(w,t)
        if rng.random()<q: learn(w,t,P,True,0.2); bumpF(w,t,P,P['kf'])
        elif rng.random()<P['elim']: learn(w,t,P,True,0.8)
        else: learn(w,t,P,False,1.0); w.s=max(0,w.s-1); w.due=t
        used+=4
    return t
def shiriT(rng,P,ws,t,budget,D,amb=0.0):
    used=0
    while used<budget:
        pl=pool(ws)
        if not pl: break
        due=[w for w in pl if w.due<=t] or sorted(pl,key=lambda x:x.due)[:5]
        w=rng.choice(due); t+=1/1440/4; q=p0(w,t)*0.85
        ok,sup=attempt(rng,q,[P['first'],P['ans']])
        if ok and sup<0.01 and rng.random()<amb: ok=False
        learn(w,t,P,ok,1-P['tr']*(1-sup) if ok else 1.0)
        if ok and sup<0.01: bumpF(w,t,P,P['kf']*P['tr']); srs(w,t,'good')
        elif ok: srs(w,t,'soso')
        else: srs(w,t,'bad')
        used+=15
    return t
MODES={'B':battle,'PA':para,'CL':cloze,'SP3':lambda *a:speed(*a,3),'SP1':lambda *a:speed(*a,1),'HY':hybrid,'HO':hayaoshi,'SH+':shiriT}

def run(cfg,P,seed):
    rng=random.Random(seed); ws=[mk(i,rng,P['pk']) for i in range(N)]; ra=random.Random(seed*7+3)
    if cfg.get('diag'):
        for w in ws:
            if (w.seen and rng.random()<0.85) or (not w.seen and w.lv<3 and rng.random()<P['fy']*0.5):
                w.intro=True; w.s=3; w.due=rng.uniform(1,14)
    rot=cfg.get('rot',[]); nm=len(set(rot)); days=0
    for day in range(DAYS):
        boost=P['v']*nm/3*(0.5+0.5*math.exp(-day/30)); ua,ub=ra.random(),ra.random()
        if ua<P['h']*(1-min(1,P['v']*nm/3))*cfg.get('hmul',1): break
        if ub>P['attend']+(1-P['attend'])*min(1,boost): continue
        days+=1; t=day+0.5; D={'new':0}
        t=battle(rng,P,ws,t,cfg.get('B',600),D)
        if rot:
            m=rot[day%len(rot)]; f=MODES[m]
            t=f(rng,P,ws,t,cfg.get('X',120),D,P['amb']) if m in('HY','SH+') else f(rng,P,ws,t,cfg.get('X',120),D)
    T=DAYS+DELAY
    rec=sum(p0(w,T) for w in ws)/N*100
    solid=sum(1 for w in ws if p0(w,T)>0.7)
    flu=sum(1 for w in ws if p0(w,T)>0.7 and Fd(w,T,P)>0.5)
    return rec,solid,flu,days
R4=['PA','CL','SP3','HY']
CFG={
 'V0 バトル10分':dict(diag=False),
 'バトル10分+診断のみ':dict(diag=True),
 'FINAL3 10+日替わり2分(診断あり)':dict(diag=True,rot=R4),
 'バトル12分(診断あり)':dict(diag=True,B=720),
 '10+毎日スピード処理2分':dict(diag=True,rot=['SP3']),
 '-診断':dict(diag=False,rot=R4),
 '-言い換え':dict(diag=True,rot=['CL','SP3','HY']),
 '-例文':dict(diag=True,rot=['PA','SP3','HY']),
 '-スピード':dict(diag=True,rot=['PA','CL','HY']),
 '-しりとり早押し':dict(diag=True,rot=['PA','CL','SP3']),
 'b) 毎日HY(しりとり早押し)':dict(diag=True,rot=['HY']),
 'b) 毎日HO(英→4択早押し)':dict(diag=True,rot=['HO']),
 'b) 毎日SH+(狙い撃ちしりとり入力)':dict(diag=True,rot=['SH+']),
 'c) 毎日SP 1周のみ':dict(diag=True,rot=['SP1']),
}
def params(NP):
    rng=random.Random(1); ps=[]
    for _ in range(NP):
        P=sample_params(rng); P.update(sample_extra(rng)); xparams(P,rng)
        P.update(pk=rng.uniform(0.5,1.5), fy=rng.uniform(0.05,0.15), ifr=rng.uniform(0.05,0.15), pg=rng.uniform(1.0,1.3), amb=0.0, soft=rng.uniform(0.5,0.9))
        ps.append(P)
    return ps
def table(ps,title,keys,mod=None):
    print('==',title); base=None
    for k in keys:
        R=[]
        for i,P in enumerate(ps):
            Q=dict(P)
            if mod: mod(Q)
            R.append(run(CFG[k],Q,i))
        if base is None: base=R
        win=sum(1 for x,y in zip(R,base) if x[0]>y[0])/len(R)
        print(f"| {k} | {st.mean(x[0] for x in R):.1f}% | {st.mean(x[1] for x in R):.0f} | {st.mean(x[2] for x in R):.0f} | {st.mean(x[3] for x in R):.1f} | {win*100:.0f}% |")
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 60
    ps=params(NP); K=list(CFG)
    table(ps,'基本 v=0 (|構成|言える|確実|瞬時|出席日|V0に勝つ|)',K,lambda Q:Q.update(v=0))
    S=['V0 バトル10分','バトル10分+診断のみ','FINAL3 10+日替わり2分(診断あり)','バトル12分(診断あり)','10+毎日スピード処理2分','-言い換え']
    table(ps,'v=0.3',S,lambda Q:Q.update(v=0.3))
    table(ps,'v=0.6',S,lambda Q:Q.update(v=0.6))
    table(ps,'干渉強め(ifr 0.3-0.5)',S,lambda Q:Q.update(v=0,ifr=Q['ifr']*3.3))
    table(ps,'別解×(産出で別の正しい語→×, 15%)',['V0 バトル10分','FINAL3 10+日替わり2分(診断あり)','b) 毎日HY(しりとり早押し)','b) 毎日SH+(狙い撃ちしりとり入力)'],lambda Q:Q.update(v=0,amb=0.15))
