# tickets/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError
import os

# ------------------- Модель Проекта (Отдела) -------------------
class Project(models.Model):
    name = models.CharField(
        max_length=150, 
        unique=True, 
        verbose_name="Название проекта (отдела)"
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Описание проекта"
    )
    project_email = models.EmailField(
        blank=True, 
        null=True, 
        verbose_name="Email проекта (для уведомлений)",
        help_text="Если указан, может использоваться для отправки/получения уведомлений по тикетам проекта."
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name="Проект активен",
        help_text="Неактивные проекты не будут отображаться для выбора и их тикеты могут быть скрыты."
    )

    class Meta:
        ordering = ['name']
        verbose_name = "Проект (отдел)"
        verbose_name_plural = "Проекты (отделы)"

    def __str__(self):
        return self.name

# ------------------- Модель Агента (Сотрудника поддержки) -------------------
class Agent(AbstractUser):
    AGENT_ROLE_CHOICES = [
        ('agent', 'Агент проекта'),
        ('project_manager', 'Руководитель проекта'),
        ('system_admin', 'Администратор системы'), # Роль для расширенных прав в приложении
    ]
    agent_role = models.CharField(
        max_length=20,
        choices=AGENT_ROLE_CHOICES,
        default='agent',
        verbose_name="Роль в системе"
    )

    projects = models.ManyToManyField(
        Project,
        related_name='agents',
        blank=True, 
        verbose_name="Проекты сотрудника",
        help_text="Проекты, к которым сотрудник имеет доступ и в которых может работать."
    )

    class Meta(AbstractUser.Meta):
        verbose_name = "Сотрудник поддержки"
        verbose_name_plural = "Сотрудники поддержки"
        ordering = ['username']

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_project_manager(self):
        return self.agent_role == 'project_manager'

    @property
    def is_system_admin(self): # Если добавили роль system_admin
        return self.agent_role == 'system_admin'

# ------------------- Справочники для Тикетов -------------------
class TicketCategory(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='ticket_categories',
        verbose_name="Проект"
    )
    name = models.CharField(max_length=100, verbose_name="Название категории")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Категория активна")

    class Meta:
        ordering = ['project__name', 'name']
        verbose_name = "Категория тикета"
        verbose_name_plural = "Категории тикетов"
        unique_together = [['project', 'name']] 

    def __str__(self):
        active_status = "" if self.is_active else " (Неактивна)"
        return f"{self.name} (Проект: {self.project.name}){active_status}"

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

# ------------------- Модель Шаблона Кастомного Поля (Библиотека полей) -------------------
class FieldTemplate(models.Model):
    FIELD_TYPE_CHOICES = [
        ('char', 'Текстовое поле (короткое)'), ('text', 'Текстовое поле (длинное)'),
        ('email', 'Email'), ('int', 'Целое число'),
        ('bool', 'Да/Нет (чекбокс)'), ('date', 'Дата'),
        ('select', 'Выпадающий список'), ('file', 'Файл (вложение)'),
    ]
    name = models.SlugField(max_length=100, unique=True, verbose_name="Уникальное имя поля (англ., для системы)", help_text="Используется в коде. Только латиница, цифры, подчеркивания.")
    label_default = models.CharField(max_length=255, verbose_name="Метка поля по умолчанию", help_text="Как поле будет называться для пользователя, если не переопределено в категории.")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, verbose_name="Тип поля")
    help_text_default = models.CharField(max_length=255, blank=True, null=True, verbose_name="Подсказка для поля по умолчанию")
    select_choices_json_default = models.JSONField(blank=True, null=True, verbose_name="Варианты для выпадающего списка (JSON) по умолчанию", help_text='Если тип поля "Выпадающий список". Пример: {"val1": "Опция 1", "val2": "Опция 2"}')
    is_active = models.BooleanField(default=True, verbose_name="Доступен для добавления в категории", help_text="Если неактивен, его нельзя будет выбрать при настройке полей для категории.")

    class Meta:
        ordering = ['label_default']
        verbose_name = "Шаблон кастомного поля (Библиотека)"
        verbose_name_plural = "Шаблоны кастомных полей (Библиотека)"

    def __str__(self):
        active_status = "" if self.is_active else " (Неактивен для добавления)"
        return f"{self.label_default} ({self.name}) - Тип: {self.get_field_type_display()}{active_status}"

# ------------------- Модель Настроенного Поля для Категории -------------------
class CustomFormField(models.Model):
    category = models.ForeignKey(TicketCategory, related_name='custom_form_fields', on_delete=models.CASCADE, verbose_name="Категория тикета")
    field_template = models.ForeignKey(FieldTemplate, on_delete=models.PROTECT, related_name='category_configurations', verbose_name="Шаблон поля из библиотеки")
    label_override = models.CharField(max_length=255, blank=True, null=True, verbose_name="Метка поля (если отличается от шаблона)", help_text="Оставьте пустым, чтобы использовать метку из шаблона поля.")
    help_text_override = models.CharField(max_length=255, blank=True, null=True, verbose_name="Подсказка для поля (если отличается от шаблона)", help_text="Оставьте пустым, чтобы использовать подсказку из шаблона поля.")
    is_required_in_category = models.BooleanField(default=False, verbose_name="Обязательное поле (в этой категории)")
    order_in_category = models.PositiveIntegerField(default=0, verbose_name="Порядок отображения (в этой категории)")
    is_active_in_category = models.BooleanField(default=True, verbose_name="Активно (в этой категории)", help_text="Отображать это поле на форме для данной категории.")

    class Meta:
        ordering = ['category', 'order_in_category']
        unique_together = [['category', 'field_template']]
        verbose_name = "Настроенное поле для формы категории"
        verbose_name_plural = "Настроенные поля для форм категорий"

    @property
    def name(self): return self.field_template.name
    @property
    def field_type(self): return self.field_template.field_type
    @property
    def effective_label(self): return self.label_override or self.field_template.label_default
    @property
    def effective_help_text(self): return self.help_text_override or self.field_template.help_text_default
    @property
    def effective_select_choices_json(self): return self.field_template.select_choices_json_default

    def __str__(self):
        active_status = "" if self.is_active_in_category else " (Неактивно в этой категории)"
        return f"Поле '{self.effective_label}' ({self.name}) для '{self.category}'{active_status}"

# ------------------- Основная Модель Тикета -------------------
class Ticket(models.Model):
    title = models.CharField(max_length=255, verbose_name="Тема тикета")
    description = models.TextField(verbose_name="Описание проблемы") 
    reporter_name = models.CharField(max_length=255, verbose_name="ФИО заявителя")
    reporter_email = models.EmailField(verbose_name="Email заявителя") 
    reporter_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон заявителя")
    reporter_building = models.CharField(max_length=100, blank=True, null=True, verbose_name="Корпус")
    reporter_room = models.CharField(max_length=50, blank=True, null=True, verbose_name="Комната/Кабинет")
    reporter_department = models.CharField(max_length=150, blank=True, null=True, verbose_name="Подразделение")
    reporter_ip_address = models.GenericIPAddressField(verbose_name="IP-адрес заявителя", null=True, blank=True) # <--- НОВОЕ ПОЛЕ

    ticket_id_display = models.CharField(max_length=20, unique=True, blank=True, verbose_name="ID тикета")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='tickets', verbose_name="Проект (отдел)")
    status = models.ForeignKey(TicketStatus, on_delete=models.PROTECT, related_name='tickets', verbose_name="Статус")
    priority = models.ForeignKey(TicketPriority, on_delete=models.PROTECT, related_name='tickets', null=True, blank=True, verbose_name="Приоритет")
    category = models.ForeignKey(TicketCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', verbose_name="Категория")
    assignee = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets', verbose_name="Исполнитель")
    
    custom_form_data = models.JSONField(blank=True, null=True, default=dict, verbose_name="Данные дополнительных полей")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата последнего обновления")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата решения")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата закрытия")

    def generate_ticket_id(self):
        # (Ваша логика генерации ID с отладкой или без - оставляю вашу последнюю рабочую версию)
        current_year = timezone.now().year
        project_code = "N_A"; next_num_for_project = 1
        if self.project:
            project_name_alphanum = "".join(filter(str.isalnum, self.project.name)); project_code = project_name_alphanum[:3].upper()
            if not project_code: project_code = f"P{self.project.pk}"[:3].upper()
            prefix_to_match = f"{project_code}-{current_year}-"
            last_ticket = Ticket.objects.filter(ticket_id_display__startswith=prefix_to_match, project=self.project).order_by('-ticket_id_display').first()
            if last_ticket and last_ticket.ticket_id_display.startswith(prefix_to_match):
                try: last_num_str = last_ticket.ticket_id_display.split('-')[-1]; next_num_for_project = int(last_num_str) + 1
                except (ValueError, IndexError): count_for_fallback = Ticket.objects.filter(project=self.project, created_at__year=current_year).count(); next_num_for_project = count_for_fallback + 1
            else: count_existing_for_project = Ticket.objects.filter(project=self.project, created_at__year=current_year).count(); next_num_for_project = count_existing_for_project + 1
            return f"{project_code}-{current_year}-{str(next_num_for_project).zfill(5)}"
        else: 
            last_generic_ticket_count = Ticket.objects.filter(ticket_id_display__startswith=f"IT-{current_year}-").count(); next_generic_num = last_generic_ticket_count + 1
            return f"IT-{current_year}-{str(next_generic_num).zfill(5)}"

    def save(self, *args, **kwargs):
        is_new = not self.pk 
        if is_new:
            if not self.ticket_id_display: 
                if self.project: self.ticket_id_display = self.generate_ticket_id()
                else: self.ticket_id_display = f"TEMP-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
            if not self.priority_id:
                try:
                    default_priority = TicketPriority.objects.get(code='NORMAL') # Убедитесь, что код 'NORMAL' существует
                    self.priority = default_priority
                except TicketPriority.DoesNotExist: pass # Можно добавить логирование или сообщение
        
        if self.status: 
            if self.status.is_resolved_status and not self.resolved_at: self.resolved_at = timezone.now()
            elif not self.status.is_resolved_status and self.resolved_at: self.resolved_at = None
            if self.status.is_closed_status and not self.closed_at: self.closed_at = timezone.now()
            elif not self.status.is_closed_status and self.closed_at: self.closed_at = None
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at'] 
        verbose_name = "Тикет"
        verbose_name_plural = "Тикеты"

    def __str__(self):
        return f"{self.ticket_id_display or 'Новый тикет'} - {self.title or 'Без темы'}"

# ------------------- Модели Комментариев и Вложений -------------------
class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments', verbose_name="Тикет")
    author_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='ticket_comments', verbose_name="Автор (сотрудник)")
    author_name_display = models.CharField(max_length=255, blank=True, verbose_name="Имя автора (для отображения)")
    author_ip_address = models.GenericIPAddressField(verbose_name="IP-адрес автора комментария", null=True, blank=True) # <--- НОВОЕ ПОЛЕ
    body = models.TextField(verbose_name="Текст комментария")
    is_internal = models.BooleanField(default=False, verbose_name="Внутренний комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def save(self, *args, **kwargs):
        if self.author_agent and not self.author_name_display:
            self.author_name_display = self.author_agent.get_full_name() or self.author_agent.username
        super().save(*args, **kwargs)

    class Meta: 
        ordering = ['created_at']
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"

    def __str__(self):
        author = self.author_name_display or (self.author_agent.username if self.author_agent else "Аноним")
        ticket_id_str = self.ticket.ticket_id_display if self.ticket and self.ticket.ticket_id_display else (f"ID {self.ticket.id}" if self.ticket else "N/A")
        return f"Комментарий от {author} к тикету #{ticket_id_str}"

def ticket_attachment_path(instance, filename):
    now = timezone.now(); path_parts = ['ticket_attachments', str(now.year), str(now.month).zfill(2)]
    ticket_obj = instance.ticket or (instance.comment and instance.comment.ticket)
    if ticket_obj:
        if ticket_obj.project: project_path_part = "".join(filter(str.isalnum, ticket_obj.project.name)).lower() or "unknown_project"; path_parts.append(project_path_part)
        path_parts.append(ticket_obj.ticket_id_display or f"ticket_{ticket_obj.id}")
        if instance.comment: path_parts.append(f"comment_{instance.comment.id}")
    else:
        path_parts.append("unassigned_attachments")
        if instance.comment: path_parts.append(f"comment_{instance.comment.id}")
    safe_filename = os.path.basename(filename); path_parts.append(safe_filename)
    return os.path.join(*path_parts)

class Attachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments', verbose_name="Тикет", null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='attachments', verbose_name="Комментарий", null=True, blank=True)
    file = models.FileField(upload_to=ticket_attachment_path, verbose_name="Файл")
    uploaded_by_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_attachments', verbose_name="Загрузил (сотрудник)")
    uploaded_by_name_display = models.CharField(max_length=255, blank=True, verbose_name="Загрузил (имя для отображения)")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    def save(self, *args, **kwargs):
        if self.uploaded_by_agent and not self.uploaded_by_name_display:
            self.uploaded_by_name_display = self.uploaded_by_agent.get_full_name() or self.uploaded_by_agent.username
        super().save(*args, **kwargs)

    class Meta: 
        ordering = ['-uploaded_at']
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"

    def __str__(self): 
        return os.path.basename(self.file.name) if self.file else "Пустое вложение"