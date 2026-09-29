// Adaptateur pour denilsonsa/lyne-solver (JavaScript, backtracking brut).
// Charge les fichiers d'origine sans les modifier : shared.js (structures),
// algorithm.js (solveur, prévu pour un Web Worker) et la fonction
// parse_text_input de ui.js.
//
// Entrée (stdin) : JSON, liste de lignes du niveau.
// Sortie (stdout) : JSON {solved, time, edges: [[ligne, col, ligne2, col2, couleur], ...]}

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const src = path.join(__dirname, '..', 'denilsonsa_lyne-solver');
const read = (f) => fs.readFileSync(path.join(src, f), 'utf8');

const context = { console, importScripts: () => {}, postMessage: () => {} };
vm.createContext(context);
vm.runInContext(read('shared.js'), context);
vm.runInContext(read('algorithm.js'), context);

const ui = read('ui.js');
const start = ui.indexOf('function parse_text_input');
const end = ui.indexOf('// Receives an already solved board.');
vm.runInContext(ui.slice(start, end), context);

const lines = JSON.parse(fs.readFileSync(0, 'utf8'));
context.lines = lines;
const t0 = process.hrtime.bigint();
vm.runInContext('board = parse_text_input(lines); solve_board(board);', context);
const elapsed = Number(process.hrtime.bigint() - t0) / 1e9;

const board = context.board;
const edges = [];
if (board.solution_found) {
    board.nodes.forEach((row, y) => row.forEach((node, x) => {
        if (!node) return;
        for (const e of node.edges) {
            edges.push([y, x, y + e.direction.dy, x + e.direction.dx, e.color]);
        }
    }));
}
process.stdout.write(JSON.stringify({ solved: !!board.solution_found, time: elapsed, edges }));
