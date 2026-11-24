"""Calcule meta/bilan à partir des documents matchs (export JSON d'un db_query sur la collection matchs).

python3 bilan.py matchs.json > bilan.json
Un match compte s'il a resultat.score et n'est pas annulé.
correct = l'issue (1/N/2) annoncée est la bonne. RPS = ranked probability score (0 = parfait).
"""
import json, sys
from collections import defaultdict


def issue(score):
    a, b = map(int, score.split("-"))
    return "1" if a > b else "N" if a == b else "2"


def rps(m, o):
    p = [m["p1"], m["pN"], m["p2"]]
    y = [1.0 if o == k else 0.0 for k in "1N2"]
    c1 = p[0] - y[0]; c2 = p[0] + p[1] - y[0] - y[1]
    return (c1 * c1 + c2 * c2) / 2


def bilan(ms):
    ms = [m for m in ms if m.get("resultat") and m["resultat"].get("score") and not m.get("annule")]
    g = {"matchs": 0, "reussis": 0, "scores_exacts": 0, "rps": 0.0}
    pc = defaultdict(lambda: {"matchs": 0, "reussis": 0})
    pj = defaultdict(lambda: {"matchs": 0, "reussis": 0})
    dc = {"matchs": 0, "reussis": 0}
    aj = {"matchs": 0, "rps_avec": 0.0, "rps_sans": 0.0}
    for m in ms:
        o = issue(m["resultat"]["score"]); ok = o == m["pronostic"]
        g["matchs"] += 1; g["reussis"] += ok; g["rps"] += rps(m, o)
        g["scores_exacts"] += m["resultat"]["score"] == m.get("score_probable")
        pc[m["comp"]]["matchs"] += 1; pc[m["comp"]]["reussis"] += ok
        pj[m["date"]]["matchs"] += 1; pj[m["date"]]["reussis"] += ok
        if m.get("double_chance"):
            dc["matchs"] += 1; dc["reussis"] += o in m["double_chance"]["issue"]
        if m.get("ajustement") and m.get("p_modele"):
            aj["matchs"] += 1; aj["rps_avec"] += rps(m, o); aj["rps_sans"] += rps(m["p_modele"], o)
    if g["matchs"]:
        g["taux"] = round(g["reussis"] / g["matchs"], 3); g["rps"] = round(g["rps"] / g["matchs"], 3)
    if dc["matchs"]:
        dc["taux"] = round(dc["reussis"] / dc["matchs"], 3)
    if aj["matchs"]:
        aj["rps_avec"] = round(aj["rps_avec"] / aj["matchs"], 3); aj["rps_sans"] = round(aj["rps_sans"] / aj["matchs"], 3)
    return {"global": g, "double_chance": dc, "ajustements": aj,
            "par_comp": [{"comp": k, **v, "taux": round(v["reussis"] / v["matchs"], 3)} for k, v in pc.items()],
            "par_jour": [{"date": k, **v} for k, v in sorted(pj.items())]}


if __name__ == "__main__":
    print(json.dumps(bilan(json.load(open(sys.argv[1]))), ensure_ascii=False))
