"""Calcule les prédictions du jour.

Usage : python agent/predict.py matchs_du_jour.json sortie.json
Entrée : liste de matchs {id, tour: atp|wta, tournoi, categorie, surface: Hard|Clay|Grass,
          conditions: indoor|outdoor, tour_tableau, heure, joueur_a, joueur_b}
Sortie : même liste enrichie de la probabilité, des facteurs et des raisons, + rankings et méta.
"""
import json, sys, os, math, datetime
from engine import Model, DATA
from features import build, FEATURES, LABELS, tourney_country

ROUND_CODES = {"1er tour": "R1", "2e tour": "R2", "3e tour": "R3", "8e de finale": "R16", "huitième": "R16",
               "quart": "QF", "demi": "SF", "finale": "F", "groupes": "RR", "qualif": "Q1"}
LEVEL_CODES = {"grand chelem": "G", "masters": "M", "1000": "M", "finals": "F", "500": "A", "250": "A"}


def code_round(txt):
    t = str(txt).lower()
    if t.upper() in ("R128", "R64", "R32", "R16", "QF", "SF", "F", "RR"):
        return t.upper()
    for k, v in ROUND_CODES.items():
        if k in t:
            return v
    return "R2"


def code_level(cat):
    t = str(cat).lower()
    for k, v in LEVEL_CODES.items():
        if k in t:
            return v
    return "A"


def full_model(tour):
    poids = json.load(open(os.path.join(DATA, "poids.json")))[tour]["coef"]
    st, _ = build(tour, collect_from=99990101)
    return st, poids


def score_full(st, poids, a, b, m, day):
    rnd = m.get("code_tour") or code_round(m.get("tour_tableau", ""))
    lvl = m.get("niveau") or code_level(m.get("categorie", ""))
    bo = int(m.get("sets_gagnants_max", 0) or (5 if (lvl == "G" and m["tour"] == "atp") else 3))
    country = m.get("pays") or tourney_country(m.get("tournoi", ""))
    f, pa, pb, p_elo = st.features(a, b, m.get("surface", "Hard"), day, bo, rnd, lvl, country, m.get("tournoi", ""))
    # Les Challengers ne sont connus que jusqu'à fin mai 2026 : pour un joueur qui joue surtout en Challenger,
    # une « longue pause » peut n'être qu'un trou dans les données. On neutralise alors ce critère.
    for q, pid in ((pa, a), (pb, b)):
        if q["rust"] and st.ng.get(pid, 0) and st.nmain.get(pid, 0) / st.ng[pid] < 0.6:
            q["rust"] = 0.0
    f["rouille"] = pa["rust"] - pb["rust"]
    z = sum(poids[k] * f[k] for k in FEATURES)
    sig = lambda v: 1 / (1 + math.exp(-v))
    p = sig(z)
    impacts = []
    for k in FEATURES:
        if k == "elo":
            continue
        d = p - sig(z - poids[k] * f[k])
        if abs(d) >= 0.003:
            impacts.append({"critere": k, "libelle": LABELS[k], "pts": round(d * 100, 1)})
    impacts.sort(key=lambda x: -abs(x["pts"]))
    extra = lambda q: {"service_12m": round(q["spw"] * 100, 1), "retour_12m": round(q["rpw"] * 100, 1),
                       "minutes_7j": round(q["min7"] * 100), "sets_7j": q["s7"],
                       "tie_breaks_12m": round(q["tb"] * 100), "sets_decisifs_12m": round(q["dec"] * 100)}
    return p, p_elo, impacts, extra(pa), extra(pb)

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
    r.append(f"Écart de {abs(gap)} points d'Elo sur {SURF_FR[surf]} en faveur de {fav} : "
             f"{round(max(p, 1 - p) * 100)} % de chances avec l'Elo seul.")
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
            r.append(f"{n} a déjà joué {f['matchs_7j']} matchs en 7 jours.")
        lt = f["dernier_tournoi"]
        recent = lt and (datetime.date(today // 10000, today // 100 % 100, today % 100)
                         - datetime.date(lt["date"] // 10000, lt["date"] // 100 % 100, lt["date"] % 100)).days <= 14
        if recent and lt["resultat"] and lt["tournoi"] != tournoi:
            r.append(f"{n} sort d'une {'victoire' if lt['resultat'] == 'titre' else 'finale'} à {lt['tournoi']} : "
                     f"risque de baisse de régime.")
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
    day = datetime.date.today().toordinal()
    models, res, fulls = {}, [], {}
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
        if t not in fulls:
            fulls[t] = full_model(t)
        st, poids = fulls[t]
        p, p_elo, impacts, xa, xb = score_full(st, poids, a, b, m, day)
        fa, fb = md.player_facts(a, surf, today), md.player_facts(b, surf, today)
        fa.update(xa); fb.update(xb)
        h = md.h2h(a, b, surf)
        rs = reasons(md.names[a], md.names[b], fa, fb, h, surf, m.get("tournoi", ""), p_elo, today)
        na, nb = md.names[a].split()[-1], md.names[b].split()[-1]
        for x in impacts[:4]:
            qui = na if x["pts"] > 0 else nb
            val = f"{abs(x['pts']):.1f}".replace(".", ",")
            rs.append(f"{x['libelle']} : {val} pt{'s' if abs(x['pts']) >= 2 else ''} en faveur de {qui}.")
        m.update({
            "joueur_a": md.names[a], "joueur_b": md.names[b],
            "proba_elo": round(p_elo, 3), "proba_modele": round(p, 3),
            "ajustement": 0, "ajustement_raison": None,
            "proba_a": round(p, 3),
            "favori": md.names[a] if p >= 0.5 else md.names[b],
            "confiance": confidence(p),
            "facteurs_a": fa, "facteurs_b": fb, "h2h": h, "impacts": impacts,
            "raisons": rs,
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
