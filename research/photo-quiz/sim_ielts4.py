# 第4回 IELTS9: 写真当てクイズの「採点方式 × 出題配分」を同じ時間予算(1日3分, 30日)で比較。14日後にテスト。
# 採点: strict=1文字違いも×(タイポ含む) / lenient=1文字違いは「おしい」→正しい綴りを見て再入力、記憶は○扱い
#       lenient_noretype=1文字違いを黙って○ / self=頭に浮かべる→答えを見る→自己評価(入力なし)
# 配分: jh=中学語(g1-3) / tricky=知ってそうで言えない物 / half=半々
# 仮定(根拠): 産出想起は形の綴りを鍛える(Nakata 2016)。covert想起は overt より少し弱い(meta g=0.17)。
#   iPhone入力: 3秒+文字数×cps。1問10秒超は学習効果0.3倍(BRIEFの教訓)。タイポ率は文字数比例。
import random, math, statistics as st, sys
DAYS=30; DELAY=14; BUDGET=180
def mk_items(r,mix,n=300):
    it=[]
    for i in range(n):
        tr = (mix=='tricky') or (mix=='half' and i%2==1)
        if tr: L=r.choice([6,7,8,9,10,11,12,13]); p0=r.uniform(0,.15); sp=r.uniform(.35,.65); w=r.uniform(.5,.9)
        else:  L=r.choice([3,4,5,5,6,7,8]); p0=r.uniform(.15,.6); sp=r.uniform(.6,.9); w=1.0
        it.append(dict(tr=tr,L=L,p0=p0,sp0=sp,sp=sp,w=w,stab=0.6,last=None,due=0,seen=False,F=0.1,known=False))
    r.shuffle(it); return it
def R(x,day):
    if x['last'] is None: return x['p0']
    return x['p0']+(1-x['p0'])*math.exp(-(day-x['last'])/x['stab'])   # 元の知識は下限
def run(score0,mix,P,seed,fun_bonus=0.0):
    r=random.Random(seed); it=mk_items(random.Random(seed*3+1),mix)
    mot=1.0; unfair=0; tsum=0; n=0; over10=0
    att=P['attend']+fun_bonus*(0.5 if mix=='half' else 1 if mix=='tricky' else 0)*(1-P['attend'])
    for day in range(DAYS):
        if r.random()>att*mot: continue
        t=0; new=0; q=[]
        while t<BUDGET:
            due=[x for x in it if x['seen'] and x['due']<=day]
            if q: x=q.pop(0)
            elif due: x=min(due,key=lambda y:y['due'])
            elif new<8: x=next((y for y in it if not y['seen']),None); new+=1
            else: x=r.choice([y for y in it if y['seen']])
            if x is None: break
            score=score0 if score0!='hybrid' else ('lenient' if x['L']<=P['hyL'] else 'self')  # 短い語は入力、長い語は自己評価
            first=not x['seen']; x['seen']=True
            rec=r.random()< (R(x,day) if not first else x['p0'])
            # 時間
            if score=='self': cost=P['think']+2.5
            else: cost=P['think']+x['L']*P['cps']+(1.5 if rec else 0)
            spelled = rec and r.random()<x['sp']
            near = rec and not spelled and r.random()<0.6          # 綴りミスの6割は1文字違い
            typo = score!='self' and spelled and r.random()<P['typo']*x['L']
            eff=1.0 if cost<=10 else 0.3
            if cost>10: over10+=1
            gain_ret = (P['grow'] if score!='self' else 1+(P['grow']-1)*P['covert'])
            if score=='self':
                okm = rec or r.random()<P['overconf']           # 思い出せていないのに○を押す
                x['sp']+= (1-x['sp'])*P['sp_view']*eff
                if okm and rec: x['stab']*=1+(gain_ret-1)*eff; x['F']+=P['kf']*(1-x['F'])*eff
                elif okm: x['stab']*=1.1
                else: x['stab']=max(.5,x['stab']*.6); q.append(x); cost+=3
            else:
                wrong_shown = (rec and not spelled) or typo
                if score=='strict' and (wrong_shown):   # 記憶はあるのに×
                    unfair+= 1 if typo else 0              # タイポで×=不当
                    if typo or near: mot=max(.3,mot-P['mot_hit'])
                    x['sp']+=(1-x['sp'])*P['sp_fb']*eff; x['stab']=max(.5,x['stab']*.7); q.append(x); cost+=3
                elif rec and (spelled or typo or (near and score!='strict')):
                    if near and score=='lenient': x['sp']+=(1-x['sp'])*P['sp_fb']*eff; cost+=3
                    if near and score=='lenient_noretype': x['sp']+=(1-x['sp'])*P['sp_fb']*0.3*eff
                    if spelled: x['sp']+=(1-x['sp'])*P['sp_ok']*eff
                    x['stab']*=1+(gain_ret-1)*eff; x['F']+=P['kf']*0.8*(1-x['F'])*eff
                elif rec:  # 2文字以上違い
                    x['sp']+=(1-x['sp'])*P['sp_fb']*eff; x['stab']=max(.5,x['stab']*.8); q.append(x); cost+=3
                else:
                    x['sp']+=(1-x['sp'])*P['sp_fb']*0.7*eff; x['stab']=max(.5,x['stab']*.6); q.append(x); cost+=3
            if first and not rec: x['stab']=0.6
            x['last']=day; x['due']=day+max(1,int(x['stab']))
            t+=cost; tsum+=cost; n+=1
            mot=min(1,mot+.002)
    T=DAYS+DELAY
    S=[x for x in it if x['seen']]
    ret=sum(R(x,T)-x['p0'] for x in S)               # 新たに言えるようになった語(期待値)
    flu=sum(R(x,T)*(x['F']>0.5) for x in S)          # 即答できる語
    spell=sum(R(x,T)*x['sp'] for x in S)             # 正しく綴れる語
    spacc=spell/max(1e-9,sum(R(x,T) for x in S))     # 言える語のうちの綴り正確率
    val=sum((R(x,T)*x['sp']-x['p0']*x['sp0'])*x['w'] for x in S)  # 実用価値加重(綴りまで正しい・新規分)
    return dict(ret=ret,flu=flu,spell=spell,spacc=spacc,val=val,seen=len(S),unfair=unfair,sec=tsum/max(1,n),o10=over10/max(1,n))
def params(r):
    return dict(attend=r.uniform(.55,.85),think=r.uniform(2.5,4),cps=r.uniform(.35,.65),grow=r.uniform(1.8,2.5),covert=r.uniform(.7,.9),
                overconf=r.uniform(.15,.35),sp_view=r.uniform(.05,.12),sp_fb=r.uniform(.25,.4),sp_ok=r.uniform(.08,.15),
                typo=r.uniform(.004,.008),hyL=7,kf=r.uniform(.12,.2),mot_hit=r.uniform(.004,.01))
def table(NP,score_list,mix_list,title,fun=0.0,mod=None):
    print('\n==',title)
    print('| 採点 | 配分 | 新規に言える語 | 即答できる語 | 正しく綴れる語 | 綴り正確率 | 実用価値加重 | 不当な× | 平均秒/問 | 10秒超 |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    base=None
    for sc in score_list:
        for mx in mix_list:
            R_=[]
            for s in range(NP):
                P=params(random.Random(s))
                if mod: mod(P)
                R_.append(run(sc,mx,P,s,fun))
            m=lambda k:st.mean(x[k] for x in R_)
            print(f"| {sc} | {mx} | {m('ret'):.1f} | {m('flu'):.1f} | {m('spell'):.1f} | {m('spacc')*100:.0f}% | {m('val'):.1f} | {m('unfair'):.0f} | {m('sec'):.1f} | {m('o10')*100:.0f}% |")
if __name__=='__main__':
    NP=int(sys.argv[1]) if len(sys.argv)>1 else 200
    SC=['strict','lenient','lenient_noretype','self','hybrid']
    table(NP,SC,['half'],'採点方式（配分=半々、1日3分×30日、14日後）')
    table(NP,['lenient','self','hybrid'],['jh','tricky','half'],'配分（採点=1文字おしい再入力 / 自己評価）')
    table(NP,['lenient'],['jh','tricky','half'],'感度: tricky は楽しく継続率↑(休む日-30%)',fun=0.3)
    table(NP,['lenient','self','hybrid'],['half'],'感度: 自己評価の甘さ大(思い出せないのに○ 35-55%)・見るだけの綴り学習小',mod=lambda P:P.update(overconf=random.Random(int(P['cps']*1e6)).uniform(.35,.55),sp_view=.03))
    table(NP,['strict','lenient','hybrid'],['half'],'感度: 入力が速い人(cps 0.25-0.35)',mod=lambda P:P.update(cps=.3))
