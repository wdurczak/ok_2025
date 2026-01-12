from __future__ import annotations

import random


def _normalize_deg(deg: list[int]) -> list[int]:
    """
    @brief Normalizuje i waliduje sekwencję stopni

    Funkcja:
    - rzutuje wszystkie wartości na int,
    - sprawdza, czy stopnie są nieujemne.

    @param deg Lista stopni wierzchołków
    @return Lista stopni jako int
    @throws ValueError Gdy którykolwiek stopień jest ujemny
    """
    d = [int(x) for x in deg]
    if any(x < 0 for x in d):
        raise ValueError("degrees must be >= 0")
    return d


def _edge_key(u: int, v: int) -> tuple[int, int]:
    """
    @brief Zwraca kanoniczną reprezentację krawędzi nieskierowanej

    @param u Pierwszy wierzchołek
    @param v Drugi wierzchołek
    @return Para (min(u,v), max(u,v))
    """
    return (u, v) if u < v else (v, u)


def _add_edge(edge_set: set[tuple[int, int]], u: int, v: int):
    """
    @brief Dodaje krawędź do zbioru krawędzi grafu prostego

    @param edge_set Zbiór krawędzi
    @param u Pierwszy wierzchołek
    @param v Drugi wierzchołek
    @throws ValueError Gdy wykryto pętlę
    """
    if u == v:
        raise ValueError("loop detected")
    edge_set.add(_edge_key(u, v))


def _has_edge(edge_set: set[tuple[int, int]], u: int, v: int) -> bool:
    """
    @brief Sprawdza, czy krawędź istnieje w zbiorze

    @param edge_set Zbiór krawędzi
    @param u Pierwszy wierzchołek
    @param v Drugi wierzchołek
    @return True jeśli krawędź istnieje, w przeciwnym razie False
    """
    return _edge_key(u, v) in edge_set


def _havel_hakimi_realize(
    deg: list[int],
    rnd: random.Random | None = None,
) -> list[tuple[int, int]]:
    """
    @brief Realizacja ciągu stopni algorytmem Havel–Hakimi

    Algorytm:
    - wybiera wierzchołek o największym pozostałym stopniu,
    - łączy go z kolejnymi wierzchołkami o największych stopniach,
    - opcjonalnie losuje kolejność dołączania (wariant random-greedy).

    @param deg Sekwencja stopni wierzchołków
    @param rnd Generator losowy (None = deterministycznie)
    @return Lista krawędzi realizująca zadany ciąg stopni
    @throws ValueError Gdy ciąg stopni nie jest graficzny
    """
    d = _normalize_deg(deg)
    n = len(d)

    items = [(d[i], i) for i in range(n)]
    edge_set: set[tuple[int, int]] = set()

    while True:
        items.sort(reverse=True, key=lambda x: x[0])

        if items[0][0] == 0:
            break

        k, v = items[0]
        items = items[1:]

        if k < 0:
            raise ValueError("non-graphical (negative remainder)")
        if k > len(items):
            raise ValueError("non-graphical (degree too large)")

        targets = list(range(k))
        if rnd is not None and k > 1:
            rnd.shuffle(targets)

        for idx in targets:
            dk, u = items[idx]
            if dk <= 0:
                raise ValueError("non-graphical (ran out of degree)")
            if _has_edge(edge_set, v, u):
                raise ValueError("failed realization (would create multiedge)")

            _add_edge(edge_set, v, u)
            items[idx] = (dk - 1, u)

    return sorted(edge_set)


def realize_greedy(deg: list[int], seed: int | None = None) -> list[tuple[int, int]]:
    """
    @brief Deterministyczna realizacja ciągu stopni

    Wariant algorytmu Havel–Hakimi bez losowości.

    @param deg Sekwencja stopni
    @param seed Nieużywany (dla zgodności interfejsu)
    @return Lista krawędzi grafu
    """
    return _havel_hakimi_realize(deg, rnd=None)


def realize_random_greedy(
    deg: list[int],
    seed: int | None = None,
) -> list[tuple[int, int]]:
    """
    @brief Losowa realizacja ciągu stopni (random-greedy)

    Wariant Havel–Hakimi z losową kolejnością dołączania
    wierzchołków do top-k, co pozwala uzyskać różne realizacje
    dla tego samego ciągu stopni.

    @param deg Sekwencja stopni
    @param seed Ziarno generatora losowego
    @return Lista krawędzi grafu
    """
    rnd = random.Random(seed)
    return _havel_hakimi_realize(deg, rnd=rnd)


def realize_backtracking(
    deg: list[int],
    seed: int | None = None,
    max_steps: int = 2_000_000,
) -> list[tuple[int, int]]:
    """
    @brief Dokładna realizacja ciągu stopni metodą backtrackingu

    Algorytm:
    - przeszukuje przestrzeń możliwych krawędzi,
    - cofa decyzje w przypadku sprzeczności,
    - znajduje jedną poprawną realizację (jeśli istnieje).

    Przeznaczony dla małych rozmiarów grafu.

    @param deg Sekwencja stopni
    @param seed Ziarno losowe (wpływa na kolejność przeszukiwania)
    @param max_steps Limit kroków zabezpieczający przed zapętleniem
    @return Lista krawędzi grafu
    @throws ValueError Gdy ciąg nie jest graficzny lub limit przekroczony
    """
    d0 = _normalize_deg(deg)
    n = len(d0)

    if sum(d0) % 2 != 0:
        raise ValueError("non-graphical (sum of degrees odd)")

    rnd = random.Random(seed)

    d = d0[:]
    edge_set: set[tuple[int, int]] = set()
    steps = 0

    all_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    if seed is not None:
        rnd.shuffle(all_pairs)

    all_pairs.sort(
        key=lambda e: max(d[e[0]], d[e[1]]),
        reverse=True,
    )

    stack: list[tuple[int, tuple[int, int], tuple[int, int]]] = []
    idx = 0

    def done() -> bool:
        return all(x == 0 for x in d)

    def can_add(u: int, v: int) -> bool:
        return d[u] > 0 and d[v] > 0 and not _has_edge(edge_set, u, v)

    while True:
        steps += 1
        if steps > max_steps:
            raise ValueError("backtracking limit exceeded")

        if done():
            return sorted(edge_set)

        if idx >= len(all_pairs):
            if not stack:
                raise ValueError("non-graphical / no realization found")

            idx, (u, v), _ = stack.pop()
            edge_set.remove(_edge_key(u, v))
            d[u] += 1
            d[v] += 1
            idx += 1
            continue

        u, v = all_pairs[idx]
        if can_add(u, v):
            _add_edge(edge_set, u, v)
            d[u] -= 1
            d[v] -= 1
            stack.append((idx, (u, v), (d[u], d[v])))
            idx = 0
            continue

        idx += 1