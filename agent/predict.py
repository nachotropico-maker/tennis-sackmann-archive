"""Calcule les prédictions du jour.

Usage : python agent/predict.py matchs_du_jour.json sortie.json
Entrée : liste de matchs {id, tour: atp|wta, tournoi, categorie, surface: Hard|Clay|Grass,
          conditions: indoor|outdoor, tour_tableau, heure, joueur_a, joueur_b}
Sortie : même liste enrichie de la probabilité, des facteurs et des raisons, + rankings et méta.
"""
import json, sys, datetime
from engine import Model

SURF_FR = {"Hard": "dur", "Clay": "terre battue", "Grass": "gazon"}


def confidence(p):
    q = max(p, 1 - p)
    if q < 0.55: return "Serré"
    if q < 0.65: return "Léger avantage"
    if q < 0.80: return "Favori net"
    return "Large favori"


def reasons(a, b, fa, fb, h2h, surf, tournoi, p, today):
    na, nb = a.split()[-1], b.split()[-1]
    r = []
    gap = fa["elo"] - fb["elo"]
    fav, und = (na, nb) if gap >= 0 else (nb, na)
    r.append(f"Écart de {abs(gap)} points d'Elo sur {SURF_FR[surf]} en faveur de {fav}, "
             f"soit {round(max(p, 1 - p) * 100)} % de chances selon le modèle.")
    for n, f in [(na, fa), (nb, fb)]:
        spec = f["elo"] - f["elo_global"]
        if spec >= 30:
            r.append(f"{n} est meilleur sur {SURF_FR[surf]} que son niveau moyen (+{spec} pts).")
        elif spec <= -30:
            r.append(f"{n} est moins à l'aise sur {SURF_FR[surf]} que son niveau moyen ({spec} pts).")
        if f["tendance_30j"] is not None and abs(f["tendance_30j"]) >= 40:
            sens = "en forte hausse" if f["tendance_30j"] > 0 else "en baisse"
            r.append(f"{n} est {sens} sur le dernier mois ({f['tendance_30j']:+d} pts d'Elo).")
        if f["matchs_7j"] >= 4:
            r.append(f"{n} a déjà joué {f['matchs_7j']} matchs en 7 jours : fatigue possible (non intégrée au calcul).")
        lt = f["dernier_tournoi"]
        recent = lt and (datetime.date(today // 10000, today // 100 % 100, today % 100)
                         - datetime.date(lt["date"] // 10000, lt["date"] // 100 % 100, lt["date"] % 100)).days <= 14
        if recent and lt["resultat"] and lt["tournoi"] != tournoi:
            r.append(f"{n} sort d'une {'victoire' if lt['resultat'] == 'titre' else 'finale'} à {lt['tournoi']} : "
                     f"risque de baisse de régime (non intégré au calcul).")
        if f["matchs_surface"] < 15:
            r.append(f"Peu de matchs de {n} sur cette surface dans la base ({f['matchs_surface']}) : estimation moins fiable.")
    wa, wb = [int(x) for x in h2h["total"].split("-")]
    if wa + wb >= 3:
        lead = na if wa > wb else nb if wb > wa else None
        r.append(f"Face-à-face {wa}-{wb}" + (f" en faveur de {lead}." if lead else ", à égalité."))
    fa10, fb10 = [int(f["forme_10"].split("-")[0]) for f in (fa, fb)]
    if abs(fa10 - fb10) >= 3:
        r.append(f"Forme récente : {na} {fa['forme_10']} contre {nb} {fb['forme_10']} sur les 10 derniers matchs.")
    return r


def main(inp, out):
    matches = json.load(open(inp))
    today = int(datetime.date.today().strftime("%Y%m%d"))
    models, res = {}, []
    for m in matches:
        t = m["tour"]
        if t not in models:
            models[t] = Model(t)
        md = models[t]
        a, b = md.resolve(m["joueur_a"]), md.resolve(m["joueur_b"])
        if a is None or b is None:
            m.update({"proba_a": None, "note": "Joueur absent de la base : pas de prédiction."})
            res.append(m); continue
        surf = m.get("surface", "Hard")
        p = md.prob(a, b, surf)
        fa, fb = md.player_facts(a, surf, today), md.player_facts(b, surf, today)
        h = md.h2h(a, b, surf)
        m.update({
            "joueur_a": md.names[a], "joueur_b": md.names[b],
            "proba_a": round(p, 3),
            "favori": md.names[a] if p >= 0.5 else md.names[b],
            "confiance": confidence(p),
            "facteurs_a": fa, "facteurs_b": fb, "h2h": h,
            "raisons": reasons(md.names[a], md.names[b], fa, fb, h, surf, m.get("tournoi", ""), p, today),
        })
        res.append(m)
    for t in ["atp", "wta"]:
        if t not in models:
            models[t] = Model(t)
    meta = {t: {"donnees_jusqu_a": models[t].data_through} for t in models}
    json.dump({"matchs": res, "meta": meta,
               "rankings": {t: models[t].rankings(150) for t in ["atp", "wta"]}},
              open(out, "w"), ensure_ascii=False, indent=1)
    print(f"{len(res)} matchs écrits dans {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
