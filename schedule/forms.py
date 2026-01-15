from django import forms
from django.utils import timezone

from .models import InspectorProfile, ScheduleEntry, User


class ScheduleEntryForm(forms.ModelForm):
    """Formulário principal para criar e editar inspeções e ausências."""

    def __init__(
        self,
        *args,
        auth_user=None,
        schedule_user=None,
        inspector_profile=None,
        **kwargs,
    ):
        instance = kwargs.get("instance")
        self.auth_user = auth_user
        self.schedule_user = schedule_user or self._resolve_schedule_user(auth_user)
        self.current_inspector_profile = inspector_profile or self._resolve_inspector_profile(self.schedule_user)
        self._original_status = instance.status if instance else None
        super().__init__(*args, **kwargs)

        self.fields["date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["status"].required = False
        self.fields["inspection_type"].required = False
        self.fields["sa_number"].required = False
        self.fields["client"].required = False

        self.fields["entry_type"].label = "Tipo de entrada"
        self.fields["inspector"].label = "Inspetor"
        self.fields["date"].label = "Data"
        self.fields["sa_number"].label = "CP"
        self.fields["content"].label = "Descrição"
        self.fields["inspection_type"].label = "Tipo de inspeção"
        self.fields["client"].label = "Cliente"
        self.fields["status"].label = "Status"

        self.fields["entry_type"].choices = [("", "Selecione"), *[
            choice for choice in self.fields["entry_type"].choices if choice[0]
        ]]
        self.fields["inspection_type"].choices = [("", "Selecione"), *[
            choice for choice in self.fields["inspection_type"].choices if choice[0]
        ]]
        self.fields["status"].choices = [("", "Selecione"), *[
            choice for choice in self.fields["status"].choices if choice[0]
        ]]

        available_inspectors = (
            InspectorProfile.objects.filter(is_active=True)
            .select_related("user")
            .order_by("full_name")
        )
        if self._user_is_manager():
            self.fields["inspector"].queryset = available_inspectors
        else:
            if self.current_inspector_profile:
                self.fields["inspector"].queryset = available_inspectors.filter(
                    pk=self.current_inspector_profile.pk
                )
                self.fields["inspector"].initial = self.current_inspector_profile
            else:
                self.fields["inspector"].queryset = available_inspectors.none()
                self.fields["inspector"].help_text = (
                    "Nenhum perfil de inspetor ativo associado ao seu usuário."
                )

    class Meta:
        model = ScheduleEntry
        fields = (
            "entry_type",
            "inspector",
            "date",
            "sa_number",
            "content",
            "inspection_type",
            "client",
            "status",
        )

    def _user_is_manager(self):
        if self.schedule_user and self.schedule_user.role == User.ROLE_MANAGER:
            return True
        if getattr(self.auth_user, "is_staff", False):
            return True
        return False

    @staticmethod
    def _resolve_schedule_user(auth_user):
        if not getattr(auth_user, "is_authenticated", False):
            return None
        return User.objects.filter(username=auth_user.username).first()

    @staticmethod
    def _resolve_inspector_profile(schedule_user):
        if not schedule_user:
            return None
        return (
            InspectorProfile.objects.filter(user=schedule_user, is_active=True)
            .select_related("user")
            .first()
        )

    def clean_inspector(self):
        inspector = self.cleaned_data.get("inspector")
        if inspector and not self._user_is_manager():
            if not self.current_inspector_profile or inspector.pk != self.current_inspector_profile.pk:
                raise forms.ValidationError("Você só pode gerenciar entradas vinculadas ao seu perfil.")
        return inspector

    def clean(self):
        cleaned_data = super().clean()
        entry_type = cleaned_data.get("entry_type")
        inspector = cleaned_data.get("inspector")
        date = cleaned_data.get("date")
        status = cleaned_data.get("status")
        inspection_type = cleaned_data.get("inspection_type")
        client = cleaned_data.get("client")

        if entry_type == ScheduleEntry.ENTRY_TYPE_INSPECTION:
            if not inspection_type:
                self.add_error("inspection_type", "Selecione o tipo de inspeção.")
            if inspection_type == ScheduleEntry.INSPECTION_TYPE_EXTERNAL and not client:
                self.add_error("client", "Informe o cliente para inspeções externas.")
            if inspection_type != ScheduleEntry.INSPECTION_TYPE_EXTERNAL:
                cleaned_data["client"] = None
            if inspector and date:
                conflict = ScheduleEntry.objects.filter(
                    inspector=inspector,
                    date=date,
                    entry_type=ScheduleEntry.ENTRY_TYPE_ABSENCE,
                )
                if self.instance.pk:
                    conflict = conflict.exclude(pk=self.instance.pk)
                if conflict.exists():
                    raise forms.ValidationError(
                        "Não é possível agendar inspeção em um dia marcado como ausência para este inspetor."
                    )
            if not status:
                cleaned_data["status"] = ScheduleEntry.STATUS_SCHEDULED
        else:
            cleaned_data["inspection_type"] = None
            cleaned_data["client"] = None
            cleaned_data["status"] = None

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        entry_type = instance.entry_type
        status = instance.status

        if entry_type in {ScheduleEntry.ENTRY_TYPE_ABSENCE, ScheduleEntry.ENTRY_TYPE_REPORT}:
            instance.inspection_type = None
            instance.status = None
            instance.concluded_by = None
            instance.concluded_at = None
        else:
            concluded_statuses = {ScheduleEntry.STATUS_COMPLETED, ScheduleEntry.STATUS_FAILED}
            original_status = self._original_status
            if status in concluded_statuses:
                if original_status != status or not instance.concluded_at:
                    if self.schedule_user:
                        instance.concluded_by = self.schedule_user
                    instance.concluded_at = timezone.now()
            else:
                instance.concluded_by = None
                instance.concluded_at = None

        if not self._user_is_manager() and self.current_inspector_profile:
            instance.inspector = self.current_inspector_profile

        if commit:
            instance.save()
            self.save_m2m()
        return instance
