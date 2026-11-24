"""Moyennes récentes d'une équipe à partir de foot/data/apifootball/historique/matchs.jsonl.

python3 foot/apifootball/moyennes.py "Brentford" [n=10]
"""
import json, os, sys, unicodedata
ICI = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(ICI, "..", "data", "apifootball", "historique", "matchs.jsonl")
CHAMPS = {"xg": "xG", "tt": "tirs", "tc": "tirs cadrés", "tirs_surface": "tirs dans la surface",
          "tirs_hors_surface": "tirs hors surface", "possession": "possession %"}


def _n(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def charger():
    if not os.path.exists(F):
        return []
    return [json.loads(l) for l in open(F)]


def moyennes(equipe, n=10, matchs=None, avant=None):
    ms = matchs if matchs is not None else charger()
    e = _n(equipe)
    sel = [m for m in ms if (_n(m["dom"]) == e or _n(m["ext"]) == e) and (avant is None or m["date"][:10] < avant)]
    sel = sorted(sel, key=lambda m: m["date"])[-n:]
    if not sel:
        return None
    out = {"matchs": len(sel)}
    for c in CHAMPS:
        pour, contre = [], []
        for m in sel:
            k, o = ("dom", "ext") if _n(m["dom"]) == e else ("ext", "dom")
            if m.get(f"{c}_{k}") is not None:
                pour.append(m[f"{c}_{k}"])
                if m.get(f"{c}_{o}") is not None:
                    contre.append(m[f"{c}_{o}"])
        if pour:
            out[f"{c}_pour"] = round(sum(pour) / len(pour), 2)
        if contre and c != "possession":
            out[f"{c}_contre"] = round(sum(contre) / len(contre), 2)
    bp = [m["bd"] if _n(m["dom"]) == e else m["be"] for m in sel]
    bc = [m["be"] if _n(m["dom"]) == e else m["bd"] for m in sel]
    out["buts_pour"] = round(sum(bp) / len(bp), 2); out["buts_contre"] = round(sum(bc) / len(bc), 2)
    if "xg_pour" in out:
        out["ecart_buts_xg"] = round(out["buts_pour"] - out["xg_pour"], 2)  # > 0 : marque plus que ses occasions
    return out


if __name__ == "__main__":
    print(json.dumps(moyennes(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10), ensure_ascii=False, indent=1))
