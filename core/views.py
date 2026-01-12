from __future__ import annotations

import json

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import Run, AutoSearchJob
from .services.generator import generate_fixed_sum
from .services.hh import is_graphical_havel_hakimi
from .services.runner import run_algorithm, degrees_hash, normalize_edges, g6_to_b64
from .services.meta import hill_climb, simulated_annealing
from .services.graph6 import edges_to_graph6
from .services.nauty import canonical_g6_via_labelg
from .services.spectrum import spectral_radius

from .services.autosearch import start_job


def dashboard(request):
    return render(request, "dashboard.html")


def _read_json(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return None


def _run_to_json(run: Run) -> dict:
    return {
        "id": run.id,
        "algorithm": run.algorithm,
        "n": run.n,
        "k": run.k,
        "degrees": run.degrees,
        "edges": run.edges,
        "graph6_b64": run.graph6_b64,
        "canonical_g6_b64": run.canonical_g6_b64,
        "graph6_decoded": run.graph6_decoded,
        "canonical_g6_decoded": run.canonical_g6_decoded,
        "time_ms": run.time_ms,
        "seed": run.seed,
        "created_at": run.created_at.isoformat(),
        "objective_name": run.objective_name,
        "objective_mode": run.objective_mode,
        "objective_value": run.objective_value,
        "spectral_radius": run.spectral_radius,
        "iterations": run.iterations,
        "accepted_moves": run.accepted_moves,
        # jak masz dodatkowe pola w Run – Django po prostu je zignoruje tu, jeśli nie dopiszesz
    }


def _save_run(algorithm: str, degrees: list[int], k: int | None, seed: int | None, result: dict) -> Run:
    return Run.objects.create(
        algorithm=algorithm,
        n=len(degrees),
        k=k,
        degrees=degrees,
        degrees_hash=result.get("degrees_hash") or degrees_hash(degrees),
        edges=[[u, v] for (u, v) in result["edges"]],
        graph6_b64=result["graph6_b64"],
        canonical_g6_b64=result["canonical_g6_b64"],
        graph6_decoded=result.get("graph6"),
        canonical_g6_decoded=result.get("canonical_g6"),
        time_ms=result["time_ms"],
        seed=seed,
        is_graphical=True,
        objective_name=result.get("objective_name", "spectral_radius"),
        objective_mode=result.get("objective_mode", "min"),
        objective_value=result.get("objective_value"),
        spectral_radius=result.get("spectral_radius"),
        iterations=result.get("iterations"),
        accepted_moves=result.get("accepted_moves"),
        meta_params=result.get("meta_params"),
    )


@csrf_exempt
def api_generate(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    data = _read_json(request)
    if not data:
        return HttpResponseBadRequest("bad json")

    n = int(data.get("n"))
    k = int(data.get("k"))
    seed = data.get("seed")
    seed = int(seed) if seed is not None else None
    max_attempts = int(data.get("max_attempts", 2000))

    deg = generate_fixed_sum(n, k, seed=seed, max_attempts=max_attempts)
    ok = is_graphical_havel_hakimi(deg)

    return JsonResponse({"n": n, "k": k, "seed": seed, "degrees": deg, "graphical": ok})


def _api_run_basic(request, algorithm: str):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    data = _read_json(request)
    if not data:
        return HttpResponseBadRequest("bad json")

    degrees = data.get("degrees")
    if not isinstance(degrees, list):
        return HttpResponseBadRequest("degrees must be list")

    degrees = [int(x) for x in degrees]
    k = data.get("k")
    k = int(k) if k is not None else None

    seed = data.get("seed")
    seed = int(seed) if seed is not None else None

    try:
        result = run_algorithm(algorithm, degrees, seed=seed)
        run = _save_run(algorithm, degrees, k, seed, result)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(_run_to_json(run))


@csrf_exempt
def api_run_greedy(request):
    return _api_run_basic(request, "greedy")


@csrf_exempt
def api_run_random(request):
    return _api_run_basic(request, "random")


@csrf_exempt
def api_run_exact(request):
    # dalej endpoint nazywa się /exact, ale w UI możesz pisać "backtracking realization"
    return _api_run_basic(request, "exact")


def _run_meta_common(degrees: list[int], mode: str, seed: int | None, edges_final: list[tuple[int, int]]) -> dict:
    edges_final = normalize_edges(len(degrees), edges_final)
    g6 = edges_to_graph6(len(degrees), edges_final)
    canon = canonical_g6_via_labelg(g6)
    sr = spectral_radius(len(degrees), edges_final)

    return {
        "edges": edges_final,
        "graph6": g6,
        "canonical_g6": canon,
        "graph6_b64": g6_to_b64(g6),
        "canonical_g6_b64": g6_to_b64(canon),
        "spectral_radius": float(sr),
        "objective_value": float(sr),
        "objective_name": "spectral_radius",
        "objective_mode": mode,
        "degrees_hash": degrees_hash(degrees),
        "seed": seed,
    }


@csrf_exempt
def api_run_hc(request):
    return _api_run_meta(request, "hc")


@csrf_exempt
def api_run_sa(request):
    return _api_run_meta(request, "sa")


def _api_run_meta(request, algorithm: str):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    data = _read_json(request)
    if not data:
        return HttpResponseBadRequest("bad json")

    degrees = data.get("degrees")
    if not isinstance(degrees, list):
        return HttpResponseBadRequest("degrees must be list")
    degrees = [int(x) for x in degrees]

    k = data.get("k")
    k = int(k) if k is not None else None

    seed = data.get("seed")
    seed = int(seed) if seed is not None else None

    mode = data.get("mode", "min")
    if mode not in ("min", "max"):
        return JsonResponse({"error": "mode must be min or max"}, status=400)

    iterations = int(data.get("iterations", 2000))
    if iterations < 1:
        return JsonResponse({"error": "iterations must be >= 1"}, status=400)

    # optional: connected_only (jak nie ma w UI to default False)
    connected_only = bool(data.get("connected_only", False))

    # start graph: greedy (stabilny)
    try:
        base = run_algorithm("greedy", degrees, seed=seed)
        start_edges = [tuple(e) for e in base["edges"]]
    except Exception as e:
        return JsonResponse({"error": f"start graph failed: {e}"}, status=400)

    try:
        if algorithm == "hc":
            meta = hill_climb(degrees, start_edges, seed=seed, iterations=iterations, mode=mode, connected_only=connected_only)
        else:
            t0_temp = float(data.get("t0", 1.0))
            t_end = float(data.get("t_end", 0.001))
            meta = simulated_annealing(
                degrees, start_edges, seed=seed, iterations=iterations,
                t0_temp=t0_temp, t_end=t_end, mode=mode, connected_only=connected_only
            )

        common = _run_meta_common(degrees, mode, seed, meta["edges"])
        common.update({
            "time_ms": meta["time_ms"],
            "iterations": meta["iterations"],
            "accepted_moves": meta["accepted_moves"],
            "meta_params": meta["meta_params"],
            "objective_value": float(meta["objective"]),
            "spectral_radius": float(meta["spectral_radius"]),
        })

        run = _save_run(algorithm, degrees, k, seed, common)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(_run_to_json(run))


def api_runs(request):
    qs = Run.objects.order_by("-created_at")[:300]
    return JsonResponse({"runs": [_run_to_json(r) for r in qs]})


def api_final(request):
    mode = request.GET.get("mode", "min")
    if mode not in ("min", "max"):
        return JsonResponse({"error": "mode must be min or max"}, status=400)

    deg_param = request.GET.get("degrees_hash")
    n = request.GET.get("n")
    k = request.GET.get("k")

    qs = Run.objects.exclude(objective_value__isnull=True)

    if deg_param:
        qs = qs.filter(degrees_hash=deg_param)
    else:
        if n is not None:
            qs = qs.filter(n=int(n))
        if k is not None:
            qs = qs.filter(k=int(k))

    if not qs.exists():
        return JsonResponse({"error": "no runs found"}, status=404)

    best = qs.order_by("objective_value", "time_ms").first() if mode == "min" else qs.order_by("-objective_value", "time_ms").first()
    return JsonResponse({"best": _run_to_json(best)})


def api_discoveries(request):
    # jeśli masz model Discovery – podłączymy go; jeśli nie masz, endpoint nadal działa.
    try:
        from .models import Discovery
        qs = Discovery.objects.order_by("-created_at")[:200]
        out = []
        for d in qs:
            out.append({
                "id": d.id,
                "time": d.created_at.isoformat(),
                "degrees_hash": d.degrees_hash,
                "mode": d.mode,
                "new_best": d.new_best,
                "impr": d.improvement,
                "flags": d.anomaly_flags,
                "algo": d.algo,
            })
        return JsonResponse({"discoveries": out})
    except Exception:
        return JsonResponse({"discoveries": []})


@csrf_exempt
def api_autosearch_start(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")
    data = _read_json(request)
    if not data:
        return HttpResponseBadRequest("bad json")

    job = start_job(data)
    return JsonResponse({"job_id": job.id, "status": job.status})


def api_autosearch_status(request):
    job_id = request.GET.get("job_id")
    if not job_id:
        return JsonResponse({"error": "job_id required"}, status=400)

    try:
        job = AutoSearchJob.objects.get(id=int(job_id))
    except Exception:
        return JsonResponse({"error": "job not found"}, status=404)

    return JsonResponse({
        "job_id": job.id,
        "status": job.status,
        "progress_done": job.progress_done,
        "progress_total": job.progress_total,
        "msg": job.last_message,
        "error": job.error,
    })