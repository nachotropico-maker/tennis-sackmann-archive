"""Test v3 : enjeu au classement, face-à-face, autres stats de tirs (2013-2022 apprentissage, 2023-2025 test)."""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from modele import LIGUES, features_hist
m = pd.read_csv("data/matchs_hist.csv", parse_dates=["MatchDate"]).dropna(subset=["HomeElo","AwayElo","FTResult","FTHome","FTAway"])
m = m.sort_values("MatchDate").reset_index(drop=True)
m["saison"] = m.MatchDate.dt.year.where(m.MatchDate.dt.month >= 7, m.MatchDate.dt.year - 1)
m["y"] = m.FTResult.map({"H":0,"D":1,"A":2}); m["d"] = (m.HomeElo-m.AwayElo)/100
f = features_hist(m); f["d"] = m.d
NREL = {"E0":3,"SP1":3,"I1":3,"F1":3,"D1":2,"T1":3,"N1":2,"P1":2,"B1":2}
# --- enjeu : classement avant chaque match
enj = np.zeros((len(m), 6))  # rien_a_jouer dom/ext, maintien dom/ext, haut dom/ext
for (lg, s), g in m.groupby(["Division", "saison"]):
    teams = sorted(set(g.HomeTeam) | set(g.AwayTeam)); n = len(teams); tot = 2 * (n - 1)
    pts = {t: 0 for t in teams}; gp = {t: 0 for t in teams}
    for i, r in g.iterrows():
        tab = sorted(pts.values(), reverse=True)
        line_eu = tab[5]; line_rel = tab[n - NREL[lg]]   # points de la 6e place et du 1er relégable
        for k, t in ((0, r.HomeTeam), (1, r.AwayTeam)):
            rem = tot - gp[t]
            if rem <= 10:
                up = line_eu - pts[t]; down = pts[t] - line_rel
                rien = (up > 3 * rem) and (down > 3 * rem)
                enj[i, k] = rien
                enj[i, 2 + k] = (down <= 6) * 1.0
                enj[i, 4 + k] = (abs(up) <= 6 and pts[t] >= line_eu - 6) * 1.0
        h, a = r.HomeTeam, r.AwayTeam
        pts[h] += {"H":3,"D":1,"A":0}[r.FTResult]; pts[a] += {"A":3,"D":1,"H":0}[r.FTResult]; gp[h] += 1; gp[a] += 1
f["rien"] = enj[:, 0] - enj[:, 1]; f["maintien"] = enj[:, 2] - enj[:, 3]; f["haut"] = enj[:, 4] - enj[:, 5]
f["rien_un"] = ((enj[:, 0] + enj[:, 1]) == 1) * 1.0
# --- face-à-face : résidu (points réels - attendus par l'Elo) du dom contre cet adversaire, 6 dernières rencontres, resserré
e = 1 / (1 + 10 ** (-(m.HomeElo - m.AwayElo + 65) / 400)); m["res"] = m.FTResult.map({"H":3,"D":1,"A":0}) - (3 * e * .8 + .27)
key = m.apply(lambda r: tuple(sorted((r.HomeTeam, r.AwayTeam))), axis=1); hist = {}; h2h = []
for i, r in m.iterrows():
    k = key[i]; past = hist.get(k, [])[-6:]
    v = sum(x if t == r.HomeTeam else -x for t, x in past) / (len(past) + 4)
    h2h.append(v); hist.setdefault(k, []).append((r.HomeTeam, r.res))
f["h2h"] = h2h
# --- autres stats : tirs totaux et corners (5 derniers)
rows = []
for side, t, a, b, c1, c2 in (("H","HomeTeam","HomeShots","AwayShots","HomeCorners","AwayCorners"),("A","AwayTeam","AwayShots","HomeShots","AwayCorners","HomeCorners")):
    rows.append(pd.DataFrame({"i": m.index, "side": side, "team": m[t], "date": m.MatchDate, "sh": m[a]-m[b], "co": m[c1]-m[c2]}))
L = pd.concat(rows).sort_values(["team","date"]); g = L.groupby("team")
for c in ["sh","co"]: L[c+"5"] = g[c].transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
H = L[L.side=="H"].set_index("i"); A = L[L.side=="A"].set_index("i")
f["tirs"] = (H.sh5.fillna(0) - A.sh5.fillna(0)) / 6; f["corners"] = (H.co5.fillna(0) - A.co5.fillna(0)) / 4
lg = pd.get_dummies(m.Division, dtype=float).reindex(columns=list(LIGUES), fill_value=0)
tr = (m.saison >= 2013) & (m.saison <= 2022); te = m.saison.isin([2023, 2024, 2025])
def rps(p, y): Y = np.eye(3)[y]; c = np.cumsum(p,1)[:,:2]-np.cumsum(Y,1)[:,:2]; return (c**2).sum(1).mean()/2
base = ["d","sot","absd","buts"]
def run(cols, label, mask=None):
    X = pd.concat([lg, f[cols]], axis=1)
    lr = LogisticRegression(max_iter=4000, fit_intercept=False).fit(X[tr], m.y[tr]); p = lr.predict_proba(X[te]); yt = m.y[te].values
    k = np.ones(len(yt), bool) if mask is None else mask[te.values]
    print(f"{label:30s} n={k.sum():5d} réussite {np.mean(p[k].argmax(1)==yt[k]):.4f}  logloss {log_loss(yt[k],p[k],labels=[0,1,2]):.4f}  RPS {rps(p[k],yt[k]):.4f}")
    return lr
run(base, "v2 (actuel)")
for c in [["rien","rien_un"], ["maintien","haut"], ["h2h"], ["tirs"], ["corners"]]: run(base + c, "+ " + "+".join(c))
fin = (enj[:, :2].sum(1) > 0) | (enj[:, 2:].sum(1) > 0)
print("--- matchs de fin de saison avec un enjeu ou un 'rien à jouer' :")
run(base, "v2", fin); lr = run(base + ["rien","rien_un","maintien","haut"], "v2 + enjeu", fin)
print(pd.DataFrame(lr.coef_[:, -8:], columns=base + ["rien","rien_un","maintien","haut"], index=["1","N","2"]).round(3))
lr = run(base + ["h2h"], "v2 + h2h"); print("coef h2h", lr.coef_[:, -1].round(3))
