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
    df = pd.DataFrame([row])
    df.to_csv(f, mode="a", header=not os.path.exists(f), index=False)


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
                                                "proba_a", "vainqueur", "score"]} for r in rows])
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
    json.dump(stats, open(os.path.join(DATA, "stats.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(stats["global"]))


if __name__ == "__main__":
    main(sys.argv[1])
