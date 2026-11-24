"""Agent Foot : modèle 1N2 + buts à partir de l'Elo des clubs.

fit()  : entraîne sur data/matchs_hist.csv (saisons 2012-2025) et écrit data/modele.json
proba(elo_dom, elo_ext, ligue) : probabilités 1/N/2, buts attendus, score le plus probable, +2,5 buts
"""
import json, math, os
import numpy as np, pandas as pd

ICI = os.path.dirname(os.path.abspath(__file__))
LIGUES = {"E0": "Premier League", "SP1": "Liga", "I1": "Serie A", "F1": "Ligue 1", "D1": "Bundesliga",
          "T1": "Süper Lig", "N1": "Eredivisie", "P1": "Liga Portugal", "B1": "Pro League"}
COUPES = {"UCL": "Ligue des champions", "UEL": "Ligue Europa", "UECL": "Ligue Conférence"}


def _saison(d):
    return d.dt.year.where(d.dt.month >= 7, d.dt.year - 1)


COLS = ["d", "sot", "absd", "buts", "tirs"]


def features_hist(m):
    """Forme aux tirs cadrés (5 derniers matchs) et volume de buts (10 derniers), calculés avant chaque match."""
    m = m.sort_values("MatchDate")
    rows = []
    for side, t, o, gf, ga, sf, sa in (("H", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "HomeTarget", "AwayTarget"),
                                      ("A", "AwayTeam", "HomeTeam", "FTAway", "FTHome", "AwayTarget", "HomeTarget")):
        rows.append(pd.DataFrame({"i": m.index, "side": side, "team": m[t], "date": m.MatchDate,
                                  "tc": m[sf] - m[sa], "n": m[sf].notna(), "b": m[gf] + m[ga],
                                  "sh": m["HomeShots" if side == "H" else "AwayShots"] - m["AwayShots" if side == "H" else "HomeShots"]}))
    L = pd.concat(rows).sort_values(["team", "date"])
    g = L.groupby("team")
    L["sot5"] = g.tc.transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    L["nb"] = g.n.transform(lambda s: s.shift(1).rolling(5, min_periods=1).sum())
    L["sh5"] = g.sh.transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    L["b10"] = g.b.transform(lambda s: s.shift(1).rolling(10, min_periods=5).mean())
    H = L[L.side == "H"].set_index("i"); A = L[L.side == "A"].set_index("i")
    ok = (H.nb >= 3) & (A.nb >= 3)
    f = pd.DataFrame(index=m.index)
    f["sot"] = ((H.sot5.fillna(0) - A.sot5.fillna(0)) / 3).where(ok, 0.0)
    f["tirs"] = ((H.sh5.fillna(0) - A.sh5.fillna(0)) / 6).where(ok, 0.0)
    f["absd"] = m.d.abs()
    f["buts"] = (H.b10.fillna(2.6) + A.b10.fillna(2.6)) / 2 - 2.6
    return f


def fit(test_saisons=(2023, 2024, 2025)):
    from sklearn.linear_model import LogisticRegression, PoissonRegressor
    from sklearn.metrics import log_loss
    m = pd.read_csv(os.path.join(ICI, "data/matchs_hist.csv"), parse_dates=["MatchDate"])
    m = m.dropna(subset=["HomeElo", "AwayElo", "FTResult", "FTHome", "FTAway"])
    m["d"] = (m.HomeElo - m.AwayElo) / 100
    m["y"] = m.FTResult.map({"H": 0, "D": 1, "A": 2})
    m["saison"] = _saison(m.MatchDate)

    f = features_hist(m)
    m = m.join(f)
    def X(df):
        x = pd.get_dummies(df.Division, dtype=float).reindex(columns=list(LIGUES), fill_value=0)
        for c in COLS:
            x[c] = df[c]
        return x

    def Xg(df):
        x = pd.get_dummies(df.Division, dtype=float).reindex(columns=list(LIGUES), fill_value=0)
        x["d"] = df.d
        return x

    res = {}
    for phase in ("test", "final"):
        tr = m[m.saison < min(test_saisons)] if phase == "test" else m
        lr = LogisticRegression(max_iter=3000, fit_intercept=False).fit(X(tr), tr.y)
        ph = PoissonRegressor(alpha=0, max_iter=1000, fit_intercept=False).fit(Xg(tr), tr.FTHome)
        pa = PoissonRegressor(alpha=0, max_iter=1000, fit_intercept=False).fit(Xg(tr), tr.FTAway)
        if phase == "test":
            te = m[m.saison.isin(test_saisons)]
            p = lr.predict_proba(X(te))
            o = te[["OddHome", "OddDraw", "OddAway"]]
            ok = o.notna().all(axis=1).values
            q = 1 / o[ok]
            q = q.div(q.sum(axis=1), axis=0).values
            res["test"] = {
                "saisons": list(test_saisons), "matchs": int(len(te)),
                "reussite_modele": round(float((p.argmax(1) == te.y).mean()), 4),
                "logloss_modele": round(float(log_loss(te.y, p)), 4),
                "reussite_bookmakers": round(float((q.argmax(1) == te.y[ok]).mean()), 4),
                "logloss_bookmakers": round(float(log_loss(te.y[ok], q)), 4),
                "reussite_toujours_domicile": round(float((te.y == 0).mean()), 4),
                "taux_nuls": round(float((te.y == 1).mean()), 4),
                "par_ligue": {LIGUES[k]: round(float((p[(te.Division == k).values].argmax(1) == te.y[te.Division == k]).mean()), 3)
                              for k in LIGUES},
            }
        else:
            cols = list(LIGUES) + COLS
            res["logit"] = {c: [float(v) for v in lr.coef_[:, i]] for i, c in enumerate(cols)}
            cg = list(LIGUES) + ["d"]
            res["buts_dom"] = {c: float(ph.coef_[i]) for i, c in enumerate(cg)}
            res["buts_ext"] = {c: float(pa.coef_[i]) for i, c in enumerate(cg)}
    json.dump(res, open(os.path.join(ICI, "data/modele.json"), "w"), indent=1, ensure_ascii=False)
    return res


_M = None


def _mod():
    global _M
    if _M is None:
        _M = json.load(open(os.path.join(ICI, "data/modele.json")))
    return _M


def _inter(table, ligue, neutre=False):
    if ligue in LIGUES:
        return table[ligue]
    # coupes d'Europe : moyenne des championnats
    v = np.mean([table[k] for k in LIGUES], axis=0)
    return v


def proba(elo_dom, elo_ext, ligue, neutre=False, sot=0.0, buts=0.0, tirs=0.0):
    """sot = (écart de tirs cadrés par match du dom sur 5 matchs − même chose pour l'ext) / 3 ;
    buts = moyenne des buts par match (pour+contre, 10 derniers) des deux équipes − 2,6."""
    M = _mod()
    d = (elo_dom - elo_ext) / 100
    lg = {c: np.array(v) for c, v in M["logit"].items()}
    extra = lambda dd, ss, tt: sum(lg[c] * v for c, v in (("sot", ss), ("absd", abs(dd)), ("buts", buts), ("tirs", tt)) if c in lg)
    z = _inter(lg, ligue) + lg["d"] * d + extra(d, sot, tirs)
    if neutre:  # pas d'avantage du terrain : symétriser
        z2 = _inter(lg, ligue) - lg["d"] * d + extra(-d, -sot, -tirs)
        z = (z + z2[::-1]) / 2
    p = np.exp(z - z.max()); p = p / p.sum()
    bh = M["buts_dom"]; ba = M["buts_ext"]
    lh = math.exp(float(_inter(bh, ligue)) + bh["d"] * d)
    la = math.exp(float(_inter(ba, ligue)) + ba["d"] * d)
    if neutre:
        base = (float(_inter(bh, ligue)) + float(_inter(ba, ligue))) / 2
        lh, la = math.exp(base + bh["d"] * d), math.exp(base + ba["d"] * d)
    # matrice de scores (Poisson indépendants)
    fac = [math.factorial(k) for k in range(11)]
    ph = [math.exp(-lh) * lh ** k / fac[k] for k in range(11)]
    pa = [math.exp(-la) * la ** k / fac[k] for k in range(11)]
    best, bp, over = (0, 0), 0, 0.0
    for i in range(11):
        for j in range(11):
            pij = ph[i] * pa[j]
            if pij > bp:
                best, bp = (i, j), pij
            if i + j >= 3:
                over += pij
    # score le plus probable cohérent avec l'issue favorite
    issue = int(np.argmax(p))
    cand = [(ph[i] * pa[j], (i, j)) for i in range(7) for j in range(7)
            if (issue == 0 and i > j) or (issue == 1 and i == j) or (issue == 2 and i < j)]
    score_issue = max(cand)[1]
    return {"p1": round(float(p[0]), 3), "pN": round(float(p[1]), 3), "p2": round(float(p[2]), 3),
            "buts_dom": round(lh, 2), "buts_ext": round(la, 2),
            "score_probable": f"{score_issue[0]}-{score_issue[1]}",
            "plus_2_5": round(over, 3)}


if __name__ == "__main__":
    r = fit()
    print(json.dumps(r["test"], indent=1, ensure_ascii=False))
    print(proba(1900, 1750, "E0"), proba(1800, 1800, "UCL"))
