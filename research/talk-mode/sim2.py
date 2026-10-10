import random, statistics as st, sim
from sim import *
def A_len(it,P,new):  # pattern-only hint still counts as good
    m=A(it,P,new); m['lenient_pat']=True; return m
# monkeypatch grading: treat support from pattern hint (<=pat share) as good
def run_series(name,variants,mod=None,NP=150):
    rng=random.Random(7); params=[sample_params(rng) for _ in range(NP)]
    if mod: [mod(P) for P in params]
    res={k:[run(v,P,i) for i,P in enumerate(params)] for k,v in variants.items()}
    base=list(res.values())[0]
    print('==',name)
    for k,r in res.items():
        r2=st.mean(x[1] for x in r); sol=st.mean(x[2] for x in r)
        win=sum(1 for x,y in zip(r,base) if x[1]>y[1])/len(r)
        print(f"  {k:28s} 2週間後 {r2*100:5.1f}%  確実 {sol:5.1f}問  勝率 {win*100:4.0f}%")
V={k:VARIANTS[k] for k in ['V0 今の方式','A 段階ヒント','A+C 段階ヒント+入力','A+C+B 場面固定']}
run_series('仮定1: ヒントを使っても記憶の伸びがほぼ減らない', V, lambda P:P.update(cuecost=random.uniform(0,0.3)))
run_series('仮定2: 答えのヒントがあまり役に立たない', V, lambda P:P.update(ans=random.uniform(0.05,0.15)))
run_series('仮定3: 毎日欠かさずやる人', V, lambda P:P.update(attend=1.0))
run_series('仮定4: 自己評価がとても甘い人', V, lambda P:P.update(overconf=random.uniform(0.5,0.7)))
run_series('仮定5: 覚えるのが早い人', V, lambda P:P.update(a=random.uniform(3,5),b=random.uniform(0.35,0.5)))
