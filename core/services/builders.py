from __future__ import annotations

import random

def greedy_build_graph(degrees: list[int]) -> list[tuple[int,int]]:
    """
    @brief Buduje realizację grafu prostego metodą zachłanną (wariant Havel–Hakimi).
    @param degrees Lista stopni wierzchołków (dla wierzchołków 0..n-1).
    @return Lista krawędzi (u, v) realizujących podany ciąg stopni.
    @throws ValueError Jeśli ciąg nie jest graficzny (w trakcie konstrukcji wyjdzie sprzeczność).

    @details
    Algorytm iteracyjnie wybiera wierzchołek o największym stopniu d i łączy go
    z d wierzchołkami o aktualnie największych stopniach, zmniejszając je o 1.
    Działa poprawnie dla ciągów graficznych i jest szybki, ale nie kontroluje spójności.
    Zwracany graf może być niespójny.
    """
    n = len(degrees)
    deg = [(degrees[i], i) for i in range(n)]
    edges: list[tuple[int,int]] = []

    while True:
        deg = [(d,v) for (d,v) in deg if d > 0]
        if not deg:
            return edges
        deg.sort(reverse=True)
        d, v = deg.pop(0)
        if d > len(deg):
            raise ValueError("Not graphical (greedy_build)")
        for i in range(d):
            di, ui = deg[i]
            edges.append((v, ui))
            deg[i] = (di - 1, ui)
            if deg[i][0] < 0:
                raise ValueError("Not graphical (greedy_build)")


def random_greedy_build_graph(degrees: list[int], seed: int | None = None) -> list[tuple[int,int]]:
    """
    @brief Losowy wariant zachłannej realizacji ciągu stopni (randomized greedy).
    @param degrees Lista stopni wierzchołków (0..n-1).
    @param seed Ziarno RNG dla powtarzalności (opcjonalnie).
    @return Lista krawędzi (u, v) realizujących podany ciąg stopni.
    @throws ValueError Jeśli ciąg nie jest graficzny (sprzeczność w trakcie konstrukcji).

    @details
    Zamiast zawsze łączyć wybrany wierzchołek z top-d wierzchołkami,
    wybierany jest losowy podzbiór kandydatów z “czołówki” (pool),
    co daje różne realizacje dla tego samego degrees.
    Nadal nie ma gwarancji spójności; graf może wyjść niespójny.
    """
    rnd = random.Random(seed)
    n = len(degrees)
    deg = [(degrees[i], i) for i in range(n)]
    edges: list[tuple[int,int]] = []

    while True:
        deg = [(d,v) for (d,v) in deg if d > 0]
        if not deg:
            return edges

        deg.sort(reverse=True)
        d, v = deg.pop(0)
        if d > len(deg):
            raise ValueError("Not graphical (random_greedy_build)")

        m = min(len(deg), max(d, 3))
        pool = deg[:m]
        rnd.shuffle(pool)
        chosen = pool[:d]
        chosen_ids = {u for _, u in chosen}

        new_deg = []
        for di, u in deg:
            if u in chosen_ids:
                di -= 1
                if di < 0:
                    raise ValueError("Not graphical (random_greedy_build)")
                edges.append((v, u))
            new_deg.append((di, u))
        deg = new_deg


def exact_build_graph(degrees: list[int]) -> list[tuple[int,int]]:
    """
    @brief Dokładna realizacja ciągu stopni przez backtracking (exact / backtracking realization).
    @param degrees Lista stopni wierzchołków (0..n-1).
    @return Lista krawędzi (i, j) realizujących podany ciąg stopni.
    @throws ValueError Jeśli ciąg nie jest graficzny (precheck lub brak rozwiązania).

    @details
    Metoda buduje macierz sąsiedztwa i rekurencyjnie dobiera sąsiadów
    dla wierzchołka o największym aktualnym stopniu. Kandydaci są sortowani
    malejąco po stopniu (heurystyka przyspieszająca), ale wynik jest dokładny:
    jeśli istnieje realizacja, zostanie znaleziona (dla małych n).
    Brak gwarancji spójności (to jest realizacja ciągu stopni, nie “connected realization”).
    Złożoność w najgorszym przypadku wykładnicza.
    """
    n = len(degrees)
    deg = [int(d) for d in degrees]
    if any(d < 0 or d > n-1 for d in deg) or sum(deg) % 2 != 0:
        raise ValueError("Not graphical (exact precheck)")

    adj = [[0]*n for _ in range(n)]

    def pick_vertex():
        best = -1
        bi = -1
        for i in range(n):
            if deg[i] > best:
                best = deg[i]
                bi = i
        return bi, best

    def backtrack():
        i, di = pick_vertex()
        if di == 0:
            return True

        cand = [j for j in range(n) if j != i and adj[i][j] == 0 and deg[j] > 0]
        if di > len(cand):
            return False

        cand.sort(key=lambda x: deg[x], reverse=True)

        chosen = []

        def choose(start, need):
            if need == 0:
                for j in chosen:
                    adj[i][j] = adj[j][i] = 1
                    deg[j] -= 1
                old_di = deg[i]
                deg[i] = 0

                ok = backtrack()

                deg[i] = old_di
                for j in chosen:
                    adj[i][j] = adj[j][i] = 0
                    deg[j] += 1
                return ok

            for idx in range(start, len(cand) - need + 1):
                j = cand[idx]
                chosen.append(j)
                if choose(idx + 1, need - 1):
                    return True
                chosen.pop()
            return False

        return choose(0, di)

    if not backtrack():
        raise ValueError("Not graphical (exact)")

    edges: list[tuple[int,int]] = []
    for i in range(n):
        for j in range(i+1, n):
            if adj[i][j]:
                edges.append((i,j))
    return edges