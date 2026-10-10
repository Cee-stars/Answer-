# 第4回 第2回会議: ROUND2.md(FINAL4) の検証。バトル10分＋おまけ2分(日替わり)。30日練習→14日後テスト。
# 記憶は 受容(英→意味: sr) と 産出(写真/意味→英語: sp) の2本。バトル=受容想起、写真クイズ=産出想起。
# 他のおまけ5種は「★3以上の語の軽い復習(受容中心・産出少し)」で代表させる(★は動かさない)。
# 写真クイズ: 1回10問まで。jh(アプリの語, 写真向き50%) と tricky(アプリ外の物) を配分で混ぜる。
# 継続効果 v: おまけの種類数/6 に比例して休む日が減る(仮定)。
import random, math, statistics as st, sys
DAYS=30; DELAY=14; INT=[0,1,3,7,14,30]
def mk(r):
    jh=[]
    for i in range(400):
        pr0=r.uniform(0,.8); L=r.choice([3,4,5,5,6,6,7,8,9])
        jh.append(dict(app=True,photo=r.random()<.5,L=L,pr0=pr0,pp0=pr0*.5,sr=.8,spp=.5,last=None,lastp=None,
                       s=0,due=0,seen=False,F=.1,sp0=r.uniform(.6,.9)))
    for x in jh: x['spell']=x['sp0']
    tr=[]
    for i in range(150):
        L=r.choice([6,7,7,8,9,10,11,12,13]); pp0=r.uniform(0,.15)
        tr.append(dict(app=False,photo=True,L=L,pr0=pp0*2,pp0=pp0,sr=.8,spp=.5,last=None,lastp=None,s=0,due=0,seen=False,F=.1,sp0=r.uniform(.35,.65)))
    for x in tr: x['spell']=x['sp0']
    jh.sort(key=lambda x:-x['pr0']); return jh,tr
def Rr(x,t):
    if x['last'] is None: return x['pr0']
    return x['pr0']+(1-x['pr0'])*math.exp(-(t-x['last'])/x['sr'])
def Rp(x,t):
    if x['lastp'] is None and x['last'] is None: return x['pp0']
    l=x['lastp'] if x['lastp'] is not None else x['last']
    return x['pp0']+(1-x['pp0'])*min(Rr(x,t),math.exp(-(t-l)/x['spp']))
def photo_q(x,t,V,P,r):
    """1問。returns cost(sec)"""
    long_ = x['L']>7
    mode = V['ans'] if V['ans']!='split' else ('self' if long_ else 'type')
    p=Rp(x,t); rec=r.random()<p; hint=False
    if not rec and V['hint'] and r.random()<P['hint_rescue']*(Rr(x,t)): rec=True; hint=True   # 文字数→頭文字で思い出す
    think=P['think']+(2.5 if hint else 0)
    typ = x['L']*P['cps'] if mode=='type' else 2.5
    cost=think+typ+1.5                     # +正解発表(音声)
    lim = think if (mode=='type' and V['stop']) else think+(typ if mode=='type' else 0)
    eff = 1.0 if lim<=10 else 0.3
    g=P['grow']; up=lambda s,k:s*(1+(g-1)*k*eff)
    if mode=='self':
        okm = rec or r.random()<P['overconf']
        x['spell']+=(1-x['spell'])*P['sp_view']*eff
        if rec:
            x['spp']=up(x['spp'],P['covert']*(0.5 if hint else 1)); x['sr']=up(x['sr'],.5); x['F']+=P['kf']*(1-x['F'])*eff
        elif not okm: x['spp']=max(.5,x['spp']*.7); cost+=2
        clean = okm and not hint
    else:
        spelled = rec and r.random()<x['spell']; near = rec and not spelled and x['L']>=5 and r.random()<.6
        typo = spelled and r.random()<P['typo']*x['L']
        if rec and ((spelled and not typo) or ((near or typo) and V['oshii'])):
            if near: x['spell']+=(1-x['spell'])*P['sp_fb']*eff; cost+=3
            elif spelled: x['spell']+=(1-x['spell'])*P['sp_ok']*eff
            x['spp']=up(x['spp'],0.5 if hint else 1); x['sr']=up(x['sr'],.5); x['F']+=P['kf']*.8*(1-x['F'])*eff
            clean = not hint
        else:
            x['spell']+=(1-x['spell'])*P['sp_fb']*eff*(1 if rec else .7)
            x['spp']=max(.5,x['spp']*(.8 if rec else .6)); cost+=3; clean=False
            if typo: P['_unfair']+=1
    if x['app'] and x['seen']:
        if clean and V['star']: x['s']=min(5,x['s']+1); x['due']=t+INT[x['s']]
        elif not clean and not rec: x['due']=min(x['due'],t)     # ×→再確認(★は下げない)
    x['lastp']=t; x['last']=t; P['_n']+=1
    return cost
def run(V,P,seed):
    r=random.Random(seed); jh,tr=mk(random.Random(seed*7+3)); P=dict(P); P['_unfair']=0; P['_n']=0
    rot=['o1','o2','o3','o4','o5']+(['photo'] if V['photo'] else [])
    if V.get('daily'): rot=['photo']
    att=P['attend']+P['v']*(1-P['attend'])*len(rot)/6
    days=0; trn=0
    for day in range(DAYS):
        if r.random()>att: continue
        days+=1; t=day+.5; used=0; new=0; q=[]
        dues=sorted([x for x in jh if x['seen'] and x['due']<=t],key=lambda x:(x['s'],x['due'])); di=0
        while used<600:
            t+=1/1440
            if q and q[0][0]<=used: x=q.pop(0)[1]
            elif di<len(dues): x=dues[di]; di+=1
            elif new<10 and any(not y['seen'] for y in jh): x=next(y for y in jh if not y['seen']); new+=1
            else: x=min((y for y in jh if y['seen']),key=lambda y:y['due'])
            if not x['seen']:
                x['seen']=True; used+=8
                if r.random()<x['pr0']: x['last']=t; x['sr']=20; x['s']=1; x['due']=t+1
                else: x['last']=t; x['sr']=.8; x['s']=0; x['due']=t; q.append((used+30,x))
                continue
            ok=r.random()<Rr(x,t); used+=6
            if ok:
                x['sr']*=P['grow']; x['spp']*=1+(P['grow']-1)*.25; x['F']+=P['kf']*(1-x['F']); x['s']=min(5,x['s']+1); x['due']=t+INT[x['s']]
            else:
                x['sr']=max(.5,x['sr']*.6); x['s']=max(0,x['s']-2); x['due']=t; used+=3; q.append((used+40,x))
            x['last']=t; q.sort(key=lambda z:z[0])
        mode=rot[days%len(rot)]; E=120; u=0
        if mode!='photo':
            for x in sorted([y for y in jh if y['seen'] and y['s']>=3],key=lambda y:y['due']):
                if u>=E: break
                u+=8; t+=8/86400
                if r.random()<Rr(x,t): x['sr']*=1+(P['grow']-1)*.4; x['spp']*=1+(P['grow']-1)*.3; x['F']+=P['kf']*.5*(1-x['F']); x['last']=t
        else:
            nj=round(10*V['ratio']); 
            cj=sorted([y for y in jh if y['photo'] and y['seen']],key=lambda y:y['due'])[:nj]
            ct=sorted([y for y in tr],key=lambda y:(not y['seen'],y['lastp'] or 0))[:10-len(cj)]
            for x in cj+ct:
                if u>=E: break
                fresh=not x['seen']; x['seen']=True
                c=photo_q(x,t,V,P,r); u+=c; t+=c/86400
    T=DAYS+DELAY; t30=DAYS
    J=[x for x in jh if x['seen']]; Tr=[x for x in tr if x['seen']]
    rec=sum(Rr(x,T)-x['pr0'] for x in J)
    prod=sum(Rp(x,T)-x['pp0'] for x in J+Tr)
    prodT=sum(Rp(x,T)-x['pp0'] for x in Tr)
    spell=sum(Rp(x,T)*x['spell']-x['pp0']*x['sp0'] for x in J+Tr)
    flu=sum(1 for x in J if Rr(x,T)>.7 and x['F']>.5)
    over=sum(1 for x in J if x['s']>=3 and Rr(x,t30)<.7)   # ★が実力より高い語
    return dict(rec=rec,prod=prod,prodT=prodT,spell=spell,flu=flu,over=over,unf=P['_unfair'],days=days,n=P['_n'])
def params(r):
    return dict(attend=r.uniform(.55,.85),think=r.uniform(2.5,4),cps=r.uniform(.35,.5),grow=r.uniform(1.8,2.5),covert=r.uniform(.7,.9),
                overconf=r.uniform(.15,.35),sp_view=r.uniform(.05,.12),sp_fb=r.uniform(.25,.4),sp_ok=r.uniform(.08,.15),
                typo=r.uniform(.004,.008),kf=r.uniform(.12,.2),hint_rescue=r.uniform(.4,.6),v=0.0)
F4=dict(photo=True,ans='split',hint=True,oshii=True,star=True,stop=True,ratio=.7)
def m(**k): d=dict(F4); d.update(k); return d
VARS={'V0 バトル+おまけ5種':dict(F4,photo=False),'FINAL4':F4,
 '全部入力':m(ans='type'),'全部自己評価':m(ans='self'),'ヒント段階なし':m(hint=False),'おしいなし(厳密)':m(oshii=False),
 '★を動かさない':m(star=False),'配分5:5':m(ratio=.5),'配分10:0':m(ratio=1.0),'入力中タイマー止めない':m(stop=False)}
def table(NP,keys,title,mod=None,daily=False):
    ps=[]
    for s in range(NP):
        P=params(random.Random(s)); 
        if mod: mod(P)
        ps.append(P)
    res={k:[run(dict(VARS[k],daily=daily and VARS[k]['photo']),P,i) for i,P in enumerate(ps)] for k in keys}
    print('\n==',title); print('| 方式 | 意味が言える(新規) | 英語で言える(新規) | うち言えない物 | 正しく綴れる(新規) | 即答 | ★過大 | 不当× | V0比 産出の勝率 |'); print('|---|---|---|---|---|---|---|---|---|')
    b=res[keys[0]]
    for k,R in res.items():
        a=lambda f:st.mean(x[f] for x in R)
        w=sum(x['prod']>y['prod'] for x,y in zip(R,b))/len(R)
        print(f"| {k} | {a('rec'):.1f} | {a('prod'):.1f} | {a('prodT'):.1f} | {a('spell'):.1f} | {a('flu'):.1f} | {a('over'):.1f} | {a('unf'):.1f} | {w*100:.0f}% |")
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 100
    table(NP,list(VARS),'基本 (v=0)')
    K=['V0 バトル+おまけ5種','FINAL4','全部入力','全部自己評価','配分5:5']
    table(NP,K,'感度: 入力が遅い (1文字0.5秒)',lambda P:P.update(cps=.5))
    table(NP,['V0 バトル+おまけ5種','FINAL4'],'感度: 継続効果 v=0.3',lambda P:P.update(v=.3))
    KD=[k for k in VARS if k!='V0 バトル+おまけ5種']
    table(NP,KD,'拡大鏡: 写真クイズを毎日2分(要素の差を見るため。1列目=FINAL4基準)',daily=True)
    table(NP,['FINAL4','全部入力','全部自己評価','配分5:5'],'拡大鏡+入力が遅い',lambda P:P.update(cps=.5),daily=True)
