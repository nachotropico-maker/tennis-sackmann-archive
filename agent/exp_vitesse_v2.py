"""Vitesse du court v2 : (a) vitesse de l'édition en cours mesurée au fil des matchs, (b) interactions
service × vitesse et retour × vitesse. Entraînement 2012-2022, test 2023+."""
import math, sys, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
import features as F
from features import State, FEATURES, load_all, tourney_country, norm

class S2(State):
    def speed_z2(self, tourney, surf, year):
        z0 = self.speed_z(tourney, surf, year)
        cur = self.speed.get((norm(tourney), year)); m = self.speed_surf.get((surf, year - 1))
        if not cur or not m or cur[1] < 300 or m[1] == 0: return z0
        zc = math.log((cur[0] / cur[1] + 1e-4) / (m[0] / m[1] + 1e-4))
        w = cur[1] / (cur[1] + 1500)
        return w * zc + (1 - w) * z0

def run(tour):
    d = load_all(tour); st = S2(tour); rows = []
    for r in d.itertuples(index=False):
        if r.main and r.tourney_date >= 20120101:
            f, fa, fb, p = st.features(r.winner_id, r.loser_id, r.surf, r.mdate, r.best_of, r.round,
                                       r.tourney_level, tourney_country(r.tourney_name), r.tourney_name)
            yr = pd.Timestamp.fromordinal(r.mdate).year
            sz0 = st.speed_z(r.tourney_name, r.surf, yr); sz2 = st.speed_z2(r.tourney_name, r.surf, yr)
            f["style_v2"] = (fa["orient"] - fb["orient"]) * sz2
            f["serv_v"] = f["service"] * sz2; f["ret_v"] = f["retour"] * sz2
            f["serv_v0"] = f["service"] * sz0; f["ret_v0"] = f["retour"] * sz0
            rows.append({"date": r.tourney_date, "sz0": sz0, "sz2": sz2, **f})
        st.update(r)
    X = pd.DataFrame(rows)
    rng = np.random.default_rng(1); flip = rng.random(len(X)) < .5; s = np.where(flip, -1., 1.); y = (~flip).astype(int)
    tr = (X.date <= 20221231).values; te = (X.date >= 20230101).values
    base = [c for c in FEATURES]
    variants = {"actuel": base,
                "+interactions (édition préc.)": base + ["serv_v0", "ret_v0"],
                "vitesse en cours (style)": [c if c != "style_vitesse" else "style_v2" for c in base],
                "vitesse en cours + interactions": [c if c != "style_vitesse" else "style_v2" for c in base] + ["serv_v", "ret_v"]}
    print(tour.upper(), "couverture vitesse: préc.", round((X.sz0 != 0).mean(), 3), "| avec édition en cours", round((X.sz2 != 0).mean(), 3))
    for k, cols in variants.items():
        M = X[cols].values * s[:, None]
        lr = LogisticRegression(fit_intercept=False, C=.5, max_iter=3000).fit(M[tr], y[tr])
        p = lr.predict_proba(M[te])[:, 1]
        c = dict(zip(cols, lr.coef_[0]))
        extra = {k2: round(c[k2], 3) for k2 in cols if k2 in ("serv_v", "ret_v", "serv_v0", "ret_v0", "style_v2", "style_vitesse")}
        print(f"  {k:34s} précision {((p > .5) == (y[te] == 1)).mean():.4f}  brier {((p - y[te]) ** 2).mean():.5f}  {extra}")

for t in sys.argv[1:] or ["atp", "wta"]: run(t)
