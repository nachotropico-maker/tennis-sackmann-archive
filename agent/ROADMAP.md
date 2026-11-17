# Idées pour l'intersaison (décembre 2026)

À reprendre en décembre, quand les tableaux de la United Cup seront connus.

1. **Premier match de la saison** (entry list United Cup 2027 : data/united_cup_2027_entry_list.csv) : les favoris se font-ils plus souvent surprendre à la reprise de janvier
   (United Cup, Brisbane, Hong Kong, Auckland, Adélaïde) ? Test sur toutes les reprises depuis 2012.
   Exemple : Fritz battu par Baez à la United Cup 2026 alors qu'il était donné à 88 %.
2. **Chaleur en Australie** : joueurs en difficulté au-delà de 35 °C ; effet du toit fermé.
3. **Blessures et changements d'entraîneur pendant l'intersaison** (enquête de contexte).
   Test à faire : après un changement d'entraîneur, le joueur fait-il mieux que prévu, et au bout de combien de temps ?
   Cas à suivre : Shelton avec Juan Carlos Ferrero à partir des ATP Finals 2026.
4. **Jeunes en forte progression** : leur Elo est-il en retard sur leur niveau en début de saison ?

Déjà testé (novembre 2026, voir exp_*.py) :
- Qualifiés fatigués face à un adversaire reposé : pas d'effet général ; en quarts de finale, un qualifié avec
  8 sets ou plus face à un adversaire qui en a joué 3 au plus gagne environ 5 points de moins que prévu
  (149 matchs ATP, piste à confirmer).
- Favori à son premier match du tournoi : environ −1 point à l'ATP, aucun effet à la WTA, pas retenu.

5. **Points gagnés derrière la première balle** (idée née aux ATP Finals 2026, Zverev–Shelton) : sur les derniers
   matchs, prédisent-ils mieux que la moyenne de points gagnés au service sur 12 mois ? Séparer 1re et 2e balle
   comme critères distincts, et tester une fenêtre courte (5-10 derniers matchs) contre la fenêtre de 12 mois.
