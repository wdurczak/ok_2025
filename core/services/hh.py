def is_graphical_havel_hakimi(deg: list[int]) -> bool:
    """
    @brief Sprawdza, czy sekwencja stopni jest graficzna algorytmem Havel–Hakimi

    Funkcja implementuje klasyczny algorytm Havel–Hakimi, który iteracyjnie:
    - usuwa wierzchołki o zerowym stopniu,
    - wybiera największy stopień,
    - redukuje kolejne największe stopnie,
    - wykrywa sprzeczności (ujemne stopnie lub zbyt duży stopień).

    Jeśli procedura zakończy się bez sprzeczności, sekwencja jest graficzna,
    tzn. istnieje graf prosty realizujący zadany ciąg stopni.

    @param deg Sekwencja stopni wierzchołków
    @return True jeśli sekwencja jest graficzna, w przeciwnym razie False
    """
    d = [int(x) for x in deg]

    while True:
        d = [x for x in d if x > 0]
        if not d:
            return True

        d.sort(reverse=True)
        x = d.pop(0)

        if x < 0 or x > len(d):
            return False

        for i in range(x):
            d[i] -= 1
            if d[i] < 0:
                return False