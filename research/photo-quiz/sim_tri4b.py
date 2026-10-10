# sim_tri4b.py -- 第4回・第2会議: ROUND2.md (FINAL4) の検証。sim_tri4.py の記憶モデル・仮定をそのまま使う。
# 1日12分 = バトル10分 + おまけ2分(日替わり)。V0 = おまけ4種(PA,CL,SP3,HY)、FINAL4 = +写真当て(5種目→5日に1回)。
# FINAL4 の1問(opt で要素を外せる):
#  答え方 mode: 'split'=7文字以下は入力・8文字以上/2語は自己評価 / 'type'=全部入力 / 'self'=全部自己評価
#  ヒント段階(文字数→頭文字→1文字ずつ) hint=True/False。各+2.5s。
#  入力: 時計は想起部分だけ(入力中は停止)。所要 = 2+3+ヒント + 文字数/cps + kb + 2.5。
#  つづりミス sp(5-20%): ochi=True なら「おしい→正しい綴りを見て再入力」で○(支え0.3, +3s)。False(厳密)なら×。
#  自動修正ON(感度): sp+0.10, kb+1.5s(切替・勝手な修正の取り消し)。
#  SRS star: 'final'=ヒントなし正解★+1・ヒントあり据え置き・×は10分後再確認(★下げない) / 'none'=★を動かさない(期日も) / 'old'=sim_tri4 方式(×で★-1)
#  配分 kp: 「知ってそうで言えない物」(アプリ600語の外。150個)の割合。600語には効かないが、物の名前を言える数(外)に効く。
#  自己評価の過信・手抜き(cs)は sim_tri4 と同じ。
import random, math, statistics as st, sys
sys.path.insert(0,'/tmp/claude-0/-home-user-Answer-/7b95110d-ba08-5cac-b5c8-030a513b1d3f/scratchpad/r4')
import sim_tri4 as T4
from sim_tri4 import W, mk, pp, learnP, rec2prod, battle_mix, params, p0, learn, attempt, srs, bumpF, Fd, B3, R4
DAYS=90; DELAY=14; N=600

def item(rng,P,w,t,o,D):
    q=max(pp(w,t),p0(w,t)*P['l1']); new=not w.intro
    two=w.ln>=8
    typed={'type':True,'self':False,'split':not two}[o['mode']]
    cues=[P['pat'],P['first'],P['ans']] if o['hint'] else []
    ok,sup=attempt(rng,q,cues) if cues else ((rng.random()<q),0.0)
    nh=0 if (ok and sup<0.01) else (3 if not ok else max(1,round(sup*3)))
    nh=nh if o['hint'] else 0
    sp=P['sp']+(0.10 if o.get('ac') else 0); kb=P['kb']+(1.5 if o.get('ac') else 0)
    if typed:
        clock=2+3+2.5*nh; sec=clock+w.ln/P['cps']+kb+2.5
        rated=ok and sup<0.5; hinted=sup>=0.01
        if ok and rng.random()<sp:
            if o['ochi'] and w.ln>=5: sec+=3; sup=max(sup,0.3)
            else: rated=False
        if ok: sup=max(0,sup-P['ov'])
    else:
        clock=P['tself']+2.5*nh; sec=clock
        if ok and sup<0.01 and rng.random()<P['cs']: sup=0.8      # 手抜き
        rated=(ok and sup<0.5) or (rng.random()<P['overconf']*0.5)
        hinted=sup>=0.01
    if not ok: sup=1.0
    learnP(w,t,P,ok,sup)
    bb=P['b']; P['b']=bb*(1+P['img'])
    learn(w,t,P,True if ok else (rng.random()<P['elim']),1-P['tr']*(1-sup) if ok else 0.85)
    P['b']=bb
    if ok and sup<0.01 and clock<=10: bumpF(w,t,P,P['kf']*P['tr'])
    if w.lv==9: return sec,clock               # 600語外: SRS は写真用の独自期日のみ
    if new: w.intro=True; w.s=0; w.due=t
    elif o['star']=='none': pass
    elif o['star']=='old':
        if rated and not hinted: srs(w,t,'good')
        elif rated: srs(w,t,'soso')
        else: w.s=max(0,w.s-1); w.due=t
    else:
        if rated and not hinted: srs(w,t,'good')
        elif not rated: w.due=min(w.due,t+10/1440)
    return sec,clock

def photo(rng,P,ws,ex,t,budget,D,o):
    used=0
    while used<budget:
        if rng.random()<o['kp']:
            due=[x for x in ex if x.intro and x.due<=t]
            w=rng.choice(due) if due else next((x for x in ex if not x.intro),None) or min(ex,key=lambda x:x.due)
            sec,clock=item(rng,P,w,t,o,D)
            if not w.intro: w.intro=True
            w.due=t+(3 if pp(w,t)>0.5 else 1)
        else:
            pl=[w for w in ws if w.pic and w.intro]; due=[w for w in pl if w.due<=t]
            if due: w=rng.choice(due)
            else:
                fresh=[w for w in ws if w.pic and not w.intro]
                if fresh and rng.random()<P['pnew']: w=fresh[0]
                elif pl: w=min(pl,key=lambda x:x.due)
                else: break
            sec,clock=item(rng,P,w,t,o,D)
        used+=sec; t+=sec/86400; D['n']+=1; D['sec']+=sec; D['slow']+=clock>10
    return t

BASE=dict(mode='split',hint=True,ochi=True,star='final',kp=0.3)
def run(cfg,P,seed):
    rng=random.Random(seed); ws=[mk(i,rng,P['pk']) for i in range(N)]; ra=random.Random(seed*7+3)
    ex=[]
    for i in range(150):
        x=mk(450+i,rng,0); x.lv=9; x.pic=True; x.seen=False; x.m=0.05; x.pm=0.0; ex.append(x)
    for w in ws:
        if (w.seen and rng.random()<0.85) or (not w.seen and w.lv<3 and rng.random()<P['fy']*0.5):
            w.intro=True; w.s=3; w.due=rng.uniform(1,14)
    o=cfg.get('o'); rot=R4+(['PHOTO'] if o else [])
    nm=4+(1 if o else 0); days=0; D=dict(new=0,n=0,sec=0,slow=0)
    for day in range(DAYS):
        boost=P['v']*nm/3*(0.5+0.5*math.exp(-day/30)); ua,ub=ra.random(),ra.random()
        if ua<P['h']*(1-min(1,P['v']*nm/3)): break
        if ub>P['attend']+(1-P['attend'])*min(1,boost): continue
        days+=1; t=day+0.5; D['new']=0
        t=battle_mix(rng,P,ws,t,600,D,0.0)
        m=rot[day%len(rot)]
        if m=='PHOTO': t=photo(rng,P,ws,ex,t,120,D,o)
        else:
            f=B3.MODES[m]; t=f(rng,P,ws,t,120,D,0.0) if m in('HY','SH+') else f(rng,P,ws,t,120,D)
    T=DAYS+DELAY
    rec=sum(p0(w,T) for w in ws)/N*100
    solid=sum(1 for w in ws if p0(w,T)>0.7)
    prod=sum(1 for w in ws if w.pic and pp(w,T)>0.5)
    prodx=sum(1 for x in ex if pp(x,T)>0.5)
    return rec,solid,prod,prodx,days,D['sec']/max(1,D['n']),D['slow']/max(1,D['n'])
def O(**k): return dict(o=dict(BASE,**k))
CFG={
 'V0 今(おまけ4種)':dict(),
 'FINAL4 (+写真当て5種目)':O(),
 '-長さ分け→全部入力':O(mode='type'),
 '-長さ分け→全部自己評価':O(mode='self'),
 '-ヒント段階なし':O(hint=False),
 '-おしいなし(厳密)':O(ochi=False),
 '★を動かさない':O(star='none'),
 '★旧方式(×で★-1)':O(star='old'),
 '配分5:5':O(kp=0.5),
 '配分10:0':O(kp=0.0),
 '自動修正ON・キーボード切替':O(ac=True),
 '全部入力+自動修正ON':O(mode='type',ac=True),
}
def table(ps,title,keys,mod=None):
    print('\n==',title); print('| 構成 | 意味が言える% | 確実 | 写真語(600内) | 言えない物(外150) | 出席日 | 秒/問 | 時計10秒超 | V0に勝つ |'); base=None
    for k in keys:
        R=[]
        for i,P in enumerate(ps):
            Q=dict(P)
            if mod: mod(Q)
            R.append(run(CFG[k],Q,i))
        if base is None: base=R
        win=sum(1 for x,y in zip(R,base) if x[0]>y[0])/len(R)
        print(f"| {k} | {st.mean(x[0] for x in R):.2f} | {st.mean(x[1] for x in R):.0f} | {st.mean(x[2] for x in R):.1f} | {st.mean(x[3] for x in R):.1f} | {st.mean(x[4] for x in R):.1f} | {st.mean(x[5] for x in R):.1f} | {st.mean(x[6] for x in R)*100:.0f}% | {win*100:.0f}% |")
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 60
    ps=params(NP); K=list(CFG)
    table(ps,'基本 v=0',K)
    S=['V0 今(おまけ4種)','FINAL4 (+写真当て5種目)','-長さ分け→全部入力','-長さ分け→全部自己評価','自動修正ON・キーボード切替']
    table(ps,'入力が遅い(1文字0.5秒=cps2, kb2.5)',S,lambda Q:Q.update(cps=2.0,kb=2.5))
    table(ps,'自己評価の手抜き・過信が多い(cs0.4, overconf×1.5)',S,lambda Q:Q.update(cs=0.4,overconf=min(0.6,Q['overconf']*1.5)))
    table(ps,'継続効果 v=0.3',S+['★を動かさない','配分10:0'],lambda Q:Q.update(v=0.3))
