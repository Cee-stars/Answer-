# 第4回・第2会議: ROUND2.md の FINAL4 をアプリ全体（バトル＋おまけ）の中で同じ時間予算で検証（翻訳者担当）
# 1日12分（バトル10分＋おまけ2分）×60日。アプリ語600（うち写真にできる語＝photo_items の g<=3）＋言えない物95。
import json, math, random, os, statistics as st
D = os.path.dirname(os.path.abspath(__file__))
PH = json.load(open(os.path.join(D, 'photo_items_v2.json')))
DAYS, BATTLE, EXTRA = 60, 600, 120
INT = [0, 1, 3, 7, 14, 30]

class W:  # 単語
    __slots__ = ('m', 'pm', 'last', 'plast', 's', 'due', 'seen', 'ph', 'kind', 'L', 'two', 'alt', 'near', 'g')

def build(r):
    ws = []
    jh = [o for o in PH if o['kind'] in ('noun', 'verb') and o['g'] <= 3]
    for i in range(600):
        w = W(); w.m = 0; w.pm = 0; w.last = w.plast = 0; w.s = 0; w.due = 0; w.seen = False; w.ph = None; w.kind = 'app'
        if i < len(jh):
            o = jh[i]; w.ph = o; w.kind = o['kind']
        ws.append(w)
    r.shuffle(ws)
    for o in PH:
        if o['kind'] == 'tricky':
            w = W(); w.m = 0; w.pm = 0.08; w.last = w.plast = 0; w.s = 0; w.due = 0; w.seen = False; w.ph = o; w.kind = 'tricky'; ws.append(w)
    for w in ws:
        if w.ph:
            a = w.ph['answer']; w.L = len(a.replace(' ', '')); w.two = ' ' in a
            w.alt = bool(w.ph['accept']); w.near = bool(w.ph.get('near'))
    return ws

def rec(m, dt): return m * math.exp(-dt / (1.5 + 10 * m))

def params(r):
    return dict(attend=r.uniform(.6, .85), alt=r.uniform(.15, .35), photo=r.uniform(.06, .14), typo=r.uniform(.08, .18),
                form=r.uniform(.15, .30), nearp=r.uniform(.05, .15), harm=r.uniform(.10, .25), quit=r.uniform(.04, .10),
                over=r.uniform(.10, .25), think=r.uniform(3, 5), cps=0.3, gain=r.uniform(.25, .40), gfb=r.uniform(.12, .20),
                tr=r.uniform(.3, .5), v=0.0, h1=r.uniform(.10, .20), h2=r.uniform(.15, .30))

def photo_q(w, V, P, r, day, st_):
    """1問。所要秒を返す"""
    k = w.kind
    if k != 'tricky' and w.pm == 0:  # 初回: 意味を知っている分だけ産出もできる状態から始める
        w.pm = 0.5 * w.m; w.plast = w.last
    p = rec(w.pm, day - w.plast) if w.pm else 0.08
    typed = V['ans'] == 'type' or (V['ans'] == 'len' and w.L <= 7 and not w.two)
    t = P['think']
    hint = False
    R = r.random() < p
    if not R and V['hint']:
        if r.random() < P['h1']: R = True; hint = True; t += 2
        elif r.random() < P['h2']: R = True; hint = True; t += 3
    wrong = r.random() < P['photo'] * (1.8 if k == 'verb' else 1) * V['screen']
    unfair = False
    if typed:
        t += w.L * P['cps'] + 1
        if R and not wrong:
            if w.alt and r.random() < P['alt'] * (1.4 if k == 'tricky' else 1) and not V['accept']: unfair = True
            near_hit = w.near and r.random() < P['nearp']
            typo = w.L >= 5 and r.random() < P['typo']
            form = k == 'verb' and r.random() < P['form']
            if (typo or form or near_hit):
                if V['osii']: t += 3
                else: unfair = True
        elif wrong: unfair = True
        ok = R and not wrong and not unfair
    else:
        t += 1.5
        ok = R and not wrong
        if not ok and r.random() < P['over']: ok = True  # 思い込み→学習効果なし
        R = R and not wrong
    st_['n'] += 1; st_['t'] += t; st_['over10'] += t > 10
    if R and not unfair:
        g = P['gain'] * (0.6 if hint else 1) * (1.15 if typed else 1)
        w.pm = w.pm + g * (1 - w.pm)
    elif unfair:
        w.pm = max(0, w.pm * (1 - P['harm'])) + P['gfb'] * 0.5 * (1 - w.pm)
        if r.random() < P['quit']: st_['quit'] = True
    else:
        w.pm = w.pm + P['gfb'] * (1 - w.pm)
    w.plast = day
    if k != 'tricky':  # 英→意味 への転移
        w.m = w.m + P['tr'] * (w.pm - w.m) * 0.5 if w.pm > w.m else w.m
        w.seen = True; w.last = day
        if V['star'] and ok and not hint: w.s = min(5, w.s + 1); w.due = day + INT[w.s]
    return t

def run(V, P, seed):
    r = random.Random(seed); ws = build(r)
    app = [w for w in ws if w.kind != 'tricky']; trk = [w for w in ws if w.kind == 'tricky']
    st_ = dict(n=0, t=0, over10=0, quit=False, days=0)
    att = P['attend'] + (1 - P['attend']) * P['v'] * 0.3 * (1 if V['photo'] else 0)
    newi = 0
    for day in range(DAYS):
        if r.random() > att: continue
        st_['days'] += 1
        # バトル: 英→意味の再認・想起 5秒/語
        t = 0
        while t < BATTLE:
            due = [w for w in app[:newi] if w.due <= day]
            if due: w = min(due, key=lambda x: x.s)
            elif newi < len(app): w = app[newi]; newi += 1
            else: break
            p = rec(w.m, day - w.last) if w.seen else 0.15
            ok = r.random() < p
            w.m = w.m + (0.30 if ok else 0.15) * (1 - w.m); w.seen = True; w.last = day
            w.s = min(5, w.s + 1) if ok else max(0, w.s - 1); w.due = day + INT[w.s] + (0 if ok else 1)
            t += 5
        # おまけ: 6種日替わり（V0は5種）
        nmodes = 6 if V['photo'] else 5
        if V['photo'] and day % nmodes == 0:
            st_['quit'] = False; t = 0; q = 0
            pool_j = [w for w in app[:max(newi, 1)] if w.ph]
            for q in range(10):
                if t > EXTRA or st_['quit']: break
                useT = r.random() < V['mix'] or not pool_j
                pool = trk if useT else pool_j
                w = min(r.sample(pool, min(8, len(pool))), key=lambda x: x.pm)
                t += photo_q(w, V, P, r, day, st_)
        else:
            t = 0; seen = [w for w in app[:newi]]
            while t < EXTRA and seen:
                w = r.choice(seen); p = rec(w.m, day - w.last)
                w.m = w.m + (0.35 if r.random() < p else 0.15) * (1 - w.m); w.last = day; t += 6
    meaning = sum(1 for w in app[:newi] if r.random() < rec(w.m, DAYS - w.last))
    def prod(w):
        if w.pm: return rec(w.pm, DAYS - w.plast)
        return 0.05 if w.kind == 'tricky' else 0.5 * rec(w.m, DAYS - w.last) if w.seen else 0
    pic = sum(1 for w in ws if w.ph and r.random() < prod(w))
    tq = st_['t'] / st_['n'] if st_['n'] else 0
    return meaning, pic, st_['n'] / max(1, st_['days']), tq, (st_['over10'] / st_['n'] if st_['n'] else 0), st_['days']

BASE = dict(photo=True, ans='len', hint=True, accept=True, osii=True, star=True, screen=0.3, mix=0.3)
def v(**k): d = dict(BASE); d.update(k); return d
VARS = [('V0 今(バトル+おまけ5種)', v(photo=False)),
        ('FINAL4', v()),
        ('-長さで分けず全部入力', v(ans='type')),
        ('-全部自己評価', v(ans='self')),
        ('-ヒント段階なし', v(hint=False)),
        ('-おしいなし(厳密)', v(osii=False)),
        ('-★を動かさない', v(star=False)),
        ('配分5:5', v(mix=0.5)),
        ('配分10:0(中学語のみ)', v(mix=0.0)),
        ('参考:写真未選別(文字・紛らわしい組あり)', v(screen=1.0))]

def table(title, mod=None, N=200):
    print(f'\n== {title}\n| 構成 | 意味が言える語 | 写真で言える語 | 写真問/日 | 秒/問 | 10秒超 | V0に勝つ(意味) | FINAL4に勝つ(写真) |\n|---|---|---|---|---|---|---|---|')
    R = {}
    for name, V in VARS:
        out = []
        for s in range(N):
            P = params(random.Random(s * 7 + 1))
            if mod: mod(P)
            out.append(run(V, P, s))
        R[name] = out
    b = R[VARS[0][0]]; f = R['FINAL4']
    for name, out in R.items():
        c = lambda i: st.mean(o[i] for o in out)
        w0 = sum(o[0] > x[0] for o, x in zip(out, b)) / N; wf = sum(o[1] > x[1] for o, x in zip(out, f)) / N
        print(f'| {name} | {c(0):.0f} | {c(1):.0f} | {c(2):.1f} | {c(3):.1f} | {c(4):.0%} | {w0:.0%} | {wf:.0%} |')

if __name__ == '__main__':
    table('基本 (v=0, 1文字0.3秒)')
    table('感度: 入力が遅い (1文字0.5秒)', lambda P: P.update(cps=0.5))
    table('感度: 継続効果 v=0.3', lambda P: P.update(v=0.3))
