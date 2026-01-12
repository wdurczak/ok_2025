from __future__ import annotations

import threading
import time
import multiprocessing as mp
from django.utils import timezone

from core.models import AutoSearchJob, Run
from core.services.generator import generate_fixed_sum
from core.services.hh import is_graphical_havel_hakimi
from core.services.runner import run_algorithm, degrees_hash, normalize_edges, g6_to_b64
from core.services.meta import hill_climb, simulated_annealing
from core.services.graph6 import edges_to_graph6
from core.services.nauty import canonical_g6_via_labelg
from core.services.spectrum import spectral_radius
from core.services.metrics import (
    build_adj, count_triangles, avg_clustering, avg_shortest_path_len, is_connected
)
from core.services.discovery import try_create_discovery

_lock = threading.Lock()


def _compute_structural(n: int, edges: list[tuple[int, int]], seed: int | None):
    """
    @brief Oblicza metryki strukturalne grafu dla danego zbioru krawędzi

    Funkcja wyznacza:
    - liczbę trójkątów,
    - średni współczynnik klasteryzacji,
    - średnią długość najkrótszych ścieżek (APL) lub None jeśli graf niespójny,
    - spójność grafu.

    Dla dużych n stosowane jest próbkowanie źródeł BFS w APL.

    @param n Liczba wierzchołków
    @param edges Lista krawędzi grafu
    @param seed Ziarno losowe używane do próbkowania źródeł APL
    @return Krotka (triangles, avg_path_len|None, clustering, is_connected)
    """
    adj = build_adj(n, edges)
    tri = count_triangles(n, adj)
    cl = avg_clustering(n, adj)
    sample = 0
    if n >= 160:
        sample = min(40, n)
    apl = avg_shortest_path_len(n, adj, sample_sources=sample, seed=seed)
    conn = is_connected(n, adj)
    return tri, apl, cl, conn


def _save_run_from_result(
    algorithm: str,
    degrees: list[int],
    k: int | None,
    seed: int | None,
    result: dict,
):
    """
    @brief Zapisuje wynik uruchomienia algorytmu jako obiekt Run w bazie danych

    Funkcja:
    - normalizuje krawędzie i wyznacza graph6,
    - oblicza kanoniczną postać grafu (nauty/labelg),
    - oblicza promień spektralny oraz metryki strukturalne,
    - tworzy rekord Run z pełnym zestawem pól.

    @param algorithm Nazwa algorytmu (np. "greedy", "random", "hc", "sa")
    @param degrees Sekwencja stopni
    @param k Liczba krawędzi (opcjonalnie)
    @param seed Ziarno losowe dla uruchomienia
    @param result Słownik wyniku (musi zawierać co najmniej "edges")
    @return Utworzony obiekt Run
    """
    edges = normalize_edges(len(degrees), [tuple(e) for e in result["edges"]])
    g6 = edges_to_graph6(len(degrees), edges)
    canon = canonical_g6_via_labelg(g6)

    sr = spectral_radius(len(degrees), edges)
    tri, apl, cl, conn = _compute_structural(len(degrees), edges, seed)

    return Run.objects.create(
        algorithm=algorithm,
        n=len(degrees),
        k=k,
        degrees=degrees,
        degrees_hash=degrees_hash(degrees),
        edges=[[u, v] for (u, v) in edges],
        graph6_b64=g6_to_b64(g6),
        canonical_g6_b64=g6_to_b64(canon),
        graph6_decoded=g6,
        canonical_g6_decoded=canon,
        time_ms=int(result.get("time_ms", 0)),
        seed=seed,
        is_graphical=True,
        objective_name="spectral_radius",
        objective_mode=result.get("objective_mode", "min"),
        objective_value=float(result.get("objective_value", sr)),
        spectral_radius=float(sr),
        iterations=result.get("iterations"),
        accepted_moves=result.get("accepted_moves"),
        meta_params=result.get("meta_params"),
        triangles=int(tri),
        avg_path_len=apl if apl is None else float(apl),
        clustering=float(cl),
        is_connected=bool(conn),
    )


def _edges_connected(n: int, edges: list[tuple[int, int]]) -> bool:
    """
    @brief Sprawdza spójność grafu na podstawie listy krawędzi

    Funkcja buduje listę sąsiedztwa i uruchamia test spójności.

    @param n Liczba wierzchołków
    @param edges Lista krawędzi grafu
    @return True jeśli graf jest spójny, w przeciwnym razie False
    """
    adj = build_adj(n, edges)
    return is_connected(n, adj)


def _run_algorithm_in_subprocess(
    algorithm: str,
    deg: list[int],
    seed: int | None,
    q: mp.Queue,
):
    """
    @brief Uruchamia run_algorithm w osobnym procesie i zwraca wynik przez kolejkę

    Funkcja jest przeznaczona do użycia jako target dla multiprocessing.Process.
    Umieszcza w kolejce:
    - ("ok", result) w przypadku sukcesu,
    - ("err", str(e)) w przypadku błędu.

    @param algorithm Nazwa algorytmu dla run_algorithm
    @param deg Sekwencja stopni
    @param seed Ziarno losowe
    @param q Kolejka międzyprocesowa do zwrotu wyniku
    """
    try:
        res = run_algorithm(algorithm, deg, seed=seed)
        q.put(("ok", res))
    except Exception as e:
        q.put(("err", str(e)))


def run_algorithm_timeout(
    algorithm: str,
    deg: list[int],
    seed: int | None,
    timeout_s: float,
) -> dict | None:
    """
    @brief Uruchamia run_algorithm w osobnym procesie z limitem czasu

    Funkcja tworzy proces potomny, czeka maksymalnie timeout_s sekund,
    a następnie:
    - zwraca dict z wynikiem w przypadku sukcesu,
    - zwraca None przy timeout lub błędzie wykonania.

    @param algorithm Nazwa algorytmu
    @param deg Sekwencja stopni
    @param seed Ziarno losowe
    @param timeout_s Limit czasu w sekundach
    @return Słownik wyniku lub None
    """
    q: mp.Queue = mp.Queue()
    p = mp.Process(
        target=_run_algorithm_in_subprocess,
        args=(algorithm, deg, seed, q),
        daemon=True,
    )
    p.start()
    p.join(timeout_s)

    if p.is_alive():
        p.terminate()
        p.join(1.0)
        return None

    try:
        status, payload = q.get_nowait()
    except Exception:
        return None

    if status != "ok":
        return None

    return payload


def start_job(params: dict) -> AutoSearchJob:
    """
    @brief Tworzy i uruchamia zadanie AutoSearchJob w osobnym wątku

    Funkcja zapisuje rekord AutoSearchJob w statusie "queued" i uruchamia
    wątek wykonujący _run_job(job_id).

    @param params Parametry zadania (np. n, k, batch, iters, seed, itp.)
    @return Utworzony obiekt AutoSearchJob
    """
    job = AutoSearchJob.objects.create(
        status="queued",
        params=params,
        progress_total=int(params.get("batch", 10)),
        progress_done=0,
        last_message="queued",
    )
    t = threading.Thread(target=_run_job, args=(job.id,), daemon=True)
    t.start()
    return job


def _run_job(job_id: int):
    """
    @brief Wykonuje zadanie AutoSearchJob: generowanie sekwencji stopni i uruchamianie heurystyk

    Funkcja:
    - zapewnia, że tylko jedno zadanie działa naraz (globalny lock),
    - iteracyjnie generuje graficzną sekwencję stopni o sumie 2k,
    - uruchamia algorytmy bazowe (greedy/random/exact) w zależności od parametrów,
    - wybiera najlepszą bazę i uruchamia metaheurystyki (hill climbing i SA),
    - zapisuje wyniki jako Run,
    - próbuje utworzyć wpis Discovery (nowy rekord lub anomalia),
    - aktualizuje postęp i status w AutoSearchJob.

    @param job_id ID obiektu AutoSearchJob
    """
    if not _lock.acquire(blocking=False):
        AutoSearchJob.objects.filter(id=job_id).update(
            status="failed",
            error="Another job is running",
        )
        return

    try:
        job = AutoSearchJob.objects.get(id=job_id)
        p = job.params

        n = int(p.get("n", 30))
        k = int(p.get("k", 120))
        batch = int(p.get("batch", 10))
        iters = int(p.get("iters", 6000))
        mode = p.get("mode", "min")
        seed = p.get("seed")

        eps = float(p.get("eps", 1e-6))
        tri_ratio = float(p.get("tri_ratio", 0.5))
        apl_ratio = float(p.get("apl_ratio", 1.25))
        cl_ratio = float(p.get("cl_ratio", 0.7))

        t0 = float(p.get("t0", 1.0))
        t_end = float(p.get("t_end", 0.001))

        do_greedy = bool(p.get("do_greedy", True))
        do_random = bool(p.get("do_random", True))
        random_reps = int(p.get("random_reps", 2))
        do_exact = bool(p.get("do_exact", True))
        exact_n_max = int(p.get("exact_n_max", 20))
        exact_timeout_s = float(p.get("exact_timeout_s", 2.0))

        connected_only = bool(p.get("connected_only", False))
        max_deg_attempts = int(p.get("max_deg_attempts", 20))

        job.status = "running"
        job.started_at = timezone.now()
        job.progress_total = batch
        job.last_message = "running"
        job.save(update_fields=["status", "started_at", "progress_total", "last_message"])

        done = 0
        for i in range(batch):
            try:
                s = int(seed) + i if seed is not None else None

                deg = None
                for att in range(max_deg_attempts):
                    deg_try = generate_fixed_sum(
                        n,
                        k,
                        seed=(None if s is None else s + att),
                        max_attempts=8000,
                    )
                    if not is_graphical_havel_hakimi(deg_try):
                        continue
                    deg = deg_try
                    break

                if deg is None:
                    job.last_message = f"skip: couldn't generate graphical deg (seed={s})"
                    done += 1
                    job.progress_done = done
                    job.save(update_fields=["progress_done", "last_message"])
                    continue

                baseline_edges: list[tuple[int, int]] | None = None
                baseline_best_sr: float | None = None

                def consider_baseline(alg_name: str, res: dict):
                    nonlocal baseline_edges, baseline_best_sr
                    edges = [tuple(e) for e in res["edges"]]
                    if connected_only and not _edges_connected(len(deg), edges):
                        return
                    sr = float(spectral_radius(len(deg), normalize_edges(len(deg), edges)))
                    better = False
                    if baseline_best_sr is None:
                        better = True
                    else:
                        better = (sr < baseline_best_sr) if mode == "min" else (sr > baseline_best_sr)
                    if better:
                        baseline_best_sr = sr
                        baseline_edges = edges

                if do_greedy:
                    g0 = run_algorithm("greedy", deg, seed=s)
                    _save_run_from_result("greedy", deg, k, s, g0)
                    consider_baseline("greedy", g0)

                if do_random:
                    for rr in range(max(1, random_reps)):
                        rs = None if s is None else (s * 1000 + rr)
                        r0 = run_algorithm("random", deg, seed=rs)
                        _save_run_from_result("random", deg, k, rs, r0)
                        consider_baseline("random", r0)

                if do_exact and len(deg) <= exact_n_max:
                    er = run_algorithm_timeout("exact", deg, seed=s, timeout_s=exact_timeout_s)
                    if er is not None:
                        _save_run_from_result("exact_realization", deg, k, s, er)
                        consider_baseline("exact_realization", er)

                if baseline_edges is None:
                    g0 = run_algorithm("greedy", deg, seed=s)
                    baseline_edges = [tuple(e) for e in g0["edges"]]

                start_edges = baseline_edges

                hc = hill_climb(deg, start_edges, seed=s, iterations=iters, mode=mode)
                if (not connected_only) or _edges_connected(len(deg), hc["edges"]):
                    _save_run_from_result(
                        "hc",
                        deg,
                        k,
                        s,
                        {
                            "edges": hc["edges"],
                            "time_ms": hc["time_ms"],
                            "objective_value": hc["objective"],
                            "objective_mode": mode,
                            "iterations": hc["iterations"],
                            "accepted_moves": hc["accepted_moves"],
                            "meta_params": hc["meta_params"],
                        },
                    )

                sa = simulated_annealing(
                    deg,
                    start_edges,
                    seed=s,
                    iterations=iters,
                    t0_temp=t0,
                    t_end=t_end,
                    mode=mode,
                )
                if (not connected_only) or _edges_connected(len(deg), sa["edges"]):
                    _save_run_from_result(
                        "sa",
                        deg,
                        k,
                        s,
                        {
                            "edges": sa["edges"],
                            "time_ms": sa["time_ms"],
                            "objective_value": sa["objective"],
                            "objective_mode": mode,
                            "iterations": sa["iterations"],
                            "accepted_moves": sa["accepted_moves"],
                            "meta_params": sa["meta_params"],
                        },
                    )

                dh = degrees_hash(deg)
                disc = try_create_discovery(
                    dh,
                    mode,
                    eps=eps,
                    tri_ratio=tri_ratio,
                    apl_ratio=apl_ratio,
                    cl_ratio=cl_ratio,
                )
                if disc:
                    job.last_message = f"DISCOVERY: {disc.degrees_hash} flags={disc.anomaly_flags}"
                else:
                    job.last_message = "ok"

            except Exception as e:
                job.last_message = f"iter error: {e}"

            done += 1
            job.progress_done = done
            job.save(update_fields=["progress_done", "last_message"])

        job.status = "done"
        job.finished_at = timezone.now()
        job.last_message = "done"
        job.save(update_fields=["status", "finished_at", "last_message"])

    except Exception as e:
        AutoSearchJob.objects.filter(id=job_id).update(status="failed", error=str(e))
    finally:
        _lock.release()