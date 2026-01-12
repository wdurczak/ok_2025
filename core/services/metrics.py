from __future__ import annotations

from collections import deque
import random


def build_adj(n: int, edges: list[tuple[int, int]]):
    """
    @brief Buduje listę sąsiedztwa grafu nieskierowanego

    Funkcja tworzy strukturę adjacency-list w postaci listy zbiorów,
    gdzie adj[v] zawiera sąsiadów wierzchołka v. Pętle (u == v)
    są ignorowane.

    @param n Liczba wierzchołków
    @param edges Lista krawędzi (u, v)
    @return Lista zbiorów sąsiadów (adjacency list)
    """
    adj = [set() for _ in range(n)]
    for u, v in edges:
        if u == v:
            continue
        adj[u].add(v)
        adj[v].add(u)
    return adj


def is_connected(n: int, adj) -> bool:
    """
    @brief Sprawdza spójność grafu metodą BFS

    Funkcja wykonuje BFS startując z wierzchołka 0 i sprawdza,
    czy odwiedzono wszystkie wierzchołki.

    @param n Liczba wierzchołków
    @param adj Lista sąsiedztwa (np. wynik build_adj)
    @return True jeśli graf jest spójny, w przeciwnym razie False
    """
    if n == 0:
        return True

    seen = set()
    q = deque([0])
    seen.add(0)

    while q:
        v = q.popleft()
        for u in adj[v]:
            if u not in seen:
                seen.add(u)
                q.append(u)

    return len(seen) == n


def count_triangles(n: int, adj) -> int:
    """
    @brief Zlicza liczbę trójkątów w grafie nieskierowanym

    Trójkąt to cykl długości 3 (u, v, w), gdzie każda para wierzchołków
    jest połączona krawędzią. Implementacja wykorzystuje przecięcia zbiorów
    sąsiedztwa dla każdej krawędzi (u, v) z warunkiem v > u, aby ograniczyć
    nadmiarowe liczenie. Wynik dzielony jest przez 3, ponieważ każda trójka
    zostaje policzona dla trzech krawędzi.

    @param n Liczba wierzchołków
    @param adj Lista sąsiedztwa
    @return Liczba trójkątów w grafie
    """
    tri = 0
    for u in range(n):
        for v in adj[u]:
            if v > u:
                tri += len(adj[u].intersection(adj[v]))
    return tri // 3


def avg_clustering(n: int, adj) -> float:
    """
    @brief Oblicza średni lokalny współczynnik klasteryzacji

    Dla wierzchołka v o stopniu deg >= 2 liczony jest lokalny współczynnik:
        C(v) = 2 * E(N(v)) / (deg * (deg - 1)),
    gdzie E(N(v)) to liczba krawędzi pomiędzy sąsiadami v.
    Funkcja zwraca średnią wartość C(v) po wszystkich wierzchołkach
    o stopniu co najmniej 2.

    @param n Liczba wierzchołków
    @param adj Lista sąsiedztwa
    @return Średni współczynnik klasteryzacji (0.0 jeśli brak wierzchołków deg>=2)
    """
    s = 0.0
    cnt = 0

    for v in range(n):
        deg = len(adj[v])
        if deg < 2:
            continue

        cnt += 1
        neigh = list(adj[v])
        links = 0

        for i in range(len(neigh)):
            a = neigh[i]
            for j in range(i + 1, len(neigh)):
                b = neigh[j]
                if b in adj[a]:
                    links += 1

        s += (2.0 * links) / (deg * (deg - 1))

    return s / cnt if cnt else 0.0


def avg_shortest_path_len(
    n: int,
    adj,
    sample_sources: int = 0,
    seed: int | None = None,
) -> float | None:
    """
    @brief Oblicza średnią długość najkrótszych ścieżek (APL) w grafie

    Funkcja:
    - zwraca None dla grafu niespójnego,
    - w grafie spójnym oblicza średnią odległość pomiędzy parami wierzchołków
      na podstawie BFS uruchamianego z wybranych źródeł.

    Jeśli sample_sources > 0 i sample_sources < n, źródła BFS są losowane
    (z ziarnem seed). W przeciwnym razie BFS wykonywany jest dla wszystkich
    wierzchołków.

    Zwracana wartość to średnia z sum dystansów od źródeł do pozostałych
    wierzchołków podzielona przez liczbę rozważanych par.

    @param n Liczba wierzchołków
    @param adj Lista sąsiedztwa
    @param sample_sources Liczba losowanych źródeł BFS (0 = wszystkie)
    @param seed Ziarno losowe do próbkowania źródeł
    @return Średnia długość najkrótszej ścieżki lub None, jeśli graf niespójny
    """
    if not is_connected(n, adj):
        return None

    def bfs(src: int):
        dist = [-1] * n
        q = deque([src])
        dist[src] = 0

        while q:
            v = q.popleft()
            for u in adj[v]:
                if dist[u] == -1:
                    dist[u] = dist[v] + 1
                    q.append(u)

        return dist

    if sample_sources and sample_sources < n:
        rnd = random.Random(seed)
        sources = rnd.sample(range(n), sample_sources)
    else:
        sources = list(range(n))

    total = 0
    pairs = 0

    for s in sources:
        dist = bfs(s)
        total += sum(dist)
        pairs += (n - 1)

    return total / pairs if pairs else 0.0