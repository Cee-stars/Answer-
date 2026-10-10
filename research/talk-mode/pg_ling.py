# sim_linguist.py  -- extension of sim.py (original untouched)
# Adds: (1) rule/construction skill per question family (Pienemann-style stages, readiness),
#       (2) chunk (frame) skill per first-two-words frame ("can i", "could you" ...),
#       (3) family *selection* skill (be vs do vs modal vs no-inversion) trained only when unprimed,
#       (4) hints that differ in WHAT they supply: frame (syntax) vs content (words),
#       (5) priming when the previous item has the same family (blocked practice),
#       (6) transfer test: saying NEW questions of the same families.
import random, math, statistics as st, sys, json, re, os
from sim import Item, p0, INTERVALS, DAYS, DELAY, TURNS, DAILY_NEW

HERE=os.path.dirname(os.path.abspath(__file__))
RAW=json.load(open(os.path.join(HERE,'qitems.json')))

def family(en):
    e=en.lower().replace("sorry, ","").replace("oh really? ","")
    if re.search(r", (isn't|aren't|do|don't|is|are) \w+\?$",e) or re.match(r"(don't|aren't|isn't|doesn't) ",e): return 'TAG_NEG'
    if re.match(r"(do you know|can you tell me|could you tell me) ",e) or 'do you think' in e: return 'EMBED'
    if re.match(r"(what about|how come|any |what was that)",e): return 'FORMULA'
    if re.match(r"(who wants|what happened|which line goes|how many people are)",e): return 'WH_SUBJ'
    if re.match(r"(can|could|may|would|should|is it okay if|do you mind if) ",e): return 'MODAL'
    if re.match(r"(have|has) ",e) or re.match(r"how long have",e): return 'PERF'
    if re.match(r"(do|does|did) ",e): return 'DO_YN'
    if re.match(r"(is|are|was|were) ",e): return 'BE_YN'
    if re.match(r"(what|where|when|which|why|who|how)\b",e):
        if re.search(r"^(what|where|when|which|why|who|how)( \w+)?( \w+)? (do|does|did) ",e): return 'WH_DO'
        return 'WH_BE'
    return 'FORMULA'
STAGE={'FORMULA':2,'MODAL':3,'BE_YN':4,'DO_YN':4,'WH_BE':4,'WH_DO':5,'WH_SUBJ':5,'PERF':5,'EMBED':6,'TAG_NEG':6}
FAMS=list(STAGE)
ECHO=re.compile(r"\b(is|was|does|do|did|don't|doesn't|am|are|can|it's not)[.!]",re.I)

class QItem(Item):
    __slots__=('fam','frame','echo','idx')

def build_items():
    out=[]
    for i,x in enumerate(RAW):
        it=QItem(x['level'],i%5); it.fam=family(x['en'])
        it.frame=' '.join(re.sub(r"^(sorry|oh really\?),? ","",x['en'].lower()).split()[:2]); it.echo=bool(ECHO.search(x['answer']))
        out.append(it)
    return out
FAMCOUNT={f:sum(1 for x in RAW if family(x['en'])==f) for f in FAMS}

def sample_params(rng):
    P=dict(a=rng.uniform(1.5,3.5), dd=rng.uniform(0.5,1.5), b=rng.uniform(0.15,0.4),
        overconf=rng.uniform(0.1,0.45), attend=rng.uniform(0.6,0.95), cuecost=rng.uniform(0.5,1.0),
        lex=rng.uniform(0.45,0.85),                       # content words available for a lv1 item
        rg=rng.uniform(0.015,0.04), rh=rng.uniform(0.05,0.12), rs=rng.uniform(0.01,0.03),
        Tg=rng.uniform(90,200), Th=rng.uniform(60,150), prime=rng.uniform(0.3,0.6),
        neg=rng.uniform(0.0,0.006),                       # negative transfer: inversion habit -> embedded/subject Qs
        # cues: (frame support, content support)
        pat=(rng.uniform(0.6,0.9),0.0), first=(rng.uniform(0.4,0.7),0.05),
        ans_echo=(rng.uniform(0.3,0.5),rng.uniform(0.1,0.3)), ans_cont=(0.0,rng.uniform(0.2,0.45)),
        tile=(rng.uniform(0.5,0.8),rng.uniform(0.6,0.9)), kw=(0.0,rng.uniform(0.3,0.6)),
        rule=(rng.uniform(0.3,0.5),0.0))
    P['g0']={f:{2:rng.uniform(0.3,0.6),3:rng.uniform(0.3,0.6),4:rng.uniform(0.15,0.4),5:rng.uniform(0.05,0.25),6:rng.uniform(0,0.1)}[STAGE[f]] for f in FAMS}
    P['s0']={f:rng.uniform(0.5,0.8) for f in FAMS}
    return P

def cue_vec(name,it,P):
    if name=='ans': return P['ans_echo'] if it.echo else P['ans_cont']
    return P[name]

class Learner:
    def __init__(s,P):
        s.P=P; s.g=dict(P['g0']); s.sel=dict(P['s0']); s.h={}
    def decay(s):
        for f in s.g: s.g[f]*=math.exp(-1/s.P['Tg'])
        for k in s.h: s.h[k]*=math.exp(-1/s.P['Th'])
    def ready(s,f):
        st_=STAGE[f]; low=[s.g[x] for x in FAMS if STAGE[x]==st_-1]
        return 1.0 if not low else min(1,max(0.15,st.mean(low)/0.5))
    def L(s,it):
        L0=max(0.1,s.P['lex']-0.1*(it.lv-1)); return L0+(1-L0)*0.5 if it.seen else L0
    def F(s,it,primed):
        F=1-(1-s.g[it.fam])*(1-s.h.get(it.frame,0)); sel=1.0 if primed else s.sel[it.fam]
        return F*sel

def attempt(rng,it,lr,t,cues,primed):
    P=lr.P; pi=p0(it,t); F=lr.F(it,primed); L=lr.L(it)
    q=1-(1-pi)*(1-F*L)
    if rng.random()<q:
        src='item' if rng.random()<pi/max(q,1e-9) else 'gen'
        return True,0.0,(0.5 if src=='item' else 1.0)
    Fc,Lc=F,L; q0=q
    for c in cues:
        cf,cl=cue_vec(c,it,P); Fc=Fc+(1-Fc)*cf; Lc=Lc+(1-Lc)*cl
        ps=1-(1-pi)*(1-Fc*Lc)
        if rng.random()<(ps-q)/(1-q):
            sup=(ps-q0)/ps; frame_sup=(Fc-F)/max(Fc,1e-9)
            return True,sup,max(0.0,1-frame_sup)
        q=ps
    return False,1.0,0.0

def learn_item(it,t,P,ok,support):
    q=p0(it,t)
    if ok:
        e=1-P['cuecost']*support
        it.S*=1+P['a']*e*(1-q)**P['dd']; it.m+=P['b']*(0.4+0.6*e)*(1-it.m)
    else:
        it.m+=P['b']*0.5*(1-it.m); it.S=max(0.2,it.S*0.6)
    it.last=t; it.seen=True

def learn_rule(lr,it,ok,rule_credit,primed):
    P=lr.P; f=it.fam; r=lr.ready(f)
    if ok:
        lr.g[f]+=P['rg']*rule_credit*r*(1-lr.g[f])
        if not primed: lr.sel[f]+=P['rs']*rule_credit*(1-lr.sel[f])
        lr.h[it.frame]=lr.h.get(it.frame,0)+P['rh']*rule_credit*(1-lr.h.get(it.frame,0))
        if f in ('BE_YN','DO_YN','WH_DO','MODAL'):           # inversion habit leaks into no-inversion forms
            for x in ('EMBED','WH_SUBJ'): lr.sel[x]=max(0.2,lr.sel[x]-P['neg']*rule_credit)
    else:  # saw the model answer (feedback)
        lr.g[f]+=P['rg']*0.2*r*(1-lr.g[f])

def run(variant,P,seed):
    rng=random.Random(seed); items=build_items(); lr=Learner(P)
    pol=variant['policy']; order=variant.get('order','data')
    if order=='stage': items_new=sorted(items,key=lambda it:(STAGE[it.fam],it.fam))
    elif order=='mixed':
        by={f:[it for it in items if it.fam==f] for f in FAMS}; items_new=[]
        while any(by.values()):
            for f in sorted(FAMS,key=lambda f:STAGE[f]):
                if by[f]: items_new.append(by[f].pop(0))
    else: items_new=list(items)
    for day in range(DAYS):
        lr.decay()
        if rng.random()>P['attend']: continue
        newc=0; t=day+0.5; queue=[]; prev=None
        fam_today=None
        if variant.get('famblock'):
            fresh=[it for it in items_new if not it.seen]
            fam_today=fresh[0].fam if fresh else None
        for turn in range(TURNS):
            t+=1/1440*2
            if turn%3==2: prev=None; continue
            due=[it for it in items if it.seen and it.due<=t and (fam_today is None or it.fam==fam_today)]
            due.sort(key=lambda it:it.s)
            if queue and queue[0][0]<=turn: it=queue.pop(0)[1]
            elif due: it=due[0]
            else:
                fresh=[it for it in items_new if not it.seen and (fam_today is None or it.fam==fam_today)]
                if variant.get('gated'):
                    fr2=[x for x in fresh if lr.ready(x.fam)>=variant['gated']]
                    fresh=fr2 or fresh
                if fresh and newc<DAILY_NEW: it=fresh[0]; newc+=1
                else:
                    rest=[it for it in items if it.seen and (fam_today is None or it.fam==fam_today)]
                    if not rest: prev=None; continue
                    it=min(rest,key=lambda x:x.due)
            primed = prev is not None and prev==it.fam
            new=not it.seen; mode=pol(it,new)
            ok,sup,rc=attempt(rng,it,lr,t,mode['cues'],primed)
            if mode['self']:
                seen_ok=ok or rng.random()<P['overconf']
                graded='good' if seen_ok and sup<0.01 else ('soso' if seen_ok else 'bad')
            else:
                graded='good' if ok and sup<0.01 else ('soso' if ok else 'bad')
                if mode.get('lenient') and ok: graded='good'
            if primed: rc*=1-P['prime']
            learn_item(it,t,P,ok,sup); learn_rule(lr,it,ok,rc,primed)
            prev=it.fam
            if new: it.s=0; it.due=t; queue.append((turn+2,it))
            elif graded=='good': it.s=min(5,it.s+1); it.due=t+INTERVALS[it.s]
            elif graded=='soso': it.due=t+INTERVALS[1]
            else: it.s=max(0,it.s-2); it.due=t; queue.append((turn+3,it))
    for _ in range(DELAY): lr.decay()
    T2=DAYS+DELAY
    def say(it): return 1-(1-p0(it,T2))*(1-lr.F(it,False)*lr.L(it))
    rec=st.mean(say(it) for it in items if it.seen) if any(it.seen for it in items) else 0; solid=sum(1 for it in items if say(it)>0.7)
    # transfer: a NEW question of each family (frame chunk not available unless shared), lv2 content
    tr={f:lr.sel[f]*lr.g[f]*max(0.1,P['lex']-0.1) for f in FAMS}
    trans=sum(tr[f]*FAMCOUNT[f] for f in FAMS)/sum(FAMCOUNT.values())
    hi=st.mean(tr[f] for f in FAMS if STAGE[f]>=5)/max(0.1,P['lex']-0.1)
    return rec,solid,trans,hi

def mk(cues_lo,cues_hi,self_hi=True,lenient_lo=False):
    def pol(it,new):
        if new or it.s<3: return dict(cues=cues_lo,self=False,lenient=lenient_lo)
        return dict(cues=cues_hi,self=self_hi)
    return pol
def V0(it,new):   # answer always visible: answer+tiles together from the start
    if new or it.s<3: return dict(cues=['ans','tile'],self=False,lenient=True,joint=True)
    return dict(cues=['ans'],self=True)
def _v0(it,new):
    m=V0(it,new)
    return m
VARIANTS={
 'V0 今の方式':dict(policy=V0),
 'A  文型→1語目→答え→タイル':dict(policy=mk(['pat','first','ans','tile'],['pat','first','ans'])),
 'A+C 同上+★3以上入力採点':dict(policy=mk(['pat','first','ans','tile'],['pat','first','ans'],self_hi=False)),
 'K  キーワード→答え→1語目→タイル':dict(policy=mk(['kw','ans','first','tile'],['kw','ans','first'],self_hi=False)),
 'KR キーワード→規則→答え→1語目→タイル':dict(policy=mk(['kw','rule','ans','first','tile'],['kw','rule','ans','first'],self_hi=False)),
 'KR+段階順(新出を発達段階順)':dict(policy=mk(['kw','rule','ans','first','tile'],['kw','rule','ans','first'],self_hi=False),order='stage'),
 'KR+交互順(新出を型ごとに混ぜる)':dict(policy=mk(['kw','rule','ans','first','tile'],['kw','rule','ans','first'],self_hi=False),order='mixed'),
 'KR+交互+準備度ゲート':dict(policy=mk(['kw','rule','ans','first','tile'],['kw','rule','ans','first'],self_hi=False),order='mixed',gated=0.8),
 'KR+型ブロック(1日1つの型)':dict(policy=mk(['kw','rule','ans','first','tile'],['kw','rule','ans','first'],self_hi=False),order='stage',famblock=True),
}

def main(NP=150,mod=None,title=None,keys=None):
    rng=random.Random(1); params=[sample_params(rng) for _ in range(NP)]
    if mod: [mod(P,rng) for P in params]
    ks=keys or list(VARIANTS)
    res={k:[run(VARIANTS[k],P,i) for i,P in enumerate(params)] for k in ks}
    base=res[ks[0]]; a=res.get('A+C 同上+★3以上入力採点')
    if title: print('==',title)
    for k,r in res.items():
        m=[st.mean(x[j] for x in r) for j in range(4)]
        win=sum(1 for x,y in zip(r,base) if x[0]>y[0])/len(r)
        winA=sum(1 for x,y in zip(r,a) if x[0]>y[0])/len(r) if a else float('nan')
        print(f"  {k:34s} 出会った質問を言える{m[0]*100:5.1f}% 確実{m[1]:5.1f}問 新しい質問{m[2]*100:5.1f}% 段階5-6の規則{m[3]*100:5.1f}% 対V0{win*100:4.0f}% 対A+C{winA*100:4.0f}%")

if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 150
    print({f:FAMCOUNT[f] for f in FAMS}, 'echo answers:',sum(1 for it in build_items() if it.echo))
    main(NP,title='基本設定')
    if len(sys.argv)>2:
        main(NP,lambda P,r:P.update(neg=0.0,prime=0.0),'感度1: 負の転移なし・プライミングなし')
        main(NP,lambda P,r:P.update(rg=r.uniform(0.004,0.01)),'感度2: 規則の伸びが遅い(項目暗記中心)')
        main(NP,lambda P,r:P.update(kw=(0.0,r.uniform(0.1,0.25))),'感度3: キーワードヒントが弱い')
        main(NP,lambda P,r:P.update(rule=(r.uniform(0.6,0.8),0.0)),'感度4: 規則ヒントが文型ヒント並みに答えを渡してしまう')
