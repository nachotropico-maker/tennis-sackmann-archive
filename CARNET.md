# Carnet de bord du projet (Agent Tennis + Agent Foot)

Notes de la conversation de développement, pour reprendre le fil dans n'importe quelle conversation.
L'utilisateur est francophone, suit tout depuis son téléphone, et veut **comprendre** le sport, pas parier.
Le **tennis est le sujet principal** de la conversation de développement (décidé le 24/11/2026).

## Ce qui tourne tout seul
- **Agent Tennis** : page https://claude.ai/artifact/BsY8JZsWu9VTGpaWPXJPJo (slug 5809c1d2-e8e8-4936-a77a-68b05e01f228).
  Tâche planifiée trig_01WphPXSuprpFbyGGYR6fWcj, 8 h 40 (Paris) : routine `agent/ROUTINE.md`, puis conversation du jour.
- **Agent Foot** : page https://claude.ai/artifact/2uZ8SEppTThr2bp9F1KGMQ (slug 0f6f9d49-7112-44f9-864d-07547f0a6ecb).
  Tâche planifiée trig_01PbtsJPXpwqPJMmpaiQv5Mb, 8 h 50 : routine `foot/ROUTINE.md`, puis conversation Foot du jour.
- **GitHub Action** `.github/workflows/api-football.yml`, 6 h 15 : API-Football (offre gratuite, 100 requêtes/jour,
  clé dans le secret API_FOOTBALL_KEY, jamais dans le chat) -> `foot/data/apifootball/`.

## Tennis : décisions et leçons
- Modèle : Elo global + surface, 20 critères appris sur 2012-2022 (`data/poids.json`). Ajustement de l'agent ±5 pts, seulement sur faits vérifiés.
- Bilan au 22/11/2026 : 28/34. Le 17/11 compte 1/2 (l'agent avait Jodar).
- Règles ajoutées après discussion : alerte physique seulement si confirmée (déclaration rassurante = pas d'ajustement) ;
  reprise après longue pause, série de défaites, premier match après un titre affichés ;
  BJK Cup / Coupe Davis : simples conditionnels quand le double passe en premier à 2-0 (leçon du 22/11 : 6 simples annulés).
- Tests faits : fatigue des qualifiés, premier match du tournoi, retour vs service selon la vitesse du court
  (retour > service seulement sur dur vraiment lent ; court moyen = service ~2× plus important).
- Coupe Davis 2026 : Bologne, nouvelle salle, dur indoor « légèrement plus lent que Turin » (SuperTennis) -> court moyen.
- Pronostics de l'utilisateur : `agent/data/pronos_utilisateur.csv` (duel utilisateur vs agent).
- Feuille de route décembre (`agent/ROADMAP.md`) : United Cup (entry list dans `agent/data/united_cup_2027_entry_list.csv`),
  premier match de la saison, chaleur en Australie, blessures et changements de coach, jeunes en progression, points derrière la 1re balle.

## Foot : décisions et leçons
- Pronostics publiés : Big Five, Süper Lig, Ligue des champions, Ligue Europa, Ligue Conférence (choix du 24/11).
  Eredivisie, Liga Portugal, Pro League : résultats en arrière-plan seulement (niveau des clubs en Coupe d'Europe).
- Modèle v3 : Elo des clubs (échelle ClubElo) + forme aux tirs cadrés et tirs (5 matchs) + volume de buts. Test 2023-2025 : 53,0 % (bookmakers 54,4 %).
- Testés et NON retenus : avantage du terrain par club, profil à l'extérieur, repos, face-à-face, enjeu au classement, corners.
- Favori < 45 % : juste ~4 fois sur 10 -> la page affiche la double chance.
- Règle d'ajustement stricte (leçon Brentford 4-0 Everton) : ≥ 3 titulaires absents, gardien absent, entraîneur limogé < 10 j, équipe B.
- Vérifier pour chaque équipe un changement d'entraîneur depuis le début de saison (leçon Çorum / Burak Yılmaz).
- xG, xGOT, compositions, notes des joueurs : via API-Football, en contexte seulement (pas dans les probabilités) tant qu'il n'y a pas assez d'historique.
- Pas de collecte automatique sur Flashscore / Sofascore / FotMob / FBref (interdite par leurs règles).
