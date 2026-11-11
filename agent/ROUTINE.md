# Routine du matin de l'Agent Tennis

Cette routine est lancée chaque matin vers 8 h 40 (heure de Paris) par une tâche planifiée.
Elle met à jour la page « Agent Tennis » (artefact claude.ai) :
`https://claude.ai/artifact/BsY8JZsWu9VTGpaWPXJPJo` (slug `5809c1d2-e8e8-4936-a77a-68b05e01f228`).

Langue : tout ce qui est écrit dans la base de la page est en **français**.

## Base de données de la page (outils `db_*` du serveur claude-artifacts, avec le slug ci-dessus)

| Chemin | Contenu |
| --- | --- |
| `matchs/{id}` | un match : `id, date (AAAA-MM-JJ), tour (atp/wta), tournoi, categorie, surface (Hard/Clay/Grass), conditions (indoor/outdoor), tour_tableau, heure, joueur_a, joueur_b, proba_elo, proba_modele, ajustement, ajustement_raison, proba_a (probabilité finale), favori, confiance, facteurs_a, facteurs_b, h2h, impacts[], raisons[], lecture, resultat {vainqueur, score} ou null, correct (true/false/null)` |
| `jours/{date}` | `date, matchs (nombre), resume` (2 à 3 phrases sur la journée) |
| `meta/bilan` | contenu de `agent/data/stats.json` |
| `meta/modele` | `donnees_jusqu_a, mise_a_jour, prochaine, version, backtest` (garder `backtest` tel quel) |
| `classements/atp`, `classements/wta` | `maj, lignes[]` : 120 premières lignes de `rankings` produites par `predict.py` |

Chaque `db_write` sur un document existant demande `ifVersion` : lire le document (`db_get`, `db_query`) juste avant.
Un appel `db_write` doit rester sous 64 Ko : découper si besoin (au plus 10 matchs par appel).

## Étapes

1. **Préparer** : `git clone https://github.com/nachotropico-maker/tennis-sackmann-archive` (profondeur 1), puis `pip install pandas` si besoin.
   Travailler dans `agent/`.
2. **Résultats d'hier** : `db_query` sur `matchs` avec `date == hier`. Pour chaque match, trouver le vainqueur et le score
   avec l'outil de scores sportifs (`fetch_sports_data`, tennis), sinon par recherche web sur des sources fiables (sites ATP/WTA, ESPN, presse).
   - Écrire `resultat: {vainqueur, score}` et `correct` (le favori a-t-il gagné ?) dans chaque document `matchs/{id}`.
   - Abandon en cours de match : compter le vainqueur officiel et ajouter « ab. » au score. Forfait avant le match : `resultat: {vainqueur: null, score: "forfait"}`, `correct: null`.
   - Écrire ces résultats dans un fichier JSON (champs : `date, id, tour, tournoi, surface, tour_tableau, joueur_a, joueur_b, proba_a, proba_modele, ajustement, vainqueur, score` ; le score au format « 6-4 3-6 7-6 », avec « RET » en cas d'abandon)
     et lancer `python agent/record.py fichier.json`. Cela ajoute les matchs à `agent/data/{tour}_live.csv` (pour l'Elo),
     au journal `agent/data/predictions_log.csv`, et recalcule `agent/data/stats.json`.
   - Écrire le contenu de `agent/data/stats.json` dans `meta/bilan`.
   - Ne jamais inventer un résultat : si un résultat reste introuvable, laisser `resultat: null` et le signaler dans le résumé du jour.
3. **Programme du jour** : lister les matchs de **simple** du circuit principal prévus aujourd'hui
   (Grands Chelems, ATP/WTA Finals, Masters 1000, WTA 1000, ATP/WTA 500 et 250 ; pas de Challengers, ITF, UTR ni double).
   Sources : `fetch_sports_data` (tennis, scores : statut `scheduled`) et les programmes officiels (« order of play ») trouvés par recherche web.
   Pour chaque match : `tour, tournoi, categorie, surface, conditions, tour_tableau, heure` (heure de Paris), `joueur_a, joueur_b`,
   `code_tour` (R128, R64, R32, R16, QF, SF, F ou RR), `niveau` (G Grand Chelem, M Masters/WTA 1000, A 250/500, F Finals),
   `pays` (code à 3 lettres du pays du tournoi, ex. FRA, USA, SWE), `sets_gagnants_max` (5 pour les Grands Chelems masculins, sinon 3), et un `id`
   de la forme `AAAA-MM-JJ-tour-tournoi-nomA-nomB` (minuscules, tirets, sans accents).
   Les matchs dont un joueur est encore à déterminer sont laissés de côté.
4. **Calcul** : écrire la liste dans `jour.json` et lancer `python agent/predict.py jour.json sortie.json` (environ 1 minute).
   Le script recalcule l'Elo et les 20 critères (historique + résultats ajoutés), applique les poids de `agent/data/poids.json`
   et renvoie pour chaque match `proba_elo`, `proba_modele`, les `impacts` de chaque critère (en points), les facteurs et des raisons.
   Ne pas relancer `fit.py` (réapprentissage des poids) sans demande de l'utilisateur.
5. **Actualité, ajustement et explication** : pour chaque match, vérifier par une recherche web rapide l'actualité
   (blessure ou gêne annoncée, abandon récent, forfait, conditions météo extrêmes, enjeu particulier : qualification, élimination déjà acquise).
   - **Ajustement de l'agent** : seulement si une information vérifiée, absente des données, change vraiment la donne.
     `ajustement` = nombre entier de points de pourcentage pour joueur_a, entre -5 et +5 (0 par défaut, et c'est le cas le plus fréquent).
     `ajustement_raison` = une phrase qui cite le fait vérifié. `proba_a` = `proba_modele` + `ajustement`/100, borné entre 0,03 et 0,97 ;
     recalculer `favori` et `confiance` en conséquence (Serré < 55 %, Léger avantage < 65 %, Favori net < 80 %, sinon Large favori).
     Ne jamais ajuster sur une intuition, une rumeur ou un critère déjà calculé (forme, fatigue, face-à-face…).
   - **Lecture** : 2 à 3 phrases en français, fondées sur `impacts` (les 2 ou 3 critères qui pèsent le plus, avec les chiffres des facteurs)
     et sur l'actualité vérifiée. Les nombres s'écrivent à la française (virgule décimale).
6. **Publier** : écrire chaque match dans `matchs/{id}` (avec `date`, `lecture`, `resultat: null`, `correct: null`),
   puis `jours/{date}` avec un `resume` de 2 à 3 phrases, puis mettre à jour `meta/modele`
   (`donnees_jusqu_a` = valeur `meta` de `sortie.json`, `mise_a_jour` = « 12 nov. à 8 h 45 » par exemple, `prochaine` = demain 8 h 40).
   Le lundi, mettre aussi à jour `classements/atp` et `classements/wta`.
7. **Sauvegarder** : `git add agent/data && git commit -m "Résultats du AAAA-MM-JJ" && git push`.
   Si le push est refusé, le dire dans le compte rendu : les résultats restent dans la page, mais l'Elo ne les gardera pas d'un jour à l'autre.
8. **Compte rendu** : envoyer à l'utilisateur un court message en français : bilan d'hier (x/y pronostics justes), nombre de matchs du jour,
   les 2 ou 3 matchs les plus intéressants, et tout problème rencontré.

Jour sans match du circuit principal : écrire quand même `jours/{date}` avec `matchs: 0` et un résumé d'une phrase.
