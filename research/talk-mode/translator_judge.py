# 別解判定 v2（入力・タイル・音声認識の文字起こし共通）。index.html の qNorm 完全一致を置き換える案。
# RULES は [正規表現, 置換] を順に適用するだけ → JS では s = s.replace(new RegExp(p,'g'), r) でそのまま移植可（lookbehind 不使用）。
import re, json, sys
NUM={'0':'zero','1':'one','2':'two','3':'three','4':'four','5':'five','6':'six','7':'seven','8':'eight','9':'nine','10':'ten',
 '11':'eleven','12':'twelve','13':'thirteen','14':'fourteen','15':'fifteen','16':'sixteen','17':'seventeen','18':'eighteen','19':'nineteen',
 '20':'twenty','30':'thirty','40':'forty','50':'fifty','60':'sixty','70':'seventy','80':'eighty','90':'ninety','100':'a hundred'}
RULES=[
 # 1 文字の統一（ASRの句読点なし/大文字/全角/曲がった引用符）
 [r"[‘’ʼ`]", "'"], [r"[！-～]", ""], [r"[?.,!;:\"()、。]", " "],
 # 2 綴りゆれ・複合語（Wi-Fi / wifi / wi fi、check-out / check out、OK / o.k.）
 [r"\bwi ?-? ?fi\b", "wifi"], [r"\bcheck ?-? ?(out|in)\b", "check$1"], [r"\bo\.? ?k\.?\b|\bokay\b", "ok"], [r"\ball ?right\b|\balright\b", "ok"],
 [r"\be ?-? ?mail\b", "email"], [r"\bunion square\b", "unionsquare"], [r"-", " "],
 # 3 くだけた発音の綴り（ASRが出しがち）
 [r"\bwanna\b", "want to"], [r"\bgonna\b", "going to"], [r"\bgotta\b", "got to"], [r"\bgimme\b", "give me"], [r"\blemme\b", "let me"],
 [r"\bya\b", "you"], [r"\bwhatcha\b", "what are you"],
 # 4 短縮形（アポストロフィあり/なし両方）
 [r"\b(what|where|when|who|how|it|that|there|here)'?s\b", "$1 is"], [r"\bi'?m\b", "i am"], [r"\b(you|we|they)'re\b", "$1 are"],
 [r"\byoure\b", "you are"], [r"\b(is|are|was|were|do|does|did|have|has|should|would|could)n'?t\b", "$1 not"],
 [r"\bcan'?t\b", "cannot"], [r"\bwon'?t\b", "will not"], [r"\b(i|you|it|we|they)'ll\b", "$1 will"], [r"\b(i|you|we|they)'ve\b", "$1 have"],
 [r"\b(i|you|we|they)'d\b", "$1 would"],
 # 5 つなぎ言葉・言いよどみ（文頭/文末の飾り）
 [r"\b(um+|uh+|er+|erm|hmm+|ah+)\b", " "], [r"^\s*(sorry|excuse me|oh|so|hey|well|and|ok)\s+", ""], [r"\s+(please|then|again)\s*$", ""],
 [r"^\s*please\s+", ""], [r"\s+", " "], [r"\b(\w+)( \1\b)+", "$1"],   # 言い直しの繰り返し "can can i"
]
# 6 数字（ASRは 15 / fifteen を混在して出す）。3:15 → three fifteen
def nums(s):
    s=re.sub(r"\b(\d{1,2}):(\d{2})\b",lambda m:m.group(1)+' '+m.group(2).lstrip('0'),s)
    def w(n):
        if n in NUM: return NUM[n]
        if len(n)==2 and n[0] in '23456789': return NUM[n[0]+'0']+' '+NUM[n[1]]
        return n
    s=re.sub(r"\b(\d+)(st|nd|rd|th)?\b",lambda m:w(m.group(1)),s)
    return s
# 7 同義語（問題を問わず同じとみなす）
SYN=[["check","bill"],["cab","taxi"],["restroom","bathroom","toilet"],["store","shop"],["picture","photo"],["drugstore","pharmacy"],
 ["bags","luggage","baggage"],["minute","second"],["anything","something"]]
# 8 同音語（音声認識のみ・正解文に含まれる語に寄せる）
HOMO=[["for","four","fore"],["to","too","two"],["write","right"],["i","eye"],["there","their","they're"],["your","you're"],["whose","who's"],
 ["meat","meet"],["eight","ate"],["by","buy","bye"],["see","sea"],["know","no"],["some","sum"],["wait","weight"],["here","hear"],
 ["would","wood"],["one","won"],["new","knew"],["check","czech"],["way","weigh"],["break","brake"],["mind","mine"],["cold","called"]]
MODAL=r"^(can|could|may) (i|we)\b|^(can|could|would) you\b"
ART={"a","an","the","some"}

def norm(s,asr=False):
    s=s.lower()
    for p,r in RULES: s=re.sub(p,r.replace('$','\\'),s)
    s=nums(s); s=re.sub(r"\s+"," ",s).strip()
    out=[]
    for w in s.split():
        for g in SYN:
            if w in g: w=g[0]; break
        out.append(w)
    return " ".join(out)
def modal(s): return re.sub(MODAL,lambda m:('can '+m.group(2)) if m.group(2) else 'can you',s)
def homo_align(u,t):
    tw=set(t.split()); out=[]
    for w in u.split():
        if w not in tw:
            for g in HOMO:
                if w in g:
                    hit=[x for x in g if x in tw]
                    if hit: w=hit[0]
                    break
        out.append(w)
    return " ".join(out)
def lev(a,b):
    d=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        p,d[0]=d[0],i
        for j,cb in enumerate(b,1): p,d[j]=d[j],min(d[j]+1,d[j-1]+1,p+(ca!=cb))
    return d[-1]

def judge(user,item,asr=False):
    """user: 文字列、または音声認識の候補リスト（maxAlternatives）。
    返り値: exact / variant(◎) / minor(◎ ただし a/the 等の注意を表示) / alt(◯ 通じる→型で言い直し) / confirm(本人確認) / wrong"""
    cands=user if isinstance(user,list) else [user]
    order=['exact','variant','minor','alt','confirm','wrong']; best='wrong'
    for c in cands:
        r=_one(c,item,asr)
        if order.index(r)<order.index(best): best=r
    return best
def _one(user,item,asr):
    mf=item.get('modal_free',False)
    def N(x):
        n=norm(x,asr); return modal(n) if mf else n
    t=N(item['en']); u=N(user)
    if asr: u=homo_align(u,t)
    if u==t:
        return 'exact' if re.sub(r"\W","",user.lower())==re.sub(r"\W","",item['en'].lower()) else 'variant'
    targets=[t]+[N(a) for a in item.get('accept',[])]
    if u in targets: return 'variant'
    strip=lambda x:" ".join(w for w in x.split() if w not in ART)
    if any(strip(u)==strip(x) for x in targets): return 'minor' if not asr else 'variant'  # ASRは冠詞を落とす/足すので区別しない
    if any(u==N(a) for a in item.get('near_miss',[])): return 'alt'
    # 1語だけ違い、綴りが近い（ASRの聞き違い/タイプミス）→ ×にせず本人確認
    uw,tw=u.split(),t.split()
    if len(uw)==len(tw):
        diff=[(a,b) for a,b in zip(uw,tw) if a!=b]
        if len(diff)==1:
            a,b=diff[0]
            gram=re.sub(r"(es|s|ed|d|ing)$","",a)==re.sub(r"(es|s|ed|d|ing)$","",b)   # 三単現s・過去形など文法の要点
            if gram: return 'confirm' if asr else 'wrong'   # 入力は×（noteの解説）、ASRは s の聞き違いもあるので本人確認
            if lev(a,b)<=max(1,len(b)//3): return 'confirm'
    return 'wrong'

if __name__=='__main__':
    Q=json.load(open('qitems_v2.json'))
    tests=[  # (発話/入力, 正解en, asr)
     ("could i try this on", "Can I try this on?", True), ("whats the wifi password", "What's the Wi-Fi password?", True),
     ("Can we get the bill", "Could we get the check, please?", False), ("sorry did you say 15 or 50", "Sorry, did you say fifteen or fifty?", True),
     ("do you wanna grab lunch", "Do you want to grab lunch?", True), ("im from osaka arent i", "You're from Osaka, aren't you?", True),
     ("could you right it down for me", "Could you write it down for me?", True), ("do you have a table for 2", "Do you have a table for two?", True),
     ("is it ok if i open the window", "Is it okay if I open the window?", True), ("is it alright if i open the window", "Is it okay if I open the window?", True),
     ("can i sit here", "Do you mind if I sit here?", True), ("do you hungry", "Are you hungry?", False),
     ("does she speaks japanese", "Does she speak Japanese?", False), ("could you drive", "Can you drive?", False),
     ("can i get refill", "Can I get a refill?", True), ("can i get refill", "Can I get a refill?", False),
     ("what time is check out", "What time is checkout?", True), ("youre from osaka arent you", "You're from Osaka, aren't you?", True), ("does she speaks japanese", "Does she speak Japanese?", True),
     ("um can can i ask you something", "Can I ask you something?", True), ("does this bus go to union square", "Does this bus go to Union Square?", True),
     ("is it within walking distant", "Is it within walking distance?", True), ("may you help me", "Can you help me?", False),
     (["can i leaf my bags here","can i leave my bags here"], "Can I leave my bags here?", True)]
    for u,en,asr in tests:
        print(f"{str(u)[:44]:44s} -> {en:38s} {'ASR' if asr else 'TXT'} {judge(u,Q[en],asr)}")
    a=sum(1 for q in Q.values() for x in q['accept']); ok=sum(judge(x,q)!='wrong' for q in Q.values() for x in q['accept'])
    n=sum(1 for q in Q.values() for x in q['near_miss']); al=sum(judge(x,q)=='alt' for q in Q.values() for x in q['near_miss'])
    fp=[(x,q['en']) for q in Q.values() for x in q['near_miss'] if judge(x,q) in ('exact','variant','minor')]
    print(f"accept {ok}/{a} が◎、near_miss {al}/{n} が◯通じる、near_miss を誤って◎にした {fp}")
    # ASR風の崩し（小文字・句読点なし・短縮のアポストロフィ削除・数字化）で全97問の正解文が通るか
    def asrify(s): return re.sub(r"[?.,!']","",s.lower()).replace("want to","wanna").replace("fifteen","15").replace("fifty","50").replace("two","2")
    print("正解文をASR風に崩しても◎:", sum(judge(asrify(q['en']),q,True) in ('exact','variant') for q in Q.values()),"/",len(Q),
          " 旧qNorm:", sum(re.sub(r"\s+"," ",re.sub(r"[?.,!]","",asrify(q['en']))).strip()==re.sub(r"\s+"," ",re.sub(r"[?.,!]","",q['en'].lower())).strip() for q in Q.values()))
    json.dump(dict(rules=RULES,numbers=NUM,synonyms=SYN,homophones_asr_only=HOMO,modal_free_regex=MODAL,articles=sorted(ART),
        order=["小文字化","RULESを順に適用（JS: s.replace(new RegExp(p,'g'),r)）","数字→英単語（3:15→three fifteen）","同義語を先頭語に統一",
               "modal_free の問題だけ文頭 Can/Could/May I・Can/Could/Would you を統一","ASRのみ: 正解文にある語へ同音語を寄せる",
               "正解/accept と一致→◎","冠詞だけ違う→入力は◎+注意, ASRは◎","near_miss と一致→◯通じる→型ヒントで言い直し",
               "1語だけ綴りが近い→本人確認（×にしない）","それ以外→×（note の解説）",
               "ASRは maxAlternatives=5 の全候補で判定し最良を採用。ASR単独で×・★−2にしない（不一致は文字起こしと正解を並べて本人が合ってた/違ったを選ぶ）"]),
        open('judge_rules.json','w'),ensure_ascii=False,indent=1)
