# Agent Tennis

Modèle Elo (global + par surface) pour les circuits ATP et WTA, avec explications par match.
Page de résultats : https://claude.ai/artifact/BsY8JZsWu9VTGpaWPXJPJo

- `engine.py` : chargement des données, calcul de l'Elo, facteurs explicatifs (forme, fatigue, face-à-face, retour de titre).
- `predict.py` : probabilités et raisons pour une liste de matchs.
- `record.py` : enregistre les résultats, alimente l'Elo et le bilan.
- `ROUTINE.md` : la mise à jour automatique de chaque matin.
- `data/` : résultats 2026 (tennis-data.co.uk, jusqu'au 8 nov.), résultats ajoutés chaque jour, journal des pronostics.

## Réglages validés

| | ATP | WTA |
| --- | --- | --- |
| Poids de l'Elo surface | 40 % | 30 % |
| Facteur de calibration | 0,76 | 0,76 |
| Pronostics justes, test 2024 – nov. 2026 | 64,0 % | 64,8 % |
| Grands Chelems | 70,1 % | 69,8 % |
| Bookmakers 2026 (même période) | 67,6 % | 68,9 % |

Réglages choisis sur 2015-2023, testés sur des matchs jamais vus (2024 – 8 nov. 2026).
Les critères affichés mais non calculés (forme, fatigue, retour de titre, face-à-face) n'entreront dans la probabilité
que s'ils améliorent ce test.

Données historiques : Jeff Sackmann, licence CC BY-NC-SA 4.0. Usage non commercial.
