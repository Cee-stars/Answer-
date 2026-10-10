# 第4回 写真当てクイズ: 別解×の害・あいまい写真の害・入力 vs 自己評価 の小シミュレーション（翻訳者担当）
# 1日5分（300秒）×14日、出題は photo_items.json の実データ（accept の数・kind で あいまいさを決める）
import json, math, random, os, statistics as st
D = os.path.dirname(os.path.abspath(__file__))
ITEMS = json.load(open(os.path.join(D, 'photo_items.json')))
DAYS, SESSION = 14, 300

def params(r):
    return dict(
        alt=r.uniform(0.15, 0.35),     # accept がある語で、学習者が自然に別解を出す率
        photo=r.uniform(0.06, 0.14),   # 写真が別物に見える率（milk→glass 等、accept 外）
        typo=r.uniform(0.08, 0.18),    # iPhone 入力の1文字ミス率
        form=r.uniform(0.15, 0.30),    # 動詞の形ミス（bake/baked）率
        harm=r.uniform(0.10, 0.25),    # 正しいのに×→その語の記憶が下がる量（干渉）
        quit=r.uniform(0.04, 0.10),    # 理不尽な×1回ごとにその日の残りをやめる確率
        overconf=r.uniform(0.10, 0.25),# 自己評価で「言えた」と思うが実は言えない率
        t_type=r.uniform(8, 11), t_self=r.uniform(4, 6),
        gain=r.uniform(0.25, 0.40),    # 自力で思い出せた時の強化
        gain_fb=r.uniform(0.12, 0.20), # 失敗→答えを見た時の強化
    )

def run(V, P, seed):
    r = random.Random(seed)
    its = [dict(o=o, m=0.0, last=-1, due=0, s=0, seen=False) for o in ITEMS]
    r.shuffle(its)
    for it in its:
        k = it['o']['kind']
        it['alt'] = P['alt'] * (1.4 if k == 'tricky' else 1) if it['o']['accept'] else 0.02
        it['photo'] = P['photo'] * (1.8 if k == 'verb' else 1) * (V.get('screen', 1))
        it['prior'] = 0.10 if k == 'tricky' else (0.45 if it['o']['g'] <= 1 else 0.25)
    def p_rec(it, day):
        if not it['seen']: return it['prior']
        return it['m'] * math.exp(-(day - it['last']) / (2 + 4 * it['m']))
    for day in range(DAYS):
        t = 0; quit_today = False; newc = 0
        while t < SESSION and not quit_today:
            due = [it for it in its if it['seen'] and it['due'] <= day]
            it = min(due, key=lambda x: x['m']) if due else next((x for x in its if not x['seen']), None)
            if it is None: break
            if not due: newc += 1
            t += P['t_self'] if V['self'] else P['t_type']
            rec = r.random() < p_rec(it, day)
            wrong_target = r.random() < it['photo']
            unfair = False
            if V['self']:
                ok = rec and not wrong_target
                if not ok and r.random() < P['overconf']: ok = True; rec = False  # 思い込み
                if wrong_target and V.get('screen', 1) == 1 and r.random() < 0.5: unfair = True  # 違う物を思い浮かべて混乱
            else:
                if rec and not wrong_target:
                    used_alt = r.random() < it['alt']
                    typo = r.random() < P['typo']
                    form = it['o']['kind'] == 'verb' and r.random() < P['form']
                    if used_alt and not V['accept']: unfair = True
                    if typo and not V['near']: unfair = True
                    if form and not V['near']: unfair = True
                    if (typo or form) and V['near']: t += 3  # 再入力
                    ok = not unfair
                else:
                    ok = False
                    if wrong_target: unfair = True  # 正しい英語(glass)なのに×
            it['seen'] = True
            if rec and not unfair:
                it['m'] = min(1, it['m'] + P['gain'] * V.get('gb', 1) * (1 - it['m']))
            elif unfair:
                it['m'] = max(0, it['m'] - P['harm'] * it['m']) + P['gain_fb'] * 0.5 * (1 - it['m'])
                if r.random() < P['quit']: quit_today = True
            else:
                it['m'] = it['m'] + P['gain_fb'] * (1 - it['m'])
            it['s'] = min(5, it['s'] + 1) if ok else 0
            it['last'] = day; it['due'] = day + [0, 1, 2, 4, 7, 14][it['s']] + (1 if it['s'] == 0 else 0)
    # 最終テスト（寛容採点＝実用で通じるか）: 14日目の翌日に全学習語
    seen = [it for it in its if it['seen']]
    known = sum(1 for it in seen if r.random() < p_rec(it, DAYS))
    return known

VARS = [
 dict(name='A 完全一致のみ', self=False, accept=False, near=False),
 dict(name='B 別解リスト○', self=False, accept=True, near=False),
 dict(name='C B+おしい再入力(1字/活用)', self=False, accept=True, near=True),
 dict(name='D C+あいまい写真を除外', self=False, accept=True, near=True, screen=0.3),
 dict(name='D2 Dで入力の産出効果+40%', self=False, accept=True, near=True, screen=0.3, gb=1.4),
 dict(name='E 自己評価(入力なし)+除外', self=True, accept=True, near=True, screen=0.3),
 dict(name='F 自己評価(写真未選別)', self=True, accept=True, near=True),
]
if __name__ == '__main__':
    N = 300; res = {}
    for V in VARS:
        res[V['name']] = [run(V, params(random.Random(s)), s) for s in range(N)]
    base = res[VARS[0]['name']]; ref = res[VARS[3]['name']]
    for k, v in res.items():
        wA = sum(a > b for a, b in zip(v, base)) / N; wD = sum(a > b for a, b in zip(v, ref)) / N
        print(f"{k:28s} 2週後に言える語 {st.mean(v):5.1f}  Aに勝つ{wA:4.0%}  Dに勝つ{wD:4.0%}")
