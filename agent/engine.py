"""Moteur de l'agent tennis : Elo global + Elo par surface, et facteurs explicatifs.

Sources, dans l'ordre chronologique :
  1. archive Jeff Sackmann (atp/ et wta/ à la racine du dépôt), jusqu'à fin 2025
  2. agent/data/{tour}_2026.csv : résultats 2026 issus de tennis-data.co.uk (jusqu'au 8 nov. 2026)
  3. agent/data/{tour}_live.csv : résultats ajoutés chaque matin par la tâche planifiée

Paramètres réglés sur 2015-2023 et validés sur 2024-2026 (voir agent/README.md).
"""
import os, re, unicodedata
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "agent", "data")
# Challengers / qualifications / ITF de haut niveau comptés à 60 % (test nov. 2026 : +1,6 pt ATP, +0,5 pt WTA)
PARAMS = {"atp": {"w_surface": 0.40, "scale": 0.92, "poids_secondaire": 0.6},
          "wta": {"w_surface": 0.30, "scale": 0.86, "poids_secondaire": 0.6}}
WTA_SECOND_LEVELS = ["C", "Q", "125", "W100", "W75", "I"]
TD_FROM = 20260608  # données récentes (export saison, sinon tennis-data) utilisées à partir de cette date
# AGENT_AVANT=AAAAMMJJ : ignore les matchs à partir de cette date (pour recalculer un pronostic sans voir le résultat)
AVANT = int(os.environ.get("AGENT_AVANT", "99999999"))


def recent_frames(tour):
    """Matchs depuis TD_FROM : export saison s'il existe (avec Challengers et stats), sinon tennis-data ; puis résultats du jour."""
    out = []
    saison = os.path.join(DATA, f"{tour}_saison.csv")
    last = 0
    if os.path.exists(saison):
        x = pd.read_csv(saison, low_memory=False)
        x = x[x.tourney_date >= TD_FROM]
        # le dernier jour de l'export est souvent incomplet : on le laisse aux résultats du jour (live)
        last = int(x.tourney_date.max())
        out.append(x[x.tourney_date < last])
        last -= 1
    else:
        f = os.path.join(DATA, f"{tour}_2026.csv")
        if os.path.exists(f):
            x = pd.read_csv(f, low_memory=False)
            x = x[x.tourney_date >= TD_FROM].assign(main=True)
            last = int(x.tourney_date.max())
            out.append(x)
    f = os.path.join(DATA, f"{tour}_live.csv")
    if os.path.exists(f):
        x = pd.read_csv(f, low_memory=False)
        out.append(x[x.tourney_date > last].assign(main=True))
    return out
SURFACES = ["Hard", "Clay", "Grass"]
COLS = ["tourney_name", "surface", "tourney_level", "tourney_date", "match_num",
        "winner_id", "winner_name", "loser_id", "loser_name", "score", "round"]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).strip()


def k_factor(n):
    return 250 / ((n + 5) ** 0.4)


def expected(ra, rb):
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def load_matches(tour):
    frames = []
    for y in range(1995, 2027):
        f = os.path.join(ROOT, tour, f"{tour}_matches_{y}.csv")
        if os.path.exists(f):
            frames.append(pd.read_csv(f, low_memory=False).assign(main=True))
    for y in range(2000, 2027):  # matchs « secondaires » : Challengers, qualifications (ATP) / qualifs + ITF haut niveau (WTA)
        f = os.path.join(ROOT, tour, f"{tour}_matches_qual_chall_{y}.csv" if tour == "atp" else f"{tour}_matches_qual_itf_{y}.csv")
        if os.path.exists(f):
            c = pd.read_csv(f, low_memory=False)
            if tour == "wta":
                c = c[c.tourney_level.astype(str).isin(WTA_SECOND_LEVELS) | c["round"].astype(str).str.match(r"^Q\d")]
            frames.append(c.assign(main=False))
    frames += recent_frames(tour)
    d = pd.concat(frames, ignore_index=True)
    for c in COLS:
        if c not in d:
            d[c] = np.nan
    d = d[COLS + ["main"]].copy()
    d.loc[d["round"].astype(str).str.match(r"^Q\d"), "main"] = False
    d["score"] = d.score.fillna("").astype(str)
    d = d[~d.score.str.contains("W/O|DEF|Walkover|unfinished", case=False)]
    d = d[d.surface.isin(["Hard", "Clay", "Grass", "Carpet"])]
    d["surf"] = d.surface.replace({"Carpet": "Hard"})
    for c in ["winner_id", "loser_id"]:
        d[c] = d[c].astype(str).str.replace(r"\.0$", "", regex=True)
    d["tourney_date"] = d.tourney_date.astype(int)
    d["main"] = d["main"].astype(bool)
    d = d.sort_values(["tourney_date", "main", "match_num"], kind="stable").reset_index(drop=True)
    return d


class Model:
    def __init__(self, tour):
        self.tour = tour
        self.p = PARAMS[tour]
        self.m = load_matches(tour)
        self._run()

    def _run(self):
        g, s, ng, ns, last, names, nmain = {}, {}, {}, {}, {}, {}, {}
        sec = self.p["poids_secondaire"]
        hist = []  # (date, pid, elo global après le match) pour la tendance
        for r in self.m.itertuples(index=False):
            w, l, sf = r.winner_id, r.loser_id, r.surf
            names[w], names[l] = r.winner_name, r.loser_name
            gw, gl = g.get(w, 1500), g.get(l, 1500)
            sw, sl = s.get((w, sf), 1500), s.get((l, sf), 1500)
            eg, es = expected(gw, gl), expected(sw, sl)
            mu = 1.0 if r.main else sec
            g[w] = gw + mu * k_factor(ng.get(w, 0)) * (1 - eg)
            g[l] = gl - mu * k_factor(ng.get(l, 0)) * (1 - eg)
            s[(w, sf)] = sw + mu * k_factor(ns.get((w, sf), 0)) * (1 - es)
            s[(l, sf)] = sl - mu * k_factor(ns.get((l, sf), 0)) * (1 - es)
            if r.main:
                nmain[w] = nmain.get(w, 0) + 1; nmain[l] = nmain.get(l, 0) + 1
            ng[w] = ng.get(w, 0) + 1; ng[l] = ng.get(l, 0) + 1
            ns[(w, sf)] = ns.get((w, sf), 0) + 1; ns[(l, sf)] = ns.get((l, sf), 0) + 1
            last[w] = last[l] = r.tourney_date
            if r.tourney_date >= 20250101 and r.main:
                hist.append((r.tourney_date, w, g[w])); hist.append((r.tourney_date, l, g[l]))
        self.g, self.s, self.ng, self.ns, self.last, self.names, self.nmain = g, s, ng, ns, last, names, nmain
        self.main = self.m[self.m.main]  # les facteurs explicatifs ne regardent que le circuit principal
        self.hist = pd.DataFrame(hist, columns=["date", "pid", "elo"])
        self.data_through = int(self.m.tourney_date.max())
        # index des noms pour la correspondance
        self.by_norm = {}
        for pid, n in names.items():
            key = norm(n)
            if key not in self.by_norm or ng.get(pid, 0) > ng.get(self.by_norm[key], 0):  # homonymes : le plus actif
                self.by_norm[key] = pid

    # ---------- correspondance des noms ----------
    def resolve(self, name):
        """Accepte 'Prénom Nom', 'Nom, Prénom' ou 'Nom P.'"""
        n = str(name).strip()
        if "," in n:
            last, first = [x.strip() for x in n.split(",", 1)]
            n = f"{first} {last}"
        key = norm(n)
        if key in self.by_norm:
            return self.by_norm[key]
        toks = key.split()
        # 'Nom P.' ou noms partiels : on cherche le nom de famille + initiale
        cands = []
        for k, pid in self.by_norm.items():
            kt = k.split()
            if not kt:
                continue
            if toks and toks[-1] == kt[-1] and toks[0][:1] == kt[0][:1]:
                cands.append(pid)
            elif len(toks) >= 2 and " ".join(toks[:-1]) == " ".join(kt[1:]) and toks[-1][:1] == kt[0][:1]:
                cands.append(pid)
        if cands:
            return max(cands, key=lambda p: (self.last.get(p, 0), self.ng.get(p, 0)))
        return None

    # ---------- notes ----------
    def mix(self, pid, surf):
        w = self.p["w_surface"]
        return w * self.s.get((pid, surf), 1500) + (1 - w) * self.g.get(pid, 1500)

    def prob(self, a, b, surf):
        d = self.mix(a, surf) - self.mix(b, surf)
        return 1 / (1 + 10 ** (-self.p["scale"] * d / 400))

    # ---------- facteurs explicatifs ----------
    def player_facts(self, pid, surf, today):
        m = self.main
        mine = m[(m.winner_id == pid) | (m.loser_id == pid)]
        last10 = mine.tail(10)
        wins10 = int((last10.winner_id == pid).sum())
        t = pd.Timestamp(str(today))
        d7 = int((t - pd.Timedelta(days=7)).strftime("%Y%m%d"))
        d30 = int((t - pd.Timedelta(days=30)).strftime("%Y%m%d"))
        d365 = int((t - pd.Timedelta(days=365)).strftime("%Y%m%d"))
        recent7 = int((mine.tourney_date >= d7).sum())
        yr = mine[(mine.tourney_date >= d365) & (mine.surf == surf)]
        yr_w = int((yr.winner_id == pid).sum())
        h = self.hist[self.hist.pid == pid]
        before = h[h.date < d30]
        trend = round(self.g.get(pid, 1500) - before.elo.iloc[-1]) if len(before) else None
        # dernier tournoi : titre ou finale ?
        last_t = None
        if len(mine):
            lt = mine.iloc[-1]
            tm = mine[mine.tourney_name == lt.tourney_name]
            tm = tm[tm.tourney_date >= lt.tourney_date - 100]
            fin = tm[tm["round"].astype(str).isin(["F", "The Final", "Final"])]
            res = None
            if len(fin):
                res = "titre" if (fin.winner_id == pid).any() else "finale"
            last_t = {"tournoi": str(lt.tourney_name), "date": int(lt.tourney_date), "resultat": res}
        return {
            "elo": round(self.mix(pid, surf)),
            "elo_global": round(self.g.get(pid, 1500)),
            "matchs_surface": int(((m.winner_id == pid) | (m.loser_id == pid)).loc[m.surf == surf].sum()),
            "forme_10": f"{wins10}-{len(last10) - wins10}",
            "matchs_7j": recent7,
            "bilan_surface_12m": f"{yr_w}-{len(yr) - yr_w}",
            "tendance_30j": trend,
            "dernier_tournoi": last_t,
        }

    def h2h(self, a, b, surf):
        m = self.main
        x = m[((m.winner_id == a) & (m.loser_id == b)) | ((m.winner_id == b) & (m.loser_id == a))]
        xs = x[x.surf == surf]
        return {"total": f"{int((x.winner_id == a).sum())}-{int((x.winner_id == b).sum())}",
                "surface": f"{int((xs.winner_id == a).sum())}-{int((xs.winner_id == b).sum())}"}

    def rankings(self, n=150, active_since=None):
        cutoff = active_since or int((pd.Timestamp(str(self.data_through)) - pd.Timedelta(days=200)).strftime("%Y%m%d"))
        act = [p for p in self.g if self.last.get(p, 0) >= cutoff and self.nmain.get(p, 0) >= 20]
        rows = [{"nom": self.names[p], "global": round(self.g[p]),
                 "dur": round(self.mix(p, "Hard")), "terre": round(self.mix(p, "Clay")),
                 "gazon": round(self.mix(p, "Grass"))} for p in act]
        return sorted(rows, key=lambda r: -r["global"])[:n]
