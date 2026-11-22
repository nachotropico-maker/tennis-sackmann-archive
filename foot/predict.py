"""Pronostics du jour.

python3 predict.py entree.json sortie.json
entree : liste de matchs {id, date, heure, comp (E0, SP1, I1, F1, D1, T1, N1, P1, B1, UCL, UEL, UECL),
          tour (ex. « 13e journée », « Phase de ligue – J5 »), dom, ext, pays_dom?, pays_ext?, neutre?,
          repere_sportradar? {p1,pN,p2}}
sortie : {matchs: [...], meta: {...}}
"""
import json, os, sys
import pandas as pd
from modele import proba, LIGUES, COUPES, _mod
from elo import elo_de, etat, F_RES
from noms import PAYS

ICI = os.path.dirname(os.path.abspath(__file__))
NOM_COMP = {**LIGUES, **COUPES}


def classement(ligue):
    """Classement courant (base ESPN du 22/11 + résultats ajoutés depuis)."""
    cl = pd.read_csv(os.path.join(ICI, "data/classements_2026-11-22.csv"))
    cl = cl[cl.ligue == ligue].copy()
    et = etat()
    m = dict(zip(et.nom_espn.fillna(""), et.club))
    cl["club"] = cl.team.map(lambda t: m.get(t, t))
    if os.path.exists(F_RES):
        r = pd.read_csv(F_RES)
        r = r[(r.comp == ligue) & (r.date > "2026-11-22")]
        for x in r.itertuples():
            for c, gf, ga in ((x.dom, x.bd, x.be), (x.ext, x.be, x.bd)):
                i = cl.index[cl.club == c]
                if len(i):
                    cl.loc[i, "gp"] += 1; cl.loc[i, "gf"] += gf; cl.loc[i, "ga"] += ga
                    cl.loc[i, "w" if gf > ga else "d" if gf == ga else "l"] += 1
                    cl.loc[i, "pts"] += 3 if gf > ga else 1 if gf == ga else 0
    cl = cl.sort_values(["pts", "gf"], ascending=False).reset_index(drop=True)
    cl["rang"] = cl.index + 1
    return cl


def derniers(club, n=5):
    if not os.path.exists(F_RES):
        return []
    r = pd.read_csv(F_RES)
    r = r[(r.dom == club) | (r.ext == club)].sort_values("date").tail(n)
    out = []
    for x in r.itertuples():
        dom = x.dom == club
        gf, ga = (x.bd, x.be) if dom else (x.be, x.bd)
        out.append({"date": x.date, "comp": x.comp, "adv": x.ext if dom else x.dom, "lieu": "dom" if dom else "ext",
                    "score": f"{gf}-{ga}", "res": "V" if gf > ga else "N" if gf == ga else "D"})
    return out


def jours_depuis(club, date):
    if not os.path.exists(F_RES):
        return None
    r = pd.read_csv(F_RES)
    r = r[((r.dom == club) | (r.ext == club)) & (r.date < date)]
    if not len(r):
        return None
    return (pd.Timestamp(date) - pd.Timestamp(r.date.max())).days


def pct(x):
    return f"{round(100 * x)} %"


def un(m):
    comp = m["comp"]
    lg = comp if comp in LIGUES else None
    cd, ed, est_d = elo_de(m["dom"], m.get("pays_dom"), lg)
    ce, ee, est_e = elo_de(m["ext"], m.get("pays_ext"), lg)
    p = proba(ed, ee, comp, neutre=m.get("neutre", False))
    et = etat().set_index("club")
    sept = lambda c, e: float(et.loc[c, "elo_septembre"]) if c in et.index else e
    issues = {"1": p["p1"], "N": p["pN"], "2": p["p2"]}
    prono = max(issues, key=issues.get)
    fav = cd if prono == "1" else ce if prono == "2" else None
    pmax = issues[prono]
    confiance = "Net favori" if pmax >= 0.6 else "Favori" if pmax >= 0.48 else "Léger avantage" if pmax >= 0.40 else "Très ouvert"
    raisons = []
    diff = ed - ee
    raisons.append(f"Écart d'Elo : {cd} {ed:.0f}, {ce} {ee:.0f} ({abs(diff):.0f} pts en faveur de {cd if diff >= 0 else ce}).")
    if not m.get("neutre"):
        raisons.append("Avantage du terrain pour " + cd + " (environ +65 pts d'Elo, soit 7 à 8 points de % en plus).")
    for c, e in ((cd, ed), (ce, ee)):
        d = e - sept(c, e)
        if abs(d) >= 25:
            raisons.append(f"{c} {'en forme' if d > 0 else 'en baisse'} depuis septembre ({d:+.0f} pts d'Elo).")
    fac = {}
    if lg:
        cl = classement(lg)
        for side, c in (("dom", cd), ("ext", ce)):
            row = cl[cl.club == c]
            if len(row):
                r = row.iloc[0]
                fac[side] = {"rang": int(r.rang), "pts": int(r.pts), "j": int(r.gp), "v": int(r.w), "n": int(r.d),
                             "d": int(r.l), "bp": int(r.gf), "bc": int(r.ga)}
        if "dom" in fac and "ext" in fac:
            a, b = fac["dom"], fac["ext"]
            raisons.append(f"Classement : {cd} {a['rang']}e ({a['pts']} pts en {a['j']} matchs), "
                           f"{ce} {b['rang']}e ({b['pts']} pts en {b['j']} matchs).")
    for side, c in (("dom", cd), ("ext", ce)):
        fac.setdefault(side, {})
        fac[side]["elo"] = round(ed if side == "dom" else ee)
        fac[side]["elo_septembre"] = round(sept(c, ed if side == "dom" else ee))
        fac[side]["derniers"] = derniers(c)
        j = jours_depuis(c, m["date"])
        if j is not None:
            fac[side]["jours_repos"] = j
            if j <= 3:
                raisons.append(f"{c} a joué il y a {j} jours : peu de récupération.")
    if p["pN"] >= 0.28 and abs(p["p1"] - p["p2"]) < 0.12:
        raisons.append(f"Match serré : le nul est une vraie option ({pct(p['pN'])}).")
    if est_d or est_e:
        raisons.append("Niveau d'un des clubs estimé (club hors des 9 championnats suivis) : pronostic moins fiable.")
    lecture = (f"{'Victoire de ' + fav if fav else 'Nul'} ({pct(pmax)}). Score le plus probable : {p['score_probable']}. "
               f"Plus de 2,5 buts : {pct(p['plus_2_5'])}.")
    return {
        "id": m["id"], "date": m["date"], "heure": m.get("heure"), "comp": comp, "competition": NOM_COMP.get(comp, comp),
        "tour": m.get("tour"), "dom": cd, "ext": ce, "dom_affiche": m["dom"], "ext_affiche": m["ext"],
        "neutre": bool(m.get("neutre", False)), "p1": p["p1"], "pN": p["pN"], "p2": p["p2"],
        "pronostic": prono, "favori": fav, "proba_favori": pmax, "confiance": confiance,
        "score_probable": p["score_probable"], "buts_dom": p["buts_dom"], "buts_ext": p["buts_ext"],
        "plus_2_5": p["plus_2_5"], "facteurs": fac, "raisons": raisons, "lecture": lecture,
        "repere_sportradar": m.get("repere_sportradar"), "contexte": m.get("contexte", []),
        "ajustement": 0, "resultat": None, "correct": None,
    }


def main(inp, out):
    ms = json.load(open(inp))
    res = [un(m) for m in ms]
    M = _mod()
    json.dump({"matchs": res, "meta": {"test": M["test"]}}, open(out, "w"), ensure_ascii=False, indent=1)
    for r in res:
        print(f"{r['heure'] or ''} {r['competition']:<22} {r['dom']:>18} – {r['ext']:<18} "
              f"1 {pct(r['p1'])} N {pct(r['pN'])} 2 {pct(r['p2'])}  → {r['pronostic']} {r['score_probable']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
