from django.urls import path

from .views import (
    MonthlyScheduleView,
    ScheduleEntryCreateView,
    ScheduleEntryDeleteView,
    ScheduleEntryUpdateView,
    ScheduleEntryStatusUpdateView,
    WeeklyScheduleView,
    ScheduleEntryMoveView,
    AdminAccessView,
    ScheduleEntrySearchView,
)

app_name = "schedule"

urlpatterns = [
    path("", WeeklyScheduleView.as_view(), name="weekly_schedule"),
    path("mensal/", MonthlyScheduleView.as_view(), name="monthly_schedule"),
    path("entradas/nova/", ScheduleEntryCreateView.as_view(), name="entry_create"),
    path("entradas/<int:pk>/editar/", ScheduleEntryUpdateView.as_view(), name="entry_update"),
    path("entradas/<int:pk>/status/", ScheduleEntryStatusUpdateView.as_view(), name="entry_status"),
    path("entradas/<int:pk>/excluir/", ScheduleEntryDeleteView.as_view(), name="entry_delete"),
    path("entradas/<int:pk>/mover/", ScheduleEntryMoveView.as_view(), name="entry_move"),
    path("busca/", ScheduleEntrySearchView.as_view(), name="entry_search"),
    path("acesso-superior/", AdminAccessView.as_view(), name="admin_access"),
]
