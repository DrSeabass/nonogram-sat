# nonogram-sat

Solve nonograms (also called Picross or paint-by-numbers) by turning them into
a propositional logic formula and handing that formula to a SAT solver
(MiniSat). The encoding is the one from the logic course lectures. The
companion repository [sudoku-sat](https://github.com/DrSeabass/sudoku-sat)
does the same for Sudoku.

## Requirements

- Python 3
- MiniSat

Install MiniSat on Debian or Ubuntu with `./setup.sh` (runs
`sudo apt-get install minisat`), or on macOS with `brew install minisat`.

## The puzzle

Fill in some of the cells of a grid. The numbers next to a row (or below a
column) are the lengths of its runs of filled cells, in order. Runs are
separated by at least one empty cell. The heart from the lectures:

```
. # . # .   1 1
# # # # #   5
# # # # #   5
. # # # .   3
. . # . .   1

2 4 4 4 2
```

## The idea

Introduce one propositional variable for every cell:

> x<sub>i,j</sub> is true &iff; cell (i, j) is filled

A row with clue 3 in a grid of width 5 can be filled in three ways, its
*placements*: `###..`, `.###.` and `..###`. The row is correct if and only if
one of them holds:

> (x<sub>1</sub> &and; x<sub>2</sub> &and; x<sub>3</sub> &and; &not;x<sub>4</sub> &and; &not;x<sub>5</sub>)
> &or; (&not;x<sub>1</sub> &and; x<sub>2</sub> &and; x<sub>3</sub> &and; x<sub>4</sub> &and; &not;x<sub>5</sub>)
> &or; (&not;x<sub>1</sub> &and; &not;x<sub>2</sub> &and; x<sub>3</sub> &and; x<sub>4</sub> &and; x<sub>5</sub>)

That is a disjunction of conjunctions, not a CNF. Multiplying it out gives
5<sup>3</sup> = 125 clauses for this row, and 5<sup>6</sup> = 15625 for the
row with clue 1 1. Instead, add a *helper variable* for every placement:

> p<sub>s</sub> is true &iff; the line uses placement s

and, for every row and column with placements 1, &hellip;, m:

| Clauses | Says | How many |
|---|---|---|
| (p<sub>1</sub> &or; &hellip; &or; p<sub>m</sub>) | the line uses some placement | 1 |
| (&not;p<sub>s</sub> &or; x<sub>c</sub>) or (&not;p<sub>s</sub> &or; &not;x<sub>c</sub>) | placement s fixes cell c: p<sub>s</sub> &rarr; x<sub>c</sub> if s fills c, p<sub>s</sub> &rarr; &not;x<sub>c</sub> if not | m &times; length of the line |

The row with clue 3 now needs 1 + 3 &middot; 5 = 16 clauses. No "at most one
placement" clauses are needed: two different placements disagree on some
cell, so they cannot both be true. This is the idea behind the Tseitin
transformation: new variables give a small CNF that is satisfiable exactly
when the original formula is.

For the heart: 25 cell variables, 16 + 14 = 30 placement variables and 160
clauses. The solution is read off the cell variables only.

## Usage

The whole pipeline in one command:

```sh
python3 nonogram.py run instances/heart.txt
```

Or one step at a time, looking at the files in between:

```sh
python3 nonogram.py encode instances/heart.txt nonogram.cnf    # puzzle -> formula
minisat nonogram.cnf nonogram.sol                              # formula -> satisfying interpretation
python3 nonogram.py decode instances/heart.txt nonogram.sol    # interpretation -> grid
```

- `nonogram.cnf` is the formula in DIMACS CNF format. Variable x<sub>i,j</sub>
  is number width&middot;(i&minus;1) + j. The placement variables come after the
  cells, line by line. Before the clauses of each row and column is a comment
  that lists its placements in order, so the first one is the first
  placement variable of that line.
- `nonogram.sol` is MiniSat's answer: `UNSAT`, or `SAT` followed by the value
  of every variable (`n` for true, `-n` for false). `decode` needs the puzzle
  file too, to know the size of the grid.

## Is the solution unique?

A good puzzle has exactly one solution. To check: solve, add a *blocking
clause* that forbids the solution found, and solve again. The blocking clause
for a grid is

> &or;<sub>filled (i, j)</sub> &not;x<sub>i,j</sub> &or; &or;<sub>empty (i, j)</sub> x<sub>i,j</sub>

If the second run is `UNSAT`, the solution is unique. Otherwise MiniSat has
found a different one.

```sh
python3 nonogram.py unique instances/heart.txt           # unique
python3 nonogram.py unique instances/two-solutions.txt   # shows a second solution
```

## Instances

The line `rows` is followed by one clue per row, top to bottom. The line
`columns` is followed by one clue per column, left to right. A clue is a list
of run lengths separated by spaces, or `0` for a line with no filled cells.
Lines starting with `#` are comments.

| File | Contents |
|---|---|
| `instances/heart.txt` | the 5&times;5 heart from the lecture slides |
| `instances/house.txt` | a 10&times;10 house, with a unique solution |
| `instances/two-solutions.txt` | a 2&times;2 puzzle with two solutions |
| `instances/unsat.txt` | a 3&times;3 puzzle with no solution |

## Files

| File | Contents |
|---|---|
| `nonogram.py` | placements, encoding, running MiniSat, decoding, the uniqueness check |
| `puzzle.py` | reading, printing and checking puzzles |
