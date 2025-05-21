# tickets/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError # Для метода delete в CustomFormField
import os

# ------------------- Модель Агента (Пользователя) -------------------
class Agent(AbstractUser):
    ROLE_CHOICES = [
        ('agent_l1', 'Агент L1'),
        ('agent_l2', 'Агент L2'),
        ('manager_l1', 'Руководитель L1'),
        ('manager_l2', 'Руководитель L2'),
        ('super_admin', 'Супер-Администратор'),
    ]
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='agent_l1', 
        verbose_name="Роль"
    )
    
    LINE_CHOICES = [
        (1, 'Линия 1'),
        (2, 'Линия 2'),
        # (None, 'Не применимо/Все линии') # Можно добавить, если нужно явно указать
    ]
    support_line = models.IntegerField(
        choices=LINE_CHOICES, 
        null=True, 
        blank=True, 
        verbose_name="Линия поддержки",
        help_text="Укажите линию поддержки для агентов и руководителей линий."
    )

    class Meta(AbstractUser.Meta):
        verbose_name = "Агент поддержки"
        verbose_name_plural = "Агенты поддержки"
        ordering = ['username']

    def __str__(self):
        return self.get_full_name() or self.username

# ------------------- Справочники для Тикетов -------------------
class TicketCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название категории")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")

    class Meta:
        ordering = ['name']
        verbose_name = "Категория тикета"
        verbose_name_plural = "Категории тикетов"

    def __str__(self):
        return self.name

class TicketStatus(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Название статуса")
    code = models.SlugField(max_length=50, unique=True, verbose_name="Код (для системы)")
    color = models.CharField(max_length=7, default="#777777", verbose_name="Цвет статуса (HEX)", help_text="Например, #FF0000 для красного.")
    is_default_status = models.BooleanField(default=False, verbose_name="Статус по умолчанию для новых тикетов")
    is_resolved_status = models.BooleanField(default=False, verbose_name="Этот статус означает, что проблема решена")
    is_closed_status = models.BooleanField(default=False, verbose_name="Этот статус означает, что тикет закрыт (финальный)")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Статус тикета"
        verbose_name_plural = "Статусы тикетов"

    def __str__(self):
        return self.name

class TicketPriority(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Название приоритета")
    code = models.SlugField(max_length=50, unique=True, verbose_name="Код (для системы)")
    color = models.CharField(max_length=7, default="#FFFFFF", verbose_name="Цвет (HEX)")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Приоритет тикета"
        verbose_name_plural = "Приоритеты тикетов"

    def __str__(self):
        return self.name

# ------------------- Модель для Кастомных Полей Формы -------------------
class CustomFormField(models.Model):
    FIELD_TYPE_CHOICES = [
        ('char', 'Текстовое поле (короткое)'),
        ('text', 'Текстовое поле (длинное)'),
        ('email', 'Email'),
        ('int', 'Целое число'),
        ('bool', 'Да/Нет (чекбокс)'),
        ('date', 'Дата'),
        ('select', 'Выпадающий список'),
    ]
    category = models.ForeignKey(TicketCategory, related_name='custom_fields', on_delete=models.CASCADE, verbose_name="Категория тикета")
    name = models.SlugField(max_length=100, verbose_name="Имя поля (англ., для системы)", help_text="Используется в коде, должно быть уникальным в рамках категории. Только латиница, цифры, подчеркивания.")
    label = models.CharField(max_length=255, verbose_name="Метка поля (для пользователя)")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, verbose_name="Тип поля")
    is_required = models.BooleanField(default=False, verbose_name="Обязательное поле")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок отображения")
    help_text_custom = models.CharField(max_length=255, blank=True, null=True, verbose_name="Подсказка для поля")
    select_choices_json = models.JSONField(blank=True, null=True, verbose_name="Варианты для выпадающего списка (JSON)", help_text='Пример: {"val1": "Опция 1", "val2": "Опция 2"}')
    
    is_standard = models.BooleanField(default=False, verbose_name="Стандартное поле модели Ticket", help_text="Отметьте, если это поле соответствует стандартному полю модели Ticket (например, title, description).")
    can_be_deleted = models.BooleanField(default=True, verbose_name="Можно удалять из настроек категории", help_text="Стандартные поля обычно нельзя удалять.")
    is_active = models.BooleanField(default=True, verbose_name="Активно (отображать на форме)")

    class Meta:
        ordering = ['category', 'order', 'label']
        unique_together = [['category', 'name']]
        verbose_name = "Поле формы категории"
        verbose_name_plural = "Поля форм категорий"

    def __str__(self):
        std_marker = '[STD]' if self.is_standard else ''
        active_marker = '' if self.is_active else '[НЕ АКТИВНО]'
        return f"{self.category.name} - {self.label} ({self.get_field_type_display()}) {std_marker} {active_marker}".strip()

    def delete(self, *args, **kwargs):
        if self.is_standard and not self.can_be_deleted:
            # Вместо ошибки можно просто не давать удалять, но в админке это может быть не очевидно.
            # Ошибка более явная.
            raise ValidationError(f"Стандартное поле '{self.label}' не может быть удалено из настроек категории.")
        super().delete(*args, **kwargs)

# ------------------- Основная Модель Тикета -------------------
class Ticket(models.Model):
    LEVEL_CHOICES = [
        (1, 'Уровень 1 (L1)'),
        (2, 'Уровень 2 (L2)'),
    ]

    # --- Стандартные поля, которые будут управляться через CustomFormField на уровне формы ---
    title = models.CharField(max_length=255, verbose_name="Тема тикета")
    description = models.TextField(verbose_name="Описание проблемы") # Будет управляться 'text' типом CustomFormField
    reporter_name = models.CharField(max_length=255, verbose_name="ФИО заявителя")
    reporter_email = models.EmailField(verbose_name="Email заявителя") # Будет управляться 'email' типом CustomFormField
    reporter_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон заявителя")
    reporter_building = models.CharField(max_length=100, blank=True, null=True, verbose_name="Корпус")
    reporter_room = models.CharField(max_length=50, blank=True, null=True, verbose_name="Комната/Кабинет")
    reporter_department = models.CharField(max_length=150, blank=True, null=True, verbose_name="Подразделение")
    # ------------------------------------------------------------------------------------

    ticket_id_display = models.CharField(max_length=20, unique=True, blank=True, verbose_name="ID тикета")
    status = models.ForeignKey(TicketStatus, on_delete=models.PROTECT, related_name='tickets', verbose_name="Статус")
    priority = models.ForeignKey(TicketPriority, on_delete=models.PROTECT, related_name='tickets', null=True, blank=True, verbose_name="Приоритет")
    category = models.ForeignKey(TicketCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', verbose_name="Категория") # Это поле обязательно для связи с CustomFormField
    assignee = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets', verbose_name="Исполнитель")
    ticket_level = models.IntegerField(choices=LEVEL_CHOICES, default=1, verbose_name="Уровень поддержки")
    
    # Поле для данных кастомных полей, которые НЕ являются стандартными полями Ticket
    custom_form_data = models.JSONField(blank=True, null=True, default=dict, verbose_name="Данные дополнительных полей")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата последнего обновления")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата решения")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата закрытия")

    def generate_ticket_id(self):
        current_year = timezone.now().year
        last_ticket_count = Ticket.objects.filter(created_at__year=current_year).count()
        next_num = last_ticket_count + 1
        return f"IT-{current_year}-{str(next_num).zfill(5)}"

    def save(self, *args, **kwargs):
        if not self.pk and not self.ticket_id_display: 
            self.ticket_id_display = self.generate_ticket_id()
        
        is_new_ticket = self._state.adding
        old_ticket_level = None
        if not is_new_ticket:
            try:
                old_ticket_level = Ticket.objects.get(pk=self.pk).ticket_level
            except Ticket.DoesNotExist: # На случай, если это все же новый, но pk уже есть (редко)
                pass
        
        # Логика для дат resolved_at и closed_at
        if self.status: 
            if self.status.is_resolved_status and not self.resolved_at: self.resolved_at = timezone.now()
            elif not self.status.is_resolved_status and self.resolved_at: self.resolved_at = None
            if self.status.is_closed_status and not self.closed_at: self.closed_at = timezone.now()
            elif not self.status.is_closed_status and self.closed_at: self.closed_at = None
        
        # Логика при смене ticket_level (если нужно сбрасывать исполнителя)
        if not is_new_ticket and old_ticket_level is not None and old_ticket_level != self.ticket_level:
            self.assignee = None # Сбрасываем исполнителя при смене уровня
            # Можно добавить создание системного комментария здесь или в view

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at'] 
        verbose_name = "Тикет"
        verbose_name_plural = "Тикеты"

    def __str__(self):
        return f"{self.ticket_id_display} - {self.title}"

# ------------------- Модели Комментариев и Вложений -------------------
class Comment(models.Model):
    # ... (код без изменений) ...
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments', verbose_name="Тикет")
    author_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='ticket_comments', verbose_name="Автор (агент)")
    author_name_display = models.CharField(max_length=255, blank=True, verbose_name="Имя автора (для отображения)")
    body = models.TextField(verbose_name="Текст комментария")
    is_internal = models.BooleanField(default=False, verbose_name="Внутренний комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def save(self, *args, **kwargs):
        if self.author_agent and not self.author_name_display:
            self.author_name_display = self.author_agent.get_full_name() or self.author_agent.username
        super().save(*args, **kwargs)
    class Meta: ordering = ['created_at']; verbose_name = "Комментарий"; verbose_name_plural = "Комментарии"
    def __str__(self):
        author = self.author_name_display or (self.author_agent.username if self.author_agent else "Аноним")
        return f"Комментарий от {author} к тикету #{self.ticket.ticket_id_display if self.ticket else 'N/A'}"

def ticket_attachment_path(instance, filename):
    # ... (код без изменений) ...
    now = timezone.now(); ticket_identifier_parts = []
    if instance.ticket: ticket_identifier_parts.append(instance.ticket.ticket_id_display or str(instance.ticket.id))
    elif instance.comment and instance.comment.ticket: ticket_identifier_parts.append(instance.comment.ticket.ticket_id_display or str(instance.comment.ticket.id))
    else: ticket_identifier_parts.append("unknown_ticket")
    if instance.comment: ticket_identifier_parts.append(f"comment_{instance.comment.id}")
    ticket_identifier = "_".join(ticket_identifier_parts); safe_filename = os.path.basename(filename)
    return os.path.join('ticket_attachments', str(now.year), str(now.month).zfill(2), str(now.day).zfill(2), str(ticket_identifier), safe_filename)

class Attachment(models.Model):
    # ... (код без изменений) ...
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments', verbose_name="Тикет", null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='attachments', verbose_name="Комментарий", null=True, blank=True)
    file = models.FileField(upload_to=ticket_attachment_path, verbose_name="Файл")
    uploaded_by_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_attachments', verbose_name="Загрузил (агент)")
    uploaded_by_name_display = models.CharField(max_length=255, blank=True, verbose_name="Загрузил (имя для отображения)")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")
    def save(self, *args, **kwargs):
        if self.uploaded_by_agent and not self.uploaded_by_name_display: self.uploaded_by_name_display = self.uploaded_by_agent.get_full_name() or self.uploaded_by_agent.username
        super().save(*args, **kwargs)
    class Meta: ordering = ['-uploaded_at']; verbose_name = "Вложение"; verbose_name_plural = "Вложения"
    def __str__(self): return os.path.basename(self.file.name) if self.file else "Пустое вложение"