# sim_poly3.py -- 第3回(多言語実践者): スピード処理/早押し/しりとり を同じ1日の秒数で比較
# 土台: research/talk-mode/sim_polyglot.py の記憶モデル(p0, learn, attempt: m=土台, S=安定度, 自力想起ほど伸びる)
#       と 即答度 F(自力で時間内に成功すると伸び、30-60日で減衰)。
# 測るもの: 90日+14日後に「英単語→意味」を言える確率(平均)、確実(>0.7)語数、瞬時(確実かつF>0.5)語数。
# 仮定(すべて明示・乱数で幅を持たせる):
#  バトル: 初見=例文ヒント付き4択15秒(手がかり支え0.7) / recall=自力想起8秒+ヒント1段4秒,自己評価(甘さoverconf) / ◎3回で4択抜き打ち6秒
#  スピード処理(SP): 1文6〜9語,1文 5.5秒(読む3.5+要するに何?3択2)。文には既習語3つ(s>=2優先)+確率pu(0.3)で未知語1つ。
#     既習語: 確率q*ctx(文脈で思い出しやすい)で意味にアクセス→弱い想起(支え0.5)+F が kfr*kf 伸びる(時間制限読み)。
#     失敗/未知語: 偶発学習 m+=b*inc (inc 0.02-0.08; Waring&Takaki:18回でも15%未満)。SRSは更新しない(未知語はタップでSRSへ入る→初見扱い)。
#  早押し(HO): 英単語→4択,CPUより先に(3秒)。1問4秒。自力で分かれば(確率q)支え0.2+F(時間制限)フル、
#     分からなければ消去法 elim(0.3-0.5)で正解→支え0.8。誤答→SRSで s-1, すぐ復習。出題=既習語(s>=1)を期日の近い順。
#  しりとり自由(SH): 自分の番12秒+CPUの番3秒。最後の文字で始まる既習語のうち一番言いやすい語を出す(=易しい語ばかり)。
#     産出→受容への転移 tr(0.4-0.8)。CPUの語は既習語なら軽い接触。
#  しりとり狙い撃ち(SH+): CPUが「次の文字=期日の来た語の頭文字」になる語を選び、5秒後に意味ヒント→ 日→英 の想起(手がかり first,ans)。
#  継続(出席率): attend(0.6-0.95)。やめてしまう確率(1日あたり)h=0.3-1.5%/日(90日で24-74%が離脱)。
#     多様さ効果は離脱率も h*(1-v*追加モード数/3) に下げる(同じ v)。
#  T5: バトルの recall に「5秒の目安バー」(新モードなしで即答度を鍛える対照)。時間制限ありの F 伸び= kf*soft(0.5-0.9)。遊びの多様さ効果: 欠席の日のうち v*(追加モード数/3)*(0.5+0.5*exp(-day/30)) を出席に変える。
import random, math, statistics as st, sys
sys.path.insert(0,'/home/user/Answer-/research/talk-mode')
from sim_polyglot import p0, learn, attempt, sample_params, sample_extra, INTERVALS
DAYS=90; DELAY=14; N=600; NEW=10
class W:
    __slots__=('m','S','last','s','due','seen','lv','L','F','Fl')
    def __init__(s,i,rng): s.m=0.05+0.05*(3-s_lv(i)); s.S=0.2; s.last=0; s.s=0; s.due=0; s.seen=False; s.lv=s_lv(i); s.L=rng.randrange(20); s.F=0.0; s.Fl=0.0
def s_lv(i): return 1 if i<200 else 2 if i<450 else 3
def Fd(w,t,P): return w.F*math.exp(-max(0,t-w.Fl)/P['Sf'])
def bumpF(w,t,P,k): f=Fd(w,t,P); w.F=f+k*(1-f); w.Fl=t
def xparams(P,rng):
    P.update(ctx=rng.uniform(1.1,1.4), kfr=rng.uniform(0.3,0.7), inc=rng.uniform(0.02,0.08), pu=0.3,
             elim=rng.uniform(0.3,0.5), tr=rng.uniform(0.4,0.8), v=0.0, h=rng.uniform(0.003,0.015), soft=rng.uniform(0.5,0.9), timed=False)
def srs(w,t,g):
    if g=='good': w.s=min(5,w.s+1); w.due=t+INTERVALS[w.s]
    elif g=='soso': w.due=t+INTERVALS[1]
    else: w.s=max(0,w.s-2); w.due=t

def battle(rng,P,ws,t,budget,st_):
    used=0; queue=[]; turn=0; goods=0
    while used<budget:
        t+=1/1440
        due=[w for w in ws if w.seen and w.due<=t]
        if queue and queue[0][0]<=turn: w=queue.pop(0)[1]
        elif due: w=min(due,key=lambda x:x.s)
        else:
            fresh=[w for w in ws if not w.seen]
            if fresh and st_['new']<NEW: w=fresh[0]; st_['new']+=1
            else:
                seen=[w for w in ws if w.seen]
                if not seen: break
                w=min(seen,key=lambda x:x.due)
        new=not w.seen; q=p0(w,t)
        if new:
            ok,sup=attempt(rng,q,[P['ans']+(1-P['ans'])*P['tile']]); learn(w,t,P,ok,max(sup,0.7)); used+=15
            w.s=0; w.due=t; queue.append((turn+2,w))
        else:
            cues=[P['pat'],P['first'],P['ans']]
            ok,sup=attempt(rng,q,cues); nh=0 if ok and sup<0.01 else (3 if not ok else max(1,round(sup*3)))
            used+=8+4*nh
            so=ok or rng.random()<P['overconf']
            g='good' if so and sup<0.01 else ('soso' if so else 'bad')
            learn(w,t,P,ok,sup)
            if ok and sup<0.01: bumpF(w,t,P,P['kf']*(P['soft'] if P['timed'] else P['untimed']))
            srs(w,t,g)
            if g=='bad': queue.append((turn+3,w))
            if g=='good':
                goods+=1
                if goods%3==0: used+=6; ok2=rng.random()<p0(w,t)+(1-p0(w,t))*P['elim']; learn(w,t,P,ok2,0.8)
        queue.sort(key=lambda x:x[0]); turn+=1
    return t

def speed(rng,P,ws,t,budget,st_):
    used=0; known=[w for w in ws if w.seen and w.s>=2] or [w for w in ws if w.seen]
    if len(known)<3: return t
    unseen=[w for w in ws if not w.seen]
    while used<budget:
        t+=1/1440/6
        for w in rng.sample(known,3):
            q=min(1,p0(w,t)*P['ctx'])
            if rng.random()<q: learn(w,t,P,True,0.5); bumpF(w,t,P,P['kf']*P['kfr'])
            else: w.m+=P['b']*P['inc']*(1-w.m)
        if unseen and rng.random()<P['pu']:
            u=rng.choice(unseen[:150]); u.m+=P['b']*P['inc']*(1-u.m)  # 未知語: 偶発学習のみ(seenにはしない=タップしない想定)
        used+=5.5; st_['sent']+=1
    return t

def hayaoshi(rng,P,ws,t,budget,st_):
    used=0; pool=sorted([w for w in ws if w.seen and w.s>=1],key=lambda x:x.due)
    if not pool: return t
    k=0
    while used<budget:
        w=pool[k%len(pool)]; k+=1; t+=1/1440/15; q=p0(w,t)
        if rng.random()<q: learn(w,t,P,True,0.2); bumpF(w,t,P,P['kf'])
        elif rng.random()<P['elim']: learn(w,t,P,True,0.8)
        else: learn(w,t,P,False,1.0); w.s=max(0,w.s-1); w.due=t
        used+=4
    return t

def shiritori(rng,P,ws,t,budget,st_,target=False):
    used=0
    while used<budget:
        t+=1/1440/4
        seen=[w for w in ws if w.seen]
        if not seen: break
        c=rng.choice(seen); c.m+=P['b']*0.05*(1-c.m); used+=3       # CPUの語
        if target:
            due=[w for w in seen if w.due<=t] or sorted(seen,key=lambda x:x.due)[:5]
            w=rng.choice(due); q=p0(w,t)*0.85                        # 日→英は少し難しい
            ok,sup=attempt(rng,q,[P['first'],P['ans']])
            learn(w,t,P,ok,1-P['tr']*(1-sup) if ok else 1.0)
            if ok and sup<0.01: bumpF(w,t,P,P['kf']*P['tr']); srs(w,t,'good')
            elif ok: srs(w,t,'soso')
            else: srs(w,t,'bad')
            used+=12
        else:
            cand=[w for w in seen if w.L==rng.randrange(20)] or seen
            w=max(cand,key=lambda x:p0(x,t))
            ok=rng.random()<p0(w,t)*0.85
            if ok: learn(w,t,P,True,1-P['tr']); bumpF(w,t,P,P['kf']*P['tr']*0.5)
            used+=12
    return t

def run(mix,P,seed,budget):
    rng=random.Random(seed); ws=[W(i,rng) for i in range(N)]
    if 'T' in mix: P=dict(P,timed=True); mix={k:v for k,v in mix.items() if k!='T'}
    nm=sum(1 for k in mix if k!='B'); days=0; st_={'sent':0}; ra=random.Random(seed*7+3)  # 出席/離脱は共通乱数(条件間で同じ日に休む)
    for day in range(DAYS):
        boost=P['v']*nm/3*(0.5+0.5*math.exp(-day/30))
        ua,ub=ra.random(),ra.random()
        if ua<P['h']*(1-min(1,P['v']*nm/3)): break     # アプリをやめる
        if ub>P['attend']+(1-P['attend'])*min(1,boost): continue
        days+=1; t=day+0.5; st_['new']=0
        for k,frac in mix.items():
            b=budget*frac
            if k=='B': t=battle(rng,P,ws,t,b,st_)
            elif k=='SP': t=speed(rng,P,ws,t,b,st_)
            elif k=='HO': t=hayaoshi(rng,P,ws,t,b,st_)
            elif k=='SH': t=shiritori(rng,P,ws,t,b,st_)
            elif k=='SH+': t=shiritori(rng,P,ws,t,b,st_,True)
    T=DAYS+DELAY
    r=[p0(w,T) for w in ws if w.seen]+[0]*0
    rec=sum(p0(w,T) for w in ws)/N*100
    solid=sum(1 for w in ws if p0(w,T)>0.7)
    flu=sum(1 for w in ws if p0(w,T)>0.7 and Fd(w,T,P)>0.5)
    return rec,solid,flu,days,st_['sent']/max(1,days)

MIX={
 '今の構成(バトルのみ)':{'B':1.0},
 '+スピード処理(25%)':{'B':0.75,'SP':0.25},
 '+早押し(25%)':{'B':0.75,'HO':0.25},
 '+しりとり自由(25%)':{'B':0.75,'SH':0.25},
 '+しりとり狙い撃ち(25%)':{'B':0.75,'SH+':0.25},
 '全部入り(B55/SP15/HO15/SH+15)':{'B':0.55,'SP':0.15,'HO':0.15,'SH+':0.15},
 '全部入り(SH自由版)':{'B':0.55,'SP':0.15,'HO':0.15,'SH':0.15},
 'T5 今の構成+recallに5秒バー':{'B':1.0,'T':1},
 'T5+スピード処理(25%)':{'B':0.75,'SP':0.25,'T':1},
}
def main(NP,budget,vs):
    rng=random.Random(1); ps=[]
    for _ in range(NP):
        P=sample_params(rng); P.update(sample_extra(rng)); xparams(P,rng); ps.append(P)
    for v in vs:
        print(f'== 1日{budget/60:.0f}分, 多様さ→出席効果 v={v}')
        base=None
        for k,mix in MIX.items():
            R=[]
            for i,P in enumerate(ps):
                Q=dict(P); Q['v']=v; R.append(run(mix,Q,i,budget))
            if base is None: base=R
            win=sum(1 for x,y in zip(R,base) if x[0]>y[0])/NP
            print(f"  {k:30s} 言える{st.mean(x[0] for x in R):5.1f}% 確実{st.mean(x[1] for x in R):6.1f}語 瞬時{st.mean(x[2] for x in R):6.1f}語 出席{st.mean(x[3] for x in R):4.1f}日 文/日{st.mean(x[4] for x in R):5.1f} 今に勝つ{win*100:4.0f}%")
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 60
    main(NP,600,[0.0,0.15,0.3,0.6])
    main(NP,300,[0.0,0.3])

def addon(NP=80):
    # 追加シナリオ: 新モードはバトル10分を削らず「おまけの+2.5分」(遊びたくて長く遊ぶ場合)
    import sim_poly3 as M
    M.MIX={'今の構成10分':{'B':1.0},'今の構成12.5分':{'B':1.0},'+SP2.5分':{'B':0.8,'SP':0.2},'+HO2.5分':{'B':0.8,'HO':0.2},'+SH+2.5分':{'B':0.8,'SH+':0.2}}
    rng=random.Random(1); ps=[]
    for _ in range(NP):
        P=sample_params(rng); P.update(sample_extra(rng)); xparams(P,rng); ps.append(P)
    for k,mix in M.MIX.items():
        bud=600 if k=='今の構成10分' else 750
        R=[run(mix,P,i,bud) for i,P in enumerate(ps)]
        print(f"  {k:14s} 言える{st.mean(x[0] for x in R):5.1f}% 確実{st.mean(x[1] for x in R):6.1f}語 瞬時{st.mean(x[2] for x in R):6.1f}語")
