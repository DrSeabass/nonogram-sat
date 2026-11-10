"""Reading, printing and checking nonograms.

Rows and columns run from 1, as in the lecture: cell (i, j) is row i, column j.
A clue is a list of run lengths, for example [1, 1] or [5]. The empty list []
is the clue of a line with no filled cells (written 0 in a puzzle file).
"""

FILLED = "#"
EMPTY = "."


def runs(line):
    """The lengths of the runs of filled cells in a line (a list of booleans)."""
    lengths = []
    length = 0
    for filled in line:
        if filled:
            length += 1
        elif length > 0:
            lengths.append(length)
            length = 0
    if length > 0:
        lengths.append(length)
    return lengths


def parse_clue(text):
    """Turn a line such as '1 1' or '0' into a clue such as [1, 1] or []."""
    clue = []
    for word in text.split():
        clue.append(int(word))
    if clue == [0]:
        return []
    for length in clue:
        if length < 1:
            raise ValueError(f"clue {text!r}: run lengths must be at least 1")
    return clue


def clue_str(clue):
    """The clue as text: '1 1', or '0' for the empty clue."""
    if not clue:
        return "0"
    words = []
    for length in clue:
        words.append(str(length))
    return " ".join(words)


class Puzzle:
    """The clues of a nonogram: one clue per row and one per column."""

    def __init__(self, row_clues, column_clues):
        self.row_clues = row_clues
        self.column_clues = column_clues
        self.height = len(row_clues)
        self.width = len(column_clues)

    @staticmethod
    def from_file(path):
        """Read a puzzle file.

        The line 'rows' is followed by one clue per row, the line 'columns'
        by one clue per column. A clue is a list of run lengths separated by
        spaces, or 0 for an empty line. Blank lines and lines starting with #
        are ignored.
        """
        sections = {"rows": [], "columns": []}
        current = None
        with open(path, encoding="utf-8") as f:
            for number, line in enumerate(f, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line in sections:
                    current = line
                    continue
                if current is None:
                    raise ValueError(f"{path}:{number}: expected 'rows' before the first clue")
                try:
                    sections[current].append(parse_clue(line))
                except ValueError as error:
                    raise ValueError(f"{path}:{number}: {error}")
        if not sections["rows"] or not sections["columns"]:
            raise ValueError(f"{path}: needs both a 'rows' and a 'columns' section")
        return Puzzle(sections["rows"], sections["columns"])


class Grid:
    """A filled-in nonogram. grid[i, j] is True if cell (i, j) is filled."""

    def __init__(self, height, width):
        self.height = height
        self.width = width
        self.filled = set()

    def __getitem__(self, cell):
        return cell in self.filled

    def __setitem__(self, cell, filled):
        if filled:
            self.filled.add(cell)
        else:
            self.filled.discard(cell)

    def row(self, i):
        line = []
        for j in range(1, self.width + 1):
            line.append(self[i, j])
        return line

    def column(self, j):
        line = []
        for i in range(1, self.height + 1):
            line.append(self[i, j])
        return line

    def is_solution_of(self, puzzle):
        """True if every row and column of the grid matches its clue."""
        if (self.height, self.width) != (puzzle.height, puzzle.width):
            return False
        for i in range(1, self.height + 1):
            if runs(self.row(i)) != puzzle.row_clues[i - 1]:
                return False
        for j in range(1, self.width + 1):
            if runs(self.column(j)) != puzzle.column_clues[j - 1]:
                return False
        return True

    def __str__(self):
        lines = []
        for i in range(1, self.height + 1):
            line = ""
            for filled in self.row(i):
                line += FILLED if filled else EMPTY
            lines.append(line)
        return "\n".join(lines)


def show(puzzle, grid=None):
    """The puzzle as text: the grid (empty if None) with the row clues on the
    right and the column clues below, read downwards."""
    if grid is None:
        grid = Grid(puzzle.height, puzzle.width)
    # Every column is as wide as its widest clue number, at least one character.
    width = 1
    for clue in puzzle.column_clues:
        for length in clue:
            width = max(width, len(str(length)))

    lines = []
    for i in range(1, puzzle.height + 1):
        cells = ""
        for filled in grid.row(i):
            cells += (FILLED if filled else EMPTY).ljust(width) + " "
        lines.append(cells + "  " + clue_str(puzzle.row_clues[i - 1]))
    lines.append("")
    depth = 1
    for clue in puzzle.column_clues:
        depth = max(depth, len(clue))
    for d in range(depth):
        line = ""
        for clue in puzzle.column_clues:
            if not clue:
                clue = [0]
            text = str(clue[d]) if d < len(clue) else ""
            line += text.ljust(width) + " "
        lines.append(line.rstrip())
    return "\n".join(lines)
