from django.db import models


class User(models.Model):
    ROLE_INSPECTOR = "INSPECTOR"
    ROLE_MANAGER = "MANAGER"
    ROLE_NORMALUSER = "NORMAL-USER"
    ROLE_CHOICES = (
        (ROLE_INSPECTOR, "Inspetor"),
        (ROLE_MANAGER, "Gestor"),
        (ROLE_NORMALUSER, "Agregador"),
    )

    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return self.username


class InspectorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="inspector_profile")
    full_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.full_name


class ScheduleEntry(models.Model):
    ENTRY_TYPE_INSPECTION = "INSPECTION"
    ENTRY_TYPE_ABSENCE = "ABSENCE"
    ENTRY_TYPE_REPORT = "REPORT"
    ENTRY_TYPE_CHOICES = (
        (ENTRY_TYPE_INSPECTION, "Inspeção"),
        (ENTRY_TYPE_ABSENCE, "Ausência"),
        (ENTRY_TYPE_REPORT, "Relatório"),
    )

    INSPECTION_TYPE_INTERNAL = "INTERNAL"
    INSPECTION_TYPE_EXTERNAL = "EXTERNAL"
    INSPECTION_TYPE_CHOICES = (
        (INSPECTION_TYPE_INTERNAL, "Interna"),
        (INSPECTION_TYPE_EXTERNAL, "Externa"),
    )

    STATUS_SCHEDULED = "AGENDADA"
    STATUS_COMPLETED = "CONCLUIDA"
    STATUS_FAILED = "REPROVADA"
    STATUS_CHOICES = (
        (STATUS_SCHEDULED, "Agendada"),
        (STATUS_COMPLETED, "Concluída"),
        (STATUS_FAILED, "Reprovada"),
    )

    inspector = models.ForeignKey(InspectorProfile, on_delete=models.CASCADE, related_name="schedule_entries")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES)
    date = models.DateField()
    sa_number = models.CharField(max_length=50, blank=True)
    content = models.TextField()
    inspection_type = models.CharField(max_length=20, choices=INSPECTION_TYPE_CHOICES, null=True, blank=True)
    client = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED, null=True, blank=True)
    concluded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="concluded_entries")
    concluded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.entry_type in {self.ENTRY_TYPE_ABSENCE, self.ENTRY_TYPE_REPORT}:
            self.inspection_type = None
            self.client = None
            self.status = None
            self.concluded_by = None
            self.concluded_at = None
        else:
            if self.inspection_type != self.INSPECTION_TYPE_EXTERNAL:
                self.client = None
            if not self.status:
                self.status = self.STATUS_SCHEDULED
            if self.status not in (self.STATUS_COMPLETED, self.STATUS_FAILED):
                self.concluded_by = None
                self.concluded_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        inspector_name = self.inspector.full_name
        return f"{inspector_name} - {self.date}"

