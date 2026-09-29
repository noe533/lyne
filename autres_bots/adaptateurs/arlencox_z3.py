''' Adaptateur pour arlencox/lyne-solver (encodage SMT résolu par Z3)

encode.ml (OCaml) ne fait qu'écrire le fichier problem.smt2 puis appeler z3.
Ce fichier reproduit ligne à ligne la fonction `emit` d'encode.ml (même
formule SMT-LIB, mêmes contraintes), puis la donne à Z3 via z3-solver.
Seul le générateur de texte change de langage, pas le solveur.

Rappel de l'encodage d'origine :
  - chaque arête orientée u->v porte une paire (path, index) : path = code
    ASCII de la couleur (0 si inutilisée), index = rang de l'arête dans le
    chemin, qui augmente de 1 à chaque case traversée (évite les cycles) ;
  - chaque case numérotée "k" énumère explicitement toutes les façons
    d'associer k arêtes entrantes à k arêtes sortantes (formule de taille
    exponentielle en k).

Usage : python arlencox_z3.py < niveau.json   (liste de lignes)
Sortie : JSON {solved, time, edges: [[l1, c1, l2, c2, couleur], ...]}
'''

import json
import sys
import time

import z3


def parse(lines):
    ''' parse d'encode.ml : 1re majuscule = Start, 2e = End '''
    cols = max(len(l) for l in lines)
    grid = [[("Empty",)] * cols for _ in lines]
    capcount = {}
    for i, s in enumerate(lines):
        for j, ch in enumerate(s):
            if ch == " ":
                continue
            if ch.isdigit():
                grid[i][j] = ("Count", int(ch))
            elif ch.isupper():
                c = ord(ch.lower())
                count = capcount.get(c, 0)
                capcount[c] = count + 1
                grid[i][j] = ("Start", c) if count == 0 else ("End", c)
            else:
                grid[i][j] = ("Shape", ord(ch))
    return grid


def emit(t):
    ''' Traduction directe de `emit` d'encode.ml (sans check-sat/get-value) '''
    rows, cols = len(t), len(t[0])
    out = []
    w = out.append

    def valid_v(v):
        i, j = v
        return 0 <= i < rows and 0 <= j < cols and t[i][j][0] != "Empty"

    def valid(l):
        return [e for e in l if valid_v(e[0]) and valid_v(e[1])]

    def off(v, di, dj):
        return (v[0] + di, v[1] + dj)

    def departing(v):
        return valid([(v, off(v, 1, 1)), (v, off(v, 1, 0)), (v, off(v, 1, -1)),
                      (v, off(v, 0, -1)), (v, off(v, -1, -1)), (v, off(v, -1, 0)),
                      (v, off(v, -1, 1)), (v, off(v, 0, 1))])

    def arriving(v):
        return valid([(off(v, 1, 1), v), (off(v, 1, 0), v), (off(v, 1, -1), v),
                      (off(v, 0, -1), v), (off(v, -1, -1), v), (off(v, -1, 0), v),
                      (off(v, -1, 1), v), (off(v, 0, 1), v)])

    def reversed_(l):
        return [(b, a) for a, b in l]

    def crossing(v):
        return valid([(v, off(v, 1, 1)), (off(v, 1, 1), v),
                      (off(v, 1, 0), off(v, 0, 1)), (off(v, 0, 1), off(v, 1, 0))])

    def vertical(v):
        return valid([(v, off(v, 1, 0)), (off(v, 1, 0), v)])

    def horizontal(v):
        return valid([(v, off(v, 0, 1)), (off(v, 0, 1), v)])

    def all_v():
        return [((i, j), t[i][j]) for i in range(rows) for j in range(cols)]

    def fe(e):
        (i1, j1), (i2, j2) = e
        return f"ev{i1}_{j1}_v{i2}_{j2}"

    path = lambda e: f"(path {fe(e)})"
    index = lambda e: f"(index {fe(e)})"
    used = lambda e: f"(ite (> {path(e)} 0) 1 0)"

    def max_one(l):
        w(f"(assert (>= 1 (+ 0 0 {' '.join(used(e) for e in l)})))")

    def only_n(n, l):
        w(f"(assert (= {n} (+ 0 0 {' '.join(used(e) for e in l)})))")

    def exact_id(l, cid):
        w("(assert (and true "
          + " ".join(f"(or (= {path(e)} {cid}) (= {path(e)} 0))" for e in l) + "))")

    def path_start(l):
        w("(assert (and true "
          + " ".join(f"(=> (> {path(e)} 0) (= {index(e)} 0))" for e in l) + "))")

    def iter_select(l):
        # (élément, liste sans cet élément), dans l'ordre d'encode.ml
        return [(h, l[:k] + l[k + 1:]) for k, h in enumerate(l)]

    def numbered(i, arr):
        if i == 0:
            return ("(and true "
                    + " ".join(f"(= {path(e)} 0)" for e in arr) + " "
                    + " ".join(f"(= {path(e)} 0)" for e in reversed_(arr)) + ")")
        parts = []
        for earr, rarr in iter_select(arr):
            for edep, rdep in iter_select(reversed_(rarr)):
                parts.append(
                    f"(and true (= {path(earr)} {path(edep)}) (> {path(earr)} 0) "
                    f"(> {path(edep)} 0) (= (+ {index(earr)} 1) {index(edep)}) "
                    + numbered(i - 1, reversed_(rdep)) + ")")
        return "(or " + " ".join(parts) + ")"

    max_id = max((cell[1] for _, cell in all_v() if cell[0] in ("Shape", "Start", "End")),
                 default=0)

    w("(declare-datatypes (T1 T2) ((Pair (pair (path T1) (index T2)))))")
    edges = [e for v, _ in all_v() if valid_v(v) for e in departing(v)]
    for e in edges:
        w(f"(declare-const {fe(e)} (Pair Int Int))")
        w(f"  (assert (and (<= 0 {path(e)}) (<= {path(e)} {max_id})))")
        w(f"  (assert (ite (> {path(e)} 0) (>= {index(e)} 0) (= {index(e)} -10)))")

    for v, _ in all_v():
        max_one(crossing(v))
        max_one(horizontal(v))
        max_one(vertical(v))

    for v, cell in all_v():
        kind = cell[0]
        if kind == "Shape":
            exact_id(arriving(v), cell[1])
            exact_id(departing(v), cell[1])
            w(f"(assert {numbered(1, arriving(v))})")
        elif kind == "Start":
            only_n(1, departing(v))
            only_n(0, arriving(v))
            exact_id(departing(v), cell[1])
            path_start(departing(v))
        elif kind == "End":
            only_n(1, arriving(v))
            only_n(0, departing(v))
            exact_id(arriving(v), cell[1])
        elif kind == "Count":
            w(f"(assert {numbered(cell[1], arriving(v))})")

    return "\n".join(out), edges


def main():
    lines = json.load(sys.stdin)
    t0 = time.perf_counter()
    smt, edges = emit(parse(lines))
    solver = z3.Solver()
    solver.from_string(smt)
    solved = solver.check() == z3.sat
    elapsed = time.perf_counter() - t0

    result = []
    if solved:
        model = solver.model()
        consts = {d.name(): d for d in model.decls()}
        for (i1, j1), (i2, j2) in edges:
            d = consts.get(f"ev{i1}_{j1}_v{i2}_{j2}")
            if d is None:
                continue
            color = model[d].arg(0).as_long()
            if color > 0:
                result.append([i1, j1, i2, j2, chr(color)])
    print(json.dumps({"solved": solved, "time": elapsed, "edges": result}))


if __name__ == "__main__":
    main()
