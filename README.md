# LYNE : solveur par programmation par contraintes

> **English summary.** Fork of [gamescomputersplay/lyne](https://github.com/gamescomputersplay/lyne).
> `solveur_CP.py` solves LYNE with constraint programming (Google OR-Tools CP-SAT):
> all 650 levels of the game are solved and verified, the hardest one in about 0.1 s.
> `bot_CP.py` plays the solution in the real game. Quick start: `pip install -r requirements.txt`
> then `python solveur_CP.py --all`.

## D'où vient le projet

Ce dépôt est un fork de [gamescomputersplay/lyne](https://github.com/gamescomputersplay/lyne), le solveur et bot LYNE présenté dans une vidéo de la chaîne YouTube *Games Computers Play*. Le projet d'origine lit le niveau depuis une capture d'écran (`read_lyne_pyzzle.py`), le résout par une recherche dans l'espace des chemins partiels (`solver.py`), puis joue la solution à la souris (`bot.py`).

On y a ajouté un autre solveur, fondé sur la **programmation par contraintes**, et un banc d'essai qui le compare à d'autres solveurs LYNE publiés sur GitHub.

## Notre solveur : `solveur_CP.py`

Au lieu de construire les chemins case par case, le modèle choisit **un ensemble d'arêtes colorées** (une couleur par forme) qui respecte les règles :

- une case de forme a 2 arêtes de sa couleur (1 seule si c'est une extrémité) ;
- une case numérotée `k` a 2k arêtes, avec un nombre pair d'arêtes de chaque couleur ;
- deux diagonales qui se croisent ne sont jamais prises ensemble ;
- les arêtes de chaque couleur forment un seul morceau connexe (contrainte de flot partant d'une extrémité).

Un graphe connexe dont seules les deux extrémités sont de degré impair admet un chemin eulérien entre elles. Le chemin de chaque couleur est donc reconstruit ensuite avec l'algorithme de Hierholzer. La résolution du modèle est confiée à [OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver).

**Résultat :** les 650 niveaux du jeu sont tous résolus et vérifiés, en 16 ms en médiane. Le niveau le plus long (`z-05`) prend 0,11 s, et l'ensemble environ 14 s.

## Installation

Python 3.10 ou plus récent :

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt
```

## Utilisation

```bash
python solveur_CP.py f-01 z-05     # résout et affiche des niveaux de puzzles.json
python solveur_CP.py --all         # résout et vérifie les 650 niveaux du jeu
```

**Bot dans le vrai jeu** (Windows, jeu LYNE ouvert et visible à l'écran) :

```bash
python bot_CP.py
```

Affiche un niveau dans le jeu puis appuie sur **F10** : le bot lit l'écran, résout le niveau avec `solveur_CP.py` et trace la solution. **Échap** pour quitter. `bot.py` fait la même chose avec le solveur d'origine.

## Banc d'essai contre d'autres solveurs

Pour situer la méthode, on a récupéré d'autres solveurs LYNE publiés sur GitHub (Z3/SMT, backtracking en JavaScript et en Rust, propagation de règles en Java). Le dossier [`autres_bots/`](autres_bots/README.md) les décrit, avec la manière dont chacun est lancé et la marche à suivre pour les installer. Les dépôts tiers ne sont pas redistribués ici : `autres_bots/construire.py` les clone et les compile.

Le dossier `benchmark/` contient :

- `generateur.py` : génère des niveaux solubles de taille N×N arbitraire (on trace d'abord une solution, puis on en déduit le niveau) ;
- `bots.py` : lance chaque solveur dans son propre processus avec une limite de temps, puis revérifie sa solution de façon indépendante ;
- `bench.py` : fait grandir la taille des grilles jusqu'à ce que chaque solveur décroche ;
- `resultats/` : les résultats obtenus.

```bash
python benchmark/bench.py --jeu --timeout 10     # les 650 niveaux du jeu
python benchmark/bench.py --bots cp8 upstream --tailles 4-12 --timeout 60
python benchmark/bench.py --resume               # tableau récapitulatif
```

## Organisation des fichiers

| Fichier | Rôle |
|---|---|
| `solveur_CP.py` | **notre solveur** CP-SAT, avec `verify()` pour contrôler une solution |
| `bot_CP.py` | bot qui joue la solution de `solveur_CP.py` dans le jeu |
| `benchmark/`, `autres_bots/` | banc d'essai et adaptateurs des solveurs tiers |
| `solver.py`, `bot.py` | solveur et bot du projet d'origine |
| `read_lyne_pyzzle.py` | lecture d'un niveau depuis une capture d'écran (origine) |
| `puzzles.json`, `solutions.json` | les 650 niveaux du jeu et les solutions du projet d'origine |
| `batch_solver.py`, `data_visualization.py`, `draw_solutions*.py` | statistiques et images du projet d'origine |

## Licence

MIT, comme le projet d'origine (voir `LICENSE`). Les solveurs tiers clonés dans `autres_bots/` gardent leur propre licence.
