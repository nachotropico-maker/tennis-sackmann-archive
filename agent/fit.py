"""Apprend les poids du modèle complet (régression logistique) et les compare à l'Elo seul.
Entraînement 2012-2022, test 2023 → aujourd'hui. Usage : python agent/fit.py  (écrit agent/data/poids.json)"""
import json, os, sys
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from features import build, FEATURES, LABELS
from engine import DATA

out = {}
for tour in ["atp", "wta"]:
    st, X = build(tour)
    rng = np.random.default_rng(1)
    flip = rng.random(len(X)) < 0.5
    sign = np.where(flip, -1.0, 1.0)
    M = X[FEATURES].values * sign[:, None]
    y = (~flip).astype(int)
    tr = (X.date >= 20120101).values & (X.date <= 20221231).values
    te = (X.date >= 20230101).values
    full = LogisticRegression(fit_intercept=False, C=0.5, max_iter=2000).fit(M[tr], y[tr])
    base = LogisticRegression(fit_intercept=False, max_iter=2000).fit(M[tr][:, :1], y[tr])
    pf, pb = full.predict_proba(M[te])[:, 1], base.predict_proba(M[te][:, :1])[:, 1]
    res = lambda p: {"precision": round(float(((p > .5) == (y[te] == 1)).mean()), 4),
                     "brier": round(float(((p - y[te]) ** 2).mean()), 4)}
    # impact moyen de chaque critère (en points de %), sur le test
    coef = dict(zip(FEATURES, full.coef_[0]))
    imp = {}
    for i, f in enumerate(FEATURES):
        M2 = M[te].copy(); M2[:, i] = 0
        imp[f] = round(float(np.mean(np.abs(pf - full.predict_proba(M2)[:, 1]))) * 100, 2)
    d26 = (X.date[te] >= 20260101).values; gs = (X.level[te] == "G").values
    sub = lambda p, msk: round(float(((p[msk] > .5) == (y[te][msk] == 1)).mean()), 4)
    extra = {"complet_2026": sub(pf, d26), "elo_2026": sub(pb, d26), "complet_gc": sub(pf, gs), "elo_gc": sub(pb, gs),
             "n_2026": int(d26.sum())}
    print(tour.upper(), extra)
    out[tour] = {**extra, "coef": {k: round(float(v), 4) for k, v in coef.items()},
                 "elo_seul": res(pb), "complet": res(pf), "n_test": int(te.sum()),
                 "impact_moyen_pts": imp}
    print(tour.upper(), "Elo seul", res(pb), "| complet", res(pf), "| n_test", int(te.sum()))
    for f in sorted(FEATURES, key=lambda f: -imp[f]):
        print(f"   {LABELS[f]:45s} poids {coef[f]:+.3f}   impact moyen {imp[f]:.2f} pts")
json.dump(out, open(os.path.join(DATA, "poids.json"), "w"), ensure_ascii=False, indent=1)
