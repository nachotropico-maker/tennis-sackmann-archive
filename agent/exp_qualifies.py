"""Test : les qualifiés qui ont accumulé des sets sont-ils surestimés face à un adversaire reposé ?
Circuit principal seulement (les qualifs comptées sont celles du même tournoi, pas les Challengers).
Usage : python agent/exp_qualifies.py"""
import sys
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from features import load_all, State, FEATURES, tourney_country
from engine import norm

MAIN_LEVELS = {"atp": {"G", "M", "A", "F"}, "wta": {"G", "PM", "P", "I", "T1", "T2", "W", "F", "M", "A"}}
LATE_OK = {"R32", "R16", "QF", "SF", "F"}


def qual_info(st, pid, day, tn):
    """(est qualifié, sets joués en qualifs + tableau du même tournoi sur 12 jours)"""
    h = [x for x in st.hist[pid] if day - 12 <= x[0] < day and x[9] == tn]
    q = any(str(x[10]).startswith("Q") for x in h)
    return q, sum(x[3] for x in h), len(h)


def run(tour):
    d = load_all(tour)
    st = State(tour)
    rows = []
    for r in d.itertuples(index=False):
        if r.main and r.tourney_date >= 20110101 and (tour == "wta" or str(r.tourney_level) in MAIN_LEVELS[tour]):
            f, fa, fb, p = st.features(r.winner_id, r.loser_id, r.surf, r.mdate, r.best_of, r.round,
                                       r.tourney_level, tourney_country(r.tourney_name), r.tourney_name)
            tn = norm(r.tourney_name)
            qa, sa, na = qual_info(st, r.winner_id, r.mdate, tn)
            qb, sb, nb = qual_info(st, r.loser_id, r.mdate, tn)
            rows.append({"date": r.tourney_date, "round": r.round, "best_of": r.best_of, **f,
                         "qa": qa, "qb": qb, "sa": sa, "sb": sb, "na": na, "nb": nb})
        st.update(r)
    X = pd.DataFrame(rows)
    # nouveaux critères (A - B)
    X["qualifie"] = X.qa.astype(float) - X.qb.astype(float)
    X["sets_qualifie"] = X.qa * X.sa - X.qb * X.sb          # sets accumulés par un qualifié
    X["sets_tournoi"] = X.sa - X.sb                          # sets accumulés dans le tournoi, tous joueurs
    rng = np.random.default_rng(1)
    flip = rng.random(len(X)) < 0.5
    sign = np.where(flip, -1.0, 1.0)
    y = (~flip).astype(int)
    tr = (X.date <= 20221231).values & (X.date >= 20120101).values
    te = (X.date >= 20230101).values
    bo3 = (X.best_of == 3).values

    def fit(cols):
        M = X[cols].values * sign[:, None]
        m = LogisticRegression(fit_intercept=False, C=0.5, max_iter=3000).fit(M[tr], y[tr])
        p = m.predict_proba(M)[:, 1]
        return m, p

    base_m, pb = fit(FEATURES)
    print(f"\n===== {tour.upper()} : {len(X)} matchs du circuit principal, test 2023+ : {te.sum()}")
    ll = lambda p, msk: float(-np.mean(y[msk] * np.log(p[msk]) + (1 - y[msk]) * np.log(1 - p[msk])))
    acc = lambda p, msk: float(((p[msk] > .5) == (y[msk] == 1)).mean())
    brier = lambda p, msk: float(((p[msk] - y[msk]) ** 2).mean())

    # 1) descriptif : qualifié contre joueur direct, en fonction des sets accumulés, écart réel - prévu
    # point de vue du qualifié
    one = (X.qa ^ X.qb).values & (X.date >= 20120101).values
    q_is_a = X.qa.values
    p_q = np.where(q_is_a, pb_unflip := np.where(flip, 1 - pb, pb), 1 - pb_unflip)
    win_q = np.where(q_is_a, 1, 0)  # dans les données, A = vainqueur
    sets_q = np.where(q_is_a, X.sa, X.sb); sets_o = np.where(q_is_a, X.sb, X.sa)
    diff = sets_q - sets_o
    print("Qualifié contre entrée directe (tous tours du tableau, 2012+) : réel vs modèle actuel")
    for lo, hi, lab in [(-99, 1, "≤ 1 set de plus"), (2, 3, "2-3 sets de plus"), (4, 5, "4-5 sets de plus"), (6, 99, "6 sets de plus ou +")]:
        m = one & (diff >= lo) & (diff <= hi)
        if m.sum() < 30:
            continue
        print(f"   {lab:22s} n={m.sum():5d}  victoires réelles {win_q[m].mean():.1%}  prévues {p_q[m].mean():.1%}  écart {100*(win_q[m].mean()-p_q[m].mean()):+.1f} pts")
    m = one & np.isin(X["round"].values, list(LATE_OK)) & (diff >= 4) & bo3
    if m.sum() >= 30:
        print(f"   Focus R32→finale, BO3, ≥4 sets de plus : n={m.sum()}  réel {win_q[m].mean():.1%}  prévu {p_q[m].mean():.1%}  écart {100*(win_q[m].mean()-p_q[m].mean()):+.1f} pts")


    for rounds,lab in [(["QF"],"QF"),(["QF","SF","F"],"QF→F")]:
        for cond,cl in [((sets_o<=3),"adversaire reposé (≤3 sets)"),((sets_o>=4),"adversaire aussi chargé")]:
            m = one & np.isin(X["round"].values, rounds) & bo3 & cond & (sets_q>=8)
            if m.sum()>=20:
                print(f"   {lab} qualifié ≥8 sets, {cl}: n={m.sum()} réel {win_q[m].mean():.1%} prévu {p_q[m].mean():.1%} écart {100*(win_q[m].mean()-p_q[m].mean()):+.1f}")
    # 2) le critère améliore-t-il le modèle sur 2023+ ?
    res = {"actuel": (acc(pb, te), brier(pb, te), ll(pb, te))}
    for name, extra in [("+ qualifié", ["qualifie"]), ("+ sets du qualifié", ["qualifie", "sets_qualifie"]),
                        ("+ sets dans le tournoi", ["sets_tournoi"])]:
        mm, pp = fit(FEATURES + extra)
        co = dict(zip(FEATURES + extra, mm.coef_[0]))
        res[name] = (acc(pp, te), brier(pp, te), ll(pp, te))
        print(f"   {name:24s} coef " + ", ".join(f"{c}={co[c]:+.3f}" for c in extra))
    for k, (a, b, c) in res.items():
        print(f"   {k:24s} précision {a:.4f}  Brier {b:.4f}  logloss {c:.4f}")
    # matchs concernés seulement
    tq = te & one
    print(f"   Sur les {tq.sum()} matchs test avec un qualifié :")
    for name, extra in [("actuel", []), ("+ sets du qualifié", ["qualifie", "sets_qualifie"])]:
        _, pp = fit(FEATURES + extra)
        print(f"     {name:22s} précision {acc(pp, tq):.4f}  Brier {brier(pp, tq):.4f}")


for t in sys.argv[1:] or ["atp", "wta"]:
    run(t)
