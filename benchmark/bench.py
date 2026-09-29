''' Banc d'essai : jusqu'à quelle taille de niveau chaque solveur tient-il ?

Pour chaque taille N (grille N x N), on génère quelques niveaux solubles
(benchmark/generateur.py, mêmes niveaux pour tous les bots, gardés en cache
dans benchmark/niveaux/) et on lance chaque bot avec une limite de temps.
Quand un bot échoue sur la majorité des niveaux d'une taille, on arrête de
le tester sur les tailles supérieures.

Les résultats sont ajoutés au fur et à mesure dans benchmark/resultats/
(on peut interrompre et relancer : ce qui est déjà fait est sauté).

Usage :
  python benchmark/bench.py                          # tous les bots installés
  python benchmark/bench.py --bots cp8 upstream --tailles 4-12 --graines 5 --timeout 60
  python benchmark/bench.py --jeu --timeout 10       # les 650 niveaux du jeu
  python benchmark/bench.py --resume                 # affiche le tableau récapitulatif
'''

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from bots import BOTS, ROOT, available, run_bot
from generateur import generate

HERE = Path(__file__).resolve().parent
LEVELS = HERE / "niveaux"
RESULTS = HERE / "resultats"
FIELDS = ["bot", "niveau", "taille", "cases", "status", "time", "wall", "verified", "reason"]


def level(n, seed):
    ''' Niveau N x N n°seed, généré une fois puis lu dans le cache '''
    LEVELS.mkdir(exist_ok=True)
    path = LEVELS / f"{n:02d}x{n:02d}-{seed}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["puzzle"]
    puzzle, solution = generate(n, seed=seed)
    path.write_text(json.dumps({"puzzle": puzzle, "solution": solution}), encoding="utf-8")
    return puzzle


def load(csv_path):
    if not csv_path.exists():
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append(csv_path, row):
    new = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def run_one(csv_path, done, bot, name, size, puzzle, timeout):
    if (bot, name) in done:
        return done[bot, name]
    r = run_bot(bot, puzzle, timeout)
    ok = r["status"] == "solved" and r["verified"]
    t = f"{r['time']:.3f}s" if r["time"] is not None else "-"
    print(f"  {bot:11s} {name:12s} {r['status']:9s} {t:>9s}"
          f"{'' if ok or r['status'] != 'solved' else '  SOLUTION FAUSSE ' + r['reason']}"
          f"{'  ' + r['reason'] if r['status'] == 'error' else ''}", flush=True)
    row = {"bot": bot, "niveau": name, "taille": size,
           "cases": sum(ch != " " for l in puzzle for ch in l),
           "status": r["status"], "time": r["time"], "wall": round(r["wall"], 3),
           "verified": r["verified"], "reason": r["reason"]}
    append(csv_path, row)
    done[bot, name] = row
    return row


def success(row):
    return row["status"] == "solved" and str(row["verified"]) == "True"


def scaling(bots, sizes, seeds, timeout):
    RESULTS.mkdir(exist_ok=True)
    csv_path = RESULTS / f"taille_timeout{timeout:g}s.csv"
    done = {(r["bot"], r["niveau"]): r for r in load(csv_path)}
    alive = set(bots)
    for n in sizes:
        if not alive:
            break
        print(f"\n=== {n}x{n}", flush=True)
        puzzles = [(f"{n}x{n}-{s}", level(n, s)) for s in range(seeds)]
        for bot in bots:
            if bot not in alive:
                continue
            rows = [run_one(csv_path, done, bot, name, n, p, timeout) for name, p in puzzles]
            if sum(map(success, rows)) * 2 < len(rows):
                print(f"  -> {bot} abandonné au-delà de {n}x{n}")
                alive.discard(bot)
    summary(csv_path)


def summary(csv_path):
    rows = load(csv_path)
    table = defaultdict(lambda: defaultdict(list))
    for r in rows:
        table[r["bot"]][int(r["taille"])].append(r)
    sizes = sorted({int(r["taille"]) for r in rows})

    print(f"\nRésumé ({csv_path.name}) : niveaux résolus / testés, temps médian des réussites")
    print(f"{'bot':11s} " + " ".join(f"{n:>2d}x{n:<11d}" for n in sizes) + "  plus grand N (100 %)")
    for bot in [b for b in BOTS if b in table]:
        cells, best = [], None
        for n in sizes:
            runs = table[bot].get(n)
            if not runs:
                cells.append(" " * 14)
                continue
            wins = [float(r["time"]) for r in runs if success(r)]
            med = f"{statistics.median(wins):.2f}s" if wins else "-"
            cells.append(f"{len(wins)}/{len(runs)} {med:>9s}")
            if len(wins) == len(runs):
                best = n
        print(f"{bot:11s} " + " ".join(f"{c:14s}" for c in cells) + f"  {best or '-'}")


def game_levels(bots, timeout):
    RESULTS.mkdir(exist_ok=True)
    csv_path = RESULTS / f"jeu_timeout{timeout:g}s.csv"
    done = {(r["bot"], r["niveau"]): r for r in load(csv_path)}
    with open(ROOT / "puzzles.json", encoding="utf-8") as f:
        puzzles = json.load(f)
    for bot in bots:
        print(f"\n=== {bot}", flush=True)
        for p in puzzles:
            text = p["puzzle"]
            size = max(len(text), max(len(l) for l in text))
            run_one(csv_path, done, bot, p["name"], size, text, timeout)
    rows = load(csv_path)
    print(f"\nNiveaux du jeu résolus en moins de {timeout:g}s :")
    for bot in bots:
        mine = [r for r in rows if r["bot"] == bot]
        wins = [float(r["time"]) for r in mine if success(r)]
        print(f"  {bot:11s} {len(wins)}/{len(mine)}"
              + (f"  (temps max {max(wins):.2f}s, total {sum(wins):.1f}s)" if wins else ""))


def parse_sizes(text):
    if "-" in text:
        a, b = map(int, text.split("-"))
        return list(range(a, b + 1))
    return [int(x) for x in text.split(",")]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bots", nargs="+", default=None)
    parser.add_argument("--tailles", default="4-16")
    parser.add_argument("--graines", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--jeu", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.resume:
        summary(RESULTS / f"taille_timeout{args.timeout:g}s.csv")
        return
    bots = args.bots or [b for b in BOTS if available(b)]
    missing = [b for b in bots if not available(b)]
    if missing:
        print("Bots non installés (ignorés) :", ", ".join(missing))
        bots = [b for b in bots if b not in missing]
    if args.jeu:
        game_levels(bots, args.timeout)
    else:
        scaling(bots, parse_sizes(args.tailles), args.graines, args.timeout)


if __name__ == "__main__":
    main()
