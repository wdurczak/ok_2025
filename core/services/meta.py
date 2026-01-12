from __future__ import annotations

import random
import time

from .runner import normalize_edges
from .spectrum import spectral_radius
from .metrics import build_adj, is_connected


def _two_switch(n: int, edge_set: set[tuple[int, int]], rnd: random.Random) -> bool:
    """
    @brief Wykonuje ruch 2-switch (przełączenie dwóch krawędzi) zachowujący stopnie

    Operacja 2-switch wybiera dwie krawędzie (a,b) oraz (c,d) z czterema różnymi
    wierzchołkami i próbuje je przełączyć do jednej z konfiguracji:
    - (a,c) i (b,d) lub
    - (a,d) i (b,c)

    Jeśli nowe krawędzie nie istnieją w grafie, to usuwa dwie stare krawędzie
    i dodaje dwie nowe, zachowując stopnie wszystkich wierzchołków.

    @param n Liczba wierzchołków (parametr informacyjny; nie jest używany wprost)
    @param edge_set Zbiór krawędzi grafu (modyfikowany w miejscu)
    @param rnd Generator losowy używany do wyboru krawędzi
    @return True jeśli wykonano poprawny 2-switch, w przeciwnym razie False
    """
    edges = list(edge_set)
    if len(edges) < 2:
        return False

    (a, b) = rnd.choice(edges)
    (c, d) = rnd.choice(edges)
    if len({a, b, c, d}) != 4:
        return False

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

    if not has(a, c) and not has(b, d):
        rem(a, b)
        rem(c, d)
        add(a, c)
        add(b, d)
        return True

    if not has(a, d) and not has(b, c):
        rem(a, b)
        rem(c, d)
        add(a, d)
        add(b, c)
        return True

    return False


def hill_climb(
    degrees: list[int],
    start_edges: list[tuple[int, int]],
    seed: int | None,
    iterations: int,
    mode: str,
    connected_only: bool = False,
) -> dict:
    """
    @brief Lokalna optymalizacja metodą hill climbing na grafach o zadanych stopniach

    Funkcja startuje od początkowej realizacji grafu (start_edges) i wykonuje
    kolejne kroki polegające na losowym ruchu 2-switch zachowującym stopnie.
    Ruch jest akceptowany wyłącznie wtedy, gdy poprawia wartość celu
    (promień spektralny) zgodnie z trybem `mode`.

    Opcjonalnie można wymusić spójność grafu, odrzucając kandydatów niespójnych.

    @param degrees Sekwencja stopni (używana do wyznaczenia n)
    @param start_edges Początkowa lista krawędzi
    @param seed Ziarno losowe
    @param iterations Liczba prób wykonania ruchu
    @param mode Tryb optymalizacji: "min" (minimalizacja) lub inny (maksymalizacja)
    @param connected_only Jeśli True, akceptowane są tylko grafy spójne
    @return Słownik z najlepszym znalezionym grafem i metadanymi przebiegu
    """
    t0 = time.perf_counter()
    rnd = random.Random(seed)

    n = len(degrees)
    cur_edges = normalize_edges(n, start_edges)
    cur_set = set(cur_edges)

    cur_sr = float(spectral_radius(n, cur_edges))
    accepted = 0

    for _ in range(iterations):
        cand_set = set(cur_set)
        ok = _two_switch(n, cand_set, rnd)
        if not ok:
            continue

        cand_edges = normalize_edges(n, list(cand_set))

        if connected_only:
            adj = build_adj(n, cand_edges)
            if not is_connected(n, adj):
                continue

        cand_sr = float(spectral_radius(n, cand_edges))
        better = cand_sr < cur_sr if mode == "min" else cand_sr > cur_sr
        if better:
            cur_set = cand_set
            cur_edges = cand_edges
            cur_sr = cand_sr
            accepted += 1

    return {
        "edges": cur_edges,
        "spectral_radius": cur_sr,
        "objective": cur_sr,
        "iterations": iterations,
        "accepted_moves": accepted,
        "meta_params": {"seed": seed, "mode": mode, "connected_only": connected_only},
        "time_ms": int((time.perf_counter() - t0) * 1000),
    }


def simulated_annealing(
    degrees: list[int],
    start_edges: list[tuple[int, int]],
    seed: int | None,
    iterations: int,
    t0_temp: float,
    t_end: float,
    mode: str,
    connected_only: bool = False,
) -> dict:
    """
    @brief Optymalizacja metodą symulowanego wyżarzania (Simulated Annealing)

    Funkcja działa podobnie do hill climbing, ale może akceptować również ruchy
    pogarszające wartość celu z pewnym prawdopodobieństwem zależnym od temperatury.
    Temperatura maleje liniowo od t0_temp do t_end w trakcie `iterations` kroków.

    Definicja delta:
    - dla mode == "min": delta = cand_sr - cur_sr
    - dla pozostałych:   delta = cur_sr - cand_sr
    Ruch lepszy (delta < 0) jest akceptowany zawsze.
    Ruch gorszy jest akceptowany z prawdopodobieństwem exp(-delta / T).

    Opcjonalnie można wymusić spójność grafu, odrzucając kandydatów niespójnych.

    @param degrees Sekwencja stopni (używana do wyznaczenia n)
    @param start_edges Początkowa lista krawędzi
    @param seed Ziarno losowe
    @param iterations Liczba prób wykonania ruchu
    @param t0_temp Temperatura początkowa
    @param t_end Temperatura końcowa
    @param mode Tryb optymalizacji: "min" (minimalizacja) lub inny (maksymalizacja)
    @param connected_only Jeśli True, rozważane są tylko grafy spójne
    @return Słownik z najlepszym znalezionym grafem i metadanymi przebiegu
    """
    t0 = time.perf_counter()
    rnd = random.Random(seed)

    n = len(degrees)
    cur_edges = normalize_edges(n, start_edges)
    cur_set = set(cur_edges)
    cur_sr = float(spectral_radius(n, cur_edges))
    accepted = 0

    for it in range(iterations):
        frac = it / max(1, iterations - 1)
        T = t0_temp + (t_end - t0_temp) * frac
        if T <= 0:
            T = 1e-12

        cand_set = set(cur_set)
        ok = _two_switch(n, cand_set, rnd)
        if not ok:
            continue

        cand_edges = normalize_edges(n, list(cand_set))

        if connected_only:
            adj = build_adj(n, cand_edges)
            if not is_connected(n, adj):
                continue

        cand_sr = float(spectral_radius(n, cand_edges))

        delta = (cand_sr - cur_sr) if mode == "min" else (cur_sr - cand_sr)
        if delta < 0:
            accept = True
        else:
            import math
            accept = rnd.random() < math.exp(-delta / T)

        if accept:
            cur_set = cand_set
            cur_edges = cand_edges
            cur_sr = cand_sr
            accepted += 1

    return {
        "edges": cur_edges,
        "spectral_radius": cur_sr,
        "objective": cur_sr,
        "iterations": iterations,
        "accepted_moves": accepted,
        "meta_params": {
            "seed": seed,
            "mode": mode,
            "t0": t0_temp,
            "t_end": t_end,
            "connected_only": connected_only,
        },
        "time_ms": int((time.perf_counter() - t0) * 1000),
    }