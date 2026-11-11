"""Importe un export « saison » (une ligne par match, circuit principal + Challengers, avec statistiques)
au format de l'agent : agent/data/{tour}_saison.csv. Utilisé à partir du 8 juin 2026, après la fin de l'archive Sackmann.

Usage : python agent/import_saison.py atp chemin/2026-atp-season.csv
        python agent/import_saison.py wta chemin/2026-wta-season.csv
Peut être relancé avec un fichier plus récent : il remplace l'import précédent.
"""
import os, re, sys
import numpy as np
import pandas as pd
from engine import ROOT, DATA, TD_FROM, norm

GC = ["australian open", "roland garros", "french open", "wimbledon", "us open"]
ATP_M = ["indian wells", "miami", "monte carlo", "madrid", "rome", "canada", "toronto", "montreal", "cincinnati",
         "shanghai", "paris"]
WTA_1000 = ["doha", "dubai", "indian wells", "miami", "madrid", "rome", "canada", "toronto", "montreal",
            "cincinnati", "beijing", "wuhan"]
ROUNDS = {"1/64-finals": "R128", "1/32-finals": "R64", "1/16-finals": "R32", "1/8-finals": "R16",
          "Quarter-finals": "QF", "Semi-finals": "SF", "Final": "F", "Qualifier": "Q1"}


def player_index(tour):
    """Index « Nom I. » -> identifiant Sackmann, sur les joueurs actifs depuis 2018 (tous niveaux)."""
    fr = []
    for y in range(2018, 2027):
        for f in [f"{tour}_matches_{y}.csv",
                  f"{tour}_matches_qual_chall_{y}.csv" if tour == "atp" else f"{tour}_matches_qual_itf_{y}.csv"]:
            p = os.path.join(ROOT, tour, f)
            if os.path.exists(p):
                fr.append(pd.read_csv(p, low_memory=False, usecols=["winner_id", "winner_name", "loser_id", "loser_name", "tourney_date"]))
    m = pd.concat(fr)
    ppl = pd.concat([m[["winner_id", "winner_name", "tourney_date"]].set_axis(["id", "name", "d"], axis=1),
                     m[["loser_id", "loser_name", "tourney_date"]].set_axis(["id", "name", "d"], axis=1)])
    ppl = ppl.groupby(["id", "name"]).d.agg(["max", "count"]).reset_index()
    idx = {}
    for r in ppl.itertuples():
        toks = str(r.name).replace("-", " ").split()
        for k in range(1, len(toks)):
            key = norm(" ".join(toks[k:])).replace(" ", "") + "|" + norm(toks[0])[:1]
            if key not in idx or (r.max, r.count) > (idx[key][2], idx[key][3]):
                idx[key] = (str(r.id), r.name, r.max, r.count)
    return idx


def key_of(short):
    s = str(short).strip()
    parts = s.rsplit(" ", 1)
    if len(parts) == 2 and "." in parts[1]:
        last, ini = parts
    else:
        last, ini = s, ""
    # « Sik M. E. » -> nom « Sik », initiale M
    m = re.match(r"^(.*?)\s+([A-Z][a-z]*\.)(\s+[A-Z][a-z]*\.)*$", s)
    if m:
        last, ini = m.group(1), m.group(2)
    return norm(last).replace(" ", "") + "|" + norm(ini)[:1]


ALIAS = {"Mpetshi G.": "Giovanni Mpetshi Perricard", "Barrios M.": "Tomas Barrios Vera",
         "Tirante T. A.": "Thiago Agustin Tirante", "Osorio M.": "Camila Osorio", "Bu Y.": "Bu Yunchaokete",
         "Williams S.": "Venus Williams"}


def convert(tour, path):
    d = pd.read_csv(path, low_memory=False)
    d = d[d.status_extra.isin(["FINISHED", "RETIRED"]) & d.winner_code.isin([1, 2])].copy()
    d["date"] = pd.to_datetime(d.date_timestamp, unit="s").dt.strftime("%Y%m%d").astype(int)
    d = d[d.date >= TD_FROM]
    idx = player_index(tour)
    byname = {}
    for v in idx.values():
        byname[v[1]] = v[0]
    miss = {}

    def resolve(short, ext_id):
        if short in ALIAS and ALIAS[short] in byname:
            return byname[ALIAS[short]], ALIAS[short]
        k = key_of(short)
        if k in idx:
            return idx[k][0], idx[k][1]
        miss[short] = miss.get(short, 0) + 1
        return f"ext_{ext_id}", short

    rows = []
    for r in d.itertuples(index=False):
        t = str(r.tournament)
        qual = "Qualification" in t
        indoor = "(indoor)" in t
        main = "Tour" in str(r.tour_type_human) and not qual
        name = re.sub(r"\s*-\s*Qualification.*$", "", t)
        name = re.sub(r"\s*\(indoor\)", "", name)
        name = re.sub(r"\s+(ATP|WTA)$", "", name).strip()
        n = norm(name)
        if not main:
            level = "C" if "Chall" in t else "Q"
        elif any(g in n for g in GC):
            level = "G"
        elif "finals" in n:
            level = "F"
        elif "davis" in n or "billie jean" in n or "united cup" in n:
            level = "D"
        elif tour == "atp" and any(x in n for x in ATP_M):
            level = "M"
        elif tour == "wta" and any(x in n for x in WTA_1000):
            level = "PM"
        else:
            level = "A" if tour == "atp" else "I"
        rnd = "Q1" if qual else ROUNDS.get(r.round, "RR")
        bo = 5 if (tour == "atp" and level == "G" and not qual) else 3
        hw = r.winner_code == 1
        wn, ln_ = (r.home_name, r.away_name) if hw else (r.away_name, r.home_name)
        wid, lid = (r.home_id, r.away_id) if hw else (r.away_id, r.home_id)
        sets, games = [], 0
        for i in range(1, 6):
            a, b = getattr(r, f"home_set_{i}_score"), getattr(r, f"away_set_{i}_score")
            if a == a and b == b:
                a, b = int(a), int(b)
                games += a + b
                sets.append(f"{a}-{b}" if hw else f"{b}-{a}")
        score = " ".join(sets) + (" RET" if r.status_extra == "RETIRED" else "")
        # statistiques : on dispose de pourcentages ; on estime le nombre de points de service à partir des jeux
        svpt = round(games / 2 * 6.3) if games else np.nan
        pre_w, pre_l = ("home", "away") if hw else ("away", "home")
        spw_w, spw_l = getattr(r, f"{pre_w}_service_points_won_perc"), getattr(r, f"{pre_l}_service_points_won_perc")
        ace_w, ace_l = getattr(r, f"{pre_w}_aces"), getattr(r, f"{pre_l}_aces")
        ok = svpt == svpt and spw_w == spw_w and spw_l == spw_l
        W = resolve(wn, wid); L = resolve(ln_, lid)
        rows.append({
            "tourney_id": f"saison-{n}", "tourney_name": name, "surface": str(r.surface).capitalize(),
            "court": "Indoor" if indoor else "Outdoor", "tourney_level": level, "tourney_date": r.date,
            "match_num": 0, "winner_id": W[0], "winner_name": W[1], "loser_id": L[0], "loser_name": L[1],
            "score": score, "best_of": bo, "round": rnd, "minutes": np.nan, "main": main,
            "w_ace": ace_w if ok else np.nan, "l_ace": ace_l if ok else np.nan,
            "w_svpt": svpt if ok else np.nan, "l_svpt": svpt if ok else np.nan,
            "w_1stWon": round(spw_w / 100 * svpt) if ok else np.nan, "w_2ndWon": 0 if ok else np.nan,
            "l_1stWon": round(spw_l / 100 * svpt) if ok else np.nan, "l_2ndWon": 0 if ok else np.nan,
        })
    out = pd.DataFrame(rows)
    out = out[out.surface.isin(["Hard", "Clay", "Grass"])]
    dest = os.path.join(DATA, f"{tour}_saison.csv")
    out.to_csv(dest, index=False)
    tot = 2 * len(out)
    print(f"{tour.upper()} : {len(out)} matchs importés ({int(out.main.sum())} circuit principal), "
          f"du {out.tourney_date.min()} au {out.tourney_date.max()} ; joueurs non reconnus : {sum(miss.values())} apparitions "
          f"({sum(miss.values()) / tot:.1%}), dont circuit principal : "
          f"{sum(v for k, v in miss.items() if k in set(out[out.main].winner_name) | set(out[out.main].loser_name))}")
    return out


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
