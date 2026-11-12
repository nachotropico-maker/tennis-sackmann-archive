"""Test : le favori est-il surestimé lors de son premier match dans un tournoi ? (circuit principal)"""
import sys
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from features import load_all, State, FEATURES, tourney_country
from engine import norm

def first_match(st, pid, day, tn):
    return not any(day - 12 <= x[0] < day and x[9] == tn for x in st.hist[pid])

for tour in sys.argv[1:] or ["atp", "wta"]:
    d = load_all(tour); st = State(tour); rows = []
    for r in d.itertuples(index=False):
        if r.main and r.tourney_date >= 20110101 and str(r.tourney_level) != "D":
            f, _, _, p = st.features(r.winner_id, r.loser_id, r.surf, r.mdate, r.best_of, r.round,
                                     r.tourney_level, tourney_country(r.tourney_name), r.tourney_name)
            tn = norm(r.tourney_name)
            rows.append({"date": r.tourney_date, "round": r.round, "level": r.tourney_level, **f,
                         "fa": first_match(st, r.winner_id, r.mdate, tn), "fb": first_match(st, r.loser_id, r.mdate, tn)})
        st.update(r)
    X = pd.DataFrame(rows)
    rng = np.random.default_rng(1); flip = rng.random(len(X)) < .5; sign = np.where(flip, -1., 1.); y = (~flip).astype(int)
    tr = ((X.date >= 20120101) & (X.date <= 20221231)).values
    X["premier"] = X.fa.astype(float) - X.fb.astype(float)
    def fit(cols):
        M = X[cols].values * sign[:, None]
        m = LogisticRegression(fit_intercept=False, C=.5, max_iter=3000).fit(M[tr], y[tr]); return m, m.predict_proba(M)[:, 1]
    _, pb = fit(FEATURES)
    pw = np.where(flip, 1 - pb, pb)               # proba prévue pour le vainqueur réel
    pfav = np.maximum(pw, 1 - pw); fav_won = (pw > .5)
    # le favori joue-t-il son premier match ? l'adversaire ?
    fav_first = np.where(pw > .5, X.fa, X.fb); dog_first = np.where(pw > .5, X.fb, X.fa)
    m2 = (X.date >= 20120101).values
    print(f"\n===== {tour.upper()} (2012-2026, {m2.sum()} matchs)")
    for lab, msk in [("favori 1er match, adversaire déjà lancé", fav_first & ~dog_first),
                     ("les deux à leur 1er match", fav_first & dog_first),
                     ("favori déjà lancé, adversaire 1er match", ~fav_first & dog_first),
                     ("les deux déjà lancés", ~fav_first & ~dog_first)]:
        k = m2 & msk
        print(f"   {lab:42s} n={k.sum():6d}  favori gagne {fav_won[k].mean():.1%}  prévu {pfav[k].mean():.1%}  écart {100*(fav_won[k].mean()-pfav[k].mean()):+.1f}")
    for lab, lo in [("gros favori ≥75 %, 1er match vs adversaire lancé", .75)]:
        k = m2 & fav_first & ~dog_first & (pfav >= lo)
        print(f"   {lab:42s} n={k.sum():6d}  favori gagne {fav_won[k].mean():.1%}  prévu {pfav[k].mean():.1%}  écart {100*(fav_won[k].mean()-pfav[k].mean()):+.1f}")
    te = (X.date >= 20230101).values
    acc = lambda p: ((p[te] > .5) == (y[te] == 1)).mean(); br = lambda p: ((p[te] - y[te]) ** 2).mean()
    mm, pp = fit(FEATURES + ["premier"])
    print(f"   test 2023+ : actuel {acc(pb):.4f} / Brier {br(pb):.4f}  |  + premier match {acc(pp):.4f} / Brier {br(pp):.4f}  coef {mm.coef_[0][-1]:+.3f}")
