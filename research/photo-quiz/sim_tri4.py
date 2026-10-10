# sim_tri4.py -- 第4回: 写真当てクイズ(写真→英語を産出)の検証。sim_poly3b.py の記憶モデル/バトル/日替わりおまけを土台にする。
# 1日12分(バトル10分=600秒 + 追加枠2分=120秒)で全条件をそろえる。90日学習→14日後に測定。
# 測る物:
#  言える%   : 600語を「英語を見て意味が言える」確率の平均(アプリの主目的。sim_poly3b と同じ)
#  確実/瞬時 : p>0.7 の語数 / さらに瞬時(F>0.5)の語数
#  写真で言える: 写真にできる語(pic)のうち「物を見て英語が出る」(産出 pp>0.5)語数 ← 写真クイズ固有の効果
# 追加仮定(すべて範囲で振る。感度分析あり):
#  pic   : 写真にできる語の割合 Lv1 45%, Lv2 35%, Lv3 25%(具体名詞+動作の見える動詞)。
#  産出記憶: 受容(英→意味)とは別の記憶 pm,pS。バトル成功で産出へ少し転移(rp=0.10-0.20)。
#           写真を見て英語を思い出す確率 = max(pp, p0*l1)。l1(0.4-0.6)=「写真→日本語→英語」のL1仲介ルート(RHM: 初級者はこちらが主)。
#  写真→英語の成功: 産出記憶を強く学習 + 受容記憶へ転移 tr(既存 0.4-0.8)。
#  img   : 画像の上乗せ(二重符号化)。受容/産出の m の伸び ×(1+img)。研究は混在(Carpenter&Olson2012は過信除去で優位、追試は差なし)→ 0-0.3、感度で0と0.5。
#  入力(タイピング): 1問 = 写真2s + 想起3s + 文字数/cps + kb(キーボード切替/修正) + 答え・音声2.5s。cps 2.0-3.5字/秒(Palin2019 平均36WPM≒3字/秒は書き写し時)、kb 0.5-2.5s。
#     つづりミス sp 5-20%(想起はできたのに綴れない)。うち半分は「おしい」で救済(支え0.3)、残りは×(★-1, 別解×と同じ害)。
#     overt bonus ov 0-0.1(声/入力での明示的想起の上乗せ。メタ分析 g=0.17、単語では差なしの報告も)。
#  自己評価: 1問 = 写真2s + 想起3s + タップ1s + 答え・音声2.5s + 評価1s = 9.5s→ 実測は速くなりがち 6-8s。
#     cs 10-30% は「ちゃんと思い出さずに答えを見る」(covertの手抜き)→ 見て学ぶ(支え0.8)。過信 overconf で★が上がりすぎる。
#  ヒント段階式: 入力 + 「文字数 _ _ _」→頭文字→1文字ずつ。各+2.5s。attempt の cues=[pat, first, ans]。
#  10秒ルール: 1問 >10s の問題は瞬時化(F)の伸びなし(出席への悪影響はモデル外=表の「10秒超」率で見る)。
#  バトル混ぜ: バトル中の pic 語の復習の mixp(20%) を写真→英語入力に置き換える(時間はその分増える)。
#  多様さ→出席 v: 写真クイズは新鮮さ +0.5 モード分として扱う(感度で v=0/0.3)。
import random, math, statistics as st, sys
sys.path.insert(0,'/home/user/Answer-/research/talk-mode'); sys.path.insert(0,'/home/user/Answer-/research/modes')
from sim_polyglot import p0, learn, attempt, sample_params, sample_extra, INTERVALS
from sim_poly3 import xparams, srs, Fd, bumpF
import sim_poly3b as B3
DAYS=90; DELAY=14; N=600; NEW=10
class W:
    __slots__=('m','S','last','s','due','seen','lv','L','F','Fl','intro','pic','pm','pS','pl','ln')
def mk(i,rng,k):
    w=W()
    w.lv=1 if i<200 else 2 if i<450 else 3; w.m=0.05+0.05*(3-w.lv); w.S=0.2; w.last=0; w.s=0; w.due=0
    w.seen=False; w.intro=False; w.L=rng.randrange(20); w.F=0.0; w.Fl=0.0
    w.pic=rng.random()<{1:0.45,2:0.35,3:0.25}[w.lv]; w.pm=0.0; w.pS=0.2; w.pl=0.0; w.ln=rng.choice([3,4,5,5,6,7,8,9])
    if rng.random()<{1:0.5,2:0.2,3:0.05}[w.lv]*k: w.seen=True; w.m=0.75; w.S=40; w.F=0.2; w.pm=0.4; w.pS=20
    return w
def pp(w,t): return w.pm*math.exp(-max(0,t-w.pl)/w.pS) if w.pm>0 else 0.0
def learnP(w,t,P,ok,sup):
    q=pp(w,t)
    if ok:
        e=1-P['cuecost']*sup; w.pS=max(w.pS,0.2)*(1+P['a']*e*(1-q)**P['dd']); w.pm+=P['b']*(1+P['img'])*(0.4+0.6*e)*(1-w.pm)
    else:
        w.pm+=P['b']*(1+P['img'])*0.5*(1-w.pm); w.pS=max(0.2,w.pS*0.6)
    w.pl=t
def rec2prod(w,t,P,k=1.0):  # 受容の成功→産出へ少し
    f=pp(w,t); w.pm=f+P['rp']*k*(1-f); w.pl=t; w.pS=max(w.pS,w.S*0.5)

def photo_item(rng,P,w,t,style):
    """1問。style: 'type','self','hint'。戻り値 秒"""
    q=max(pp(w,t),p0(w,t)*P['l1'])
    new=not w.intro
    if style=='self':
        sec=P['tself']
        if rng.random()<P['cs']: ok,sup=True,0.8          # 手抜き: 見て覚えるだけ
        else: ok,sup=(rng.random()<q),0.0
        if not ok: sup=1.0
        rated_ok = (ok and sup<0.5) or rng.random()<P['overconf']*(0.5 if sup>=0.5 else 1)
    else:
        typ=w.ln/P['cps']+P['kb']
        cues=[P['pat'],P['first'],P['ans']] if style in('hint','hintT') else []
        ok,sup=attempt(rng,q,cues) if cues else ((rng.random()<q),0.0)
        nh=0 if (ok and sup<0.01) else (3 if not ok else max(1,round(sup*3)))
        sec=2+3+typ+2.5+(2.5*nh if style in('hint','hintT') else 0)
        if not ok: sup=1.0
        rated_ok=ok and sup<0.5
        if ok and rng.random()<P['sp']:          # 綴れない
            sec+=3
            if rng.random()<0.5: sup=max(sup,0.3)
            else: rated_ok=False
        if ok: sup=max(0,sup-P['ov'])             # overt の上乗せ = 自力度が少し上がる扱い
    learnP(w,t,P,ok,sup if ok else 1.0)
    # 受容(英→意味)への効果: 答えの英単語+写真を見る=意味づけ。画像ぶん上乗せ
    bb=P['b']; P['b']=bb*(1+P['img'])
    learn(w,t,P,True if ok else (rng.random()<P['elim']), 1-P['tr']*(1-sup) if ok else 0.85)
    P['b']=bb
    clock=sec-(typ if style=='hintT' else 0) if style!='self' else sec   # hintT: 想起8秒タイマー、入力中は時計を止める
    if ok and sup<0.01 and clock<=10: bumpF(w,t,P,P['kf']*P['tr'])
    if new: w.intro=True; w.s=0; w.due=t
    elif rated_ok and sup<0.5: srs(w,t,'good')
    elif rated_ok: srs(w,t,'soso')
    else: w.s=max(0,w.s-1); w.due=t
    return sec

def photo(rng,P,ws,t,budget,D,style):
    used=0; n=0; slow=0
    while used<budget:
        pl=[w for w in ws if w.pic and w.intro]
        due=[w for w in pl if w.due<=t]
        if due: w=rng.choice(due)
        else:
            fresh=[w for w in ws if w.pic and not w.intro]
            if fresh and rng.random()<P['pnew']: w=fresh[0]      # 未習の物も「当てずっぽう→答え」(pretest)で出す
            elif pl: w=min(pl,key=lambda x:x.due)
            else: break
        sec=photo_item(rng,P,w,t,style); used+=sec; n+=1; slow+=sec>10; t+=sec/86400
    D['ph']=D.get('ph',0)+n; D['slow']=D.get('slow',0)+slow
    return t

def battle_mix(rng,P,ws,t,budget,D,mixp):
    """sim_poly3b.battle と同じ。ただし pic 語の復習の mixp を写真→英語入力に置換"""
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
                pl=[w for w in ws if w.intro]
                if not pl: break
                w=min(pl,key=lambda x:x.due)
        new=not w.intro; q=p0(w,t)
        if new:
            ok,sup=attempt(rng,q,[P['ans']+(1-P['ans'])*P['tile']]); learn(w,t,P,ok,max(sup,0.7) if sup>0 or not ok else 0.3); used+=15
            w.intro=True; w.s=0; w.due=t; queue.append((turn+2,w)); rec2prod(w,t,P,0.5)
        elif w.pic and w.s>=1 and rng.random()<mixp:
            used+=photo_item(rng,P,w,t,'hint'); D['ph']=D.get('ph',0)+1
        else:
            ok,sup=attempt(rng,q,[P['pat'],P['first'],P['ans']]); nh=0 if ok and sup<0.01 else (3 if not ok else max(1,round(sup*3)))
            used+=8+4*nh
            so=ok or rng.random()<P['overconf']
            g='good' if so and sup<0.01 else ('soso' if so else 'bad')
            learn(w,t,P,ok,sup)
            if ok: rec2prod(w,t,P,1-sup)
            if ok and sup<0.01: bumpF(w,t,P,P['kf']*P['soft'])
            srs(w,t,g)
            if g=='bad': queue.append((turn+3,w))
            if g=='good':
                goods+=1
                if goods%3==0: used+=6; q2=p0(w,t); learn(w,t,P,rng.random()<q2+(1-q2)*P['elim'],0.8)
        queue.sort(key=lambda x:x[0]); turn+=1
    return t

PH={'PT':'type','PS':'self','PH':'hint','PHT':'hintT'}
def run(cfg,P,seed):
    rng=random.Random(seed); ws=[mk(i,rng,P['pk']) for i in range(N)]; ra=random.Random(seed*7+3)
    for w in ws:   # 診断(FINAL3 と同じ)
        if (w.seen and rng.random()<0.85) or (not w.seen and w.lv<3 and rng.random()<P['fy']*0.5):
            w.intro=True; w.s=3; w.due=rng.uniform(1,14)
    rot=cfg['rot']; nm=len(set(r for r in rot if r not in PH))+(0.5 if any(r in PH for r in rot) or cfg.get('mixp') else 0)
    slowpen=cfg.get('slowpen',1.0)
    days=0; D={}
    for day in range(DAYS):
        boost=P['v']*nm/3*slowpen*(0.5+0.5*math.exp(-day/30)); ua,ub=ra.random(),ra.random()
        if ua<P['h']*(1-min(1,P['v']*nm/3*slowpen)): break
        if ub>P['attend']+(1-P['attend'])*min(1,boost): continue
        days+=1; t=day+0.5; D['new']=0
        t=battle_mix(rng,P,ws,t,600,D,cfg.get('mixp',0.0))
        m=rot[day%len(rot)]
        if m in PH: t=photo(rng,P,ws,t,120,D,PH[m])
        else:
            f=B3.MODES[m]; t=f(rng,P,ws,t,120,D,0.0) if m in('HY','SH+') else f(rng,P,ws,t,120,D)
    T=DAYS+DELAY
    rec=sum(p0(w,T) for w in ws)/N*100
    solid=sum(1 for w in ws if p0(w,T)>0.7)
    flu=sum(1 for w in ws if p0(w,T)>0.7 and Fd(w,T,P)>0.5)
    prod=sum(1 for w in ws if w.pic and pp(w,T)>0.5)
    return rec,solid,flu,prod,days,D.get('ph',0)/max(1,days),D.get('slow',0)/max(1,D.get('ph',1))
R4=['PA','CL','SP3','HY']
CFG={
 '1 今(バトル10+日替わりおまけ2分)':dict(rot=R4),
 '2 写真クイズ・入力(毎日2分)':dict(rot=['PT']),
 '3 写真クイズ・自己評価(毎日2分)':dict(rot=['PS']),
 '4 写真クイズ・入力+文字数ヒント段階式(毎日2分)':dict(rot=['PH']),
 '5 写真をバトルに混ぜる(pic語復習の20%)+おまけ':dict(rot=R4,mixp=0.2),
 '6 おまけの5つ目として段階式(5日に1回)':dict(rot=R4+['PH']),
 '7 =6だが想起タイマー8秒・入力中は時計停止':dict(rot=R4+['PHT']),
 '8 おまけの5つ目として自己評価(5日に1回)':dict(rot=R4+['PS']),
}
def params(NP):
    rng=random.Random(1); ps=[]
    for _ in range(NP):
        P=sample_params(rng); P.update(sample_extra(rng)); xparams(P,rng)
        P.update(pk=rng.uniform(0.5,1.5), fy=rng.uniform(0.05,0.15), ifr=rng.uniform(0.05,0.15), pg=rng.uniform(1.0,1.3), amb=0.0, soft=rng.uniform(0.5,0.9),
                 rp=rng.uniform(0.10,0.20), l1=rng.uniform(0.4,0.6), img=rng.uniform(0.0,0.3), cps=rng.uniform(2.0,3.5), kb=rng.uniform(0.5,2.5),
                 sp=rng.uniform(0.05,0.2), ov=rng.uniform(0.0,0.1), tself=rng.uniform(6,8), cs=rng.uniform(0.1,0.3), pnew=0.3, v=0.0)
        ps.append(P)
    return ps
def table(ps,title,keys,mod=None):
    print('\n==',title); print('| 構成 | 言える% | 確実 | 瞬時 | 写真で言える | 出席日 | 写真問/日 | 10秒超 | 1に勝つ |'); base=None
    for k in keys:
        R=[]
        for i,P in enumerate(ps):
            Q=dict(P)
            if mod: mod(Q)
            R.append(run(CFG[k],Q,i))
        if base is None: base=R
        win=sum(1 for x,y in zip(R,base) if x[0]>y[0])/len(R)
        print(f"| {k} | {st.mean(x[0] for x in R):.1f} | {st.mean(x[1] for x in R):.0f} | {st.mean(x[2] for x in R):.0f} | {st.mean(x[3] for x in R):.0f} | {st.mean(x[4] for x in R):.1f} | {st.mean(x[5] for x in R):.1f} | {st.mean(x[6] for x in R)*100:.0f}% | {win*100:.0f}% |")
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 40
    ps=params(NP); K=list(CFG)
    table(ps,'基本(v=0, img 0-0.3)',K)
    table(ps,'画像効果なし img=0',K,lambda Q:Q.update(img=0))
    table(ps,'画像効果大 img=0.5',K,lambda Q:Q.update(img=0.5))
    table(ps,'入力が遅い(cps1.5, kb3s=キーボード切替あり)',K,lambda Q:Q.update(cps=1.5,kb=3.0))
    table(ps,'入力が速い(cps3.5, kb0.3s=英字キーボード固定)',K,lambda Q:Q.update(cps=3.5,kb=0.3))
    table(ps,'自己評価の手抜き多い(cs 0.4)+過信',['1 今(バトル10+日替わりおまけ2分)','3 写真クイズ・自己評価(毎日2分)'],lambda Q:Q.update(cs=0.4,overconf=min(0.6,Q['overconf']*1.5)))
    table(ps,'多様さ→出席 v=0.3',K,lambda Q:Q.update(v=0.3))
