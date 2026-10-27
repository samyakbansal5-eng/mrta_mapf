"""Grid helpers. A cell is an (x, y) tuple: x = column, y = row; grid[y][x]."""
from collections import deque

INF = 10 ** 9
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def cell(c):
    return (int(c[0]), int(c[1]))


def size(grid):
    return len(grid[0]), len(grid)


def is_wall(grid, c):
    x, y = c
    w, h = size(grid)
    return not (0 <= x < w and 0 <= y < h) or grid[y][x] == "#"


def neighbours(grid, c, blocked=frozenset()):
    """4-connected free neighbours of c (walls and blocked cells excluded)."""
    x, y = c
    out = []
    for dx, dy in DIRS:
        n = (x + dx, y + dy)
        if not is_wall(grid, n) and n not in blocked:
            out.append(n)
    return out


def bfs_dist(grid, goal, blocked=frozenset(), exempt=frozenset()):
    """Distance (in cells) from every reachable cell to goal.

    `exempt` cells may be entered even if blocked, but only as the goal itself
    (used when a robot must reach a failed robot's cell to take over its product).
    """
    goal = cell(goal)
    dist = {goal: 0}
    q = deque([goal])
    while q:
        c = q.popleft()
        for n in neighbours(grid, c, blocked):
            if n not in dist:
                dist[n] = dist[c] + 1
                q.append(n)
    return dist
