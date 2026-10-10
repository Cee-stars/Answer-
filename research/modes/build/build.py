import json, re, random, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from para import P; from cloze import C, BAD; from gist import G; from gist_opts import O; from check_gist import rank; from paraq import Q3, QD
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = set(l.strip() for l in open(os.path.join(R,'wordlist.txt')) if l.strip())
# W2/CULTURE/KOUGO も追加
src = open('/home/user/Answer-/index.html', encoding='utf-8').read()
for m in re.finditer(r"^\s*\[['\"]([^'\"]+)['\"],['\"]", src[src.find('const W2'):src.find('const KOUGO')+20000], re.M): APP.add(m.group(1))
low = {a.lower() for a in APP}
SRC={}
sec=None; cat=None
for ln in src.splitlines():
    m=re.match(r'const (WORDS|W2|CULTURE|KOUGO|QITEMS)\b',ln)
    if m: sec=m.group(1); cat=None; continue
    if sec in (None,'QITEMS'): continue
    if ln.startswith('];') or ln.startswith('};'): sec=None; continue
    mc=re.match(r'^\s*([a-z]+):\[',ln)
    if sec=='W2' and mc: cat=mc.group(1)
    for mw in re.finditer(r"w:'([^']+)'|w:\"([^\"]+)\"",ln):
        SRC.setdefault((mw.group(1) or mw.group(2)).lower(),sec)
    mw=re.match(r"^\s*\[['\"]([^'\"]+)['\"],",ln)
    if mw: SRC.setdefault(mw.group(1).lower(), sec+('.'+cat if cat else ''))
warn = []
# --- paraphrase
pairs=[]; seen=set()
for i,(a,b,rel,swap,nu,ok,ng) in enumerate(P):
    k=(a.lower(),b.lower(),rel)
    if k in seen: warn.append(f'dup pair {k}')
    seen.add(k)
    inapp=[x for x in (a,b) if x.lower() in low]
    if not inapp: warn.append(f'para {a}/{b}: neither in app')
    pairs.append(dict(id=f'p{i+1:03d}',a=a,b=b,rel=rel,swap=swap,nuance=nu,ok=ok,ng=ng,in_app=inapp))
# 連鎖（言い換えバトルの鎖の例）
chains=[["big","large","huge","↔","tiny"],["hungry","starving","↔","full"],["tired","exhausted"],["Hold on.","Hang on.","(= wait)"],["begin","start","↔","finish","≒","end"]]
json.dump(dict(meta=dict(count=len(pairs),
  rel={r:sum(p['rel']==r for p in pairs) for r in ['syn','ant','para','usuk','trap']},
  swap={s:sum(p['swap']==s for p in pairs) for s in ['yes','part','no']},
  legend=dict(rel='syn=類義 ant=対義 para=言い換え usuk=米英差 trap=日本語訳が同じ/似ているが英語では別物', swap='yes=ほぼ置換可 part=文脈しだい（ok/ngの例で判定）no=置換不可', in_app='アプリのWORDS/W2/CULTURE/KOUGOに含まれる側'),
  chains_example=chains), pairs=pairs), open(os.path.join(R,'paraphrase.json'),'w'), ensure_ascii=False, indent=1)
# --- cloze
rng=random.Random(3); items=[]
for w,s,ja,ds,why,acc in C:
    if w.lower() not in low: warn.append(f'cloze {w} not in app')
    if s.count('___')!=1: warn.append(f'cloze {w} blanks')
    accl=[x.strip() for x in acc.split(',') if x.strip()]
    for d,t,_ in ds:
        if d==w or d in accl: warn.append(f'cloze {w}: distractor {d} is correct')
    opts=[w]+[d for d,_,_ in ds]; rng.shuffle(opts)
    items.append(dict(w=w,sentence_with_blank=s,ja=ja,options=opts,
       distractors=[dict(word=d,type=t,why=r) for d,t,r in ds], why=why,
       app_word=w, app_source=SRC.get(w.lower(),'?'),
       len_check=dict(lengths={o:len(o) for o in opts}, answer_rank=('最長' if len(w)>max(len(d) for d,_,_ in ds) else '最短' if len(w)<min(len(d) for d,_,_ in ds) else '中間/同長'), max_min_ratio=round(max(map(len,opts))/min(map(len,opts)),2)),
       accept_free_input=[w]+accl, note_accept='自由入力（recall）では accept の語も○。選択肢には accept の語を入れない'))
rk=[i['len_check']['answer_rank'] for i in items]
json.dump(dict(meta=dict(count=len(items), answer_len_rank={k:rk.count(k) for k in ['最長','中間/同長','最短']}, ratio_over_2=sum(i['len_check']['max_min_ratio']>2 for i in items), distractor_types={t:sum(d['type']==t for i in items for d in i['distractors']) for t in ['meaning','grammar']},
  rules=['空所は1つ','選択肢（正解＋3）の中で文法的にも意味的にも入るのは正解だけ','別解は accept_free_input に列挙し、選択肢からは外す','空所の後ろか前に「答えを決める手がかり」（因果・対比・定義・コロケーション）を必ず置く','訳 ja は回答後に表示（先に見せると翻訳問題になる）']),
  items=items, bad_examples=BAD), open(os.path.join(R,'cloze.json'),'w'), ensure_ascii=False, indent=1)
# --- gist
rng=random.Random(7); gs=[]; longest_ans=0
ranks=[]
for (text,_a,_t,_w,topic),(ans,trap,wrong) in zip(G,O):
    Ls=[len(ans),len(trap),len(wrong)]; ranks.append(rank(Ls))
    if max(Ls)/min(Ls)>1.3: warn.append(f'gist len ratio {text[:20]}')
    ns=len(re.findall(r'[.!?](\s|$)',text)); nw=len(text.split())
    if ns>3 or nw>30: warn.append(f'gist too long: {text[:30]} {ns}s {nw}w')
    opts=[ans,trap,wrong]; rng.shuffle(opts)
    if len(ans)>=max(len(trap),len(wrong)): longest_ans+=1
    gs.append(dict(text=text,q_ja='要するに何？',options=opts,answer=opts.index(ans),trap=opts.index(trap),
       trap_why='本文に書いてある細部だが、話し手が一番伝えたいことではない', wrong_type='言い過ぎ・逆・本文にない',topic=topic,words=nw,opt_len=[len(o) for o in opts],answer_len_rank={'L':'最長','M':'中間','S':'最短','T':'同長'}[rank(Ls)]))
json.dump(dict(meta=dict(count=len(gs),avg_words=round(sum(g['words'] for g in gs)/len(gs),1),
  answer_pos={i:sum(g['answer']==i for g in gs) for i in range(3)},
  answer_len_rank={'最長':ranks.count('L'),'中間':ranks.count('M'),'最短':ranks.count('S'),'同長あり':ranks.count('T')},
  max_min_len_ratio=round(max(max(g['opt_len'])/min(g['opt_len']) for g in gs),2),
  caution='初稿は正解が最長27/30→短縮しすぎて最短27/30。現版は長さ順位を1/3ずつ・最大/最小≦1.3に固定（build/check_gist.py）',
  rules=['1〜3文・30語以内','正解=話し手の目的/結論（〜したい・〜してほしい・〜なので〜）','trap=本文の細部をそのまま訳した選択肢（キーワード一致の罠）','もう1つ=逆・言い過ぎ・本文にない','制限時間の目安: 語数×0.4秒+3秒（中学レベル音読速度 約150wpmの1.5倍余裕）']),
  items=gs), open(os.path.join(R,'gist.json'),'w'), ensure_ascii=False, indent=1)
rng=random.Random(11); pq=[]
OPT3=['もっと強い','ほぼ同じ','反対']; IDX={'stronger':0,'same':1,'opposite':2}
for t,a,rel,nu,en,ja in Q3:
    pq.append(dict(id=f'q{len(pq)+1:03d}',type='scale',target=t,anchor=a,relation=rel,q_ja=f'{t} は {a} と比べて？',options=OPT3,answer=IDX[rel],
       nuance=nu,example_en=en,example_ja=ja,in_app={'target':t.lower() in low,'anchor':a.lower() in low}))
for q,ok,ngs,anc,tg,nu,ja in QD:
    opts=[ok]+ngs; rng.shuffle(opts)
    pq.append(dict(id=f'q{len(pq)+1:03d}',type='diff',target=tg,anchor=anc,relation='diff',q_ja=q,options=opts,answer=opts.index(ok),
       nuance=nu,example_en=ok,example_ja=ja,in_app={'target':tg.lower() in low,'anchor':anc.lower() in low}))
for x in pq:
    if not (x['in_app']['target'] or x['in_app']['anchor']): warn.append(f"para_q {x['target']}/{x['anchor']} neither in app")
json.dump(dict(meta=dict(count=len(pq),relation={r:sum(x['relation']==r for x in pq) for r in ['stronger','same','opposite','diff']},
  both_in_app=sum(x['in_app']['target'] and x['in_app']['anchor'] for x in pq), one_in_app=sum(x['in_app']['target']!=x['in_app']['anchor'] for x in pq),
  rules=['scale型は 3択「もっと強い／ほぼ同じ／反対」固定順（尺度なので並びは固定）。target が強い側になるよう向きをそろえた（weaker は使わない）','diff型は英語2〜3択、正解は自然な言い方1つだけ','nuance は使い分けが必要な組だけ（same でも置換に条件がある組には付ける。完全な対義や単純な組は空）','回答後に nuance と例文を表示'],
  source='paraphrase.json の組から作成'), items=pq), open(os.path.join(R,'para_q.json'),'w'), ensure_ascii=False, indent=1)
print('para_q',len(pq))
print('pairs',len(pairs),'cloze',len(items),'gist',len(gs)); print('\n'.join(warn) or 'no warnings')
