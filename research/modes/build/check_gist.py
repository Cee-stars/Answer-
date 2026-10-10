import sys,os;sys.path.insert(0,os.path.dirname(__file__));from gist_opts import O
def rank(L):
    a=L[0];o=L[1:]
    if a>max(o): return 'L'
    if a<min(o): return 'S'
    if min(o)<a<max(o): return 'M'
    return 'T'
if __name__=='__main__':
  bad=0
  for i,o in enumerate(O):
    L=[len(x) for x in o]; r=rank(L); ok=max(L)/min(L)<=1.3 and r==['L','M','S'][i%3]
    bad+=not ok
    if not ok: print(i,['L','M','S'][i%3],r,L,round(max(L)/min(L),2),o)
  print('bad',bad)
