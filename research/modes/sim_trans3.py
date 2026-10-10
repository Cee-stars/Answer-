# 第3回 翻訳者: 「別解を×にする害」と「ニュアンス説明の有無」を同じ時間予算で比較
# 項目のあいまいさ率・紛らわしい組の率は 作ったデータ(cloze.json / paraphrase.json)から実測して使う
import json, random, math, statistics as st, os
D=os.path.dirname(os.path.abspath(__file__))
cl=json.load(open(os.path.join(D,'cloze.json')))['items']; pp=json.load(open(os.path.join(D,'paraphrase.json')))['pairs']
AMB=sum(len(i['accept_free_input'])>1 for i in cl)/len(cl)         # 自由入力で別解がある率
CONF=sum(p['swap']!='yes' and p['rel'] in('syn','trap','para','usuk') for p in pp)/len(pp)  # 使い分けが要る組の率
N=60; DAYS=30; BUDGET=600  # 1日10分
def run(V,P,seed):
    r=random.Random(seed); items=[]
    for i in range(N):
        items.append(dict(amb=r.random()<AMB, conf=r.random()<CONF, S=0.0, stab=1.0, due=0, seen=False,
                          alt=r.uniform(0.3,0.6),  # 別解を先に思いつく率(あいまい項目)
                          cz=P['cz0'], bad=False))
    mot=1.0; unfair=0; quit_day=None
    for day in range(DAYS):
        if quit_day is not None: break
        if r.random()>P['attend']*mot: continue
        t=0; new=0
        while t<BUDGET:
            due=[it for it in items if it['seen'] and it['due']<=day]
            if due: it=min(due,key=lambda x:x['due'])
            else:
                fr=[x for x in items if not x['seen']]
                if not fr or new>=10:
                    pool=[x for x in items if x['seen']]
                    if not pool: break
                    it=r.choice(pool)
                else: it=fr[0]; new+=1
            cost=P['sec']+(P['nu_sec'] if V['nuance'] and (it['conf'] or V.get('nu_all')) else 0)+(P['alt_sec'] if V['accept'] and it['amb'] else 0)
            t+=cost
            if not it['seen']: it['seen']=True; it['S']=0.4; it['last']=day; it['due']=day; continue
            gap=day-it.get('last',day); rec=it['S']*math.exp(-gap/it['stab'])
            ok=r.random()<rec
            used_alt=ok and it['amb'] and r.random()<it['alt']
            confused=ok and it['conf'] and r.random()<it['cz']   # 類義語を取り違える
            if confused: ok=False
            if used_alt and not V['accept']:
                # 正しいのに×: やり直し扱い、学習者は別解を「誤り」と信じる・やる気が下がる
                unfair+=1; it['bad']= it['bad'] or r.random()<P['unlearn']; mot=max(0.3,mot-P['mot_hit'])
                it['stab']=max(0.5,it['stab']*0.8); it['due']=day; it['S']=min(1,it['S']+P['b']*0.5)
            elif ok:
                it['S']=min(1,it['S']+P['b']*(P['mc'] if V.get('mc') else 1)); it['stab']*=P['grow']; it['due']=day+int(it['stab'])
            else:
                it['S']=min(1,it['S']+P['b']*0.5); it['stab']=max(0.5,it['stab']*0.8); it['due']=day
            if it['conf']:  # 取り違えの減り方: ニュアンス説明ありは大きく、なしは誤答フィードバックからだけ少し
                it['cz']*= (1-P['nu_gain']) if V['nuance'] else (1-P['fb_gain'] if confused else 1)
            it['last']=day
            mot=min(1.0,mot+0.002)
        if mot<P['quit_th'] and r.random()<0.05: quit_day=day
    # 最終テスト(30日目+7日)
    know=sum(1 for it in items if it['seen'] and r.random()<it['S']*math.exp(-7/it['stab']))
    conf_items=[it for it in items if it['conf'] and it['seen']]
    cz=st.mean(it['cz'] for it in conf_items) if conf_items else 0
    return dict(know=know, cz=cz, bad=sum(it['bad'] for it in items), unfair=unfair, quit=quit_day is not None)
def params(r):
    return dict(attend=r.uniform(.6,.9), sec=r.uniform(7,10), nu_sec=r.uniform(3,6), alt_sec=r.uniform(1,2),
                b=r.uniform(.15,.3), grow=r.uniform(1.8,2.6), cz0=r.uniform(.2,.4), nu_gain=r.uniform(.15,.3),
                fb_gain=r.uniform(.03,.08), unlearn=r.uniform(.2,.5), mot_hit=r.uniform(.004,.012), quit_th=.5, mc=r.uniform(.6,.85))
VS={'A 別解×・説明なし':dict(accept=False,nuance=False),'B 別解○・説明なし':dict(accept=True,nuance=False),
    'C 別解×・説明あり':dict(accept=False,nuance=True),'D 別解○・説明あり':dict(accept=True,nuance=True),
    'E ROUND2案: 4択(別解は選択肢から除外)・説明は必要な組だけ':dict(accept=True,nuance=True,mc=True),
    'F 4択・説明を全組に表示':dict(accept=True,nuance=True,mc=True,nu_all=True)}
if __name__=='__main__':
    print(f'実測: 自由入力で別解がある率 AMB={AMB:.2f}（cloze.json）, 使い分けが要る組 CONF={CONF:.2f}（paraphrase.json）')
    res={k:[] for k in VS}
    for s in range(400):
        P=params(random.Random(s))
        for k,V in VS.items(): res[k].append(run(V,P,s*7+1))
    q=lambda xs:(st.median(xs),sorted(xs)[len(xs)//10],sorted(xs)[len(xs)*9//10])
    print('条件 | 1週後に言える語(/60) 中央[10%,90%] | 取り違え率 | 別解を誤りと信じた語 | 不当な× 回数 | 途中でやめた率')
    for k in VS:
        R=res[k]; a=q([x['know'] for x in R])
        print(f"{k} | {a[0]:.0f} [{a[1]},{a[2]}] | {st.mean(x['cz'] for x in R):.2f} | {st.mean(x['bad'] for x in R):.1f} | {st.mean(x['unfair'] for x in R):.0f} | {100*st.mean(x['quit'] for x in R):.0f}%")
    # 対応のある差
    for a,b in [('A 別解×・説明なし','B 別解○・説明なし'),('B 別解○・説明なし','D 別解○・説明あり'),('E ROUND2案: 4択(別解は選択肢から除外)・説明は必要な組だけ','F 4択・説明を全組に表示')]:
        d=[y['know']-x['know'] for x,y in zip(res[a],res[b])]
        print(f'{b} − {a}: 言える語 +{st.mean(d):.1f}（{100*sum(v>0 for v in d)/len(d):.0f}%の学習者で改善, {100*sum(v<0 for v in d)/len(d):.0f}%で悪化）')
