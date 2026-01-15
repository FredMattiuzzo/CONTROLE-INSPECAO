import json
from calendar import Calendar, monthrange
from collections import defaultdict
from datetime import timedelta, datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from .forms import ScheduleEntryForm
from .models import InspectorProfile, ScheduleEntry, User


class ScheduleUserMixin(LoginRequiredMixin):
    """Provides helpers to bridge Django auth users to SAI user records."""

    def get_schedule_user(self):
        if not hasattr(self, "_schedule_user"):
            auth_user = getattr(self.request, "user", None)
            schedule_user = None
            if getattr(auth_user, "is_authenticated", False):
                schedule_user = User.objects.filter(username=auth_user.username).first()
            self._schedule_user = schedule_user
        return self._schedule_user

    def is_manager(self):
        schedule_user = self.get_schedule_user()
        if schedule_user and schedule_user.role == User.ROLE_MANAGER:
            return True
        auth_user = getattr(self.request, "user", None)
        return bool(getattr(auth_user, "is_staff", False))

    def get_inspector_profile(self):
        if not hasattr(self, "_inspector_profile"):
            profile = None
            schedule_user = self.get_schedule_user()
            if schedule_user:
                profile = (
                    InspectorProfile.objects.filter(user=schedule_user, is_active=True)
                    .select_related("user")
                    .first()
                )
            self._inspector_profile = profile
        return self._inspector_profile


class ScheduleFilterMixin(ScheduleUserMixin):
    inspector_param = "inspector"
    sa_param = "sa"

    def get_inspectors(self):
        return (
            InspectorProfile.objects.filter(is_active=True)
            .select_related("user")
            .order_by("full_name")
        )

    def get_selected_inspector(self):
        inspector_id = self.request.GET.get(self.inspector_param)
        if not inspector_id:
            return None
        try:
            return self.get_inspectors().get(pk=inspector_id)
        except InspectorProfile.DoesNotExist:
            return None

    def get_sa_filter(self):
        return self.request.GET.get(self.sa_param, "").strip()

    def apply_filters(self, queryset):
        inspector = self.get_selected_inspector()
        if inspector:
            queryset = queryset.filter(inspector=inspector)
        sa_number = self.get_sa_filter()
        if sa_number:
            queryset = queryset.filter(sa_number__icontains=sa_number)
        return queryset, inspector, sa_number

    def base_context(self):
        return {
            "inspectors": self.get_inspectors(),
            "selected_inspector": self.get_selected_inspector(),
            "sa_filter": self.get_sa_filter(),
            "is_manager": self.is_manager(),
            "current_inspector": self.get_inspector_profile(),
        }

    def get_entry_form(self):
        if not hasattr(self, "_entry_form"):
            form_kwargs = {
                "auth_user": getattr(self.request, "user", None),
                "schedule_user": self.get_schedule_user(),
                "inspector_profile": self.get_inspector_profile(),
            }
            initial = {}
            selected = self.get_selected_inspector()
            if selected:
                initial["inspector"] = selected
            self._entry_form = ScheduleEntryForm(initial=initial, **form_kwargs)
        return self._entry_form


class WeeklyScheduleView(ScheduleFilterMixin, TemplateView):
    template_name = "schedule/weekly.html"
    filters_enabled = False

    def base_context(self):
        base = super().base_context()
        if not self.filters_enabled:
            base["selected_inspector"] = None
            base["sa_filter"] = ""
        return base

    def get_week_offset(self):
        if not hasattr(self, "_week_offset"):
            offset_str = self.request.GET.get("week", "0")
            try:
                self._week_offset = int(offset_str)
            except ValueError:
                self._week_offset = 0
        return self._week_offset

    def get_week_start(self):
        today = timezone.localdate()
        start = today - timedelta(days=today.weekday())
        return start + timedelta(days=self.get_week_offset() * 7)

    def get_week_days(self, start_date):
        return [start_date + timedelta(days=delta) for delta in range(5)]

    def get_entries_for_week(self, start_date):
        end_date = start_date + timedelta(days=4)
        queryset = ScheduleEntry.objects.select_related("inspector", "inspector__user", "concluded_by")
        queryset = queryset.filter(date__range=(start_date, end_date))
        inspector = None
        if self.filters_enabled:
            queryset, inspector, _ = self.apply_filters(queryset)
        entries = list(queryset)
        return entries, inspector

    def build_rows(self, inspectors, week_days, entries):
        row_map = {}
        rows = []
        for inspector in inspectors:
            day_map = {}
            day_entries = []
            for day in week_days:
                bucket = []
                day_map[day] = bucket
                day_entries.append((day, bucket))
            row_map[inspector.pk] = day_map
            rows.append({"inspector": inspector, "day_entries": day_entries})
        for entry in entries:
            day_map = row_map.get(entry.inspector_id)
            if day_map:
                bucket = day_map.get(entry.date)
                if bucket is not None:
                    bucket.append(entry)
        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = self.base_context()
        week_start = self.get_week_start()
        week_days = self.get_week_days(week_start)
        entries, selected_inspector = self.get_entries_for_week(week_start)
        inspectors_qs = base["inspectors"]
        if selected_inspector:
            inspectors_qs = inspectors_qs.filter(pk=selected_inspector.pk)
        display_inspectors = list(inspectors_qs)
        grid_rows = self.build_rows(display_inspectors, week_days, entries)
        context.update(base)
        context.update(
            {
                "week_start": week_start,
                "week_days": week_days,
                "week_end": week_days[-1],
                "week_offset": self.get_week_offset(),
                "previous_offset": self.get_week_offset() - 1,
                "next_offset": self.get_week_offset() + 1,
                "grid_rows": grid_rows,
                "entries": entries,
                "display_inspectors": display_inspectors,
                "entry_form": self.get_entry_form(),
                "entry_create_url": reverse_lazy("schedule:entry_create"),
            }
        )
        return context


class ScheduleEntryMoveView(ScheduleUserMixin, View):
    def post(self, request, pk, *args, **kwargs):
        entry = get_object_or_404(
            ScheduleEntry.objects.select_related("inspector"), pk=pk
        )

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Dados inválidos."}, status=400)

        target_date = payload.get("date")
        target_inspector_id = payload.get("inspector_id")
        if not target_date or not target_inspector_id:
            return JsonResponse({"error": "Data e inspetor são obrigatórios."}, status=400)

        try:
            new_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"error": "Formato de data inválido."}, status=400)

        target_inspector = get_object_or_404(
            InspectorProfile.objects.filter(is_active=True), pk=target_inspector_id
        )

        if not self.is_manager():
            inspector_profile = self.get_inspector_profile()
            if not inspector_profile or entry.inspector_id != inspector_profile.pk:
                return JsonResponse({"error": "Sem permissão para mover esta entrada."}, status=403)
            if target_inspector.pk != inspector_profile.pk:
                return JsonResponse({"error": "Só é possível mover para a sua própria linha."}, status=403)

        entry.inspector = target_inspector
        entry.date = new_date
        entry.save()

        return JsonResponse({"ok": True, "date": entry.date.isoformat(), "inspector_id": entry.inspector_id})


class ScheduleEntryStatusUpdateView(ScheduleUserMixin, View):
    def post(self, request, pk, *args, **kwargs):
        entry = get_object_or_404(
            ScheduleEntry.objects.select_related("inspector"), pk=pk
        )

        if entry.entry_type != ScheduleEntry.ENTRY_TYPE_INSPECTION:
            return JsonResponse({"ok": False, "error": "Somente inspeções podem ter status alterado."}, status=400)

        if not self.is_manager():
            inspector = self.get_inspector_profile()
            if not inspector or inspector.pk != entry.inspector_id:
                raise PermissionDenied

        new_status = (request.POST.get("status") or "").strip().upper()
        allowed = {
            ScheduleEntry.STATUS_SCHEDULED,
            ScheduleEntry.STATUS_COMPLETED,
            ScheduleEntry.STATUS_FAILED,
        }
        if new_status not in allowed:
            return JsonResponse({"ok": False, "error": "Status inválido."}, status=400)

        entry.status = new_status
        if new_status in {ScheduleEntry.STATUS_COMPLETED, ScheduleEntry.STATUS_FAILED}:
            entry.concluded_at = timezone.now()
            entry.concluded_by = self.get_schedule_user()
        else:
            entry.concluded_at = None
            entry.concluded_by = None

        entry.save()

        return JsonResponse({
            "ok": True,
            "status": entry.status,
            "status_display": entry.get_status_display(),
        })


class MonthlyScheduleView(ScheduleFilterMixin, TemplateView):
    template_name = "schedule/monthly.html"

    def get_month_reference(self):
        reference = self.request.GET.get("month")
        today = timezone.localdate()
        if reference:
            try:
                year, month = map(int, reference.split("-"))
                return today.replace(year=year, month=month, day=1)
            except (ValueError, TypeError):
                pass
        return today.replace(day=1)

    def get_calendar_weeks(self, month_start):
        calendar = Calendar(firstweekday=0)
        return calendar.monthdatescalendar(month_start.year, month_start.month)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = self.base_context()
        month_start = self.get_month_reference()
        raw_weeks = self.get_calendar_weeks(month_start)
        queryset = ScheduleEntry.objects.select_related("inspector", "inspector__user", "concluded_by")
        queryset = queryset.filter(date__month=month_start.month, date__year=month_start.year)
        queryset, inspector, _ = self.apply_filters(queryset)
        inspectors_qs = base["inspectors"]
        if inspector:
            inspectors_qs = inspectors_qs.filter(pk=inspector.pk)
        display_inspectors = list(inspectors_qs)
        daily_entries = defaultdict(list)
        for entry in queryset:
            daily_entries[entry.date].append(entry)
        weeks = []
        for week in raw_weeks:
            week_cells = []
            for day in week:
                week_cells.append(
                    {
                        "date": day,
                        "entries": list(daily_entries.get(day, [])),
                        "is_current_month": day.month == month_start.month,
                    }
                )
            weeks.append(week_cells)
        previous_month = (month_start - timedelta(days=1)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        context.update(base)
        context.update(
            {
                "month_start": month_start,
                "weeks": weeks,
                "display_inspectors": display_inspectors,
                "month_previous": previous_month,
                "month_next": next_month,
                "month_end": month_start.replace(day=monthrange(month_start.year, month_start.month)[1]),
                "month_slug": month_start.strftime("%Y-%m"),
                "month_previous_slug": previous_month.strftime("%Y-%m"),
                "month_next_slug": next_month.strftime("%Y-%m"),
                "entry_form": self.get_entry_form(),
                "entry_create_url": reverse_lazy("schedule:entry_create"),
            }
        )
        return context


class ScheduleEntryFormMixin(ScheduleUserMixin):
    model = ScheduleEntry
    form_class = ScheduleEntryForm
    success_url = reverse_lazy("schedule:weekly_schedule")

    def dispatch(self, request, *args, **kwargs):
        if not self.is_manager() and not self.get_inspector_profile():
            raise PermissionDenied("Perfil de inspetor não encontrado para este usuário.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["auth_user"] = getattr(self.request, "user", None)
        kwargs["schedule_user"] = self.get_schedule_user()
        kwargs["inspector_profile"] = self.get_inspector_profile()
        return kwargs

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        return next_url or super().get_success_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "is_manager": self.is_manager(),
                "current_inspector": self.get_inspector_profile(),
            }
        )
        return context


class ScheduleEntryQuerysetMixin(ScheduleUserMixin):
    def get_queryset(self):
        queryset = (
            ScheduleEntry.objects.select_related("inspector", "inspector__user", "concluded_by")
            .order_by("-date", "inspector__full_name")
        )
        if self.is_manager():
            return queryset
        inspector = self.get_inspector_profile()
        if inspector:
            return queryset.filter(inspector=inspector)
        return queryset.none()


class ScheduleEntryCreateView(ScheduleEntryFormMixin, CreateView):
    template_name = "schedule/entry_form.html"


class ScheduleEntryUpdateView(ScheduleEntryFormMixin, ScheduleEntryQuerysetMixin, UpdateView):
    template_name = "schedule/entry_form.html"


class ScheduleEntryDeleteView(ScheduleEntryQuerysetMixin, DeleteView):
    template_name = "schedule/entry_confirm_delete.html"
    success_url = reverse_lazy("schedule:weekly_schedule")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "is_manager": self.is_manager(),
                "current_inspector": self.get_inspector_profile(),
            }
        )
        return context

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        return next_url or super().get_success_url()


class AdminAccessView(ScheduleUserMixin, TemplateView):
    template_name = "schedule/admin_access.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_access_admin = bool(getattr(self.request.user, "is_staff", False) or self.is_manager())
        context.update(
            {
                "can_access_admin": can_access_admin,
                "admin_url": reverse_lazy("admin:index"),
            }
        )
        return context
