''' Générateur de niveaux LYNE solubles, de taille arbitraire

On construit d'abord une solution, puis on en déduit le niveau :
  - chaque couleur trace un chemin par marche aléatoire (arêtes jamais
    réutilisées, pas de diagonales croisées, extrémités jamais revisitées) ;
  - une case traversée une seule fois devient une forme de la couleur
    (majuscule aux deux bouts du chemin) ;
  - une case traversée k >= 2 fois devient une case numérotée "k" ;
  - une case jamais traversée devient un trou.
Le niveau obtenu a donc au moins une solution (celle qu'on vient de tracer).

Réglages par défaut calés sur les 650 niveaux du jeu : 3 couleurs,
~28 % de cases numérotées (surtout des 2), ~3 % de trous.

Usage :
  python benchmark/generateur.py 6        # affiche un niveau 6x6
'''

import random
import sys

DIRECTIONS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
]
COLORS = "dst"
MAX_VISITS = 4


def _crossing(p, q):
    ''' Diagonale qui croise l'arête p-q (None si p-q n'est pas diagonale) '''
    if p[0] == q[0] or p[1] == q[1]:
        return None
    return frozenset(((p[0], q[1]), (q[0], p[1])))


def _try_generate(rows, cols, n_colors, revisit_rate, rng):
    ''' Une tentative : renvoie (niveau, solution) ou None '''
    cells = [(r, c) for r in range(rows) for c in range(cols)]
    visits = {p: 0 for p in cells}
    used = set()
    terminals = set()
    paths = []
    target = rows * cols / n_colors

    def moves(p):
        for dr, dc in DIRECTIONS:
            q = (p[0] + dr, p[1] + dc)
            if q not in visits or q in terminals or visits[q] >= MAX_VISITS:
                continue
            edge = frozenset((p, q))
            if edge in used or _crossing(p, q) in used:
                continue
            yield q

    def free_degree(q):
        return sum(1 for r in moves(q) if visits[r] == 0)

    for _ in range(n_colors):
        fresh = [p for p in cells if visits[p] == 0]
        if not fresh:
            return None
        # Démarrer près d'un bord aide à couvrir la grille
        fresh.sort(key=lambda p: (free_degree(p), rng.random()))
        start = fresh[0] if rng.random() < 0.7 else rng.choice(fresh)
        path = [start]
        visits[start] += 1
        terminals.add(start)
        new_cells = 1

        while new_cells < target * rng.uniform(0.9, 1.3):
            cur = path[-1]
            options = list(moves(cur))
            if not options:
                break
            unvisited = [q for q in options if visits[q] == 0]
            if unvisited and rng.random() >= revisit_rate:
                # Warnsdorff : aller d'abord vers les cases les plus coincées
                unvisited.sort(key=lambda q: (free_degree(q), rng.random()))
                nxt = unvisited[0] if rng.random() < 0.8 else rng.choice(unvisited)
            else:
                nxt = rng.choice(options)
            used.add(frozenset((cur, nxt)))
            new_cells += visits[nxt] == 0
            visits[nxt] += 1
            path.append(nxt)

        # L'extrémité doit être une case traversée une seule fois
        while len(path) > 1 and visits[path[-1]] > 1:
            last = path.pop()
            visits[last] -= 1
            used.discard(frozenset((path[-1], last)))
        if len(path) < 3:
            return None
        terminals.add(path[-1])
        paths.append(path)

    # Construction du texte du niveau
    grid = [[" "] * cols for _ in range(rows)]
    for color, path in zip(COLORS, paths):
        for p in path:
            if visits[p] == 1:
                grid[p[0]][p[1]] = color
        grid[path[0][0]][path[0][1]] = color.upper()
        grid[path[-1][0]][path[-1][1]] = color.upper()
    for p, v in visits.items():
        if v >= 2:
            grid[p[0]][p[1]] = str(v)

    puzzle = ["".join(line) for line in grid]
    solution = [[(c, r) for r, c in path] for path in paths]
    return puzzle, solution


def generate(rows, cols=None, seed=0, n_colors=3, revisit_rate=0.35,
             max_holes=0.05, numbered_range=(0.18, 0.38), attempts=20000):
    ''' Génère un niveau rows x cols soluble et proche des niveaux du jeu.
    Renvoie (niveau, solution) ; niveau = liste de chaînes.
    '''
    cols = cols or rows
    rng = random.Random(f"{rows}x{cols}-{seed}")
    best = None
    for _ in range(attempts):
        result = _try_generate(rows, cols, n_colors, revisit_rate, rng)
        if result is None:
            continue
        text = "".join(result[0])
        holes = text.count(" ") / len(text)
        numbered = sum(ch.isdigit() for ch in text) / len(text)
        if holes <= max_holes and numbered_range[0] <= numbered <= numbered_range[1]:
            return result
        if best is None or holes < best[0]:
            best = (holes, result)
    if best is None:
        raise RuntimeError(f"aucun niveau {rows}x{cols} généré")
    return best[1]


if __name__ == "__main__":
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    puzzle, solution = generate(size, seed=seed)
    for line in puzzle:
        print(line.replace(" ", "."))
    for path in solution:
        print(path)
