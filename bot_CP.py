''' Bot LYNE qui joue toujours la solution du solveur CP-SAT
(jamais celle de solutions.json), pour tester le modèle dans le vrai jeu.

Usage : lancer le jeu, afficher un niveau, puis F10. Échap pour quitter.
'''

import time

import keyboard
import pyautogui

from bot import play_solution
from read_lyne_pyzzle import read_pic_into_puzzle
from solveur_CP import solve, verify


def main():

    screenshot = pyautogui.screenshot()
    puzzle_text, rows, cols = read_pic_into_puzzle(screenshot)

    print("Niveau détecté :")
    for line in puzzle_text:
        print(f"  {line}")

    solution, infos = solve(puzzle_text, workers=1)
    if solution is None:
        print(f"Pas de solution ({infos['status']}) : lecture de l'écran ratée ?\n")
        return

    ok, reason = verify(puzzle_text, solution)
    print(f"Résolu en {infos['wall_time']*1000:.0f} ms, vérificateur : "
          f"{'OK' if ok else reason}")
    for path in solution:
        print(f"  {path}")

    time.sleep(0.1)
    play_solution(solution, rows, cols)
    print("Joué. Le jeu a-t-il validé le niveau ?\n")


if __name__ == "__main__":
    keyboard.add_hotkey("f10", main)
    print("Prêt : affiche un niveau dans le jeu et appuie sur F10 (Échap pour quitter).")
    keyboard.wait("esc")
