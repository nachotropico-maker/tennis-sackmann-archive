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


def forme_tirs_buts(club, date, ligue):
    """(écart de tirs cadrés par match sur 5 matchs ou None, buts par match pour+contre, écart de tirs totaux ou None)"""
    sot, buts, tirs = None, None, None
    if os.path.exists(F_RES):
        r = pd.read_csv(F_RES)
        r = r[((r.dom == club) | (r.ext == club)) & (r.date < date)].sort_values("date")
        if "tc_dom" in r:
            t = r.dropna(subset=["tc_dom", "tc_ext"]).tail(5)
            if len(t) >= 3:
                sot = float(((t.tc_dom - t.tc_ext).where(t.dom == club, t.tc_ext - t.tc_dom)).mean())
        if "tt_dom" in r:
            t = r.dropna(subset=["tt_dom", "tt_ext"]).tail(5)
            if len(t) >= 3:
                tirs = float(((t.tt_dom - t.tt_ext).where(t.dom == club, t.tt_ext - t.tt_dom)).mean())
        if len(r) >= 5:
            buts = float((r.bd + r.be).tail(10).mean())
    if buts is None and ligue:
        cl = classement(ligue); row = cl[cl.club == club]
        if len(row) and row.iloc[0].gp:
            buts = float((row.iloc[0].gf + row.iloc[0].ga) / row.iloc[0].gp)
    return sot, (buts if buts is not None else 2.6), tirs


def pct(x):
    return f"{round(100 * x)} %"


def un(m):
    comp = m["comp"]
    lg = comp if comp in LIGUES else None
    cd, ed, est_d = elo_de(m["dom"], m.get("pays_dom"), lg)
    ce, ee, est_e = elo_de(m["ext"], m.get("pays_ext"), lg)
    sd, bd_, td = forme_tirs_buts(cd, m["date"], lg)
    se, be_, te_ = forme_tirs_buts(ce, m["date"], lg)
    sot = (sd - se) / 3 if sd is not None and se is not None else 0.0
    tirs = (td - te_) / 6 if td is not None and te_ is not None else 0.0
    p = proba(ed, ee, comp, neutre=m.get("neutre", False), sot=sot, buts=(bd_ + be_) / 2 - 2.6, tirs=tirs)
    et = etat().set_index("club")
    sept = lambda c, e: float(et.loc[c, "elo_septembre"]) if c in et.index else e
    issues = {"1": p["p1"], "N": p["pN"], "2": p["p2"]}
    prono = max(issues, key=issues.get)
    fav = cd if prono == "1" else ce if prono == "2" else None
    pmax = issues[prono]
    confiance = "Net favori" if pmax >= 0.6 else "Favori" if pmax >= 0.48 else "Léger avantage" if pmax >= 0.40 else "Très ouvert"
    # sous 45 %, le favori n'a raison que 4 fois sur 10 (test 2023-2025) : on donne aussi la double chance
    double = None
    if prono != "N" and pmax < 0.45:
        double = {"issue": "1N" if prono == "1" else "N2", "proba": round(pmax + p["pN"], 3)}
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
        st_, bu_ = (sd, bd_) if side == "dom" else (se, be_)
        if st_ is not None:
            fac[side]["tirs_cadres_5"] = round(st_, 1)
        tt_ = td if side == "dom" else te_
        if tt_ is not None:
            fac[side]["tirs_5"] = round(tt_, 1)
        fac[side]["buts_par_match"] = round(bu_, 2)
        j = jours_depuis(c, m["date"])
        if j is not None:
            fac[side]["jours_repos"] = j
            if j <= 3:
                raisons.append(f"{c} a joué il y a {j} jours : peu de récupération.")
    if sd is not None and se is not None and abs(sd - se) >= 2:
        meilleur = cd if sd > se else ce
        raisons.append(f"Forme aux tirs cadrés (5 derniers matchs) : {meilleur} domine nettement ({sd:+.1f} contre {se:+.1f} par match).")
    if p["pN"] >= 0.28 and abs(p["p1"] - p["p2"]) < 0.12:
        raisons.append(f"Match serré : le nul est une vraie option ({pct(p['pN'])}).")
    if est_d or est_e:
        raisons.append("Niveau d'un des clubs estimé (club hors des 9 championnats suivis) : pronostic moins fiable.")
    lecture = (f"{'Victoire de ' + fav if fav else 'Nul'} ({pct(pmax)}). Score le plus probable : {p['score_probable']}. "
               f"Plus de 2,5 buts : {pct(p['plus_2_5'])}.")
    # textes avec les noms affichés, pas les noms internes Elo
    nd, ne = m["dom"], m["ext"]
    def aff(t):
        return t.replace(cd, nd).replace(ce, ne) if cd != ce else t
    raisons = [aff(x) for x in raisons]
    lecture = aff(lecture)
    fav = nd if prono == "1" else ne if prono == "2" else None
    return {
        "id": m["id"], "date": m["date"], "heure": m.get("heure"), "comp": comp, "competition": NOM_COMP.get(comp, comp),
        "tour": m.get("tour"), "dom": cd, "ext": ce, "dom_affiche": m["dom"], "ext_affiche": m["ext"],
        "neutre": bool(m.get("neutre", False)), "p1": p["p1"], "pN": p["pN"], "p2": p["p2"],
        "pronostic": prono, "favori": fav, "double_chance": double,
        "p_modele": {"p1": p["p1"], "pN": p["pN"], "p2": p["p2"]}, "proba_favori": pmax, "confiance": confiance,
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
