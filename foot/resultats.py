"""Intègre des résultats (Elo + resultats_live.csv).

python3 resultats.py resultats.json
resultats.json : [{date, comp (E0…B1, UCL, UEL, UECL), dom, ext, bd, be, pays_dom?, pays_ext?, neutre?, tc_dom?, tc_ext?}]
(tc = tirs cadrés de chaque équipe : à remplir dès qu'on les a, ils alimentent la forme aux tirs cadrés)
Les doublons (même date, mêmes clubs) sont ignorés. Affiche chaque mise à jour.
"""
import json, sys
from elo import maj

if __name__ == "__main__":
    rs = sorted(json.load(open(sys.argv[1])), key=lambda r: r["date"])
    for r in rs:
        # les championnats sont déjà intégrés jusqu'au 22/11/2026 via les classements ESPN
        if r["comp"] not in ("UCL", "UEL", "UECL") and r["date"] <= "2026-11-22":
            print(f"{r['date']} {r['comp']} {r['dom']}–{r['ext']} : ignoré (déjà dans la base du 22/11)")
            continue
        d = maj(r["date"], r["comp"], r["dom"], r["ext"], int(r["bd"]), int(r["be"]),
                r.get("pays_dom"), r.get("pays_ext"), r.get("neutre", False), r.get("tc_dom"), r.get("tc_ext"))
        print(f"{r['date']} {r['comp']:<5} {r['dom']} {r['bd']}-{r['be']} {r['ext']} : "
              + ("déjà intégré" if d is None else f"{d:+.1f} pts d'Elo pour {r['dom']}"))
