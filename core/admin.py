from django.contrib import admin
from core.models import Run

@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "algorithm", "n", "time_ms", "seed")
    list_filter = ("algorithm", "n")
    search_fields = ("graph6", "canonical_g6")