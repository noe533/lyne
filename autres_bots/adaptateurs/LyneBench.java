/*
 * Adaptateur pour jbosboom/lynebot (Java, inférence locale + backtracking).
 * Compilé avec les sources d'origine (non modifiées) et Guava 17.
 *
 * Le parseur d'origine (Puzzle.fromString) ne gère pas les trous : on
 * construit donc la grille Node[][] nous-mêmes, avec null pour un trou, ce
 * que le reste du code d'origine accepte.
 *
 * Entrée (stdin) : lignes du niveau (légende du dépôt : d/s/t, D/S/T, 2/3/4,
 * espace). Sortie : "SOLVED <secondes>" puis un chemin par ligne
 * "l,c l,c ...", ou "UNSOLVED <secondes>".
 */
package com.jeffreybosboom.lyne;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

public final class LyneBench {
	public static void main(String[] args) throws Exception {
		BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
		List<String> lines = new ArrayList<>();
		for (String l; (l = in.readLine()) != null; )
			if (!l.isEmpty()) lines.add(l);
		int cols = lines.stream().mapToInt(String::length).max().getAsInt();

		Node[][] nodes = new Node[lines.size()][cols];
		for (int r = 0; r < lines.size(); ++r)
			for (int c = 0; c < lines.get(r).length(); ++c) {
				char ch = lines.get(r).charAt(c);
				if (ch == ' ') continue;
				if (Character.isDigit(ch)) {
					nodes[r][c] = Node.octagon(r, c, Character.digit(ch, 10));
					continue;
				}
				Node.Kind kind = ch == 'd' || ch == 'D' ? Node.Kind.DIAMOND
						: ch == 's' || ch == 'S' ? Node.Kind.SQUARE : Node.Kind.TRIANGLE;
				nodes[r][c] = Character.isUpperCase(ch)
						? Node.terminal(r, c, kind) : Node.nonterminal(r, c, kind);
			}

		long t0 = System.nanoTime();
		Set<List<Node>> paths;
		try {
			paths = Solver.solve(new Puzzle(nodes));
		} catch (ContradictionException e) {
			paths = null;
		}
		double elapsed = (System.nanoTime() - t0) / 1e9;

		if (paths == null) {
			System.out.println("UNSOLVED " + elapsed);
			return;
		}
		System.out.println("SOLVED " + elapsed);
		for (List<Node> p : paths)
			System.out.println(p.stream().map(n -> n.row() + "," + n.col())
					.collect(Collectors.joining(" ")));
	}
}
