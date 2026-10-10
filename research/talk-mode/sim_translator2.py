# 第2回: FINAL案とその要素抜き（sim_translator.py のあいまいさモデル + sim_polyglot.py の シャドーイング/言い直し/返事ターン発話/音声認識 を取り込み）
import random, math, statistics as st, sys
from sim_translator import Item, p0, learn, attempt, sample_params, CLS, LEVELS, SCENES, N_ITEMS, DAYS, DELAY, TURNS, DAILY_NEW, INTERVALS
def extra(rng):
    return dict(sh=rng.uniform(0.2,0.6), fr=rng.uniform(0.10,0.25), fa=rng.uniform(0.03,0.10),
                fmt=rng.uniform(0.15,0.35),   # 文字起こしの表記ゆれで完全一致が外れる率（数字/wanna/句読点/大文字/Im等）
                fmtres=rng.uniform(0.02,0.06)) # 頑健な判定でも残る外れ率

def amb_rate(it,P,V,ans_visible):
    b={'A':P['ambA'],'B':P['ambB'],'C':P['ambC'],'D':0.03}[it.cl]
    if ans_visible: b*=1-P['ansfix']
    if V['rewrite']: b*= P['rwkeep'] if it.cl in 'AC' else 0.7
    if V['judge'] and it.cl in 'BC': b*=1-P['synfix']
    return b

def run(V,P,seed):
    rng=random.Random(seed); items=[Item(LEVELS[i],SCENES[i]) for i in range(N_ITEMS)]
    for i,it in enumerate(items): it.cl=CLS[i]
    attend=P['attend']; prod=0
    def sched(it,t,g,new,queue,turn):
        if new: it.s=0; it.due=t; queue.append((turn+2,it)); (V.get('reask') and queue.append((turn+5,it)))
        elif g=='good': it.s=min(5,it.s+1); it.due=t+INTERVALS[it.s]
        elif g=='soso':
            it.due=t+INTERVALS[1]
            if V.get('reask'): queue.append((turn+3,it))
        else: it.s=max(0,it.s-2); it.due=t; queue.append((turn+3,it))
        queue.sort(key=lambda x:x[0])
    for day in range(DAYS):
        if rng.random()>attend: continue
        newc=0; t=day+0.5; queue=[]
        for turn in range(TURNS):
            t+=2/1440
            reply=(turn%3==2)
            if reply and not V['reply_prod']: continue
            due=sorted([it for it in items if it.seen and it.due<=t],key=lambda it:it.s)
            if reply: # 返事を聞いて質問を言うターン：既習項目のみ
                pool=due or [it for it in items if it.seen]
                if not pool: continue
                it=pool[0]
            elif queue and queue[0][0]<=turn: it=queue.pop(0)[1]
            elif due: it=due[0]
            else:
                fresh=[it for it in items if not it.seen]
                if fresh and newc<DAILY_NEW: it=fresh[0]; newc+=1
                else:
                    rest=[it for it in items if it.seen]
                    if not rest: continue
                    it=min(rest,key=lambda x:x.due)
            new=not it.seen
            if V['name']=='V0':
                if new or it.s<3: cues=[P['ans']+(1-P['ans'])*P['tile']]; grade='tile'; ansv=True
                else: cues=[P['ans']]; grade='self'; ansv=True
            else:
                if new and V.get('shadow'): it.m+=P['b']*P['sh']*(1-it.m); it.seen=True; it.last=t
                if reply: cues=[P['first'],P['tile']]; ansv=True
                else: cues=[P['pat'],P['pat']*0.7,P['ans'],P['first']]+([P['tile']] if it.s<2 else []); ansv=False
                grade=V['grade']
            q=p0(it,t)
            if grade!='tile': prod+=1
            # あいまい: 自力で言えたが別の正しい言い方
            if grade!='tile' and rng.random()<q and rng.random()<amb_rate(it,P,V,ansv):
                if V['judge'] and grade!='self':   # 「◯通じる」→型ヒントで言い直し
                    ok,sup=attempt(rng,0.0,[0.85]); ok=True; sup=max(sup,0.3); g='soso'
                elif grade=='self': ok,sup,g=True,0.5,'soso'
                else:   # 完全一致で×→次のヒントへ
                    ok,sup=attempt(rng,0.0,cues[1:] or [0.0]); sup=max(sup,0.5) if ok else sup; g='soso' if ok else 'bad'
                learn(it,t,P,ok,sup); sched(it,t,g,new,queue,turn); continue
            ok,sup=attempt(rng,q,cues)
            if grade=='tile': g='good' if ok else 'bad'
            elif grade=='self':
                so=ok or rng.random()<P['overconf']; g='good' if so and sup<0.01 else ('soso' if so else 'bad')
            else: # asr
                fr=P['fr']+(1-P['fr'])*(P['fmtres'] if V['judge'] else P['fmt'])
                if ok: rec=rng.random()>fr or rng.random()<(0.9 if V.get('assist') else 0.5)  # 不一致時は文字起こしと正解を並べて本人が確認(assist)/ボタンで半分救済
                else: rec=rng.random()<P['fa'] or rng.random()<P['overconf']*0.25
                g='good' if rec and sup<0.01 else ('soso' if rec else 'bad')
            learn(it,t,P,ok,sup); sched(it,t,g,new,queue,turn)
    T2=DAYS+DELAY
    return st.mean(p0(it,T2) for it in items), sum(p0(it,T2)>0.7 for it in items), prod/(DAYS*P['attend'])

FINAL=dict(name='F',rewrite=True,judge=True,grade='asr',reply_prod=True,shadow=True,reask=True)
VARS={'V0 今の方式':dict(name='V0',rewrite=False,judge=False,grade='tile',reply_prod=False),
 'FINAL':FINAL,
 'FINAL -1 書き換えなし':dict(FINAL,rewrite=False),
 'FINAL -5 別解判定なし(完全一致)':dict(FINAL,judge=False),
 'FINAL -3 音声→自己評価':dict(FINAL,grade='self'),
 'FINAL -6 返事ターンは4択のまま':dict(FINAL,reply_prod=False),
 'FINAL+ 音声は補助(不一致は本人確認)':dict(FINAL,assist=True),
 'FINAL -1-5 (書換も別解もなし)':dict(FINAL,rewrite=False,judge=False)}
def main(NP=150,mod=None,title=''):
    rng=random.Random(1); ps=[sample_params(rng) for _ in range(NP)]
    r2=random.Random(2); [P.update(extra(r2)) for P in ps]
    if mod: r3=random.Random(3); [mod(P,r3) for P in ps]
    res={k:[run(v,P,i) for i,P in enumerate(ps)] for k,v in VARS.items()}
    b=res['V0 今の方式']; f=res['FINAL']; print('==',title)
    for k,r in res.items():
        print(f"{k:28s} 2週間後{st.mean(x[0] for x in r)*100:5.1f}% 確実{st.mean(x[1] for x in r):5.1f}問 発話{st.mean(x[2] for x in r):4.1f}回/日 "
              f"V0に勝つ{sum(x[0]>y[0] for x,y in zip(r,b))/NP*100:4.0f}% FINALに勝つ{sum(x[0]>y[0] for x,y in zip(r,f))/NP*100:4.0f}%")
if __name__=='__main__':
    main(title='基本')
    main(mod=lambda P,r:P.update(fr=r.uniform(0.3,0.45)),title='感度: 音声認識が厳しい fr30-45%')
    main(mod=lambda P,r:[P.update({k:min(.95,P[k]*1.5)}) for k in ('ambA','ambB','ambC')],title='感度: あいまいさ1.5倍')
