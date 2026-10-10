# sim_ling3.py -- 第3回(言語学者担当): 新機能5つを「1日の練習秒数をそろえて」比較する学習者モデル
# 土台: research/talk-mode/sim.py の記憶モデル (p=m*exp(-dt/S), 自力想起ほど S が伸びる, 手がかり依存はcuecostで割引)
# 追加した仮定(すべて範囲で乱数化し、感度分析で動かす):
#  [A] 単語プール430語(アプリのWORDS+W2相当)。難度帯 易40%/中40%/難20%。学習者の語彙力θで「最初から知っている語」が決まる。
#      知っている語は m=0.95,S=2000日(ほぼ忘れない), 即答度F=0.2-0.7 から開始。
#  [B] 意味的干渉(Tinkham 1993/97, Waring 1997, Nakata&Suzuki 2019): 35%の語は類義・対義グループ(2-4語)に属す。
#      同じグループの「弱い(p<0.6)」語を直近2日以内に練習していると、想起率と学習量が I(類義) / I*antr(対義) だけ下がる。
#      強い語(★3以上 or 既知)と結ぶ場合は干渉なし(既知語への結び付けは手がかり＋関係づけの深い処理になる)。
#  [C] 文脈(Webb 2007, Laufer&Hulstijn 2001): 例文つき出題は記銘に ctxb の上乗せ(コロケーション・用法)。
#      ただし例文を先に見せると意味が推測でき(ctxcue)、その分は「手がかりで当たった」扱い(自力想起の効果が減る)。
#  [D] 即答度F: 時間制限のある自力正解で kf ずつ上がり、Sf日で減衰。即答 = p>0.7 かつ F>0.5。
#  [E] 診断(CAT/Yes-No): 180秒。θの推定誤差 sd=σ。推定で「ほぼ既知(P>0.85)」の語は新出扱いせず ★3・1-14日後の確認に回す。
#      誤って既知扱いされた未知語は確認で×→通常の学習に戻る。
#  [F] スピード処理: 既知/★3以上の語を含む短文を6秒で処理、1文に2語。F を上げ S を少し伸ばすが SRS は動かさない(流暢さの柱: Nation)。
#  [G] しりとり: 5秒/語、語の頭文字から自分で出す→出てくるのは主に既知の易しい語(SRSの対象外)。F が上がるのみ。
#      motivation(継続率の上昇)は mot で別に入れ、感度で 0 と +10% を比べる。
import random, math, statistics as st, sys

DAYS=60; DELAY=14; BUDGET=300; NWORDS=430; DAILY_NEW=10
INTERVALS=[0, 10/1440, 1/24, 1, 3, 7]
BAND=[-1.0]*172+[0.5]*172+[1.5]*86

def sample_params(rng):
    return dict(a=rng.uniform(1.5,3.5), dd=rng.uniform(0.5,1.5), b=rng.uniform(0.15,0.4),
        overconf=rng.uniform(0.1,0.4), attend=rng.uniform(0.6,0.95), cuecost=rng.uniform(0.5,1.0),
        theta=rng.uniform(-1.0,1.5), I=rng.uniform(0.15,0.35), antr=rng.uniform(0.3,0.8),
        rel=rng.uniform(0.1,0.3), ctxb=rng.uniform(0.05,0.2), ctxcue=rng.uniform(0.2,0.45),
        gen=rng.uniform(0.1,0.3), prodpen=rng.uniform(0.6,0.85), kf=rng.uniform(0.15,0.3), Sf=rng.uniform(20,50),
        sigma=rng.uniform(0.2,0.5), mot=0.0, guess4=0.25)

class W:
    __slots__=('F0','d','m','S','last','s','due','seen','F','Fl','g','ant','known0','lastp')
def pk(theta,d): return 1/(1+math.exp(-2.0*(theta-d)))
def p(w,t): return w.m*math.exp(-max(0,t-w.last)/w.S) if w.seen else 0.0
def Fv(w,t,P): return max(w.F0,w.F*math.exp(-max(0,t-w.Fl)/P['Sf']))  # 既知語の即答度は元の水準より下がらない

def build(rng,P):
    ws=[]
    for i in range(NWORDS):
        w=W(); w.d=BAND[i]; w.s=0; w.due=0; w.g=-1; w.ant=False; w.lastp=-99
        w.known0=rng.random()<pk(P['theta'],w.d)
        if w.known0: w.m=0.95; w.S=2000; w.last=0; w.seen=False; w.F=rng.uniform(0.2,0.7); w.Fl=0; w.F0=w.F
        else: w.m=0; w.S=0.3; w.last=0; w.seen=False; w.F=0; w.Fl=0; w.F0=0
        ws.append(w)
    # 類義・対義グループ: 35%の語, 同じ難度帯の中で 2-4語(データ順では隣接=テーマ別に並んでいる想定)
    idx=list(range(NWORDS)); g=0; i=0
    while i<NWORDS:
        if rng.random()<0.35/3*1.0:
            k=rng.choice([2,3,4])
            for j in range(i,min(NWORDS,i+k)):
                ws[j].g=g; ws[j].ant=(j>i and rng.random()<0.4)
            g+=1; i+=k
        else: i+=1
    return ws

def known_p(w,t):  # 本当に意味が出る確率(初期既知は seen でなくても記憶あり)
    if w.seen: return p(w,t)
    return w.m*math.exp(-t/w.S) if w.known0 else 0.0

def interf(w,ws,groups,t,P,partner=None):
    if w.g<0: return 0.0
    tot=0.0
    for o in groups[w.g]:
        if o is w or o is partner: continue
        if t-o.lastp<2 and known_p(o,t)<0.6:
            tot+=P['I']*(P['antr'] if (o.ant or w.ant) else 1.0)
    return min(0.6,tot)

def learn(w,t,P,ok,sup,q,mult=1.0,Sx=1.0):
    if ok:
        e=1-P['cuecost']*sup
        w.S*=(1+P['a']*e*(1-q)**P['dd']*mult)*Sx
        w.m+=P['b']*(0.4+0.6*e)*(1-w.m)*mult
    else:
        w.m+=P['b']*0.5*(1-w.m)*mult; w.S=max(0.8,w.S*0.7)   # 失敗→答えを見る=再学習
    w.last=t; w.seen=True; w.lastp=t

def bumpF(w,t,P,amt):
    f=Fv(w,t,P); w.F=f+amt*(1-f); w.Fl=t

def run(V,P,seed):
    rng=random.Random(seed); ws=build(rng,P)
    groups={}
    for w in ws:
        if w.g>=0: groups.setdefault(w.g,[]).append(w)
    order=list(ws)
    if V.get('spread'):   # 同じグループの新出を3日以上ずらす: グループの2語目以降を後ろへ回す
        first=[w for w in ws if w.g<0 or groups[w.g][0] is w]; rest=[w for w in ws if not (w.g<0 or groups[w.g][0] is w)]
        order=[];
        while first or rest:
            order+=first[:25]; first=first[25:]; order+=rest[:5]; rest=rest[5:]
    flu0=sum(1 for w in ws if w.known0 and w.m>0.7 and w.F0>0.5)
    attend=min(0.99,P['attend']*(1+(P['mot'] if V.get('game') else 0)))
    skipdiag=set()
    days=0; secs=0
    for day in range(DAYS):
        if rng.random()>attend: continue
        days+=1; t=day+0.5; used=0; newc=0
        if V.get('diag') and days==1:
            used+=180
            th=P['theta']+rng.gauss(0,P['sigma'])
            for w in ws:
                if pk(th,w.d)>0.85:
                    w.seen=True; w.s=3; w.due=day+rng.uniform(1,14)
                    if w.known0: w.m=0.95; w.S=2000; w.last=0
                    else: w.m=0.0; w.S=0.3; w.last=0
            order=sorted([w for w in order if not w.seen],key=lambda w:-pk(th,w.d)) if V.get('adapt_order') else [w for w in order if not w.seen]
        # 流暢さ枠(スピード処理/しりとり): 予算の一部
        side=V.get('side'); sideb=int(P.get('budget',BUDGET)*V.get('side_share',0)) if side else 0
        B=P.get('budget',BUDGET)
        if side and sideb>0:
            pool=[w for w in ws if (w.known0 and not w.seen) or (w.seen and w.s>=3)]
            if pool:
                u=0
                while u<sideb:
                    t+=6/86400
                    if side=='speed':
                        for w in rng.sample(pool,min(2,len(pool))):
                            q=known_p(w,t)
                            if rng.random()<q:
                                bumpF(w,t,P,P['kf']*0.6)
                                if w.seen: w.S*=1.08
                        u+=6
                    else:  # しりとり: 易しい語に偏る
                        w=min(rng.sample(pool,min(4,len(pool))),key=lambda x:x.d)
                        if rng.random()<known_p(w,t)*0.85: bumpF(w,t,P,P['kf']*0.5)
                        u+=5
                used+=u
        queue=[]; turn=0; sinceq=0
        dues=sorted([w for w in ws if w.seen and w.due<=t+0.01],key=lambda w:(w.s,w.due))
        di=0; prev=None
        while used<B:
            t+=1/1440
            if queue and queue[0][0]<=turn: w=queue.pop(0)[1]
            elif di<len(dues): w=dues[di]; di+=1
            else:
                fw=next((x for x in order if not x.seen),None) if newc<DAILY_NEW else None
                if fw is not None:
                    w=fw; newc+=1
                else:
                    rest=[w for w in ws if w.seen]
                    if not rest: break
                    w=min(rest,key=lambda x:x.due)
            new=not w.seen
            if new:
                # meet: 例文ヒント付き4択。既知語は即正解だが時間は使う
                cost=8; q=known_p(w,t)
                I=interf(w,ws,groups,t,P)
                if w.known0 and rng.random()<q:
                    w.seen=True; w.last=t; w.lastp=t; w.s=1; w.due=t+INTERVALS[1]  # 今のアプリ: 知ってても★0→1から
                    if V.get('meet_skip'): w.s=3; w.due=t+3
                else:
                    w.m=0.35*(1-I)+ (P['ctxb'] if V.get('ctx') else 0); w.S=0.8; w.seen=True; w.last=t; w.lastp=t
                    w.s=0; w.due=t; queue.append((turn+2,w))
                used+=cost; turn+=1; continue
            q0=known_p(w,t)
            if not w.seen: pass
            kind=V['policy'](w,turn,rng)
            I=interf(w,ws,groups,t,P)
            cost=6; mult=1.0; Sx=1.0; sup=0.0; timed=True; selfg=True
            if kind=='recall':
                q=q0*(1-I)
                ok=rng.random()<q
                if not ok: cost+=3
            elif kind=='syn_safe' or kind=='syn_naive':
                # 言い換え: 相手語を見せて目標語の意味/語を出す。safe=相手は強い語のみ。naive=グループ内の誰でも(弱い語も)
                cand=[o for o in (groups.get(w.g,[]) if w.g>=0 else []) if o is not w]
                if kind=='syn_safe': cand=[o for o in cand if (o.known0 and not o.seen) or o.s>=3]
                if not cand:  # 相手がいない語は通常想起
                    q=q0*(1-I); ok=rng.random()<q; cost=6+(0 if ok else 3)
                else:
                    o=rng.choice(cand); cost=9
                    po=known_p(o,t)
                    if kind=='syn_naive': I=min(0.6,I+P['I']*(P['antr'] if (o.ant or w.ant) else 1)*(1-po))
                    cue=0.2*po
                    q=q0*(1-I); ok=rng.random()<q
                    if not ok and rng.random()<cue: ok=True; sup=0.5
                    mult=(1+P['rel']*po)*(1-I)
                    if rng.random()<po: bumpF(o,t,P,P['kf']*0.4); o.lastp=t
                    if not ok: cost+=3
            elif kind=='ctx_first':   # 例文の中で単語を見せて意味(推測できる分は手がかり)
                cost=9; q=q0*(1-I); ok=rng.random()<q
                if not ok and rng.random()<P['ctxcue']: ok=True; sup=0.7
                mult=1+P['ctxb']*2
                if not ok: cost+=3
            elif kind=='ctx_after':   # まず単語だけで思い出す→例文はフィードバック
                cost=10; q=q0*(1-I); ok=rng.random()<q
                mult=1+P['ctxb']*1.5
                if not ok: cost+=2
            elif kind=='ctx_fail':    # 単語だけで想起。×のときだけ例文つきで答えを見せる(+4秒)
                cost=6; q=q0*(1-I); ok=rng.random()<q
                if not ok: cost+=7; mult=1+P['ctxb']*1.5
            elif kind=='cloze':       # 和訳付き例文の空所に英語を言う(産出)。客観採点(4択でない,タップで答え合わせ)
                cost=10; q=q0*P['prodpen']*(1-I); ok=rng.random()<q
                if not ok and rng.random()<0.3: ok=True; sup=0.6   # 頭文字ヒント
                mult=1+P['ctxb']*2; Sx=1+P['gen'] if ok and sup==0 else 1
                selfg=False
                if not ok: cost+=3
            else: raise ValueError(kind)
            seen_ok = ok or (selfg and rng.random()<P['overconf'])
            graded='good' if seen_ok and sup<0.01 else ('soso' if seen_ok else 'bad')
            learn(w,t,P,ok,sup,q0,mult,Sx)
            if ok and sup<0.01 and timed: bumpF(w,t,P,P['kf'])
            elif ok: bumpF(w,t,P,P['kf']*0.2)
            if kind=='cloze' and V.get('cloze_sep') and not ok: graded='soso'   # 産出の失敗で受容のSRSを下げない
            if graded=='good': w.s=min(5,w.s+1); w.due=t+INTERVALS[w.s]
            elif graded=='soso': w.due=t+INTERVALS[1]
            else: w.s=max(0,w.s-2); w.due=t; queue.append((turn+3,w))
            queue.sort(key=lambda x:x[0]); used+=cost; turn+=1
        secs+=used
    global LAST; LAST=ws
    T2=DAYS+DELAY
    unk=[w for w in ws if not w.known0]
    ret=st.mean(known_p(w,T2) for w in unk) if unk else 0
    solid=sum(1 for w in unk if known_p(w,T2)>0.7)
    flu=sum(1 for w in ws if known_p(w,T2)>0.7 and Fv(w,T2,P)>0.5)-flu0
    return ret,solid,flu,len(unk)

def mix(*kinds):
    def pol(w,turn,rng): return kinds[turn%len(kinds)]
    return pol
REC=mix('recall')
VARS={
 'V0 今のバトルのみ':dict(policy=REC),
 'S1 言い換え(素朴:新語同士も結ぶ)':dict(policy=mix('recall','syn_naive')),
 'S2 言い換え(既知語とだけ結ぶ+新出を離す)':dict(policy=mix('recall','syn_safe'),spread=True),
 'C1 例文を先に見せる':dict(policy=mix('ctx_first'),ctx=True),
 'C2 単語で想起→例文で確認':dict(policy=mix('ctx_after'),ctx=True),
 'C3 例文の空所に言う(★3以上)':dict(policy=lambda w,t,r:'cloze' if w.s>=3 else 'recall',ctx=True),
 'C4 ×の時だけ例文で答え':dict(policy=mix('ctx_fail'),ctx=True),
 'C3b 空所(★3以上,失敗で★を下げない)':dict(policy=lambda w,t,r:'cloze' if w.s>=3 else 'recall',ctx=True,cloze_sep=True),
 'D1 診断あり':dict(policy=REC,diag=True,adapt_order=True),
 'D0 診断なし・既知語は一発で★3':dict(policy=REC,meet_skip=True),
 'F1 スピード処理25%':dict(policy=REC,side='speed',side_share=0.25),
 'F2 しりとり25%':dict(policy=REC,side='shiri',side_share=0.25,game=True),
 'ALL 推奨(診断+言い換え1/3+×時例文+スピード10%)':dict(policy=lambda w,t,r:('syn_safe' if t%3==1 else 'ctx_fail'),
                     ctx=True,spread=True,diag=True,adapt_order=True,side='speed',side_share=0.10),
}
def main(NP,title,mod=None,keys=None):
    rng=random.Random(1); ps=[sample_params(rng) for _ in range(NP)]
    if mod:
        r=random.Random(9)
        for P in ps: mod(P,r)
    keys=keys or list(VARS)
    res={k:[run(VARS[k],P,i) for i,P in enumerate(ps)] for k in keys}
    b=res[keys[0]]
    print('==',title)
    for k,r in res.items():
        m=[st.mean(x[j] for x in r) for j in range(4)]
        win=sum(1 for x,y in zip(r,b) if x[0]>y[0])/len(r)
        print(f"  {k:30s} 未知語の14日後保持{m[0]*100:5.1f}%  定着{m[1]:5.1f}語/{m[3]:.0f}  即答+{m[2]:5.1f}語  V0に勝つ{win*100:4.0f}%")

if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 100
    main(NP,f'基本: 1日{BUDGET}秒・{DAYS}日+{DELAY}日あけて測定')
    K=['V0 今のバトルのみ','S1 言い換え(素朴:新語同士も結ぶ)','S2 言い換え(既知語とだけ結ぶ+新出を離す)','C1 例文を先に見せる','C2 単語で想起→例文で確認','C3 例文の空所に言う(★3以上)','C3b 空所(★3以上,失敗で★を下げない)','C4 ×の時だけ例文で答え','ALL 推奨(診断+言い換え1/3+×時例文+スピード10%)']
    main(NP,'感度1: 干渉が強い(I=0.35-0.5)',lambda P,r:P.update(I=r.uniform(0.35,0.5)),K)
    main(NP,'感度2: 干渉なし(I=0)・関係づけの効果大',lambda P,r:P.update(I=0,rel=r.uniform(0.3,0.5)),K)
    main(NP,'感度3: 文脈の上乗せ0',lambda P,r:P.update(ctxb=0),K)
    KD=['V0 今のバトルのみ','D1 診断あり','D0 診断なし・既知語は一発で★3','ALL 推奨(診断+言い換え1/3+×時例文+スピード10%)']
    main(NP,'感度4: 初級者(θ=-1〜0)',lambda P,r:P.update(theta=r.uniform(-1,0)),KD)
    main(NP,'感度5: 上級寄り(θ=1〜2)',lambda P,r:P.update(theta=r.uniform(1,2)),KD)
    main(NP,'感度6: 診断の誤差大(σ=0.8-1.2)',lambda P,r:P.update(sigma=r.uniform(0.8,1.2)),KD)
    KF=['V0 今のバトルのみ','F1 スピード処理25%','F2 しりとり25%']
    main(NP,'感度8: 1日600秒(10分)',lambda P,r:P.update(budget=600),['V0 今のバトルのみ','S2 言い換え(既知語とだけ結ぶ+新出を離す)','C1 例文を先に見せる','C4 ×の時だけ例文で答え','D1 診断あり','F1 スピード処理25%','ALL 推奨(診断+言い換え1/3+×時例文+スピード10%)'])
    main(NP,'感度7: しりとりで継続率+10%',lambda P,r:P.update(mot=0.10),KF)
