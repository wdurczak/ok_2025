from __future__ import annotations

import subprocess


def canonical_g6_via_labelg(g6: str) -> str:
    """
    @brief Wyznacza kanoniczną reprezentację grafu w formacie graph6

    Funkcja uruchamia narzędzie z pakietu nauty (`labelg`)
    w trybie cichym i kanonizującym, przekazując graf
    w postaci graph6 przez standardowe wejście.

    Zwracana reprezentacja:
    - jest niezależna od etykiet wierzchołków,
    - umożliwia porównywanie grafów do izomorfizmu,
    - nadaje się do zapisu i deduplikacji w bazie danych.

    @param g6 Reprezentacja grafu w formacie graph6
    @return Kanoniczna reprezentacja graph6
    @throws RuntimeError Gdy wywołanie `labelg` zakończy się błędem
    """
    p = subprocess.run(
        ["labelg", "-q", "-g"],
        input=(g6.strip() + "\n"),
        text=True,
        capture_output=True,
    )

    if p.returncode != 0:
        raise RuntimeError(
            f"labelg failed: {p.stderr.strip() or p.stdout.strip()}"
        )

    lines = [
        ln.strip()
        for ln in p.stdout.splitlines()
        if ln.strip() and not ln.startswith(">")
    ]

    if not lines:
        raise RuntimeError("labelg returned empty output")

    return lines[0]