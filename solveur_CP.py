''' Solveur CP-SAT (OR-Tools) pour le jeu LYNE

Formulation : au lieu de construire les chemins pas à pas, on choisit un
ensemble d'arêtes colorées (une couleur = une forme) tel que :
  - une case de forme a 2 arêtes de sa couleur (1 pour une extrémité) ;
  - une case numérotée "k" a 2k arêtes, et un nombre pair par couleur ;
  - deux diagonales qui se croisent ne sont jamais prises ensemble ;
  - pour chaque couleur, les arêtes forment un seul morceau connexe
    (contrainte de flot depuis une des extrémités).
Un graphe connexe dont seules les deux extrémités sont de degré impair admet
un chemin eulérien entre elles : on le reconstruit avec Hierholzer.

Usage :
  python solveur_CP.py f-01 y-13      # résout et affiche des niveaux
  python solveur_CP.py --all          # résout et vérifie les 650 niveaux
'''

import json
import sys
import time
from collections import defaultdict

from ortools.sat.python import cp_model

## Légende (identique à solver.py) :
# d|s|t - losange | carré | triangle
# D|S|T - même chose, extrémité d'un chemin
# 2|3|4 - case sans forme à traverser ce nombre de fois
# [espace] - pas de case

PUZZLE_FILE = "puzzles.json"

DIRECTIONS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
]


class LyneModel:
    ''' Graphe du niveau (cases, arêtes, croisements) '''

    def __init__(self, puzzle_text):
        # Cases : position (ligne, colonne) -> caractère
        self.cells = {
            (row, col): char
            for row, line in enumerate(puzzle_text)
            for col, char in enumerate(line)
            if char != " "
        }
        self.positions = sorted(self.cells)
        self.index = {pos: i for i, pos in enumerate(self.positions)}

        # Forme de chaque case (None pour une case numérotée)
        self.shape = [
            None if c.isdigit() else c.lower()
            for c in (self.cells[p] for p in self.positions)
        ]
        self.visits = [
            int(c) if c.isdigit() else 1
            for c in (self.cells[p] for p in self.positions)
        ]
        self.is_terminal = [
            self.cells[p].isupper() for p in self.positions
        ]

        # Extrémités par couleur
        self.terminals = defaultdict(list)
        for i, pos in enumerate(self.positions):
            if self.is_terminal[i]:
                self.terminals[self.shape[i]].append(i)
        self.colors = sorted(self.terminals)

        # Arêtes : paires de cases voisines compatibles
        edges = set()
        for pos in self.positions:
            for dr, dc in DIRECTIONS:
                other = (pos[0] + dr, pos[1] + dc)
                if other not in self.cells:
                    continue
                a, b = self.index[pos], self.index[other]
                if self.shape[a] and self.shape[b] and self.shape[a] != self.shape[b]:
                    continue
                edges.add((min(a, b), max(a, b)))
        self.edges = sorted(edges)
        self.edge_index = {e: i for i, e in enumerate(self.edges)}

        # Couleurs possibles pour chaque arête
        self.edge_colors = []
        for a, b in self.edges:
            forced = self.shape[a] or self.shape[b]
            self.edge_colors.append([forced] if forced else list(self.colors))

        # Arêtes incidentes à chaque case
        self.node_edges = defaultdict(list)
        for e, (a, b) in enumerate(self.edges):
            self.node_edges[a].append(e)
            self.node_edges[b].append(e)

        # Paires de diagonales qui se croisent
        self.crossings = []
        for (r, c) in self.positions:
            corners = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
            if not all(p in self.cells for p in corners):
                continue
            tl, tr, bl, br = (self.index[p] for p in corners)
            d1 = self.edge_index.get((min(tl, br), max(tl, br)))
            d2 = self.edge_index.get((min(tr, bl), max(tr, bl)))
            if d1 is not None and d2 is not None:
                self.crossings.append((d1, d2))


def build_model(lm):
    ''' Construit le modèle CP-SAT. Renvoie (modèle, variables y[(arête, couleur)]) '''
    model = cp_model.CpModel()
    n_nodes = len(lm.positions)

    # y[e, c] : l'arête e est utilisée par le chemin de couleur c
    y = {}
    for e, colors in enumerate(lm.edge_colors):
        for c in colors:
            y[e, c] = model.NewBoolVar(f"y_{e}_{c}")
        # Chaque arête sert au plus une fois
        model.AddAtMostOne(y[e, c] for c in colors)

    # active[n, c] : la case n est traversée par le chemin de couleur c
    active = {}

    for n in range(n_nodes):
        incident = lm.node_edges[n]

        if lm.shape[n] is not None:
            c = lm.shape[n]
            degree = 1 if lm.is_terminal[n] else 2
            model.Add(sum(y[e, c] for e in incident) == degree)
            active[n, c] = 1
            continue

        # Case numérotée : 2k arêtes au total, un nombre pair par couleur
        k = lm.visits[n]
        model.Add(
            sum(y[e, c] for e in incident for c in lm.edge_colors[e]) == 2 * k
        )
        for c in lm.colors:
            passes = model.NewIntVar(0, k, f"z_{n}_{c}")
            model.Add(
                sum(y[e, c] for e in incident if c in lm.edge_colors[e]) == 2 * passes
            )
            a = model.NewBoolVar(f"a_{n}_{c}")
            model.Add(passes >= 1).OnlyEnforceIf(a)
            model.Add(passes == 0).OnlyEnforceIf(a.Not())
            active[n, c] = a

    # Diagonales qui se croisent
    for d1, d2 in lm.crossings:
        model.AddAtMostOne(
            [y[d1, c] for c in lm.edge_colors[d1]]
            + [y[d2, c] for c in lm.edge_colors[d2]]
        )

    # Connexité : pour chaque couleur, un flot part d'une extrémité et
    # apporte une unité à chaque case active de cette couleur
    for c in lm.colors:
        root = lm.terminals[c][0]
        members = [n for n in range(n_nodes) if (n, c) in active]
        capacity = len(members)

        inflow = defaultdict(list)
        outflow = defaultdict(list)
        for e, (a, b) in enumerate(lm.edges):
            if c not in lm.edge_colors[e]:
                continue
            for src, dst in ((a, b), (b, a)):
                f = model.NewIntVar(0, capacity, f"f_{c}_{src}_{dst}")
                model.Add(f == 0).OnlyEnforceIf(y[e, c].Not())
                outflow[src].append(f)
                inflow[dst].append(f)

        for n in members:
            if n == root:
                continue
            model.Add(sum(inflow[n]) - sum(outflow[n]) == active[n, c])

    return model, y


def euler_path(lm, used_edges, start):
    ''' Hierholzer : parcours de toutes les arêtes utilisées depuis start '''
    adjacency = defaultdict(list)
    for e in used_edges:
        a, b = lm.edges[e]
        adjacency[a].append((b, e))
        adjacency[b].append((a, e))

    seen = set()
    stack = [start]
    path = []
    while stack:
        node = stack[-1]
        while adjacency[node] and adjacency[node][-1][1] in seen:
            adjacency[node].pop()
        if adjacency[node]:
            nxt, e = adjacency[node].pop()
            seen.add(e)
            stack.append(nxt)
        else:
            path.append(stack.pop())
    return path[::-1]


def solve(puzzle_text, time_limit=10, workers=8):
    ''' Résout un niveau.
    Renvoie (solution, infos) ; solution au format de solver.py :
    [[(col, ligne), ...], ...] ou None si pas de solution trouvée.
    '''
    lm = LyneModel(puzzle_text)
    model, y = build_model(lm)

    cp_solver = cp_model.CpSolver()
    cp_solver.parameters.max_time_in_seconds = time_limit
    cp_solver.parameters.num_workers = workers
    status = cp_solver.Solve(model)

    infos = {
        "status": cp_solver.StatusName(status),
        "wall_time": cp_solver.WallTime(),
        "branches": cp_solver.NumBranches(),
        "conflicts": cp_solver.NumConflicts(),
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, infos

    solution = []
    for c in lm.colors:
        used = [e for e, colors in enumerate(lm.edge_colors)
                if c in colors and cp_solver.Value(y[e, c])]
        nodes = euler_path(lm, used, lm.terminals[c][0])
        solution.append([
            (lm.positions[n][1], lm.positions[n][0]) for n in nodes
        ])
    return solution, infos


def verify(puzzle_text, solution):
    ''' Vérifie une solution indépendamment du modèle.
    Renvoie (True, "") ou (False, raison).
    '''
    cells = {
        (col, row): char
        for row, line in enumerate(puzzle_text)
        for col, char in enumerate(line)
        if char != " "
    }
    terminals = {p for p, ch in cells.items() if ch.isupper()}
    colors = {cells[p].lower() for p in terminals}

    if solution is None or len(solution) != len(colors):
        return False, "nombre de chemins incorrect"

    used_edges = set()
    visits = defaultdict(int)
    seen_colors = set()

    for path in solution:
        path = [tuple(p) for p in path]
        if len(path) < 2:
            return False, "chemin trop court"
        start, end = path[0], path[-1]
        if start not in terminals or end not in terminals or start == end:
            return False, f"extrémités invalides {start} {end}"
        color = cells[start].lower()
        if cells[end].lower() != color or color in seen_colors:
            return False, f"extrémités de couleurs incohérentes {start} {end}"
        seen_colors.add(color)

        for p in path:
            if p not in cells:
                return False, f"case inexistante {p}"
            if not cells[p].isdigit() and cells[p].lower() != color:
                return False, f"case {p} de mauvaise forme"

        for p, q in zip(path, path[1:]):
            if max(abs(p[0] - q[0]), abs(p[1] - q[1])) != 1:
                return False, f"cases non voisines {p} {q}"
            edge = frozenset((p, q))
            if edge in used_edges:
                return False, f"arête utilisée deux fois {p} {q}"
            used_edges.add(edge)

        for p in path[1:-1]:
            visits[p] += 1
        visits[start] += 1
        visits[end] += 1

    for p, ch in cells.items():
        required = int(ch) if ch.isdigit() else 1
        if visits[p] != required:
            return False, f"case {p} visitée {visits[p]} fois au lieu de {required}"

    # Diagonales croisées
    for edge in used_edges:
        p, q = sorted(edge)
        if abs(p[0] - q[0]) == 1 and abs(p[1] - q[1]) == 1:
            other = frozenset(((p[0], q[1]), (q[0], p[1])))
            if other in used_edges:
                return False, f"diagonales croisées en {p} {q}"

    return True, ""


def main():
    with open(PUZZLE_FILE, "r", encoding="utf-8") as f:
        puzzles = {p["name"]: p["puzzle"] for p in json.load(f)}

    args = sys.argv[1:] or ["f-01"]

    if args == ["--all"]:
        start = time.perf_counter()
        solved = 0
        for name, puzzle_text in puzzles.items():
            solution, infos = solve(puzzle_text)
            ok, reason = verify(puzzle_text, solution)
            solved += ok
            if not ok:
                print(f"{name}: ÉCHEC ({infos['status']}) {reason}")
        elapsed = time.perf_counter() - start
        print(f"Résolus et vérifiés : {solved} / {len(puzzles)} en {elapsed:.1f}s")
        return

    for name in args:
        puzzle_text = puzzles[name]
        print(f"\n{name}")
        for line in puzzle_text:
            print(f"  {line}")
        solution, infos = solve(puzzle_text)
        ok, reason = verify(puzzle_text, solution)
        print(f"Statut : {infos['status']}, temps : {infos['wall_time']:.3f}s, "
              f"vérification : {'OK' if ok else reason}")
        for path in solution or []:
            print(path)


if __name__ == "__main__":
    main()
