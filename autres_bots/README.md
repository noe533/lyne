# Autres solveurs LYNE trouvés en ligne

Ce dossier sert à comparer notre modèle CP-SAT (`solveur_CP.py`) à d'autres solveurs LYNE publiés.
Les dépôts sont clonés ici sans modification. Seuls les petits programmes de `adaptateurs/` sont à nous : ils font lire un niveau à chaque bot et récupèrent sa solution.

| Bot | Langage | Méthode | Dernier commit |
|---|---|---|---|
| [gamescomputersplay/lyne](https://github.com/gamescomputersplay/lyne) (`solver.py`, le dépôt dont on est partis) | Python | Recherche dans l'espace des états partiels (DFS avec redémarrages, cache d'états) | 2026 |
| [arlencox/lyne-solver](https://github.com/arlencox/lyne-solver) | OCaml → SMT-LIB → **Z3** | Chaque arête orientée porte (couleur, rang). Les cases numérotées énumèrent toutes les façons d'apparier les arêtes entrantes et sortantes, d'où une formule exponentielle en k. | 2015 |
| [denilsonsa/lyne-solver](https://github.com/denilsonsa/lyne-solver) ([version en ligne](https://denilsonsa.github.io/lyne-solver/lyne-solver.html)) | JavaScript | Backtracking brut : les chemins sont prolongés une arête à la fois, sans aucun élagage | 2023 |
| [jbosboom/lynebot](https://github.com/jbosboom/lynebot) | Java (+ Guava) | Propagation de règles locales (degrés, croisements, couleurs) jusqu'au point fixe, puis branchement sur l'arête la plus contrainte (proche d'un solveur de contraintes fait main) | 2014 |
| [yahvk-cuna/lyne_solver](https://github.com/yahvk-cuna/lyne_solver) | Rust | Backtracking couleur par couleur. Les cases numérotées ne sont vérifiées qu'à la fin. | 2023 |

Autres pistes non retenues : le [guide Steam « LYNE solver and hint generator »](https://steamcommunity.com/sharedfiles/filedetails/?id=451090114) décrit un solveur web open source qui révèle la solution trait par trait, ce qui correspond au solveur de denilsonsa (page non consultable directement, Steam a répondu HTTP 429).

## Comment chaque bot est lancé

| Bot | Adaptateur | Remarque |
|---|---|---|
| arlencox | `adaptateurs/arlencox_z3.py` | `encode.ml` se contente d'écrire un fichier `.smt2` puis d'appeler `z3`. L'adaptateur reproduit sa fonction `emit` ligne à ligne en Python (même formule) et la passe à Z3 via `pip install z3-solver`. On évite ainsi d'installer OCaml. |
| denilsonsa | `adaptateurs/denilsonsa.js` | Charge `shared.js`, `algorithm.js` et le parseur de `ui.js` dans Node, sans navigateur. |
| jbosboom | `adaptateurs/LyneBench.java` | Le parseur d'origine ne gère pas les trous : la grille est construite directement avec `null`. `Effector.java` (capture d'écran) n'est pas compilé. |
| yahvk | aucun, on appelle directement l'exécutable | Couleurs r/g/b au lieu de d/s/t et `.` pour un trou : la conversion se fait dans `benchmark/bots.py`. |

## Installation

```powershell
winget install OpenJS.NodeJS.LTS                  # denilsonsa
winget install EclipseAdoptium.Temurin.21.JDK     # jbosboom
winget install Rustlang.Rustup                    # yahvk
rustup toolchain install stable-x86_64-pc-windows-gnu
rustup default stable-x86_64-pc-windows-gnu
.venv\Scripts\pip install z3-solver               # arlencox
.venv\Scripts\python autres_bots\construire.py    # clone + compile
.venv\Scripts\python benchmark\bots.py            # liste des bots prêts
```

## Licences

Les dépôts clonés gardent leur licence (GPL-3 pour lynebot, AGPL-3 pour yahvk-cuna, MIT pour les autres). Ils sont dans `.gitignore` et ne sont donc pas redistribués avec ce projet.
