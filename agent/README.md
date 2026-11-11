# Agent Tennis

Modèle Elo (global + par surface) pour les circuits ATP et WTA, avec explications par match.
Page de résultats : https://claude.ai/artifact/BsY8JZsWu9VTGpaWPXJPJo

- `engine.py` : chargement des données, calcul de l'Elo, facteurs explicatifs affichés.
- `features.py` : les 20 critères du modèle complet (service/retour, balles de break, forme, tie-breaks, sets décisifs, fatigue, pause, 5 sets, domicile…).
- `fit.py` : apprend les poids des critères (2012-2022) et les teste (2023-2026) ; écrit `data/poids.json`.
- `predict.py` : probabilités et raisons pour une liste de matchs.
- `record.py` : enregistre les résultats, alimente l'Elo et le bilan.
- `ROUTINE.md` : la mise à jour automatique de chaque matin.
- `data/` : résultats 2026 (tennis-data.co.uk, jusqu'au 8 nov.), résultats ajoutés chaque jour, journal des pronostics.

## Réglages validés

| | ATP | WTA |
| --- | --- | --- |
| Poids de l'Elo surface | 40 % | 30 % |
| Poids des Challengers / qualifications | 60 % | 60 % |
| Facteur de calibration | 0,92 | 0,86 |
| Pronostics justes, test 2024 – nov. 2026 | 65,1 % | 65,3 % |
| Grands Chelems | 71,5 % | 70,5 % |
| Modèle sur les matchs 2026 | 65,3 % | 66,2 % |
| Bookmakers 2026 (mêmes matchs) | 67,6 % | 68,9 % |

`python agent/backtest.py` refait ce test (Elo seul).

## Modèle complet (Elo + 20 critères, poids appris)

| Test 2023 – 8 nov. 2026 | ATP | WTA |
| --- | --- | --- |
| Elo seul | 65,2 % | 65,8 % |
| Modèle complet | 65,8 % | 66,3 % |
| Modèle complet, Grands Chelems | 71,8 % | 71,2 % |

Les critères qui pèsent le plus après l'Elo : matchs et minutes des 7 derniers jours, points gagnés au service,
forme pondérée par l'adversaire, sets décisifs et tie-breaks (une réussite exceptionnelle y est légèrement pénalisée).
Styles de jeu (Serveur / Relanceur) testés seuls : aucun gain, donc gardés uniquement croisés avec la vitesse du court.

Réglages choisis sur 2015-2023, testés sur des matchs jamais vus (2024 – 8 nov. 2026).
Les critères affichés mais non calculés (forme, fatigue, retour de titre, face-à-face) n'entreront dans la probabilité
que s'ils améliorent ce test.

Données historiques : Jeff Sackmann, licence CC BY-NC-SA 4.0. Usage non commercial.
