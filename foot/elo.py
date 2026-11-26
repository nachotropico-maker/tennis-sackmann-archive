"""Elo des clubs (échelle ClubElo, commune à toute l'Europe).

init()   : état au 22/11/2026 = snapshot ClubElo provisoire du 01/09/2026
           + ajustement par les classements ESPN (matchs joués depuis le 1er septembre)
maj(...) : mise à jour match par match (résultats du jour), écrit data/elo_courant.csv
"""
import json, math, os, sys
import pandas as pd
from noms import Resolveur, PAYS

ICI = os.path.dirname(os.path.abspath(__file__))
F_ETAT = os.path.join(ICI, "data/elo_courant.csv")
F_RES = os.path.join(ICI, "data/resultats_live.csv")
HFA = 65.0
K = 20.0
# niveau par défaut d'un club absent des données (coupes d'Europe), par pays
DEFAUT_PAYS = {"SCO": 1600, "CZE": 1620, "CRO": 1580, "SRB": 1580, "SUI": 1590, "UKR": 1600, "AZE": 1540,
               "CYP": 1520, "ISR": 1520, "GRE": 1600, "AUT": 1600, "DEN": 1600, "NOR": 1600, "SWE": 1540,
               "POL": 1540, "HUN": 1500, "SVK": 1480, "SLO": 1480, "BUL": 1500, "ROU": 1520, "KAZ": 1460,
               # ajout 26/11/2026 : petites nations de la Ligue Conférence, et clubs portugais hors Liga Portugal (2e division)
               "SVN": 1480, "ROM": 1520, "BIH": 1450, "GEO": 1450, "ARM": 1430, "ALB": 1430, "FIN": 1430, "LTU": 1420,
               "LVA": 1420, "AND": 1380, "GIB": 1380, "POR": 1400}


def _snapshot(date="2026-09-01"):
    e = pd.read_csv(os.path.join(ICI, "data/elo_snapshots.csv"))
    return e[e.date == date].drop_duplicates("club", keep="last")


def _equipes_saison():
    m = pd.read_csv(os.path.join(ICI, "data/matchs_hist.csv"), parse_dates=["MatchDate"])
    s = m[m.MatchDate >= "2026-07-01"]
    eq = {}
    for _, r in s.iterrows():
        eq.setdefault(r.Division, set()).update([r.HomeTeam, r.AwayTeam])
    return s, {k: sorted(v) for k, v in eq.items()}


def resolveur():
    snap = _snapshot()
    cp = {}
    for _, r in snap.iterrows():
        cp.setdefault(r.country, []).append(r.club)
    if os.path.exists(F_ETAT):
        et = pd.read_csv(F_ETAT)
        for _, r in et.iterrows():
            if r.club not in cp.get(r.pays, []):
                cp.setdefault(r.pays, []).append(r.club)
    # les noms utilisés dans les matchs de la saison passent en premier
    _, eq = _equipes_saison()
    for lg, l in eq.items():
        p = PAYS[lg]
        cp[p] = l + [c for c in cp.get(p, []) if c not in l]
    return Resolveur(cp)


def exp_score(ra, rb, hfa=HFA):
    return 1 / (1 + 10 ** (-(ra + hfa - rb) / 400))


def mult_ecart(gd):
    gd = abs(gd)
    return 1.0 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8


def init(f_classements):
    snap = _snapshot()
    elo0 = dict(zip(snap.club, snap.elo))
    s, eq = _equipes_saison()
    res = resolveur()
    pre = s[s.MatchDate < "2026-09-01"]
    cl = pd.read_csv(f_classements)
    lignes, inconnus = [], []
    for lg, g in cl.groupby("ligue"):
        pool = eq.get(lg, [])
        rows = []
        for _, r in g.iterrows():
            nom = res(r.team, PAYS[lg])
            if nom is None or nom not in elo0:
                # promu absent du snapshot : niveau d'un promu (bas du classement Elo de la ligue)
                inconnus.append((lg, r.team, nom))
                nom = nom or r.team
                elo0.setdefault(nom, sorted(elo0[c] for c in pool if c in elo0)[2] if pool else 1550)
            h = pre[pre.HomeTeam == nom]; a = pre[pre.AwayTeam == nom]
            pw = (h.FTResult == "H").sum() + (a.FTResult == "A").sum()
            pdd = (h.FTResult == "D").sum() + (a.FTResult == "D").sum()
            pgp = len(h) + len(a)
            pgf = h.FTHome.sum() + a.FTAway.sum(); pga = h.FTAway.sum() + a.FTHome.sum()
            rows.append(dict(club=nom, espn=r.team, n=max(0, r.gp - pgp), w=r.w - pw, d=r.d - pdd,
                             gd=(r.gf - r.ga) - (pgf - pga)))
        R = {x["club"]: float(elo0[x["club"]]) for x in rows}
        base = dict(R)
        for _ in range(4):  # quelques itérations : les adversaires bougent aussi
            moy = sum(R.values()) / len(R)
            new = {}
            for x in rows:
                n = x["n"]
                if n <= 0:
                    new[x["club"]] = base[x["club"]]; continue
                e = exp_score(base[x["club"]], moy, hfa=0)
                S = x["w"] + 0.5 * x["d"]
                # écart de buts attendu contre un adversaire moyen (~0,35 but par 100 pts d'Elo)
                egd = n * 0.0035 * (base[x["club"]] - moy)
                new[x["club"]] = base[x["club"]] + K * 1.2 * (S - n * e) + 3.0 * (x["gd"] - egd)
            R = new
        for x in rows:
            lignes.append(dict(club=x["club"], pays=PAYS[lg], ligue=lg, elo=round(R[x["club"]], 1),
                               elo_septembre=round(base[x["club"]], 1), nom_espn=x["espn"], maj="2026-11-22"))
    et = pd.DataFrame(lignes).sort_values("elo", ascending=False)
    # autres clubs européens du snapshot (adversaires en coupe)
    autres = snap[~snap.club.isin(et.club)]
    autres = pd.DataFrame(dict(club=autres.club, pays=autres.country, ligue="", elo=autres.elo,
                               elo_septembre=autres.elo, nom_espn="", maj="2026-09-01"))
    pd.concat([et, autres]).to_csv(F_ETAT, index=False)
    return et, inconnus


def etat():
    return pd.read_csv(F_ETAT)


def elo_de(nom, pays=None, ligue=None):
    """(nom Elo, elo, estimé?)"""
    et = etat()
    res = resolveur()
    p = pays or (PAYS.get(ligue) if ligue else None)
    c = res(nom, p)
    if c is not None and c in set(et.club):
        return c, float(et.loc[et.club == c, "elo"].iloc[0]), False
    return nom, float(DEFAUT_PAYS.get(p, 1550)), True


def maj(date, comp, dom, ext, bd, be, pays_dom=None, pays_ext=None, neutre=False, tc_dom=None, tc_ext=None, tt_dom=None, tt_ext=None):
    """Applique un résultat. Écrit l'état et ajoute la ligne à resultats_live.csv (sans doublon)."""
    et = etat()
    cd, rd, est_d = elo_de(dom, pays_dom, comp if comp in PAYS else None)
    ce, re_, est_e = elo_de(ext, pays_ext, comp if comp in PAYS else None)
    if os.path.exists(F_RES):
        r0 = pd.read_csv(F_RES)
        if ((r0.date == date) & (r0.dom == cd) & (r0.ext == ce)).any():
            return None
    e = exp_score(rd, re_, 0 if neutre else HFA)
    S = 1.0 if bd > be else 0.5 if bd == be else 0.0
    dl = K * mult_ecart(bd - be) * (S - e)
    for c, r, est, p, sgn in ((cd, rd, est_d, pays_dom, 1), (ce, re_, est_e, pays_ext, -1)):
        if c in set(et.club):
            et.loc[et.club == c, "elo"] = round(r + sgn * dl, 1)
            et.loc[et.club == c, "maj"] = date
        else:
            et = pd.concat([et, pd.DataFrame([dict(club=c, pays=p or "", ligue="", elo=round(r + sgn * dl, 1),
                                                   elo_septembre=r, nom_espn="", maj=date)])])
    et.to_csv(F_ETAT, index=False)
    ligne = pd.DataFrame([dict(date=date, comp=comp, dom=cd, ext=ce, bd=bd, be=be, elo_dom=rd, elo_ext=re_,
                               delta=round(dl, 1), tc_dom=tc_dom, tc_ext=tc_ext, tt_dom=tt_dom, tt_ext=tt_ext)])
    if os.path.exists(F_RES):
        ligne = pd.concat([pd.read_csv(F_RES), ligne])
    ligne.to_csv(F_RES, index=False)
    return dl


if __name__ == "__main__":
    et, inc = init(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, "data/classements_2026-11-22.csv"))
    print("non trouvés :", inc)
    for lg, g in et.groupby("ligue"):
        print(lg, " | ".join(f"{r.club} {r.elo:.0f} ({r.elo - r.elo_septembre:+.0f})" for r in g.head(6).itertuples()))
