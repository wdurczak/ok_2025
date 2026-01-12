from __future__ import annotations

import numpy as np


def spectral_radius(n: int, edges: list[tuple[int, int]]) -> float:
    """
    @brief Oblicza promień spektralny grafu nieskierowanego

    Funkcja buduje macierz sąsiedztwa A grafu prostego
    o n wierzchołkach i zadanym zbiorze krawędzi,
    a następnie wyznacza największą wartość własną macierzy A.

    Promień spektralny:
        ρ(G) = max(λ_i), gdzie λ_i są wartościami własnymi macierzy sąsiedztwa.

    @param n Liczba wierzchołków grafu
    @param edges Lista krawędzi (u, v), graf nieskierowany
    @return Największa wartość własna macierzy sąsiedztwa (promień spektralny)

    @note Funkcja zakłada graf prosty (bez pętli i wielokrawędzi)
    """
    a = np.zeros((n, n), dtype=np.float64)

    for u, v in edges:
        a[u, v] = 1.0
        a[v, u] = 1.0
    vals = np.linalg.eigvalsh(a)
    return float(np.max(vals))