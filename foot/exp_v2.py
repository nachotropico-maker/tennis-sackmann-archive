"""Test des pistes v2 (2012-2022 apprentissage, 2023-2025 test)."""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from modele import LIGUES
m = pd.read_csv("data/matchs_hist.csv", parse_dates=["MatchDate"]).dropna(subset=["HomeElo","AwayElo","FTResult","FTHome","FTAway"])
m = m.sort_values("MatchDate").reset_index(drop=True)
m["saison"] = m.MatchDate.dt.year.where(m.MatchDate.dt.month >= 7, m.MatchDate.dt.year - 1)
m["y"] = m.FTResult.map({"H":0,"D":1,"A":2}); m["d"] = (m.HomeElo-m.AwayElo)/100
# format long : une ligne par équipe et par match
h = pd.DataFrame({"i":m.index,"team":m.HomeTeam,"date":m.MatchDate,"dom":1,"gf":m.FTHome,"ga":m.FTAway,"sf":m.HomeTarget,"sa":m.AwayTarget,
                  "pts":m.FTResult.map({"H":3,"D":1,"A":0}),"elo":m.HomeElo,"eloadv":m.AwayElo,"lg":m.Division,"saison":m.saison})
a = pd.DataFrame({"i":m.index,"team":m.AwayTeam,"date":m.MatchDate,"dom":0,"gf":m.FTAway,"ga":m.FTHome,"sf":m.AwayTarget,"sa":m.HomeTarget,
                  "pts":m.FTResult.map({"A":3,"D":1,"H":0}),"elo":m.AwayElo,"eloadv":m.HomeElo,"lg":m.Division,"saison":m.saison})
L = pd.concat([h,a]).sort_values(["team","date","dom"]).reset_index(drop=True)
# points attendus selon l'Elo (approx. logistique, avantage terrain 65)
e = 1/(1+10**(-(L.elo-L.eloadv+np.where(L.dom==1,65,-65))/400)); L["xpts"] = 3*e*0.8 + 0.27  # approx
L["res"] = L.pts - L.xpts
g = L.groupby("team")
sh = lambda s: s.shift(1)
L["sot_diff"] = (L.sf-L.sa); L["sot5"] = g.sot_diff.transform(lambda s: sh(s).rolling(5,min_periods=3).mean())
L["sot_nb"] = g.sf.transform(lambda s: sh(s).notna().rolling(5,min_periods=1).sum())
L["gd5"] = g.apply(lambda x: sh(x.gf-x.ga).rolling(5,min_periods=3).mean()).reset_index(level=0,drop=True)
L["res5"] = g.res.transform(lambda s: sh(s).rolling(5,min_periods=3).mean())
L["buts10"] = g.apply(lambda x: sh(x.gf+x.ga).rolling(10,min_periods=5).mean()).reset_index(level=0,drop=True)
L["repos"] = g.date.transform(lambda s: s.diff().dt.days)
# avantage du terrain propre au club : résidu dom - résidu ext cumulé sur les saisons PASSÉES, resserré (k=80 matchs)
def club_hfa(x):
    out=[]; 
    for s in x.saison.unique():
        past=x[x.saison<s]; rd=past[past.dom==1].res; ra=past[past.dom==0].res
        n=min(len(rd),len(ra)); v=(rd.mean()-ra.mean())*n/(n+80) if n else 0.0
        out.append(pd.Series(v,index=x.index[x.saison==s]))
    return pd.concat(out)
L["hfa_club"] = g.apply(club_hfa).reset_index(level=0,drop=True)
# profil à l'extérieur cette saison : résidu moyen des matchs ext de la saison en cours (avant le match), resserré k=6
def prof_ext(x):
    r=[];
    for s,y in x.groupby("saison"):
        v=y.res.where(y.dom==0); c=sh(v.notna().cumsum()).fillna(0); sm=sh(v.fillna(0).cumsum()).fillna(0)
        r.append(sm/(c+6))
    return pd.concat(r)
L["ext_saison"] = g.apply(prof_ext).reset_index(level=0,drop=True)
H = L[L.dom==1].set_index("i"); A = L[L.dom==0].set_index("i")
f = pd.DataFrame(index=m.index)
f["d"]=m.d
f["sot"]=(H.sot5.fillna(0)-A.sot5.fillna(0))/3
f["gd"]=H.gd5.fillna(0)-A.gd5.fillna(0)
f["res"]=H.res5.fillna(0)-A.res5.fillna(0)
f["hfa"]=H.hfa_club.fillna(0)
f["ext"]=A.ext_saison.fillna(0)
f["repos"]=(H.repos.clip(2,10).fillna(7)-A.repos.clip(2,10).fillna(7))/3
f["court_dom"]=(H.repos<=3).astype(float)-(A.repos<=3).astype(float)
f["absd"]=m.d.abs(); f["buts"]=((H.buts10.fillna(2.6)+A.buts10.fillna(2.6))/2-2.6)
f["sot_ok"]=((H.sot_nb>=3)&(A.sot_nb>=3)).astype(float); f["sot"]*=f.sot_ok
lg=pd.get_dummies(m.Division,dtype=float).reindex(columns=list(LIGUES),fill_value=0)
tr=(m.saison>=2013)&(m.saison<=2022); te=m.saison.isin([2023,2024,2025])
def rps(p,y):
    Y=np.eye(3)[y]; c=np.cumsum(p,1)[:,:2]-np.cumsum(Y,1)[:,:2]; return (c**2).sum(1).mean()/2
def run(cols,label):
    X=pd.concat([lg,f[cols]],axis=1)
    lr=LogisticRegression(max_iter=4000,fit_intercept=False,C=1.0).fit(X[tr],m.y[tr]); p=lr.predict_proba(X[te])
    yt=m.y[te].values; pred=p.argmax(1)
    print(f"{label:38s} réussite {np.mean(pred==yt):.4f}  logloss {log_loss(yt,p):.4f}  RPS {rps(p,yt):.4f}  nuls prédits {np.mean(pred==1):.1%}")
    return lr,p
run(["d"],"actuel (Elo)")
for c in ["sot","gd","res","hfa","ext","repos","court_dom"]: run(["d",c],"+ "+c)
run(["d","absd","buts"],"+ nul (écart abs, buts)")
lr,p=run(["d","sot","hfa","ext","repos","absd","buts"],"tout (sans gd/res)")
lr2,p2=run(["d","sot","res","hfa","ext","repos","absd","buts"],"tout + res")
cols=["d","sot","res","hfa","ext","repos","absd","buts"]
print(pd.DataFrame(lr2.coef_[:,-len(cols):],columns=cols,index=["1","N","2"]).round(3))
o=m.loc[te,["OddHome","OddDraw","OddAway"]]; ok=o.notna().all(1).values; q=(1/o[ok]); q=(q.div(q.sum(1),axis=0)).values; yt=m.y[te].values[ok]
print(f"bookmakers                             réussite {np.mean(q.argmax(1)==yt):.4f}  logloss {log_loss(yt,q):.4f}  RPS {rps(q,yt):.4f}")
f.to_pickle("/tmp/f_v2.pkl")
yt=m.y[te].values
for lo,hi in [(0,.24),(.24,.27),(.27,.29),(.29,.31),(.31,1)]:
    k=(p2[:,1]>=lo)&(p2[:,1]<hi); print(f"pN {lo:.2f}-{hi:.2f} n={k.sum():5d} nul réel {np.mean(yt[k]==1):.3f} annoncé {p2[k,1].mean():.3f} favori gagne {np.mean(p2[k].argmax(1)==yt[k]):.3f}")
fav=p2.max(1)
for lo,hi in [(0,.45),(.45,.55),(.55,.65),(.65,1)]:
    k=(fav>=lo)&(fav<hi); print(f"favori {lo:.2f}-{hi:.2f} n={k.sum():5d} juste {np.mean(p2[k].argmax(1)==yt[k]):.3f}")
