"""Solve nonograms by encoding them as propositional satisfiability (SAT).

The pipeline:

    puzzle file --encode--> CNF in DIMACS format --minisat--> model --decode--> solved grid

Each step can be run on its own:

    python3 nonogram.py encode instances/heart.txt nonogram.cnf
    minisat nonogram.cnf nonogram.sol
    python3 nonogram.py decode instances/heart.txt nonogram.sol

or all at once:

    python3 nonogram.py run instances/heart.txt

To check that a puzzle has exactly one solution:

    python3 nonogram.py unique instances/heart.txt
"""

import argparse
import subprocess
import sys

from puzzle import Grid, Puzzle, clue_str, show

# ---------------------------------------------------------------------------
# Variables
#
# x_{i,j} is true  <=>  cell (i, j) is filled.
# p_{line,s} is true  <=>  the line (a row or a column) uses placement s.
#
# DIMACS names variables 1, 2, 3, ...: the cells come first, numbered
# width(i-1) + j, and the placement variables after them, line by line.
# ---------------------------------------------------------------------------


def x(puzzle, i, j):
    """The DIMACS number of the variable x_{i,j}."""
    return puzzle.width * (i - 1) + j


# ---------------------------------------------------------------------------
# Placements
#
# A placement of a clue is one way to put its runs into a line, written as a
# list of booleans (True = filled). Clue [3] in a line of length 5 has three:
#
#     ###..    .###.    ..###
# ---------------------------------------------------------------------------


def placements(clue, length):
    """All placements of clue in a line of the given length."""
    if not clue:
        return [[False] * length]
    first = clue[0]
    rest = clue[1:]
    # The rest needs its runs plus one empty cell before each of them.
    room_for_rest = sum(rest) + len(rest)
    result = []
    for start in range(length - first - room_for_rest + 1):
        prefix = [False] * start + [True] * first
        if rest:
            prefix.append(False)
            for tail in placements(rest, length - len(prefix)):
                result.append(prefix + tail)
        else:
            result.append(prefix + [False] * (length - len(prefix)))
    return result


def line_str(line):
    text = ""
    for filled in line:
        text += "#" if filled else "."
    return text


# ---------------------------------------------------------------------------
# The formula
#
# For every line with cells x_1, ..., x_n and placements 1, ..., m:
#
#   some placement is used:      (p_1 or ... or p_m)
#   a placement fixes each cell:  p_s -> x_c      as the clause (not p_s or x_c)
#                                 p_s -> not x_c  as the clause (not p_s or not x_c)
#
# No "at most one placement" is needed: two placements disagree on some cell.
# ---------------------------------------------------------------------------


class Encoding:
    """The formula for a puzzle: its clauses in named parts, and the variables."""

    def __init__(self, puzzle):
        self.puzzle = puzzle
        self.num_vars = puzzle.height * puzzle.width   # the x_{i,j}
        self.parts = []                                # (name, clauses)
        self.placement_vars = 0

        for i in range(1, puzzle.height + 1):
            cells = []
            for j in range(1, puzzle.width + 1):
                cells.append(x(puzzle, i, j))
            self.add_line(f"row {i}", puzzle.row_clues[i - 1], cells)

        for j in range(1, puzzle.width + 1):
            cells = []
            for i in range(1, puzzle.height + 1):
                cells.append(x(puzzle, i, j))
            self.add_line(f"column {j}", puzzle.column_clues[j - 1], cells)

    def new_var(self):
        self.num_vars += 1
        self.placement_vars += 1
        return self.num_vars

    def add_line(self, name, clue, cells):
        """Add the clauses that say: this line (with these cell variables) matches clue."""
        options = placements(clue, len(cells))
        if not options:
            raise ValueError(f"{name}: clue {clue_str(clue)} does not fit in {len(cells)} cells")

        clauses = []
        some_placement = []
        for line in options:
            p = self.new_var()
            some_placement.append(p)
            for c in range(len(cells)):
                if line[c]:
                    clauses.append([-p, cells[c]])
                else:
                    clauses.append([-p, -cells[c]])
        clauses.insert(0, some_placement)

        names = []
        for line in options:
            names.append(line_str(line))
        self.parts.append((f"{name}, clue {clue_str(clue)}: "
                           f"placements {', '.join(names)}", clauses))

    def num_clauses(self):
        total = 0
        for name, clauses in self.parts:
            total += len(clauses)
        return total


def write_dimacs(encoding, path, extra_clauses=()):
    """Write the formula in DIMACS CNF format, with a comment line before each line's clauses."""
    puzzle = encoding.puzzle
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"c Nonogram as SAT: x_(i,j) is variable {puzzle.width}(i-1) + j; "
                f"placement variables start at {puzzle.height * puzzle.width + 1}\n")
        f.write(f"p cnf {encoding.num_vars} {encoding.num_clauses() + len(extra_clauses)}\n")
        for name, clauses in encoding.parts:
            f.write(f"c {name} ({len(clauses)} clauses)\n")
            for clause in clauses:
                write_clause(f, clause)
        if extra_clauses:
            f.write(f"c blocking clauses ({len(extra_clauses)})\n")
            for clause in extra_clauses:
                write_clause(f, clause)


def write_clause(f, clause):
    for literal in clause:
        f.write(f"{literal} ")
    f.write("0\n")


# ---------------------------------------------------------------------------
# Solving and decoding
# ---------------------------------------------------------------------------


def run_minisat(cnf_path, sol_path, quiet=False):
    """Run MiniSat on cnf_path; it writes its result to sol_path."""
    output = subprocess.DEVNULL if quiet else None
    sys.stdout.flush()  # print our own output before MiniSat's
    try:
        result = subprocess.run(["minisat", cnf_path, sol_path], stdout=output)
    except FileNotFoundError:
        sys.exit("minisat not found; see the README for how to install it")
    # MiniSat's exit code is 10 for satisfiable and 20 for unsatisfiable.
    if result.returncode not in (10, 20):
        sys.exit(f"minisat failed with exit code {result.returncode}")


def decode(puzzle, sol_path):
    """Read MiniSat's result file. Return the solved Grid, or None if unsatisfiable.

    Only the cell variables x_{i,j} matter for the solution: cell (i, j) is
    filled if and only if x_{i,j} is true. The placement variables are helpers.
    """
    with open(sol_path, encoding="utf-8") as f:
        status = f.readline().strip()
        if status == "UNSAT":
            return None
        if status != "SAT":
            raise ValueError(f"{sol_path}: expected SAT or UNSAT, found {status!r}")
        model = f.read().split()

    true_vars = set()
    for word in model:
        literal = int(word)
        if literal > 0:
            true_vars.add(literal)

    grid = Grid(puzzle.height, puzzle.width)
    for i in range(1, puzzle.height + 1):
        for j in range(1, puzzle.width + 1):
            grid[i, j] = x(puzzle, i, j) in true_vars
    return grid


def blocking_clause(puzzle, grid):
    """The clause that forbids exactly this grid:
    OR_{filled cells} not x_{i,j}  or  OR_{empty cells} x_{i,j}"""
    clause = []
    for i in range(1, puzzle.height + 1):
        for j in range(1, puzzle.width + 1):
            if grid[i, j]:
                clause.append(-x(puzzle, i, j))
            else:
                clause.append(x(puzzle, i, j))
    return clause


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def cmd_encode(puzzle_path, cnf_path):
    puzzle = Puzzle.from_file(puzzle_path)
    encoding = Encoding(puzzle)
    write_dimacs(encoding, cnf_path)
    cells = puzzle.height * puzzle.width
    print(f"Wrote {cnf_path}: {encoding.num_vars} variables "
          f"({cells} cells + {encoding.placement_vars} placements), "
          f"{encoding.num_clauses()} clauses")
    for name, clauses in encoding.parts:
        print(f"  {name}: {len(clauses)}")
    return puzzle


def cmd_decode(puzzle_path, sol_path):
    puzzle = Puzzle.from_file(puzzle_path)
    grid = decode(puzzle, sol_path)
    if grid is None:
        print("Unsatisfiable: this puzzle has no solution.")
    else:
        print(show(puzzle, grid))
    return grid


def cmd_run(puzzle_path, cnf_path, sol_path):
    puzzle = cmd_encode(puzzle_path, cnf_path)
    print()
    print(show(puzzle))
    print()
    run_minisat(cnf_path, sol_path)
    print()
    grid = cmd_decode(puzzle_path, sol_path)
    if grid is not None:
        print()
        print("Correct solution." if grid.is_solution_of(puzzle)
              else "Not a correct solution: the encoding has a bug!")


def cmd_unique(puzzle_path, cnf_path, sol_path):
    """Solve, forbid the solution with a blocking clause, and solve again."""
    puzzle = Puzzle.from_file(puzzle_path)
    encoding = Encoding(puzzle)

    write_dimacs(encoding, cnf_path)
    run_minisat(cnf_path, sol_path, quiet=True)
    first = decode(puzzle, sol_path)
    if first is None:
        print("Unsatisfiable: this puzzle has no solution.")
        return
    print("A solution:")
    print(show(puzzle, first))
    print()

    write_dimacs(encoding, cnf_path, [blocking_clause(puzzle, first)])
    run_minisat(cnf_path, sol_path, quiet=True)
    second = decode(puzzle, sol_path)
    if second is None:
        print("With the blocking clause added: UNSAT, so the solution is unique.")
    else:
        print("With the blocking clause added: SAT, so there is another solution:")
        print(show(puzzle, second))


def main():
    parser = argparse.ArgumentParser(description="Solve nonograms with a SAT solver.")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("encode", help="write the puzzle as a CNF formula in DIMACS format")
    p.add_argument("puzzle")
    p.add_argument("cnf", nargs="?", default="nonogram.cnf")

    p = commands.add_parser("decode", help="turn MiniSat's result file back into a grid")
    p.add_argument("puzzle")
    p.add_argument("solution", nargs="?", default="nonogram.sol")

    for command, text in (("run", "encode, run MiniSat and decode"),
                          ("unique", "check whether the solution is unique")):
        p = commands.add_parser(command, help=text)
        p.add_argument("puzzle")
        p.add_argument("--cnf", default="nonogram.cnf")
        p.add_argument("--solution", default="nonogram.sol")

    args = parser.parse_args()
    try:
        if args.command == "encode":
            cmd_encode(args.puzzle, args.cnf)
        elif args.command == "decode":
            cmd_decode(args.puzzle, args.solution)
        elif args.command == "run":
            cmd_run(args.puzzle, args.cnf, args.solution)
        else:
            cmd_unique(args.puzzle, args.cnf, args.solution)
    except (OSError, ValueError) as error:
        sys.exit(f"error: {error}")


if __name__ == "__main__":
    main()
