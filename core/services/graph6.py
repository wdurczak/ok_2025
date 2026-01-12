from __future__ import annotations


def _encode_n_graph6(n: int) -> str:
    """
    @brief Koduje liczbę wierzchołków n zgodnie ze specyfikacją graph6

    Funkcja implementuje standardowe kodowanie rozmiaru grafu dla graph6:
    - dla n <= 62: pojedynczy znak (n + 63),
    - dla 63 <= n <= 258047: prefiks "~" oraz 3 znaki (18 bitów),
    - dla 258048 <= n <= 2^36 - 1: prefiks "~~" oraz 6 znaków (36 bitów).

    @param n Liczba wierzchołków
    @return Prefiks graph6 kodujący n
    @throws ValueError Gdy n < 0 lub n przekracza obsługiwany zakres
    """
    if n < 0:
        raise ValueError("graph6: n must be >= 0")

    if n <= 62:
        return chr(n + 63)

    if n <= 258047:
        x = n
        b1 = (x >> 12) & 0x3F
        b2 = (x >> 6) & 0x3F
        b3 = x & 0x3F
        return "~" + chr(b1 + 63) + chr(b2 + 63) + chr(b3 + 63)

    if n <= 68719476735:
        x = n
        out = ["~", "~"]
        for shift in (30, 24, 18, 12, 6, 0):
            out.append(chr(((x >> shift) & 0x3F) + 63))
        return "".join(out)

    raise ValueError("graph6: n too large")


def edges_to_graph6(n: int, edges: list[tuple[int, int]]) -> str:
    """
    @brief Konwertuje listę krawędzi grafu nieskierowanego do formatu graph6

    Funkcja buduje macierz sąsiedztwa grafu prostego o n wierzchołkach,
    następnie koduje górny trójkąt macierzy (i < j) jako strumień bitów,
    dopełnia go zerami do wielokrotności 6 i mapuje kolejne 6-bitowe bloki
    na znaki ASCII (wartość 63 + blok).

    Wynik ma postać:
        encode_n(n) + data

    @param n Liczba wierzchołków grafu
    @param edges Lista krawędzi (u, v)
    @return Reprezentacja grafu w formacie graph6
    @throws ValueError Gdy krawędź wychodzi poza zakres [0, n)
    """
    adj = [[0] * n for _ in range(n)]
    for u, v in edges:
        u = int(u)
        v = int(v)

        if u == v:
            continue

        if not (0 <= u < n and 0 <= v < n):
            raise ValueError(f"graph6: edge out of range: {(u, v)} for n={n}")

        adj[u][v] = 1
        adj[v][u] = 1

    bits: list[int] = []
    for i in range(n):
        for j in range(i + 1, n):
            bits.append(adj[i][j])

    while len(bits) % 6 != 0:
        bits.append(0)

    data: list[str] = []
    for k in range(0, len(bits), 6):
        val = 0
        for b in bits[k:k + 6]:
            val = (val << 1) | b
        data.append(chr(63 + val))

    return _encode_n_graph6(n) + "".join(data)