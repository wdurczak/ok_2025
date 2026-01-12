from django.urls import path
from core import views

urlpatterns = [
    path("", views.dashboard),

    path("api/generate", views.api_generate),
    path("api/run/greedy", views.api_run_greedy),
    path("api/run/random", views.api_run_random),
    path("api/run/exact", views.api_run_exact),

    path("api/run/hc", views.api_run_hc),
    path("api/run/sa", views.api_run_sa),

    path("api/runs", views.api_runs),
    path("api/final", views.api_final),

    path("api/discoveries", views.api_discoveries),

    path("api/autosearch/start", views.api_autosearch_start),
    path("api/autosearch/status", views.api_autosearch_status),
]