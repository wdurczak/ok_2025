from __future__ import annotations

from django.db import transaction
from core.models import Run, Discovery


def _better(new_val: float, old_val: float, mode: str, eps: float) -> bool:
    """
    @brief Sprawdza, czy nowa wartość celu jest istotnie lepsza od poprzedniej

    Dla trybu minimizacji:
        new_val < old_val - eps
    Dla trybu maksymalizacji:
        new_val > old_val + eps

    Parametr eps zapewnia tolerancję numeryczną i eliminuje przypadki,
    w których różnice wynikają jedynie z błędów zaokrągleń.

    @param new_val Nowa wartość funkcji celu
    @param old_val Poprzednia (referencyjna) wartość funkcji celu
    @param mode "min" dla minimizacji, dowolna inna wartość dla maksymalizacji
    @param eps Minimalna różnica uznawana za poprawę
    @return True jeśli nowa wartość jest lepsza, w przeciwnym razie False
    """
    if mode == "min":
        return new_val < old_val - eps
    return new_val > old_val + eps


def _baseline_stats(degrees_hash: str):
    """
    @brief Wyznacza statystyki bazowe metryk dla danego degrees_hash

    Funkcja pobiera wyniki Run dla danego degrees_hash ograniczając się do
    algorytmów bazowych ("greedy" oraz "exact") i wyznacza mediany metryk:
    - liczby trójkątów,
    - średniej długości najkrótszej ścieżki (APL),
    - średniego współczynnika klasteryzacji.

    Medianę wyznacza przez posortowanie listy i wybór elementu środkowego
    (dla parzystej liczby elementów wybierany jest "górny środek").

    @param degrees_hash Hash sekwencji stopni, identyfikujący eksperyment
    @return Słownik z medianami metryk bazowych (lub None jeśli brak danych)
    """
    qs = Run.objects.filter(
        degrees_hash=degrees_hash,
        algorithm__in=["greedy", "exact"],
    )

    tri = [r.triangles for r in qs if r.triangles is not None]
    apl = [r.avg_path_len for r in qs if r.avg_path_len is not None]
    cl = [r.clustering for r in qs if r.clustering is not None]

    return {
        "tri_median": sorted(tri)[len(tri) // 2] if tri else None,
        "apl_median": sorted(apl)[len(apl) // 2] if apl else None,
        "cl_median": sorted(cl)[len(cl) // 2] if cl else None,
    }


def _anomaly_flags(
    run: Run,
    base: dict,
    tri_ratio: float,
    apl_ratio: float,
    cl_ratio: float,
):
    """
    @brief Wyznacza flagi anomalii na podstawie odchyleń metryk od bazowych median

    Funkcja porównuje metryki badanego Run z medianami z _baseline_stats.
    Flagi wykrywane są przy użyciu progów w postaci mnożników (ratio):
    - triangles: LOW/HIGH_TRIANGLES,
    - avg_path_len: LOW/HIGH_APL,
    - clustering: LOW/HIGH_CLUSTERING,
    - dodatkowo DISCONNECTED jeśli run.is_connected == False.

    Dla HIGH_* używany jest próg odwrotny (dzielenie przez ratio),
    z zabezpieczeniem przed dzieleniem przez 0.

    """
    flags = []

    if run.triangles is not None and base["tri_median"]:
        if run.triangles < base["tri_median"] * tri_ratio:
            flags.append("LOW_TRIANGLES")
        if run.triangles > base["tri_median"] / max(tri_ratio, 1e-9):
            flags.append("HIGH_TRIANGLES")

    if run.avg_path_len is not None and base["apl_median"]:
        if run.avg_path_len > base["apl_median"] * apl_ratio:
            flags.append("HIGH_APL")
        if run.avg_path_len < base["apl_median"] / max(apl_ratio, 1e-9):
            flags.append("LOW_APL")

    if run.clustering is not None and base["cl_median"]:
        if run.clustering < base["cl_median"] * cl_ratio:
            flags.append("LOW_CLUSTERING")
        if run.clustering > base["cl_median"] / max(cl_ratio, 1e-9):
            flags.append("HIGH_CLUSTERING")

    if run.is_connected is False:
        flags.append("DISCONNECTED")

    return flags


@transaction.atomic
def try_create_discovery(
    degrees_hash: str,
    mode: str,
    eps: float = 1e-6,
    tri_ratio: float = 0.5,
    apl_ratio: float = 1.25,
    cl_ratio: float = 0.7,
):
    """
    @brief Próbuje utworzyć wpis Discovery dla najlepszego wyniku lub anomalii

    Funkcja:
    - wyszukuje najlepszy Run dla danego degrees_hash i trybu (min/max),
    - porównuje go z ostatnim zapisanym Discovery (poprzednim rekordem),
    - oblicza poprawę (improvement) jeśli zaszła istotna zmiana,
    - wykrywa anomalie metryk względem statystyk bazowych.

    """
    qs = Run.objects.filter(degrees_hash=degrees_hash).exclude(objective_value__isnull=True)
    if not qs.exists():
        return None

    best = (
        qs.order_by("objective_value", "time_ms").first()
        if mode == "min"
        else qs.order_by("-objective_value", "time_ms").first()
    )
    if best is None or best.objective_value is None:
        return None

    prev = (
        Discovery.objects.filter(degrees_hash=degrees_hash, mode=mode)
        .order_by("-created_at")
        .first()
    )
    prev_val = prev.new_best_value if prev else None

    new_val = float(best.objective_value)
    base = _baseline_stats(degrees_hash)
    flags = _anomaly_flags(best, base, tri_ratio, apl_ratio, cl_ratio)

    if prev_val is None:
        return Discovery.objects.create(
            degrees_hash=degrees_hash,
            mode=mode,
            objective_name=best.objective_name or "spectral_radius",
            best_run=best,
            prev_best_value=None,
            new_best_value=new_val,
            improvement=None,
            anomaly_flags=flags,
            note=f"FIRST for this degrees_hash/mode. flags={flags}",
        )

    if not _better(new_val, float(prev_val), mode, eps):
        if len(flags) >= 2:
            return Discovery.objects.create(
                degrees_hash=degrees_hash,
                mode=mode,
                objective_name=best.objective_name or "spectral_radius",
                best_run=best,
                prev_best_value=float(prev_val),
                new_best_value=new_val,
                improvement=0.0,
                anomaly_flags=flags,
                note=f"ANOMALY without new record. flags={flags}",
            )
        return None

    improvement = (float(prev_val) - new_val) if mode == "min" else (new_val - float(prev_val))
    return Discovery.objects.create(
        degrees_hash=degrees_hash,
        mode=mode,
        objective_name=best.objective_name or "spectral_radius",
        best_run=best,
        prev_best_value=float(prev_val),
        new_best_value=new_val,
        improvement=float(improvement),
        anomaly_flags=flags,
        note=f"NEW BEST + flags={flags}",
    )