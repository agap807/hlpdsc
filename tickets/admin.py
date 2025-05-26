# tickets/admin.py
import os
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from django.core.mail import EmailMessage # Используем EmailMessage для большей гибкости
from django.core.exceptions import ValidationError # Для EmailSettings.clean()

from .models import (
    Project, Agent, Ticket, TicketCategory, TicketStatus, TicketPriority,
    Comment, Attachment, CustomFormField, FieldTemplate,
    EmailSettings, NotificationTemplate, Feedback
)

# 1. FieldTemplateAdmin
@admin.register(FieldTemplate)
class FieldTemplateAdmin(admin.ModelAdmin):
    list_display = ('label_default', 'name', 'field_type', 'is_active')
    search_fields = ('name', 'label_default')
    list_filter = ('field_type', 'is_active')
    list_editable = ('is_active',)
    fields = ('label_default', 'name', 'field_type', 'help_text_default', 'select_choices_json_default', 'is_active')

# 2. AgentAdmin
@admin.register(Agent)
class AgentAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 
                    'agent_role', 'display_projects', 'is_active')
    list_filter = BaseUserAdmin.list_filter + ('agent_role', 'projects',)
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    custom_fieldsets = list(BaseUserAdmin.fieldsets)
    custom_fieldsets.append(
        ('Роль и Проекты Сотрудника', {'fields': ('agent_role', 'projects')})
    )
    fieldsets = tuple(custom_fieldsets)
    
    custom_add_fieldsets = list(BaseUserAdmin.add_fieldsets)
    custom_add_fieldsets.append(
        ('Роль и Проекты (при создании)', {'fields': ('agent_role', 'projects')})
    )
    add_fieldsets = tuple(custom_add_fieldsets)
    
    filter_horizontal = ('projects', 'groups', 'user_permissions')

    def display_projects(self, obj):
        return ", ".join([project.name for project in obj.projects.all()])
    display_projects.short_description = 'Проекты'

# 3. ProjectAdmin
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'project_email', 'is_active', 'count_agents', 'count_categories', 'count_tickets')
    search_fields = ('name', 'description', 'project_email')
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    fields = ('name', 'description', 'project_email', 'is_active') 

    def count_agents(self, obj):
        return obj.agents.count()
    count_agents.short_description = "Кол-во сотрудников"

    def count_categories(self, obj):
        return obj.ticket_categories.count()
    count_categories.short_description = "Кол-во категорий"

    def count_tickets(self, obj):
        return obj.tickets.count()
    count_tickets.short_description = "Кол-во тикетов"

# 4. Инлайн для CustomFormField
class CustomFormFieldForCategoryInline(admin.TabularInline):
    model = CustomFormField
    extra = 1
    fields = ('field_template', 'label_override', 'is_required_in_category', 'order_in_category', 'is_active_in_category', 'help_text_override')
    autocomplete_fields = ['field_template']
    verbose_name = "Поле формы из библиотеки"
    verbose_name_plural = "Поля формы для этой категории (из библиотеки)"
    ordering = ('order_in_category',)

# 5. TicketCategoryAdmin
@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'project_with_status', 'description', 'count_configured_fields', 'is_active') # Добавил is_active
    search_fields = ('name', 'project__name')
    list_filter = ('project', 'is_active') # Добавил is_active
    list_editable = ('is_active',) # Сделал is_active редактируемым
    ordering = ('project', 'name',)
    inlines = [CustomFormFieldForCategoryInline]

    def project_with_status(self, obj): # Для более информативного отображения
        return f"{obj.project.name} ({'Активен' if obj.project.is_active else 'Неактивен'})"
    project_with_status.short_description = "Проект (статус)"
    project_with_status.admin_order_field = 'project__name'


    def count_configured_fields(self, obj):
        return obj.custom_form_fields.count()
    count_configured_fields.short_description = "Кол-во настроенных полей"

# 6. CustomFormFieldAdmin
@admin.register(CustomFormField)
class CustomFormFieldAdmin(admin.ModelAdmin):
    list_display = ('get_field_template_label', 'category_with_project_and_status', 'is_required_in_category', 'order_in_category', 'is_active_in_category')
    list_filter = ('category__project', 'category', 'field_template__field_type', 'is_required_in_category', 'is_active_in_category')
    search_fields = ('field_template__label_default', 'field_template__name', 'category__name', 'category__project__name')
    list_editable = ('is_required_in_category', 'order_in_category', 'is_active_in_category')
    ordering = ('category__project', 'category', 'order_in_category')
    autocomplete_fields = ['category', 'field_template']
    
    fieldsets = (
        (None, {'fields': ('category', 'field_template')}),
        ('Настройки для этой категории', {
            'fields': ('label_override', 'help_text_override', 'is_required_in_category', 'order_in_category', 'is_active_in_category')
        }),
    )
    
    def get_field_template_label(self, obj):
        return obj.effective_label
    get_field_template_label.short_description = 'Метка поля (эффективная)'
    get_field_template_label.admin_order_field = 'field_template__label_default'

    def category_with_project_and_status(self, obj):
        cat_status = 'Активна' if obj.category.is_active else 'Неактивна'
        proj_status = 'Активен' if obj.category.project.is_active else 'Неактивен'
        return f"{obj.category.name} ({cat_status}) / {obj.category.project.name} ({proj_status})"
    category_with_project_and_status.short_description = "Категория (статус) / Проект (статус)"
    category_with_project_and_status.admin_order_field = 'category__name'


# 7. TicketStatusAdmin
@admin.register(TicketStatus)
class TicketStatusAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'code', 'color', 'is_default_status', 
        'is_resolved_status', 'is_closed_status', 'order', 'color_display'
    )
    list_editable = (
        'order', 'color', 'is_default_status', 
        'is_resolved_status', 'is_closed_status'
    )
    ordering = ('order',)
    fields = ('name', 'code', 'color', 'is_default_status', 'is_resolved_status', 'is_closed_status', 'order')
    search_fields = ('name', 'code')

    def color_display(self, obj):
        if obj.color:
            return format_html(
                '<span style="background-color: {}; padding: 2px 8px; border-radius: 3px; color: white; text-shadow: 1px 1px 1px black;">{}</span>',
                obj.color, obj.color
            )
        return "-"
    color_display.short_description = "Цвет (Вид)"

# 8. TicketPriorityAdmin
@admin.register(TicketPriority)
class TicketPriorityAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'color', 'color_display', 'order')
    list_editable = ('order', 'color')
    ordering = ('order',)
    search_fields = ('name', 'code')

    def color_display(self, obj):
        if obj.color:
            return format_html(
                '<span style="background-color: {}; padding: 2px 8px; border-radius: 3px; color: white; text-shadow: 1px 1px 1px black;">{}</span>',
                obj.color, obj.color
            )
        return "-"
    color_display.short_description = "Цвет (Вид)"

# 9. Инлайн для Attachment на странице Comment
class AttachmentInlineForComment(admin.TabularInline):
    model = Attachment
    extra = 1
    fields = ('file', 'uploaded_by_agent', 'uploaded_by_name_display', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'uploaded_by_name_display') # uploaded_by_name_display теперь readonly, т.к. из модели
    verbose_name_plural = "Вложения к этому комментарию"

# 10. CommentAdmin
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('ticket_link', 'author_name_display_admin', 'short_body', 'is_internal', 'created_at_formatted_comment', 'author_ip_address')
    list_filter = ('is_internal', 'created_at', 'author_agent', 'ticket__project') # Убрал ticket__ticket_id_display для простоты
    search_fields = ('body', 'author_name_display', 'ticket__title', 'ticket__ticket_id_display', 'ticket__project__name', 'author_ip_address')
    readonly_fields = ('created_at', 'author_name_display', 'author_ip_address') # author_name_display и IP заполняются моделью
    list_select_related = ('ticket', 'ticket__project', 'author_agent')
    fieldsets = (
        (None, {'fields': ('ticket', 'author_agent', 'author_name_display', 'body', 'is_internal', 'author_ip_address')}),
        ('Даты (только чтение)', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    inlines = [AttachmentInlineForComment]
    autocomplete_fields = ['ticket', 'author_agent'] # Добавил автокомплит

    def ticket_link(self, obj):
        if obj.ticket:
            link = reverse("admin:tickets_ticket_change", args=[obj.ticket.id])
            project_name = obj.ticket.project.name if obj.ticket.project else "N/A"
            return format_html('<a href="{}">{} (Проект: {})</a>', link, obj.ticket.ticket_id_display or f"Тикет ID {obj.ticket.id}", project_name)
        return "N/A"
    ticket_link.short_description = "Тикет"
    ticket_link.admin_order_field = 'ticket__ticket_id_display'

    def author_name_display_admin(self, obj):
        return obj.author_name_display or (obj.author_agent.username if obj.author_agent else "Система/Аноним")
    author_name_display_admin.short_description = "Автор"

    def created_at_formatted_comment(self, obj):
        return obj.created_at.strftime("%d.%m.%Y %H:%M")
    created_at_formatted_comment.short_description = "Дата комментария"
    created_at_formatted_comment.admin_order_field = 'created_at'

    def short_body(self, obj):
        return (obj.body[:75] + '...') if len(obj.body) > 75 else obj.body
    short_body.short_description = "Текст (начало)"

# 11. TicketAdmin
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_id_display', 'title', 'project', 'status', 'priority', 'category',
        'reporter_name', 'assignee', 'created_at_formatted', 'reporter_ip_address'
    )
    list_filter = ('project', 'status', 'priority', 'category', 'assignee', 'created_at')
    search_fields = (
        'ticket_id_display', 'title', 'description', 
        'reporter_name', 'reporter_email', 'reporter_ip_address',
        'project__name', 'category__name', 'assignee__username',
        'status__name', 'priority__name',
        'custom_form_data'
    )
    readonly_fields = (
        'ticket_id_display', 'created_at', 'updated_at', 'resolved_at', 
        'closed_at', 'custom_form_data_display', 'reporter_ip_address'
    )
    list_select_related = ('project', 'status', 'priority', 'category', 'assignee')
    autocomplete_fields = ['project', 'category', 'assignee', 'status', 'priority']
    
    fieldsets = (
        ('Основная информация', {'fields': ('ticket_id_display', 'project', 'title', 'description')}),
        ('Данные заявителя', {'fields': (
            'reporter_name', 'reporter_email', 'reporter_phone', 
            'reporter_building', 'reporter_room', 'reporter_department', 'reporter_ip_address'
        )}),
        ('Классификация и статус', {'fields': ('status', 'priority', 'category', 'assignee')}),
        ('Дополнительные данные формы (только чтение)', {'fields': ('custom_form_data_display',), 'classes': ('collapse',)}),
        ('Даты (только чтение)', {'fields': (
            'created_at', 'updated_at', 'resolved_at', 'closed_at'
        ), 'classes': ('collapse',)}),
    )

    def created_at_formatted(self, obj):
        return obj.created_at.strftime("%d.%m.%Y %H:%M")
    created_at_formatted.short_description = "Дата создания"
    created_at_formatted.admin_order_field = 'created_at'

    def custom_form_data_display(self, obj):
        if obj.custom_form_data and isinstance(obj.custom_form_data, dict) and obj.category:
            configured_fields = obj.category.custom_form_fields.select_related('field_template').all()
            labels_and_types = {cf.name: {'label': cf.effective_label, 'type': cf.field_type} for cf in configured_fields}
            items = []
            for field_name, value in obj.custom_form_data.items():
                field_info = labels_and_types.get(field_name)
                label = field_info['label'] if field_info else field_name.replace('_', ' ').capitalize()
                items.append(f"<b>{format_html(label)}:</b> {format_html(value)}")
            return format_html("<br>".join(items))
        return "Нет данных"
    custom_form_data_display.short_description = "Данные доп. полей"

# 12. AttachmentAdmin
@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename_admin', 'ticket_link_admin', 'comment_id_admin', 'uploaded_by_display_admin', 'uploaded_at_formatted_attach')
    list_filter = ('uploaded_at', 'uploaded_by_agent', 'ticket__project', 'comment__ticket__project') # Упростил фильтры
    search_fields = ('file', 'ticket__ticket_id_display', 'comment__body', 'uploaded_by_name_display')
    readonly_fields = ('uploaded_at', 'uploaded_by_name_display') # uploaded_by_name_display из модели
    list_select_related = ('ticket', 'ticket__project', 'comment', 'comment__ticket', 'comment__ticket__project', 'uploaded_by_agent')
    fields = ('file', 'ticket', 'comment', 'uploaded_by_agent', 'uploaded_by_name_display', 'uploaded_at')
    autocomplete_fields = ['ticket', 'comment', 'uploaded_by_agent']

    def filename_admin(self, obj):
        return os.path.basename(obj.file.name) if obj.file else "N/A"
    filename_admin.short_description = "Имя файла"
    filename_admin.admin_order_field = 'file'

    def ticket_link_admin(self, obj):
        ticket_to_display = obj.ticket or (obj.comment and obj.comment.ticket)
        prefix = "(к комм.) " if obj.comment and obj.comment.ticket and not obj.ticket else ""
        if ticket_to_display:
            link = reverse("admin:tickets_ticket_change", args=[ticket_to_display.id])
            project_name = ticket_to_display.project.name if ticket_to_display.project else "N/A"
            return format_html('{}<a href="{}">{} (Проект: {})</a>', prefix, link, ticket_to_display.ticket_id_display or f"Тикет ID {ticket_to_display.id}", project_name)
        return "—" 
    ticket_link_admin.short_description = "Тикет (вложение)"
    
    def comment_id_admin(self, obj):
        if obj.comment:
            return f"ID: {obj.comment.id}"
        return "—"
    comment_id_admin.short_description = "Комментарий (ID)"
    comment_id_admin.admin_order_field = 'comment__id'

    def uploaded_by_display_admin(self, obj):
        return obj.uploaded_by_name_display or (obj.uploaded_by_agent.username if obj.uploaded_by_agent else "N/A")
    uploaded_by_display_admin.short_description = "Кем загружено"

    def uploaded_at_formatted_attach(self, obj):
        return obj.uploaded_at.strftime("%d.%m.%Y %H:%M")
    uploaded_at_formatted_attach.short_description = "Дата загрузки"
    uploaded_at_formatted_attach.admin_order_field = 'uploaded_at'

# 13. EmailSettingsAdmin
@admin.register(EmailSettings)
class EmailSettingsAdmin(admin.ModelAdmin): # Убрал action_mixin, т.к. send_mail напрямую не работает с connection
    list_display = ('__str__', 'is_active', 'smtp_host', 'smtp_port', 'default_from_email')
    list_editable = ('is_active',)
    
    fieldsets = (
        (None, {'fields': ('is_active', 'default_from_email')}),
        ('Настройки SMTP сервера', {
            'fields': ('smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'use_tls', 'use_ssl')
        }),
        ('Тестирование', {
            'fields': ('test_email_recipient',)
        })
    )
    actions = ['send_test_email_action']

    def send_test_email_action(self, request, queryset):
        settings_obj = queryset.first()
        if not settings_obj:
            self.message_user(request, "Настройки Email не найдены.", level='ERROR'); return
        if not settings_obj.is_active:
            self.message_user(request, "Отправка Email не активна в настройках.", level='WARNING'); return
        if not settings_obj.test_email_recipient:
            self.message_user(request, "Не указан Email для тестового письма в настройках.", level='ERROR'); return

        subject = "Тестовое письмо из Helpdesk"
        message_body = (
            f"Это тестовое письмо отправлено из системы Helpdesk для проверки настроек Email.\n"
            f"Хост: {settings_obj.smtp_host}\nПорт: {settings_obj.smtp_port}\n"
            f"Отправитель: {settings_obj.default_from_email}"
        )
        
        from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
        backend = SMTPEmailBackend(
            host=settings_obj.smtp_host, port=settings_obj.smtp_port,
            username=settings_obj.smtp_user, password=settings_obj.smtp_password,
            use_tls=settings_obj.use_tls, use_ssl=settings_obj.use_ssl,
            fail_silently=False
        )
        
        email = EmailMessage(
            subject, message_body, settings_obj.default_from_email,
            [settings_obj.test_email_recipient]
        )
        try:
            # EmailMessage.send() не принимает 'connection_override'
            # Мы должны открыть соединение и отправить через него
            backend.open()
            num_sent = backend.send_messages([email])
            backend.close()

            if num_sent > 0:
                self.message_user(request, f"Тестовое письмо успешно отправлено на {settings_obj.test_email_recipient}.")
            else:
                self.message_user(request, "Тестовое письмо НЕ было отправлено. Проверьте консоль.", level='ERROR')
        except Exception as e:
            self.message_user(request, f"Ошибка при отправке тестового письма: {e}", level='ERROR')
            import traceback; traceback.print_exc()
            
    send_test_email_action.short_description = "Отправить тестовое письмо (для выбранных)"

# 14. NotificationTemplateAdmin
@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'event_code', 'recipient_type', 'is_active')
    list_filter = ('is_active', 'recipient_type')
    search_fields = ('name', 'event_code', 'subject_template', 'body_template_html')
    list_editable = ('is_active',)
    fieldsets = (
        (None, {'fields': ('name', 'event_code', 'description', 'is_active', 'recipient_type')}),
        ('Шаблоны письма (Django Template Language)', {'fields': ('subject_template', 'body_template_html')}),
        ('Подсказка по переменным контекста', {
            'description': (
                "<p>В шаблонах можно использовать переменные в зависимости от события. Например:</p>"
                "<ul>"
                "<li>События тикета: <code>{{ ticket.ticket_id_display }}</code>, <code>{{ ticket.title }}</code>, <code>{{ ticket.reporter_name }}</code>, <code>{{ ticket.status.name }}</code>, <code>{{ ticket.assignee.get_full_name }}</code>, <code>{{ ticket_url }}</code>.</li>"
                "<li>События комментария: <code>{{ comment.body }}</code>, <code>{{ comment.author_name_display }}</code>, <code>{{ comment_url }}</code>.</li>"
                "<li>Имя пользователя: <code>{{ user.get_full_name }}</code>.</li>"
                "<li>URL сайта: <code>{{ site_url }}</code>.</li>"
                "</ul>"
                "<p>Точный набор переменных зависит от уведомления.</p>"
            ), 'fields': ()
        })
    )

# 15. FeedbackAdmin
@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'feedback_type', 'submitted_at', 'is_reviewed')
    list_filter = ('feedback_type', 'is_reviewed', 'submitted_at')
    search_fields = ('name', 'email', 'subject', 'message')
    list_editable = ('is_reviewed',)
    readonly_fields = ('submitted_at', 'name', 'email', 'feedback_type', 'subject', 'message') # Сделал основные поля readonly

    fieldsets = (
        ('Информация об обращении (только чтение)', {
            'fields': ('feedback_type', 'subject', 'message', 'name', 'email', 'submitted_at')
        }),
        ('Обработка (для администратора)', {
            'fields': ('is_reviewed', 'reviewer_notes')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        # Разрешаем редактирование reviewer_notes и is_reviewed всегда
        # Остальные поля - только чтение, если объект уже существует
        if obj: # obj is not None, so this is an edit page
             return self.readonly_fields + ('feedback_type', 'subject', 'message', 'name', 'email', 'submitted_at')
        # Это страница создания, здесь readonly_fields по умолчанию
        return self.readonly_fields