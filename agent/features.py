"""Modèle complet : Elo + tous les critères mesurables, poids appris sur l'historique.

Un seul passage chronologique sur tous les matchs. Avant chaque match du circuit principal, on calcule
les critères (rien qui dépende du match lui-même), puis on met à jour l'état. Le même objet sert
pour l'entraînement (fit.py) et pour les prédictions du jour (predict.py).
"""
import os, re, math, bisect
from collections import defaultdict, deque
import numpy as np
import pandas as pd
from engine import ROOT, DATA, PARAMS, k_factor, expected, norm, WTA_SECOND_LEVELS, TD_FROM, AVANT, recent_frames

# ---------- pays des tournois (pour l'avantage du domicile) ----------
COUNTRY = {
 "australian open": "AUS", "roland garros": "FRA", "wimbledon": "GBR", "us open": "USA",
 "indian wells": "USA", "miami": "USA", "rome": "ITA", "madrid": "ESP", "cincinnati": "USA", "canada": "CAN",
 "montreal": "CAN", "toronto": "CAN", "paris masters": "FRA", "bnp paribas masters": "FRA", "shanghai": "CHN",
 "monte carlo": "MON", "washington": "USA", "winston salem": "USA", "barcelona": "ESP", "dubai": "UAE",
 "rotterdam": "NED", "acapulco": "MEX", "vienna": "AUT", "hamburg": "GER", "doha": "QAT", "delray beach": "USA",
 "halle": "GER", "queens club": "GBR", "montpellier": "FRA", "marseille": "FRA", "buenos aires": "ARG",
 "kitzbuhel": "AUT", "tokyo": "JPN", "basel": "SUI", "swiss indoors": "SUI", "munich": "GER", "geneva": "SUI",
 "stuttgart": "GER", "bastad": "SWE", "umag": "CRO", "gstaad": "SUI", "metz": "FRA", "stockholm": "SWE",
 "beijing": "CHN", "china open": "CHN", "newport": "USA", "auckland": "NZL", "asb classic": "NZL", "houston": "USA",
 "estoril": "POR", "s hertogenbosch": "NED", "atlanta": "USA", "los cabos": "MEX", "antwerp": "BEL",
 "european open": "BEL", "marrakech": "MAR", "sofia": "BUL", "eastbourne": "GBR", "rio de janeiro": "BRA",
 "brisbane": "AUS", "chengdu": "CHN", "lyon": "FRA", "sydney": "AUS", "st petersburg": "RUS", "moscow": "RUS",
 "cordoba": "ARG", "santiago": "CHI", "sao paulo": "BRA", "pune": "IND", "mallorca": "ESP", "antalya": "TUR",
 "dallas": "USA", "quito": "ECU", "bucharest": "ROU", "istanbul": "TUR", "shenzhen": "CHN", "nottingham": "GBR",
 "chennai": "IND", "memphis": "USA", "budapest": "HUN", "new york": "USA", "adelaide": "AUS", "astana": "KAZ",
 "almaty": "KAZ", "hong kong": "HKG", "nice": "FRA", "charleston": "USA", "wuhan": "CHN", "prague": "CZE",
 "monterrey": "MEX", "strasbourg": "FRA", "bogota": "COL", "birmingham": "GBR", "linz": "AUT", "hobart": "AUS",
 "seoul": "KOR", "guangzhou": "CHN", "rabat": "MAR", "palermo": "ITA", "luxembourg": "LUX", "guadalajara": "MEX",
 "tianjin": "CHN", "tashkent": "UZB", "nanchang": "CHN", "cleveland": "USA", "bad homburg": "GER",
 "abu dhabi": "UAE", "berlin": "GER", "quebec": "CAN", "nurnberg": "GER", "lausanne": "SUI", "hua hin": "THA",
 "osaka": "JPN", "new haven": "USA", "san jose": "USA", "kuala lumpur": "MAS", "zhuhai": "CHN", "merida": "MEX",
 "zhengzhou": "CHN", "ningbo": "CHN", "stanford": "USA", "ostrava": "CZE", "san diego": "USA", "singapore": "SGP",
 "florianopolis": "BRA", "katowice": "POL", "bol": "CRO", "taipei": "TPE", "austin": "USA", "monastir": "TUN",
 "charlotte": "USA", "mexico": "MEX", "kyoto": "JPN", "pan pacific": "JPN", "toray": "JPN", "western southern": "USA",
 "national bank": "CAN", "canadian open": "CAN", "italian open": "ITA", "internazionali": "ITA", "mutua madrid": "ESP",
 "indian wells masters": "USA", "miami open": "USA", "hertogenbosch": "NED", "libema": "NED", "boss open": "GER",
 "terra wortmann": "GER", "cinch": "GBR", "hsbc": "GBR", "citi open": "USA", "mubadala": "USA", "jiangxi": "CHN",
 "korea open": "KOR", "japan open": "JPN", "kinoshita": "JPN", "rolex shanghai": "CHN", "erste bank": "AUT",
 "grand prix auvergne": "FRA", "open sud de france": "FRA", "open 13": "FRA", "abn amro": "NED", "qatar": "QAT",
 "argentina open": "ARG", "rio open": "BRA", "chile open": "CHI", "abierto mexicano": "MEX", "us mens clay": "USA",
 "grand prix hassan": "MAR", "millennium estoril": "POR", "bmw open": "GER", "gonet geneva": "SUI",
 "nordea": "SWE", "plava laguna": "CRO", "generali": "AUT", "efg swiss": "SUI", "mifel": "MEX", "atx": "USA",
 "transylvania": "ROU", "cluj": "ROU", "ultima": "GBR", "lexus": "GBR", "rothesay": "GBR", "credit one": "USA",
}


# Tournois en altitude (mètres) : balle plus rapide, plus d'aces. Affiché et utilisable par l'agent ;
# l'effet est déjà en partie capté par le taux d'aces du tournoi.
ALTITUDE = {"bogota": 2640, "quito": 2850, "guadalajara": 1560, "gstaad": 1050, "kitzbuhel": 760, "madrid": 650,
            "mutua madrid": 650, "monterrey": 540, "sofia": 550, "munich": 520, "bmw open": 520, "san luis potosi": 1860,
            "budapest": 100, "johannesburg": 1750}


def tourney_altitude(name):
    n = norm(name)
    for k, v in ALTITUDE.items():
        if k in n and v >= 500:
            return v
    return None


def tourney_country(name):
    n = norm(name)
    for k, c in COUNTRY.items():
        if k in n:
            return c
    return None


# ---------- outils de score ----------
SET_RE = re.compile(r"(\d+)-(\d+)(?:\((\d+)\))?")


def parse_score(score, best_of):
    """Renvoie (sets_joués, tb_gagnés_vainqueur, tb_gagnés_perdant, set_décisif_joué, abandon)."""
    s = str(score)
    ret = "RET" in s.upper()
    sets = SET_RE.findall(s.split("RET")[0])
    tbw = sum(1 for a, b, _ in sets if a == "7" and b == "6")
    tbl = sum(1 for a, b, _ in sets if a == "6" and b == "7")
    try:
        bo = int(best_of)
    except (TypeError, ValueError):
        bo = 3
    decider = (len(sets) == bo) and not ret
    return len(sets), tbw, tbl, decider, ret


ROUND_NORM = {"1st Round": "R1", "2nd Round": "R2", "3rd Round": "R3", "4th Round": "R4", "Quarterfinals": "QF",
              "Semifinals": "SF", "The Final": "F", "Round Robin": "RR"}
OFFSET_BO3 = {"Q1": -3, "Q2": -2, "Q3": -1, "Q4": -1, "R128": 0, "R64": 1, "R32": 2, "R16": 3, "QF": 4, "SF": 5,
              "F": 6, "RR": 2, "BR": 6, "R1": 0, "R2": 2, "R3": 3, "R4": 4}
OFFSET_BO5 = {"R128": 1, "R64": 3, "R32": 5, "R16": 7, "QF": 9, "SF": 11, "F": 13}
LATE = {"QF", "SF", "F", "BR"}


def to_ord(yyyymmdd):
    y, m, d = yyyymmdd // 10000, yyyymmdd // 100 % 100, yyyymmdd % 100
    try:
        return pd.Timestamp(year=y, month=m, day=max(1, d)).toordinal()
    except ValueError:
        return pd.Timestamp(year=y, month=m, day=1).toordinal()


# ---------- chargement complet ----------
KEEP = ["tourney_name", "surface", "tourney_level", "tourney_date", "match_num", "winner_id", "winner_name",
        "loser_id", "loser_name", "score", "best_of", "round", "minutes", "winner_ioc", "loser_ioc", "court",
        "w_ace", "w_svpt", "w_1stWon", "w_2ndWon", "w_bpSaved", "w_bpFaced",
        "l_ace", "l_svpt", "l_1stWon", "l_2ndWon", "l_bpSaved", "l_bpFaced"]


def load_all(tour):
    fr = []
    for y in range(2000, 2027):
        f = os.path.join(ROOT, tour, f"{tour}_matches_{y}.csv")
        if os.path.exists(f):
            fr.append(pd.read_csv(f, low_memory=False).assign(main=True, exact_date=False))
        if y == 2026:
            continue
        f = os.path.join(ROOT, tour, f"{tour}_matches_qual_chall_{y}.csv" if tour == "atp" else f"{tour}_matches_qual_itf_{y}.csv")
        if os.path.exists(f):
            c = pd.read_csv(f, low_memory=False)
            if tour == "wta":
                c = c[c.tourney_level.astype(str).isin(WTA_SECOND_LEVELS) | c["round"].astype(str).str.match(r"^Q\d")]
            fr.append(c.assign(main=False, exact_date=False))
    f = os.path.join(ROOT, tour, f"{tour}_matches_qual_chall_2026.csv" if tour == "atp" else f"{tour}_matches_qual_itf_2026.csv")
    if os.path.exists(f):
        c = pd.read_csv(f, low_memory=False)
        if tour == "wta":
            c = c[c.tourney_level.astype(str).isin(WTA_SECOND_LEVELS) | c["round"].astype(str).str.match(r"^Q\d")]
        fr.append(c.assign(main=False, exact_date=False))
    for x in recent_frames(tour):
        fr.append(x.assign(exact_date=True))
    d = pd.concat(fr, ignore_index=True)
    for c in KEEP:
        if c not in d:
            d[c] = np.nan
    d = d[KEEP + ["main", "exact_date"]].copy()
    d["score"] = d.score.fillna("").astype(str)
    d = d[~d.score.str.contains("W/O|DEF|Walkover|unfinished", case=False)]
    d = d[d.surface.isin(["Hard", "Clay", "Grass", "Carpet"])]
    d["surf"] = d.surface.replace({"Carpet": "Hard"})
    for c in ["winner_id", "loser_id"]:
        d[c] = d[c].astype(str).str.replace(r"\.0$", "", regex=True)
    d["round"] = d["round"].astype(str).map(lambda r: ROUND_NORM.get(r, r))
    d.loc[d["round"].str.match(r"^Q\d"), "main"] = False
    d["main"] = d["main"].astype(bool)
    d["tourney_date"] = d.tourney_date.astype(int)
    d = d[d.tourney_date < AVANT]
    d["best_of"] = pd.to_numeric(d.best_of, errors="coerce").fillna(3).astype(int)
    # date approximative du match (Sackmann ne donne que le début du tournoi)
    def mdate(r):
        o = to_ord(r.tourney_date)
        if r.exact_date:
            return o
        tab = OFFSET_BO5 if r.best_of == 5 else OFFSET_BO3
        return o + tab.get(r["round"], 2)
    d["mdate"] = d.apply(mdate, axis=1)
    # nationalités manquantes (fichiers 2026) : depuis le fichier des joueurs
    pl = pd.read_csv(os.path.join(ROOT, tour, f"{tour}_players.csv"), low_memory=False)
    ioc = dict(zip(pl.player_id.astype(str), pl.ioc))
    d["winner_ioc"] = d.winner_ioc.fillna(d.winner_id.map(ioc))
    d["loser_ioc"] = d.loser_ioc.fillna(d.loser_id.map(ioc))
    d = d.sort_values(["mdate", "main", "match_num"], kind="stable").reset_index(drop=True)
    return d


FEATURES = ["elo", "tendance", "service", "retour", "bp_sauvees", "bp_converties", "style_vitesse",
            "forme", "tie_breaks", "sets_decisifs", "titre_recent", "matchs_7j", "sets_7j", "minutes_7j",
            "abandon_recent", "rouille", "cinq_sets", "fin_de_tournoi", "grand_chelem", "face_a_face", "domicile"]

LABELS = {"elo": "Niveau Elo (surface + global)", "tendance": "Tendance de l'Elo (3 mois)",
          "service": "Points gagnés au service (12 mois)", "retour": "Points gagnés au retour (12 mois)",
          "bp_sauvees": "Balles de break sauvées", "bp_converties": "Balles de break converties",
          "style_vitesse": "Style × vitesse du court", "forme": "Forme récente (10 matchs, selon l'adversaire)",
          "tie_breaks": "Tie-breaks (12 mois)", "sets_decisifs": "Sets décisifs (12 mois)",
          "titre_recent": "Titre ou finale ces 14 jours", "matchs_7j": "Matchs joués (7 jours)",
          "sets_7j": "Sets joués (7 jours)", "minutes_7j": "Minutes de jeu (7 jours)",
          "abandon_recent": "Abandon récent (30 jours)", "rouille": "Retour après une longue pause",
          "cinq_sets": "Format en 5 sets", "fin_de_tournoi": "Fin de tournoi (quarts et après)",
          "grand_chelem": "Grand Chelem", "face_a_face": "Face-à-face récent sur la surface",
          "domicile": "Joue à domicile"}

MEANS = {"atp": (0.635, 0.365), "wta": (0.565, 0.435)}


class State:
    def __init__(self, tour):
        self.tour = tour
        self.p = PARAMS[tour]
        self.g, self.s, self.ng, self.ns = {}, {}, {}, {}
        self.nmain = defaultdict(int)
        self.names, self.ioc = {}, {}
        self.hist = defaultdict(lambda: deque(maxlen=40))     # derniers matchs (tous niveaux)
        self.serve = defaultdict(lambda: deque(maxlen=120))   # stats service/retour
        self.elo_hist = defaultdict(lambda: deque(maxlen=120))
        self.h2h = defaultdict(list)
        self.speed = defaultdict(lambda: [0.0, 0.0])          # (tournoi, année) -> aces, points
        self.speed_surf = defaultdict(lambda: [0.0, 0.0])     # (surface, année)
        self.last_date = 0

    # ----- niveau -----
    def mix(self, pid, surf):
        w = self.p["w_surface"]
        return w * self.s.get((pid, surf), 1500) + (1 - w) * self.g.get(pid, 1500)

    def p_elo(self, a, b, surf):
        return 1 / (1 + 10 ** (-self.p["scale"] * (self.mix(a, surf) - self.mix(b, surf)) / 400))

    def elo_at(self, pid, day):
        h = self.elo_hist[pid]
        val = None
        for d, e in h:
            if d <= day:
                val = e
            else:
                break
        return val

    # ----- critères d'un joueur -----
    def pfacts(self, pid, day, tourney):
        h = [x for x in self.hist[pid] if x[0] < day]
        last10 = h[-10:]
        forme = float(np.mean([x[1] - x[2] for x in last10])) if last10 else 0.0
        yr = [x for x in h if x[0] >= day - 365]
        tbw = sum(x[5] for x in yr); tbl = sum(x[6] for x in yr)
        dw = sum(1 for x in yr if x[7] and x[1]); dl = sum(1 for x in yr if x[7] and not x[1])
        w7 = [x for x in h if x[0] >= day - 7]
        m7 = len(w7); s7 = sum(x[3] for x in w7)
        min7 = sum((x[4] if x[4] == x[4] and x[4] else x[3] * 42) for x in w7) / 100
        ret = 1.0 if any(x[8] and not x[1] for x in h if x[0] >= day - 30) else 0.0
        rust = 1.0 if (not h or day - h[-1][0] > 45) else 0.0
        titre = 0.0
        for x in reversed(h):
            if x[0] < day - 14:
                break
            if x[10] == "F" and x[9] != tourney:
                titre = 1.0 if x[1] else 0.5
                break
        sv = [x for x in self.serve[pid] if day - 365 <= x[0] < day]
        svpt = sum(x[1] for x in sv); rtpt = sum(x[3] for x in sv)
        ms, mr = MEANS[self.tour]
        spw = (sum(x[2] for x in sv) + 200 * ms) / (svpt + 200)
        rpw = (sum(x[4] for x in sv) + 200 * mr) / (rtpt + 200)
        bpf = sum(x[5] for x in sv); bps = sum(x[6] for x in sv)
        bpo = sum(x[7] for x in sv); bpc = sum(x[8] for x in sv)
        bps_r = (bps + 30 * 0.6) / (bpf + 30)
        bpc_r = (bpc + 30 * 0.4) / (bpo + 30)
        g_now = self.g.get(pid, 1500); g_old = self.elo_at(pid, day - 90)
        trend = (g_now - g_old) / 100 if g_old is not None else 0.0
        return {"forme": forme, "tb": (tbw + 5) / (tbw + tbl + 10), "dec": (dw + 5) / (dw + dl + 10),
                "m7": m7, "s7": s7, "min7": min7, "ret": ret, "rust": rust, "titre": titre,
                "spw": spw, "rpw": rpw, "orient": (spw - ms) / 0.04 - (rpw - mr) / 0.04,
                "bps": bps_r, "bpc": bpc_r, "trend": trend}

    def speed_lookup(self, tourney, year):
        """Taux d'aces du même tournoi l'année précédente. Accepte « Stockholm Open » pour « Stockholm »."""
        n = norm(tourney)
        t = self.speed.get((n, year - 1))
        if t:
            return t
        cands = [k for k in self.speed if k[1] == year - 1 and k[0] and (k[0] in n or n in k[0])]
        return self.speed[max(cands, key=lambda k: len(k[0]))] if cands else None

    def speed_z(self, tourney, surf, year):
        t = self.speed_lookup(tourney, year)
        m = self.speed_surf.get((surf, year - 1))
        if not t or not m or t[1] < 2000 or m[1] == 0:
            return 0.0
        return math.log((t[0] / t[1] + 1e-4) / (m[0] / m[1] + 1e-4))

    def court_info(self, tourney, surf, year):
        """Vitesse estimée du court (taux d'aces de l'édition précédente comparé à la moyenne de la surface)."""
        t = self.speed_lookup(tourney, year)
        m = self.speed_surf.get((surf, year - 1))
        if not t or not m or t[1] < 2000 or m[1] == 0:
            return None
        r = (t[0] / t[1]) / (m[0] / m[1])
        label = "lent" if r < 0.85 else "rapide" if r > 1.15 else "moyen"
        return {"vitesse": label, "aces_pct": round(t[0] / t[1] * 100, 1), "moyenne_surface_pct": round(m[0] / m[1] * 100, 1),
                "annee_reference": year - 1}

    def features(self, a, b, surf, day, best_of, rnd, level, country, tourney):
        p = min(max(self.p_elo(a, b, surf), 1e-4), 1 - 1e-4)
        x0 = math.log(p / (1 - p))
        fa, fb = self.pfacts(a, day, tourney), self.pfacts(b, day, tourney)
        year = pd.Timestamp.fromordinal(day).year
        sz = self.speed_z(tourney, surf, year)
        key = (a, b) if a < b else (b, a)
        rec = [x for x in self.h2h[key] if x[0] >= day - 3 * 365 and x[1] == surf]
        wa = sum(1 for x in rec if x[2] == a); wb = len(rec) - wa
        ia, ib = self.ioc.get(a), self.ioc.get(b)
        home = (1.0 if country and ia == country else 0.0) - (1.0 if country and ib == country else 0.0)
        f = {
            "elo": x0,
            "tendance": fa["trend"] - fb["trend"],
            "service": (fa["spw"] - fb["spw"]) * 10,
            "retour": (fa["rpw"] - fb["rpw"]) * 10,
            "bp_sauvees": (fa["bps"] - fb["bps"]) * 10,
            "bp_converties": (fa["bpc"] - fb["bpc"]) * 10,
            "style_vitesse": (fa["orient"] - fb["orient"]) * sz,
            "forme": (fa["forme"] - fb["forme"]) * 10,
            "tie_breaks": (fa["tb"] - fb["tb"]) * 10,
            "sets_decisifs": (fa["dec"] - fb["dec"]) * 10,
            "titre_recent": fa["titre"] - fb["titre"],
            "matchs_7j": fa["m7"] - fb["m7"],
            "sets_7j": fa["s7"] - fb["s7"],
            "minutes_7j": fa["min7"] - fb["min7"],
            "abandon_recent": fa["ret"] - fb["ret"],
            "rouille": fa["rust"] - fb["rust"],
            "cinq_sets": x0 * (1.0 if best_of == 5 else 0.0),
            "fin_de_tournoi": x0 * (1.0 if rnd in LATE else 0.0),
            "grand_chelem": x0 * (1.0 if level == "G" else 0.0),
            "face_a_face": (wa - wb) / (len(rec) + 3),
            "domicile": home,
        }
        return f, fa, fb, p

    # ----- mise à jour après un match -----
    def update(self, r):
        w, l, sf = r.winner_id, r.loser_id, r.surf
        self.names[w], self.names[l] = r.winner_name, r.loser_name
        if isinstance(r.winner_ioc, str): self.ioc[w] = r.winner_ioc
        if isinstance(r.loser_ioc, str): self.ioc[l] = r.loser_ioc
        gw, gl = self.g.get(w, 1500), self.g.get(l, 1500)
        sw, sl = self.s.get((w, sf), 1500), self.s.get((l, sf), 1500)
        eg, es = expected(gw, gl), expected(sw, sl)
        mu = 1.0 if r.main else self.p["poids_secondaire"]
        k = k_factor
        self.g[w] = gw + mu * k(self.ng.get(w, 0)) * (1 - eg); self.g[l] = gl - mu * k(self.ng.get(l, 0)) * (1 - eg)
        self.s[(w, sf)] = sw + mu * k(self.ns.get((w, sf), 0)) * (1 - es)
        self.s[(l, sf)] = sl - mu * k(self.ns.get((l, sf), 0)) * (1 - es)
        self.ng[w] = self.ng.get(w, 0) + 1; self.ng[l] = self.ng.get(l, 0) + 1
        self.ns[(w, sf)] = self.ns.get((w, sf), 0) + 1; self.ns[(l, sf)] = self.ns.get((l, sf), 0) + 1
        if r.main:
            self.nmain[w] += 1; self.nmain[l] += 1
        day = r.mdate
        nsets, tbw, tbl, dec, ret = parse_score(r.score, r.best_of)
        mins = r.minutes if r.minutes == r.minutes else None
        # (jour, gagné, attendu, sets, minutes, tb gagnés, tb perdus, décisif, abandon, tournoi, tour)
        tn = norm(r.tourney_name)
        self.hist[w].append((day, 1, eg, nsets, mins, tbw, tbl, dec, ret, tn, r.round))
        self.hist[l].append((day, 0, 1 - eg, nsets, mins, tbl, tbw, dec, ret, tn, r.round))
        self.elo_hist[w].append((day, self.g[w])); self.elo_hist[l].append((day, self.g[l]))
        key = (w, l) if w < l else (l, w)
        self.h2h[key].append((day, sf, w))
        if r.w_svpt == r.w_svpt and r.l_svpt == r.l_svpt and r.w_svpt > 0 and r.l_svpt > 0:
            wsw = r.w_1stWon + r.w_2ndWon; lsw = r.l_1stWon + r.l_2ndWon
            nz = lambda v: 0.0 if v != v or v is None else float(v)
            wbf, wbs = nz(r.w_bpFaced), nz(r.w_bpSaved)
            lbf, lbs = nz(r.l_bpFaced), nz(r.l_bpSaved)
            if wsw == wsw and lsw == lsw:
                self.serve[w].append((day, r.w_svpt, wsw, r.l_svpt, r.l_svpt - lsw, wbf, wbs, lbf, lbf - lbs))
                self.serve[l].append((day, r.l_svpt, lsw, r.w_svpt, r.w_svpt - wsw, lbf, lbs, wbf, wbf - wbs))
            if r.main and r.w_ace == r.w_ace and r.l_ace == r.l_ace:
                yr = pd.Timestamp.fromordinal(day).year
                t = self.speed[(tn, yr)]; t[0] += r.w_ace + r.l_ace; t[1] += r.w_svpt + r.l_svpt
                m = self.speed_surf[(sf, yr)]; m[0] += r.w_ace + r.l_ace; m[1] += r.w_svpt + r.l_svpt
        self.last_date = max(self.last_date, day)


def build(tour, collect_from=20110101):
    """Passe sur tout l'historique. Renvoie l'état final et le tableau des critères des matchs principaux."""
    d = load_all(tour)
    st = State(tour)
    rows = []
    start = to_ord(collect_from)
    for r in d.itertuples(index=False):
        if r.main and r.mdate >= start:
            f, _, _, p = st.features(r.winner_id, r.loser_id, r.surf, r.mdate, r.best_of, r.round,
                                     r.tourney_level, tourney_country(r.tourney_name), r.tourney_name)
            rows.append({"day": r.mdate, "date": r.tourney_date, "level": r.tourney_level, **f})
        st.update(r)
    return st, pd.DataFrame(rows)
