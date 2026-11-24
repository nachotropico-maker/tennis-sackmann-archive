"""Récupération quotidienne API-Football (lancée par la GitHub Action, clé dans le secret API_FOOTBALL_KEY).

Budget offre gratuite : 100 requêtes par jour (95 utilisées au maximum) :
  1 × fixtures?date=hier        -> matchs d'hier des 12 compétitions
  n × fixtures/statistics       -> tirs, xG si dispo (tous les matchs)
  puis compositions et joueurs par match, tant qu'il reste de la marge
  1 × fixtures?date=aujourd'hui -> programme du jour
  1 × injuries?date=aujourd'hui -> blessés et suspendus annoncés
Écrit foot/data/apifootball/AAAA-MM-JJ.json (données d'hier + programme et absents du jour) et journal.csv.
"""
import datetime as dt, json, os, sys, time, urllib.error, urllib.parse, urllib.request

KEY = os.environ.get("API_FOOTBALL_KEY", "")
BASE = "https://v3.football.api-sports.io/"
LIGUES = {39: "E0", 140: "SP1", 135: "I1", 61: "F1", 78: "D1", 203: "T1", 88: "N1", 94: "P1", 144: "B1",
          2: "UCL", 3: "UEL", 848: "UECL"}
ICI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ICI, "..", "data", "apifootball")
appels = []
LIMITE = 95  # sur 100 gratuits


def get(path, **params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    for essai in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                reste = r.headers.get("x-ratelimit-requests-remaining")
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and essai < 3:      # trop de requêtes à la minute : on attend
                time.sleep(65)
                continue
            appels.append({"path": path, "params": params, "reste_jour": None, "erreurs": f"HTTP {e.code}"})
            return []
    appels.append({"path": path, "params": params, "reste_jour": reste, "erreurs": d.get("errors")})
    time.sleep(7)  # l'offre gratuite limite le nombre de requêtes par minute
    return d.get("response", [])


def stat(team_stats, name):
    for s in team_stats.get("statistics", []):
        if s.get("type", "").lower() == name.lower():
            v = s.get("value")
            if isinstance(v, str) and v.endswith("%"):
                v = float(v[:-1])
            try:
                return float(v) if v is not None else None
            except ValueError:
                return None
    return None


def resume(f):
    fx, tm, gl, lg = f["fixture"], f["teams"], f["goals"], f["league"]
    out = {"id": fx["id"], "date": fx["date"], "statut": fx["status"]["short"], "comp": LIGUES.get(lg["id"]),
           "tour": lg.get("round"), "dom": tm["home"]["name"], "ext": tm["away"]["name"],
           "bd": gl["home"], "be": gl["away"]}
    st = {s["team"]["id"]: s for s in f.get("statistics", [])}
    for side in ("home", "away"):
        k = "dom" if side == "home" else "ext"
        s = st.get(tm[side]["id"])
        if s:
            out[f"tc_{k}"] = stat(s, "Shots on Goal")
            out[f"tt_{k}"] = stat(s, "Total Shots")
            out[f"tirs_surface_{k}"] = stat(s, "Shots insidebox")
            out[f"tirs_hors_surface_{k}"] = stat(s, "Shots outsidebox")
            out[f"possession_{k}"] = stat(s, "Ball Possession")
            out[f"xg_{k}"] = stat(s, "expected_goals")
            out[f"buts_evites_{k}"] = stat(s, "goals_prevented")
            out[f"rouges_{k}"] = stat(s, "Red Cards")
    for lu in f.get("lineups", []):
        k = "dom" if lu["team"]["id"] == tm["home"]["id"] else "ext"
        out[f"schema_{k}"] = lu.get("formation")
        out[f"titulaires_{k}"] = [p["player"]["name"] for p in lu.get("startXI", [])]
        out[f"entraineur_{k}"] = (lu.get("coach") or {}).get("name")
    joueurs = []
    for t in f.get("players", []):
        k = "dom" if t["team"]["id"] == tm["home"]["id"] else "ext"
        for p in t.get("players", []):
            s = (p.get("statistics") or [{}])[0]
            g = s.get("games") or {}
            if g.get("minutes"):
                joueurs.append({"equipe": k, "nom": p["player"]["name"], "poste": g.get("position"),
                                "minutes": g.get("minutes"), "note": g.get("rating"),
                                "buts": (s.get("goals") or {}).get("total"), "passes_d": (s.get("goals") or {}).get("assists"),
                                "duels_gagnes": (s.get("duels") or {}).get("won"), "passes_cles": (s.get("passes") or {}).get("key")})
    if joueurs:
        out["joueurs"] = joueurs
    return out


def main():
    if not KEY:
        sys.exit("API_FOOTBALL_KEY manquant")
    auj = dt.datetime.now(dt.timezone.utc).date()
    hier = auj - dt.timedelta(days=1)
    os.makedirs(OUT, exist_ok=True)
    res = {"genere": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    # matchs d'hier terminés
    fh = [f for f in get("fixtures", date=hier.isoformat(), timezone="Europe/Paris") if f["league"]["id"] in LIGUES]
    finis = [f for f in fh if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN")]
    # l'offre gratuite n'accepte pas fixtures?ids= : un appel par match et par type de données.
    # Priorité : statistiques (tous les matchs), puis compositions, puis joueurs, tant qu'il reste de la marge.
    for f in finis:
        f["statistics"] = get("fixtures/statistics", fixture=f["fixture"]["id"])
    for cle, path in (("lineups", "fixtures/lineups"), ("players", "fixtures/players")):
        for f in finis:
            if len(appels) >= LIMITE - 3:   # garder 2 appels pour le programme et les absents du jour
                break
            f[cle] = get(path, fixture=f["fixture"]["id"])
    res["hier"] = {"date": hier.isoformat(), "matchs": [resume(f) for f in finis]}
    # programme et absents du jour
    fa = [f for f in get("fixtures", date=auj.isoformat(), timezone="Europe/Paris") if f["league"]["id"] in LIGUES]
    res["aujourdhui"] = {"date": auj.isoformat(), "matchs": [resume(f) for f in fa]}
    ids_auj = {f["fixture"]["id"] for f in fa}
    inj = get("injuries", date=auj.isoformat())
    res["aujourdhui"]["absents"] = [{"fixture": x["fixture"]["id"], "equipe": x["team"]["name"], "joueur": x["player"]["name"],
                                     "type": x["player"].get("type"), "raison": x["player"].get("reason")}
                                    for x in inj if x.get("fixture", {}).get("id") in ids_auj]
    res["appels"] = appels
    with open(os.path.join(OUT, f"{auj.isoformat()}.json"), "w") as fh_:
        json.dump(res, fh_, ensure_ascii=False, indent=1)
    j = os.path.join(OUT, "journal.csv")
    new = not os.path.exists(j)
    with open(j, "a") as fh_:
        if new:
            fh_.write("date,appels,reste_jour,matchs_hier,avec_xg,matchs_jour,absents\n")
        xg = sum(1 for m in res["hier"]["matchs"] if m.get("xg_dom") is not None)
        fh_.write(f"{auj},{len(appels)},{appels[-1]['reste_jour'] if appels else ''},{len(res['hier']['matchs'])},{xg},"
                  f"{len(res['aujourdhui']['matchs'])},{len(res['aujourdhui']['absents'])}\n")
    print(json.dumps({k: v for k, v in res.items() if k != "appels"}, ensure_ascii=False)[:1500])
    print("erreurs :", [a["erreurs"] for a in appels if a["erreurs"]])


if __name__ == "__main__":
    main()
