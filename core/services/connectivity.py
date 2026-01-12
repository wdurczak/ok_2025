from __future__ import annotations

import random
from collections import deque


def _build_adj(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """
    @brief Buduje listę sąsiedztwa w postaci list list (graf nieskierowany)

    Funkcja tworzy strukturę adjacency-list:
    adj[v] zawiera listę sąsiadów wierzchołka v.

    @param n Liczba wierzchołków
    @param edges Lista krawędzi (u, v)
    @return Lista sąsiedztwa jako list[list[int]]
    """
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def components(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """
    @brief Wyznacza spójne składowe grafu metodą BFS

    Funkcja buduje listę sąsiedztwa, a następnie wykonuje BFS z każdego
    nieodwiedzonego wierzchołka, zbierając wierzchołki należące do danej składowej.

    @param n Liczba wierzchołków
    @param edges Lista krawędzi (u, v)
    @return Lista składowych, gdzie każda składowa to lista wierzchołków
    """
    adj = _build_adj(n, edges)
    vis = [False] * n
    comps: list[list[int]] = []

    for s in range(n):
        if vis[s]:
            continue

        q = deque([s])
        vis[s] = True
        comp = [s]

        while q:
            x = q.popleft()
            for y in adj[x]:
                if not vis[y]:
                    vis[y] = True
                    q.append(y)
                    comp.append(y)

        comps.append(comp)

    return comps


def is_connected(n: int, edges: list[tuple[int, int]]) -> bool:
    """
    @brief Sprawdza, czy graf jest spójny

    Dla n <= 1 graf jest spójny trywialnie.
    W pozostałych przypadkach graf jest spójny wtedy i tylko wtedy,
    gdy liczba składowych spójnych wynosi 1.

    @param n Liczba wierzchołków
    @param edges Lista krawędzi
    @return True jeśli graf jest spójny, w przeciwnym razie False
    """
    if n <= 1:
        return True
    return len(components(n, edges)) == 1


def enforce_connected_2switch(
    n: int,
    edges: list[tuple[int, int]],
    seed: int | None = None,
    max_outer: int = 2000,
    max_inner: int = 4000,
) -> list[tuple[int, int]]:
    """
    @brief Próbuje wymusić spójność grafu operacjami 2-switch bez zmiany stopni

    Funkcja wykonuje iteracje, w których:
    - wyznacza dwie pierwsze składowe spójne,
    - losuje po jednej krawędzi z każdej składowej,
    - wykonuje 2-switch, który łączy składowe, o ile nie tworzy multikrawędzi.

    Jeśli w grafie istnieją wierzchołki izolowane (stopień 0), to spójności nie da
    się osiągnąć bez zmiany stopni — w takim przypadku funkcja zgłasza błąd.

    @param n Liczba wierzchołków
    @param edges Lista krawędzi wejściowych
    @param seed Ziarno losowe dla wyborów losowych
    @param max_outer Maksymalna liczba iteracji prób łączenia składowych
    @param max_inner Maksymalna liczba prób znalezienia poprawnego 2-switch w danej iteracji
    @return Lista krawędzi grafu spójnego (posortowana)
    @throws ValueError Gdy nie da się uzyskać spójności lub przekroczono limity prób
    """
    rnd = random.Random(seed)

    edge_set: set[tuple[int, int]] = set()
    for u, v in edges:
        if u == v:
            continue
        if u > v:
            u, v = v, u
        edge_set.add((u, v))

    def has(u: int, v: int) -> bool:
        if u > v:
            u, v = v, u
        return (u, v) in edge_set

    def rem(u: int, v: int):
        if u > v:
            u, v = v, u
        edge_set.remove((u, v))

    def add(u: int, v: int):
        if u > v:
            u, v = v, u
        edge_set.add((u, v))

    for _ in range(max_outer):
        comps = components(n, list(edge_set))
        if len(comps) == 1:
            return sorted(edge_set)

        c1 = comps[0]
        c2 = comps[1]
        c1_set = set(c1)
        c2_set = set(c2)

        c1_edges = [(u, v) for (u, v) in edge_set if u in c1_set and v in c1_set]
        c2_edges = [(u, v) for (u, v) in edge_set if u in c2_set and v in c2_set]
        if not c1_edges or not c2_edges:
            raise ValueError("connected_only: cannot connect (isolated vertices / zero-degree)")

        for _try in range(max_inner):
            a, b = rnd.choice(c1_edges)
            c, d = rnd.choice(c2_edges)

            if a != c and b != d and (not has(a, c)) and (not has(b, d)):
                rem(a, b)
                rem(c, d)
                add(a, c)
                add(b, d)
                break

            if a != d and b != c and (not has(a, d)) and (not has(b, c)):
                rem(a, b)
                rem(c, d)
                add(a, d)
                add(b, c)
                break
        else:
            continue

    raise ValueError("connected_only: failed to enforce connectivity within limits")