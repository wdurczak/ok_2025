from __future__ import annotations

import base64
import time
from typing import Callable

from .rewrite import (
    realize_greedy,
    realize_random_greedy,
    realize_backtracking,
)
from .graph6 import edges_to_graph6
from .nauty import canonical_g6_via_labelg
from .spectrum import spectral_radius


def degrees_hash(deg: list[int]) -> str:
    """
    @brief Generuje stabilny hash sekwencji stopni wierzchołków

    Funkcja serializuje listę stopni do postaci JSON
    (z zachowaniem jednoznacznego formatu),
    a następnie oblicza skrót SHA-1 tej reprezentacji.

    Hash służy do:
    - jednoznacznej identyfikacji sekwencji stopni,
    - porównań backend–frontend,
    - kluczy cache lub bazy danych.

    @param deg Lista stopni wierzchołków grafu
    @return Skrót SHA-1 jako string szesnastkowy
    """
    import json
    import hashlib

    s = json.dumps(
        [int(x) for x in deg],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def normalize_edges(n: int, edges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    @brief Normalizuje listę krawędzi grafu prostego

    Funkcja:
    - usuwa pętle (u == v),
    - wymusza postać (min(u,v), max(u,v)),
    - usuwa duplikaty krawędzi,
    - usuwa krawędzie spoza zakresu [0, n),
    - sortuje wynikową listę.

    @param n Liczba wierzchołków grafu
    @param edges Lista krawędzi (u, v)
    @return Posortowana lista unikalnych krawędzi grafu prostego
    """
    norm: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    for u, v in edges:
        u = int(u)
        v = int(v)

        if u == v:
            continue

        if u > v:
            u, v = v, u

        if not (0 <= u < n and 0 <= v < n):
            continue

        if (u, v) in seen:
            continue

        seen.add((u, v))
        norm.append((u, v))

    norm.sort()
    return norm


def g6_to_b64(g6: str) -> str:
    """
    @brief Koduje zapis graph6 do Base64

    Funkcja umożliwia bezpieczne przesyłanie
    reprezentacji graph6 w JSON lub API.

    @param g6 String w formacie graph6
    @return Zakodowany string Base64
    """
    return base64.b64encode(
        g6.encode("ascii", "ignore")
    ).decode("ascii")


def _build_result(
    deg: list[int],
    edges: list[tuple[int, int]],
    t0: float,
) -> dict:
    """
    @brief Buduje kompletną strukturę wyniku algorytmu

    Funkcja:
    - normalizuje krawędzie,
    - generuje reprezentację graph6,
    - oblicza kanoniczną postać grafu (nauty),
    - oblicza promień spektralny,
    - mierzy czas wykonania.

    Zwracany słownik jest zgodny z wymaganiami:
    - warstwy views.py,
    - zapisu do bazy danych.

    @param deg Sekwencja stopni grafu
    @param edges Lista krawędzi wygenerowanych przez algorytm
    @param t0 Czas startu (perf_counter)
    @return Słownik z pełnym opisem wyniku
    """
    n = len(deg)
    edges = normalize_edges(n, edges)

    g6 = edges_to_graph6(n, edges)
    canon = canonical_g6_via_labelg(g6)
    sr = spectral_radius(n, edges)

    return {
        "edges": edges,
        "graph6": g6,
        "canonical_g6": canon,
        "graph6_b64": g6_to_b64(g6),
        "canonical_g6_b64": g6_to_b64(canon),
        "spectral_radius": float(sr),
        "objective_value": float(sr),
        "objective_name": "spectral_radius",
        "objective_mode": "min",
        "degrees_hash": degrees_hash(deg),
        "time_ms": int((time.perf_counter() - t0) * 1000),
    }


def run_algorithm(
    algorithm: str,
    degrees: list[int],
    seed: int | None = None,
) -> dict:
    """
    @brief Uruchamia wybrany algorytm realizacji sekwencji stopni

    Dostępne algorytmy:
    - "greedy"  – deterministyczna heurystyka zachłanna,
    - "random"  – losowa wersja heurystyki zachłannej,
    - "exact"   – dokładny algorytm z nawrotami (backtracking).

    Funkcja:
    - realizuje graf o zadanej sekwencji stopni,
    - oblicza promień spektralny,
    - zwraca pełny opis wyniku.

    @param algorithm Nazwa algorytmu ("greedy" | "random" | "exact")
    @param degrees Sekwencja stopni wierzchołków
    @param seed Opcjonalne ziarno losowe
    @return Słownik opisujący wygenerowany graf i wynik optymalizacji
    @throws ValueError Gdy podano nieznany algorytm
    """
    deg = [int(x) for x in degrees]
    t0 = time.perf_counter()

    if algorithm == "greedy":
        edges = realize_greedy(deg, seed=seed)
        return _build_result(deg, edges, t0)

    if algorithm == "random":
        edges = realize_random_greedy(deg, seed=seed)
        return _build_result(deg, edges, t0)

    if algorithm == "exact":
        edges = realize_backtracking(deg, seed=seed)
        return _build_result(deg, edges, t0)

    raise ValueError(f"unknown algorithm: {algorithm}")