from __future__ import annotations

import random


def generate_fixed_sum(
    n: int,
    k: int,
    seed: int | None = None,
    max_attempts: int = 2000,
):
    """
    @brief Generuje sekwencję stopni o zadanej sumie (2k)

    Funkcja losuje wstępnie sekwencję stopni długości n, następnie skaluje ją
    tak, aby suma była możliwie bliska wartości docelowej target = 2 * k.
    Po skalowaniu wykonuje korektę przez inkrementacje/dekrementacje losowych
    pozycji, aż suma stopni będzie dokładnie równa target, z zachowaniem ograniczeń:
        0 <= deg[i] <= n - 1.

    Funkcja nie gwarantuje, że wygenerowana sekwencja jest graficzna
    (tj. realizowalna przez graf prosty) — zapewnia jedynie sumę stopni
    oraz poprawny zakres wartości.

    @param n Liczba wierzchołków
    @param k Liczba krawędzi (docelowo suma stopni = 2k)
    @param seed Ziarno losowe
    @param max_attempts Maksymalna liczba prób generowania
    @return Lista stopni długości n o sumie 2k
    @throws RuntimeError Gdy nie uda się wygenerować sekwencji w zadanym limicie prób
    """
    rnd = random.Random(seed)
    target = 2 * k

    for _ in range(max_attempts):
        deg = [rnd.randrange(0, n) for _ in range(n)]
        s = sum(deg)

        if s == 0:
            deg[rnd.randrange(n)] = 1
            s = 1

        scale = target / s
        deg = [min(n - 1, int(d * scale)) for d in deg]

        s = sum(deg)
        while s < target:
            i = rnd.randrange(n)
            if deg[i] < n - 1:
                deg[i] += 1
                s += 1

        while s > target:
            i = rnd.randrange(n)
            if deg[i] > 0:
                deg[i] -= 1
                s -= 1

        if sum(deg) == target and all(0 <= d <= n - 1 for d in deg):
            return deg

    raise RuntimeError("generate_fixed_sum: max_attempts exceeded")