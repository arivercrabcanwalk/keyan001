import json, sys, numpy as np, collections
def load(f):
    C=collections.defaultdict(dict)
    for l in open(f):
        r=json.loads(l); C[r['case']][r['reserve']]=r
    return C
A=load(sys.argv[1]); B=load(sys.argv[2])
G=sorted({g for c in A for g in A[c]}); cs=sorted(c for c in A if not any(A[c][g].get('infeasible') for g in G))
M=lambda C,k: np.array([[C[c][g][k] for g in G] for c in cs])
ca,fa,cb,fb=M(A,'cost'),M(A,'failed'),M(B,'cost'),M(B,'failed')
W=np.array([A[c][G[0]]['ctx']['W'] for c in cs]); sg=np.array([A[c][G[0]]['ctx']['sigma'] for c in cs])
for P in (25,50,100,200):
    Ja,Jb=ca+P*fa,cb+P*fb; bf=Ja.mean(0).argmin(); k=Ja.argmin(1)
    orc=Jb[np.arange(len(cs)),k].mean(); fix=Jb[:,bf].mean(); full=Jb.min(1).mean()
    print(f'P={P}: fixed r={G[bf]} J={fix:.2f} | oracle(chosen on seedA, eval seedB) J={orc:.2f} headroom {100*(fix-orc)/fix:.2f}% | eval-on-B oracle {100*(fix-full)/fix:.2f}%')
