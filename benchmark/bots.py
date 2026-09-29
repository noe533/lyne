''' Lancement uniforme des solveurs LYNE (le nôtre et ceux trouvés en ligne)

Chaque solveur tourne dans son propre processus, avec une limite de temps
(le processus est tué si elle est dépassée). La solution renvoyée est
convertie au format de solver.py puis revérifiée par solveur_CP.verify,
indépendamment du bot.

  run_bot(nom, niveau, timeout) -> {"status", "time", "wall", "verified", "reason"}
  status : "solved" | "unsolved" | "timeout" | "error"
  time   : temps de résolution mesuré par le bot lui-même (sans démarrage
           de l'interpréteur / JVM), ou temps total si le bot ne le donne pas
  wall   : temps total du processus

Usage interne : python benchmark/bots.py run cp8 < niveau.json
'''

import glob
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OTHERS = ROOT / "autres_bots"
PYTHON = sys.executable

sys.path.insert(0, str(ROOT))


def find_tool(name, *candidates):
    ''' Cherche un exécutable dans le PATH puis dans les dossiers d'installation
    habituels (un terminal ouvert avant l'installation n'a pas le PATH à jour). '''
    found = shutil.which(name)
    if found:
        return found
    for pattern in candidates:
        matches = sorted(glob.glob(pattern), reverse=True)
        if matches:
            return matches[0]
    return None


HOME = Path.home()
NODE = find_tool("node", r"C:\Program Files\nodejs\node.exe")
JAVA = find_tool("java", "C:/Program Files/Eclipse Adoptium/*/bin/java.exe")
JAVAC = find_tool("javac", "C:/Program Files/Eclipse Adoptium/*/bin/javac.exe")
CARGO = find_tool("cargo", str(HOME / ".cargo" / "bin" / "cargo.exe"))

JBOSBOOM_CP = os.pathsep.join([
    str(OTHERS / "build" / "jbosboom"),
    str(OTHERS / "build" / "guava-17.0.jar"),
])
YAHVK_EXE = OTHERS / "yahvk-cuna_lyne_solver" / "target" / "release" / (
    "lyne.exe" if os.name == "nt" else "lyne")


# ---------------------------------------------------------------------------
# Conversions vers le format de solver.py : [[(col, ligne), ...], ...]

def edges_to_paths(puzzle, edges):
    ''' Arêtes colorées [(l1, c1, l2, c2, couleur)] -> chemins (Hierholzer) '''
    by_color = defaultdict(list)
    for l1, c1, l2, c2, color in edges:
        by_color[color].append(((l1, c1), (l2, c2)))

    paths = []
    for color, color_edges in by_color.items():
        adjacency = defaultdict(list)
        for k, (a, b) in enumerate(color_edges):
            adjacency[a].append((b, k))
            adjacency[b].append((a, k))
        terminals = [p for p in adjacency
                     if puzzle[p[0]][p[1]].isupper() and len(adjacency[p]) % 2 == 1]
        start = terminals[0] if terminals else next(iter(adjacency))
        seen, stack, path = set(), [start], []
        while stack:
            node = stack[-1]
            while adjacency[node] and adjacency[node][-1][1] in seen:
                adjacency[node].pop()
            if adjacency[node]:
                nxt, k = adjacency[node].pop()
                seen.add(k)
                stack.append(nxt)
            else:
                path.append(stack.pop())
        paths.append([(c, l) for l, c in reversed(path)])
    return paths


# ---------------------------------------------------------------------------
# Solveurs Python lancés dans un sous-processus (mode "run")

def _run_inline(name, puzzle, timeout):
    if name in ("cp1", "cp8"):
        from solveur_CP import solve
        t0 = time.perf_counter()
        solution, infos = solve(puzzle, time_limit=timeout,
                                workers=1 if name == "cp1" else 8)
        return {"solved": solution is not None, "time": time.perf_counter() - t0,
                "solution": solution, "detail": infos["status"]}
    if name == "upstream":
        import solver
        t0 = time.perf_counter()
        p = solver.Puzzle(puzzle, verbose=False)
        s = solver.Solver(p, time_limit=timeout)
        s.solve()
        elapsed = time.perf_counter() - t0
        solution = p.export_solution(s.solution) if s.solution else None
        return {"solved": solution is not None, "time": elapsed,
                "solution": solution, "detail": "timeout" if s.timed_out else ""}
    raise ValueError(name)


# ---------------------------------------------------------------------------
# Description des bots

def _cmd_python(name):
    return [PYTHON, str(Path(__file__).resolve()), "run", name]


BOTS = {
    # nom : (description, commande, format d'entrée, format de sortie)
    "cp8": ("Notre modèle CP-SAT, 8 threads", lambda: _cmd_python("cp8"), "json", "inline"),
    "cp1": ("Notre modèle CP-SAT, 1 thread", lambda: _cmd_python("cp1"), "json", "inline"),
    "upstream": ("gamescomputersplay/lyne (solver.py, Python, recherche avec restarts)",
                 lambda: _cmd_python("upstream"), "json", "inline"),
    "arlencox": ("arlencox/lyne-solver (encodage SMT + Z3)",
                 lambda: [PYTHON, str(OTHERS / "adaptateurs" / "arlencox_z3.py")], "json", "edges"),
    "denilsonsa": ("denilsonsa/lyne-solver (JavaScript, backtracking brut)",
                   lambda: NODE and [NODE, str(OTHERS / "adaptateurs" / "denilsonsa.js")],
                   "json", "edges"),
    "jbosboom": ("jbosboom/lynebot (Java, inférence + backtracking)",
                 lambda: JAVA and [JAVA, "-Xss512m", "-cp", JBOSBOOM_CP,
                                   "com.jeffreybosboom.lyne.LyneBench"], "text", "jbosboom"),
    "yahvk": ("yahvk-cuna/lyne_solver (Rust, backtracking)",
              lambda: YAHVK_EXE.exists() and [str(YAHVK_EXE)], "yahvk", "yahvk"),
}

YAHVK_COLORS = {"d": "r", "s": "g", "t": "b"}
YAHVK_DIRS = {
    "Right": (0, 1), "DownRight": (1, 1), "Down": (1, 0), "DownLeft": (1, -1),
    "Left": (0, -1), "UpLeft": (-1, -1), "Up": (-1, 0), "UpRight": (-1, 1),
}


def available(name):
    return bool(BOTS[name][1]())


def _encode_input(fmt, puzzle):
    if fmt == "json":
        return json.dumps(puzzle)
    width = max(len(l) for l in puzzle)
    if fmt == "text":
        return "\n".join(l.ljust(width) for l in puzzle) + "\n"
    # yahvk : r/g/b au lieu de d/s/t, "." pour un trou, lignes de même longueur
    table = {**YAHVK_COLORS, **{k.upper(): v.upper() for k, v in YAHVK_COLORS.items()}, " ": "."}
    return "\n".join("".join(table.get(ch, ch) for ch in l.ljust(width)) for l in puzzle) + "\n"


def _decode_output(fmt, puzzle, out):
    ''' -> (résolu, temps interne ou None, solution ou None) '''
    if fmt == "inline":
        data = json.loads(out)
        return data["solved"], data["time"], data["solution"]
    if fmt == "edges":
        data = json.loads(out)
        solution = edges_to_paths(puzzle, data["edges"]) if data["solved"] else None
        return data["solved"], data["time"], solution
    if fmt == "jbosboom":
        lines = out.strip().splitlines()
        status, seconds = lines[0].split()
        if status != "SOLVED":
            return False, float(seconds), None
        solution = [[tuple(int(x) for x in cell.split(","))[::-1] for cell in l.split()]
                    for l in lines[1:]]
        return True, float(seconds), solution
    if fmt == "yahvk":
        inverse = {v: k for k, v in YAHVK_COLORS.items()}
        names = {"Red": "r", "Green": "g", "Blue": "b"}
        edges, color = [], None
        for line in out.splitlines():
            line = line.strip()
            if line.endswith(":") and line[:-1] in names:
                color = inverse[names[line[:-1]]]
            elif line.split(" ")[0] in YAHVK_DIRS and color:
                direction, point = line.split(" ", 1)
                x, y = (int(v) for v in point.strip("()").split(","))
                dl, dc = YAHVK_DIRS[direction]
                edges.append((y, x, y + dl, x + dc, color))
        if not edges:
            return False, None, None
        return True, None, edges_to_paths(puzzle, edges)
    raise ValueError(fmt)


def run_bot(name, puzzle, timeout):
    from solveur_CP import verify
    _, cmd_factory, fmt_in, fmt_out = BOTS[name]
    cmd = cmd_factory()
    if not cmd:
        return {"status": "error", "time": None, "wall": 0, "verified": False,
                "reason": "bot non installé"}

    stdin = _encode_input(fmt_in, puzzle)
    if fmt_out == "inline":
        cmd = cmd + [str(timeout)]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True,
                              timeout=timeout + 5, cwd=ROOT)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "time": None, "wall": time.perf_counter() - t0,
                "verified": False, "reason": ""}
    wall = time.perf_counter() - t0

    try:
        solved, internal, solution = _decode_output(fmt_out, puzzle, proc.stdout)
    except Exception as exc:  # sortie inattendue (plantage, pile trop profonde...)
        err = (proc.stderr or proc.stdout).strip().splitlines()
        return {"status": "error", "time": None, "wall": wall, "verified": False,
                "reason": f"{type(exc).__name__}: {err[-1] if err else ''}"[:200]}

    elapsed = internal if internal is not None else wall
    if not solved:
        # Un solveur interne peut s'arrêter tout seul sur sa limite de temps
        status = "timeout" if elapsed >= timeout * 0.98 else "unsolved"
        return {"status": status, "time": elapsed, "wall": wall, "verified": False, "reason": ""}
    if elapsed > timeout:
        return {"status": "timeout", "time": elapsed, "wall": wall, "verified": False, "reason": ""}
    ok, reason = verify(puzzle, solution)
    return {"status": "solved", "time": elapsed, "wall": wall, "verified": ok, "reason": reason}


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "run":
        limit = float(sys.argv[3]) if len(sys.argv) > 3 else 60
        result = _run_inline(sys.argv[2], json.load(sys.stdin), limit)
        print(json.dumps(result))
    else:
        for bot, (desc, *_rest) in BOTS.items():
            print(f"{bot:11s} {'OK ' if available(bot) else '---'} {desc}")
