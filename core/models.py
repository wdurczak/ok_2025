from django.db import models

class Run(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    n = models.IntegerField()
    k = models.IntegerField(null=True, blank=True)

    degrees = models.JSONField()
    degrees_hash = models.CharField(max_length=64, db_index=True)

    algorithm = models.CharField(max_length=32)  # greedy/random/exact/hc/sa
    edges = models.JSONField()

    graph6_b64 = models.TextField()
    canonical_g6_b64 = models.TextField()
    graph6_decoded = models.TextField(null=True, blank=True)
    canonical_g6_decoded = models.TextField(null=True, blank=True)

    time_ms = models.IntegerField()
    seed = models.IntegerField(null=True, blank=True)
    is_graphical = models.BooleanField(default=True)

    objective_name = models.CharField(max_length=64, default="spectral_radius")
    objective_mode = models.CharField(max_length=3, default="min")  # min/max
    objective_value = models.FloatField(null=True, blank=True)
    spectral_radius = models.FloatField(null=True, blank=True)

    iterations = models.IntegerField(null=True, blank=True)
    accepted_moves = models.IntegerField(null=True, blank=True)
    meta_params = models.JSONField(null=True, blank=True)
    connected_only = models.BooleanField(default=False)

    # --- NOWE: metryki strukturalne/anomalie ---
    triangles = models.IntegerField(null=True, blank=True)
    avg_path_len = models.FloatField(null=True, blank=True)
    clustering = models.FloatField(null=True, blank=True)
    is_connected = models.BooleanField(null=True, blank=True)

    def __str__(self):
        return f"{self.algorithm} n={self.n} t={self.time_ms}ms"


class Discovery(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    degrees_hash = models.CharField(max_length=64, db_index=True)
    mode = models.CharField(max_length=3)  # min/max
    objective_name = models.CharField(max_length=64, default="spectral_radius")

    best_run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="discoveries")

    prev_best_value = models.FloatField(null=True, blank=True)
    new_best_value = models.FloatField()
    improvement = models.FloatField(null=True, blank=True)

    # tu jest „wow” info dla człowieka
    anomaly_flags = models.JSONField(default=list)  # ["LOW_TRIANGLES", "HIGH_APL", ...]
    note = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["degrees_hash", "mode"])]

    def __str__(self):
        return f"Discovery {self.degrees_hash} {self.mode} {self.new_best_value}"


class AutoSearchJob(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=16, default="queued")  # queued/running/done/failed
    params = models.JSONField(default=dict)

    progress_done = models.IntegerField(default=0)
    progress_total = models.IntegerField(default=0)

    last_message = models.TextField(blank=True, default="")
    error = models.TextField(blank=True, default="")