"""Test : le retour pèse-t-il plus sur dur lent/moyen que sur dur rapide ? (ATP, circuit principal, 2012-2026)"""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from features import load_all, State, tourney_country
d = load_all("atp"); st = State("atp"); rows = []
for r in d.itertuples(index=False):
    if r.main and r.tourney_date >= 20120101 and str(r.tourney_level) != "D" and r.surf == "Hard":
        f, fa, fb, p = st.features(r.winner_id, r.loser_id, r.surf, r.mdate, r.best_of, r.round,
                                   r.tourney_level, tourney_country(r.tourney_name), r.tourney_name)
        sz = st.speed_z(r.tourney_name, r.surf, pd.Timestamp.fromordinal(r.mdate).year)
        rows.append({"elo": f["elo"], "service": f["service"], "retour": f["retour"], "sz": sz})
    st.update(r)
X = pd.DataFrame(rows)
rng = np.random.default_rng(1); flip = rng.random(len(X)) < .5; s = np.where(flip, -1., 1.); y = (~flip).astype(int)
X = X[X.sz != 0].copy(); s = s[X.index]; y = y[X.index]
cuts = X.sz.quantile([1/3, 2/3]).values
for lab, m in [("dur lent", X.sz <= cuts[0]), ("dur moyen", (X.sz > cuts[0]) & (X.sz <= cuts[1])), ("dur rapide", X.sz > cuts[1])]:
    M = X.loc[m, ["elo", "service", "retour"]].values * s[m.values][:, None]
    lr = LogisticRegression(fit_intercept=False, C=1, max_iter=2000).fit(M, y[m.values])
    c = lr.coef_[0]
    print(f"{lab:11s} n={m.sum():5d}  coef Elo {c[0]:.2f}  service {c[1]:+.3f}  retour {c[2]:+.3f}  ratio retour/service {c[2]/c[1]:.2f}")
