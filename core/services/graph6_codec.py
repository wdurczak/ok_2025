import base64


def g6_to_b64(g6: str) -> str:
    """
    @brief Koduje reprezentację graph6 do postaci Base64

    Funkcja przekształca string w formacie graph6 do bezpiecznej
    reprezentacji Base64, odpowiedniej do przesyłania w JSON,
    API lub zapisu w bazie danych.

    @param g6 Reprezentacja grafu w formacie graph6
    @return Zakodowany string Base64
    """
    return base64.b64encode(g6.encode("ascii")).decode("ascii")


def g6_from_b64(b64: str) -> str:
    """
    @brief Dekoduje reprezentację Base64 do formatu graph6

    Funkcja odtwarza oryginalny zapis graph6 z jego reprezentacji
    zakodowanej w Base64.

    @param b64 String Base64 zawierający zakodowany graph6
    @return Oryginalna reprezentacja grafu w formacie graph6
    """
    return base64.b64decode(b64.encode("ascii")).decode("ascii")