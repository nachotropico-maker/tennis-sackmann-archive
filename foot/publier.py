"""Prépare les écritures pour la base de la page Agent Foot.

python3 publier.py sortie_predict.json date "résumé du jour" > ops.json
Produit des listes d'opérations db_write (paquets de 40 max) :
  matchs/{id}, jours/{date}, meta/modele, classements/elo
Le bilan (meta/bilan) est calculé par bilan.py.
"""
import json, os, sys
import pandas as pd
from elo import etat, F_RES

ICI = os.path.dirname(os.path.abspath(__file__))


def ops(sortie, date, resume):
    d = json.load(open(sortie))
    out = []
    for m in d["matchs"]:
        out.append({"op": "set", "path": f"matchs/{m['id']}", "data": m})
    out.append({"op": "set", "path": f"jours/{date}", "data": {"date": date, "resume": resume, "nb": len(d["matchs"])}})
    dern = "2026-11-22"
    if os.path.exists(F_RES):
        r = pd.read_csv(F_RES)
        if len(r):
            dern = max(dern, r.date.max())
    j, mth, a = dern.split("-")[2], int(dern.split("-")[1]), dern.split("-")[0]
    mois = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    out.append({"op": "set", "path": "meta/modele", "data": {
        "donnees_jusqu_a": f"{int(j)} {mois[mth - 1]} {a}", "mise_a_jour": date,
        "prochaine": "chaque matin, 8 h 50", "test": d["meta"]["test"], "version": "foot-1"}})
    et = etat()
    et = et[et.ligue.notna() & (et.ligue != "")]
    lignes = [{"nom": r.nom_espn if isinstance(r.nom_espn, str) and r.nom_espn else r.club,
               "ligue": r.ligue, "elo": round(float(r.elo)), "evol": round(float(r.elo - r.elo_septembre))}
              for r in et.itertuples()]
    out.append({"op": "set", "path": "classements/elo", "data": {"lignes": lignes}})
    return [out[i:i + 40] for i in range(0, len(out), 40)]


if __name__ == "__main__":
    print(json.dumps(ops(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""), ensure_ascii=False))
