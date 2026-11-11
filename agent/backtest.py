"""Backtest du modèle tel qu'il tourne (engine.py) : chaque match du circuit principal depuis 2024 est prédit
AVANT la mise à jour, donc sans voir son résultat. Usage : python agent/backtest.py"""
import json, os
import numpy as np, pandas as pd
from engine import load_matches, PARAMS, k_factor, expected, DATA


def bt(tour):
    p = PARAMS[tour]; d = load_matches(tour)
    g, s, ng, ns = {}, {}, {}, {}
    rows = []
    for r in d.itertuples(index=False):
        w, l, sf = r.winner_id, r.loser_id, r.surf
        gw, gl = g.get(w, 1500), g.get(l, 1500); sw, sl = s.get((w, sf), 1500), s.get((l, sf), 1500)
        if r.main and r.tourney_date >= 20240101:
            diff = p["w_surface"] * (sw - sl) + (1 - p["w_surface"]) * (gw - gl)
            rows.append((r.tourney_date, r.tourney_level, 1 / (1 + 10 ** (-p["scale"] * diff / 400))))
        mu = 1.0 if r.main else p["poids_secondaire"]
        eg, es = expected(gw, gl), expected(sw, sl)
        g[w] = gw + mu * k_factor(ng.get(w, 0)) * (1 - eg); g[l] = gl - mu * k_factor(ng.get(l, 0)) * (1 - eg)
        s[(w, sf)] = sw + mu * k_factor(ns.get((w, sf), 0)) * (1 - es); s[(l, sf)] = sl - mu * k_factor(ns.get((l, sf), 0)) * (1 - es)
        ng[w] = ng.get(w, 0) + 1; ng[l] = ng.get(l, 0) + 1
        ns[(w, sf)] = ns.get((w, sf), 0) + 1; ns[(l, sf)] = ns.get((l, sf), 0) + 1
    x = pd.DataFrame(rows, columns=["date", "level", "p"])  # p = proba du vainqueur réel
    gs = x[x.level == "G"]
    return {"n": len(x), "precision": round(float((x.p > 0.5).mean()), 3),
            "brier": round(float(((1 - x.p) ** 2).mean()), 4),
            "grand_chelem": round(float((gs.p > 0.5).mean()), 3),
            "precision_2026": round(float((x[x.date >= 20260101].p > 0.5).mean()), 3)}


if __name__ == "__main__":
    print(json.dumps({t: bt(t) for t in ["atp", "wta"]}, indent=1))
