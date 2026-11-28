"""Faire correspondre les noms de clubs de toutes les sources (ESPN, SportRadar, football.json…) aux noms Elo."""
import difflib, json, os, re, unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
PAYS = {"E0": "ENG", "SP1": "ESP", "I1": "ITA", "F1": "FRA", "D1": "GER", "T1": "TUR", "N1": "NED", "P1": "POR", "B1": "BEL"}

# alias manuels (forme normalisée -> nom Elo)
ALIAS = {
    "manchester city": "Man City", "man city": "Man City", "manchester united": "Man United", "man utd": "Man United",
    "man united": "Man United", "nottingham forest": "Nott'm Forest", "nottm forest": "Nott'm Forest",
    "wolverhampton wanderers": "Wolves", "wolverhampton": "Wolves", "tottenham hotspur": "Tottenham", "spurs": "Tottenham",
    "brighton hove albion": "Brighton", "newcastle united": "Newcastle", "leeds united": "Leeds", "west ham united": "West Ham",
    "sheffield united": "Sheffield United", "atletico madrid": "Ath Madrid", "atletico de madrid": "Ath Madrid",
    "athletic bilbao": "Ath Bilbao", "athletic club": "Ath Bilbao", "real betis": "Betis", "celta vigo": "Celta",
    "rc celta": "Celta", "espanyol barcelona": "Espanol", "espanyol": "Espanol", "rayo vallecano": "Vallecano",
    "real sociedad": "Sociedad", "deportivo alaves": "Alaves", "real oviedo": "Oviedo", "racing santander": "Santander",
    "paris saint germain": "Paris SG", "psg": "Paris SG", "olympique marseille": "Marseille", "olympique de marseille": "Marseille",
    "olympique lyonnais": "Lyon", "olympique lyon": "Lyon", "stade rennais": "Rennes", "stade brestois": "Brest",
    "saint etienne": "St Etienne", "as monaco": "Monaco", "inter milan": "Inter", "internazionale": "Inter",
    "inter milano": "Inter", "ac milan": "Milan", "as roma": "Roma", "ss lazio": "Lazio", "ssc napoli": "Napoli",
    "hellas verona": "Verona", "bayern munchen": "Bayern Munich", "bayern munich": "Bayern Munich",
    "borussia dortmund": "Dortmund", "borussia monchengladbach": "M'gladbach", "monchengladbach": "M'gladbach",
    "bayer leverkusen": "Leverkusen", "bayer 04 leverkusen": "Leverkusen", "eintracht frankfurt": "Ein Frankfurt",
    "vfb stuttgart": "Stuttgart", "1 fsv mainz 05": "Mainz", "fsv mainz": "Mainz", "mainz 05": "Mainz",
    "tsg hoffenheim": "Hoffenheim", "1899 hoffenheim": "Hoffenheim", "sc freiburg": "Freiburg", "fc koln": "FC Koln",
    "1 fc koln": "FC Koln", "koln": "FC Koln", "hamburger sv": "Hamburg", "fc st pauli": "St Pauli", "st pauli": "St Pauli",
    "werder bremen": "Werder Bremen", "1 fc heidenheim": "Heidenheim", "union berlin": "Union Berlin",
    "1 fc union berlin": "Union Berlin", "fc augsburg": "Augsburg", "vfl wolfsburg": "Wolfsburg", "rb leipzig": "RB Leipzig",
    "psv": "PSV Eindhoven", "psv eindhoven": "PSV Eindhoven", "az alkmaar": "AZ Alkmaar", "az": "AZ Alkmaar",
    "feyenoord rotterdam": "Feyenoord", "ajax amsterdam": "Ajax", "fc twente": "Twente", "fc utrecht": "Utrecht",
    "fc groningen": "Groningen", "nec nijmegen": "Nijmegen", "nec": "Nijmegen", "go ahead eagles": "Go Ahead Eagles",
    "sporting cp": "Sp Lisbon", "sporting lisbon": "Sp Lisbon", "sporting": "Sp Lisbon", "sporting clube de portugal": "Sp Lisbon",
    "fc porto": "Porto", "sl benfica": "Benfica", "sc braga": "Braga", "sporting braga": "Braga", "vitoria guimaraes": "Guimaraes",
    "vitoria sc": "Guimaraes", "club brugge": "Club Brugge", "club brugge kv": "Club Brugge", "rsc anderlecht": "Anderlecht",
    "royale union saint gilloise": "St. Gilloise", "union saint gilloise": "St. Gilloise", "union sg": "St. Gilloise",
    "krc genk": "Genk", "kaa gent": "Gent", "royal antwerp": "Antwerp", "standard liege": "Standard",
    "standard de liege": "Standard", "sint truiden": "St Truiden", "stvv": "St Truiden", "kv mechelen": "Mechelen",
    "oh leuven": "Oud-Heverlee Leuven", "oud heverlee leuven": "Oud-Heverlee Leuven", "sporting charleroi": "Charleroi",
    "cercle brugge": "Cercle Brugge", "kvc westerlo": "Westerlo", "sv zulte waregem": "Waregem", "zulte waregem": "Waregem",
    "galatasaray": "Galatasaray", "ohl": "Oud-Heverlee Leuven", "fc cologne": "FC Koln", "cologne": "FC Koln", "deportivo": "La Coruna", "deportivo la coruna": "La Coruna", "rc deportivo": "La Coruna", "braga": "Sp Braga", "goztepe": "Goztep", "fortuna sittard": "For Sittard", "ado den haag": "Den Haag", "waasland beveren": "Beveren", "sk beveren": "Beveren", "pec zwolle": "Zwolle", "cd nacional": "Nacional", "c d nacional": "Nacional", "fenerbahce": "Fenerbahce", "besiktas": "Besiktas", "trabzonspor": "Trabzonspor",
    "istanbul basaksehir": "Buyuksehyr", "basaksehir": "Buyuksehyr", "caykur rizespor": "Rizespor",
    "amed sfk": "Amedspor", "amed sportif faaliyetler": "Amedspor", "erzurum bb": "Erzurumspor", "bb erzurumspor": "Erzurumspor",
    "atiker konyaspor": "Konyaspor", "aytemiz alanyaspor": "Alanyaspor", "gaziantep fk": "Gaziantep", "corum fk": "Corum",
    "naples": "Napoli", "come": "Como", "betis seville": "Betis", "venise": "Venezia", "bologne": "Bologna",
    "kasimpasa": "Kasimpasa", "mayence": "Mainz", "eintracht francfort": "Ein Frankfurt", "francfort": "Ein Frankfurt", "gencler birligi": "Genclerbirligi", "genclerbirligi": "Genclerbirligi",
}

STOP = {"fc", "afc", "cf", "sc", "sk", "fk", "ac", "as", "ssc", "ss", "us", "cd", "ud", "sd", "rc", "rcd", "ca", "club",
        "calcio", "kv", "krc", "kaa", "rsc", "sv", "vfl", "vfb", "tsg", "bv", "bsc", "1", "jk", "fsv", "ogc", "losc", "rb",
        "de", "the", "sl", "cp", "sad", "fcsb"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def core(s):
    return " ".join(w for w in norm(s).split() if w not in STOP)


_EXTRA = os.path.join(ICI, "data/alias_appris.json")


class Resolveur:
    def __init__(self, clubs_par_pays):
        """clubs_par_pays : {pays: [noms Elo]}"""
        self.cp = clubs_par_pays
        self.tous = {c: p for p, l in clubs_par_pays.items() for c in l}
        self.appris = json.load(open(_EXTRA)) if os.path.exists(_EXTRA) else {}

    def __call__(self, nom, pays=None):
        n = norm(nom)
        if nom in self.tous:
            return nom
        if n in self.appris:
            return self.appris[n]
        if n in ALIAS and ALIAS[n] in self.tous:
            return ALIAS[n]
        c = core(nom)
        if c in ALIAS and ALIAS[c] in self.tous:
            return ALIAS[c]
        pool = self.cp.get(pays, []) if pays else list(self.tous)
        if not pool:
            pool = list(self.tous)
        cn = {core(x): x for x in pool}
        if c in cn:
            return cn[c]
        # inclusion de mots
        for k, v in cn.items():
            if c and k and (c in k.split() or k in c.split() or c.startswith(k) or k.startswith(c)):
                return v
        m = difflib.get_close_matches(c, list(cn), n=1, cutoff=0.72)
        return cn[m[0]] if m else None

    def apprendre(self, nom, elo_nom):
        self.appris[norm(nom)] = elo_nom
        json.dump(self.appris, open(_EXTRA, "w"), indent=1, ensure_ascii=False)
