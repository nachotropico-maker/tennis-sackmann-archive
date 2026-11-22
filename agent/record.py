"""Enregistre les résultats de la veille et recalcule le bilan.

Usage : python agent/record.py resultats.json
Entrée : liste {date: AAAA-MM-JJ, id, tour, tournoi, surface, tour_tableau, joueur_a, joueur_b,
                proba_a, vainqueur, score}
  - ajoute chaque match joué à agent/data/{tour}_live.csv (pour que l'Elo en tienne compte)
  - ajoute la ligne au journal agent/data/predictions_log.csv
  - écrit agent/data/stats.json (bilan global, par circuit, par jour, calibration)
"""
import json, os, sys
import pandas as pd
from engine import DATA

LOG = os.path.join(DATA, "predictions_log.csv")


def append_live(r):
    if not r.get("vainqueur") or r.get("score", "").lower() in ("w/o", "walkover"):
        return
    f = os.path.join(DATA, f"{r['tour']}_live.csv")
    win, los = (r["joueur_a"], r["joueur_b"]) if r["vainqueur"] == r["joueur_a"] else (r["joueur_b"], r["joueur_a"])
    row = {"tourney_name": r["tournoi"], "surface": r["surface"], "tourney_level": r.get("niveau", ""),
           "tourney_date": int(r["date"].replace("-", "")), "match_num": 0,
           "winner_id": r["id_vainqueur"], "winner_name": win,
           "loser_id": r["id_perdant"], "loser_name": los, "score": r.get("score", ""),
           "round": r.get("tour_tableau", "")}
    # Statistiques du match (format SportRadar de fetch_sports_data game_stats), facultatives :
    # r["stats_a"] / r["stats_b"] = dictionnaires « statistics » de joueur_a / joueur_b.
    sa, sb = r.get("stats_a"), r.get("stats_b")
    if sa and sb:
        sw, sl = (sa, sb) if r["vainqueur"] == r["joueur_a"] else (sb, sa)
        row.update(sackmann_stats("w", sw, sl)); row.update(sackmann_stats("l", sl, sw))
    old = pd.read_csv(f, low_memory=False) if os.path.exists(f) else pd.DataFrame()
    pd.concat([old, pd.DataFrame([row])], ignore_index=True).to_csv(f, index=False)


def sackmann_stats(p, s, opp):
    """Statistiques SportRadar -> colonnes Sackmann (w_ / l_)."""
    g = lambda d, k: int(d.get(k, 0) or 0)
    svpt = g(s, "service_points_won") + g(s, "service_points_lost")
    faced = g(opp, "total_breakpoints")
    return {f"{p}_ace": g(s, "aces"), f"{p}_df": g(s, "double_faults"), f"{p}_svpt": svpt,
            f"{p}_1stIn": g(s, "first_serve_successful"), f"{p}_1stWon": g(s, "first_serve_points_won"),
            f"{p}_2ndWon": g(s, "second_serve_points_won"),
            f"{p}_bpFaced": faced, f"{p}_bpSaved": faced - g(opp, "breakpoints_won")}


def main(path):
    rows = json.load(open(path))
    from engine import Model
    models = {}
    for r in rows:
        if r.get("vainqueur") and r.get("proba_a") is not None:
            t = r["tour"]
            if t not in models:
                models[t] = Model(t)
            md = models[t]
            a, b = md.resolve(r["joueur_a"]), md.resolve(r["joueur_b"])
            if a and b:
                r["id_vainqueur"], r["id_perdant"] = (a, b) if r["vainqueur"] == r["joueur_a"] else (b, a)
                append_live(r)
    log = pd.DataFrame([{k: r.get(k) for k in ["date", "id", "tour", "tournoi", "joueur_a", "joueur_b",
                                                "proba_a", "proba_modele", "ajustement", "vainqueur", "score"]} for r in rows])
    if os.path.exists(LOG):
        old = pd.read_csv(LOG)
        log = pd.concat([old[~old.id.isin(log.id)], log], ignore_index=True)
    log.to_csv(LOG, index=False)
    write_stats(log)


def write_stats(log):
    d = log[log.vainqueur.notna() & log.proba_a.notna()].copy()
    d["y"] = (d.vainqueur == d.joueur_a).astype(int)
    d["fav_ok"] = ((d.proba_a >= 0.5) & (d.y == 1)) | ((d.proba_a < 0.5) & (d.y == 0))
    d["brier"] = (d.proba_a - d.y) ** 2

    def summ(x):
        return {"matchs": int(len(x)), "reussis": int(x.fav_ok.sum()),
                "taux": round(float(x.fav_ok.mean()), 3) if len(x) else None,
                "brier": round(float(x.brier.mean()), 4) if len(x) else None}
    by_day = [{"date": k, **summ(g)} for k, g in d.groupby("date")]
    cal = []
    q = d.proba_a.where(d.proba_a >= 0.5, 1 - d.proba_a)
    for lo, hi in [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]:
        x = d[(q >= lo) & (q < hi)]
        if len(x):
            cal.append({"tranche": f"{int(lo*100)}–{min(int(hi*100),100)} %", "matchs": int(len(x)),
                        "annonce": round(float(q[x.index].mean()), 3), "reel": round(float(x.fav_ok.mean()), 3)})
    stats = {"global": summ(d), "atp": summ(d[d.tour == "atp"]), "wta": summ(d[d.tour == "wta"]),
             "par_jour": by_day, "calibration": cal}
    # le modèle seul (sans l'ajustement de l'agent), pour vérifier que les ajustements aident
    if "proba_modele" in d and d.proba_modele.notna().any():
        m = d[d.proba_modele.notna()].copy()
        ok = ((m.proba_modele >= 0.5) & (m.y == 1)) | ((m.proba_modele < 0.5) & (m.y == 0))
        adj = m[m.ajustement.fillna(0) != 0]
        okf = adj.fav_ok
        okm = ((adj.proba_modele >= 0.5) & (adj.y == 1)) | ((adj.proba_modele < 0.5) & (adj.y == 0))
        stats["modele_seul"] = {"matchs": int(len(m)), "taux": round(float(ok.mean()), 3),
                                "brier": round(float(((m.proba_modele - m.y) ** 2).mean()), 4)}
        stats["ajustements"] = {"matchs": int(len(adj)), "justes_avec": int(okf.sum()), "justes_sans": int(okm.sum()),
                                "brier_avec": round(float(((adj.proba_a - adj.y) ** 2).mean()), 4) if len(adj) else None,
                                "brier_sans": round(float(((adj.proba_modele - adj.y) ** 2).mean()), 4) if len(adj) else None}
    json.dump(stats, open(os.path.join(DATA, "stats.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(stats["global"]))


if __name__ == "__main__":
    main(sys.argv[1])
