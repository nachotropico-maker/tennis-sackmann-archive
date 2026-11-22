# Agent Foot

Pronostics 1N2 expliqués pour 9 championnats (Angleterre, Espagne, Italie, France, Allemagne, Turquie, Pays-Bas, Portugal, Belgique)
et les 3 coupes d'Europe. Page : https://claude.ai/artifact/2uZ8SEppTThr2bp9F1KGMQ — routine quotidienne : `ROUTINE.md`.

- `modele.py` : régression multinomiale (issue 1/N/2) et Poisson (buts) sur l'écart d'Elo, intercept par championnat.
  Test 2023-2025 (8 813 matchs) : 52,7 % de bons pronostics (bookmakers 54,4 %, « domicile gagne » 43,3 %).
- `elo.py` : Elo des clubs, échelle ClubElo commune à l'Europe. Départ : snapshot du 01/09/2026, ajusté par les classements ESPN
  du 22/11/2026 (`data/classements_2026-11-22.csv`), puis mis à jour match par match (`resultats.py`, `data/resultats_live.csv`).
- `noms.py` : correspondance des noms de clubs entre sources. `predict.py` : pronostics. `publier.py` : écritures pour la page.
  `bilan.py` : bilan en conditions réelles.
- Données : `data/matchs_hist.csv` et `data/elo_snapshots.csv` extraits de « Club Football Match Data 2000-2025 »
  (github.com/xgabora, d'après football-data.co.uk et ClubElo).
