# tickets/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
import os

from .models import (
    Project,
    Agent,
    Ticket,
    TicketCategory,
    TicketStatus,
    TicketPriority,
    Comment,
    Attachment,
    CustomFormField,
    FieldTemplate # Добавлена новая модель
)

# 1. FieldTemplateAdmin (Для библиотеки полей)
@admin.register(FieldTemplate)
class FieldTemplateAdmin(admin.ModelAdmin):
    list_display = ('label_default', 'name', 'field_type', 'is_active')
    search_fields = ('name', 'label_default')
    list_filter = ('field_type', 'is_active')
    list_editable = ('is_active',)
    fields = ('label_default', 'name', 'field_type', 'help_text_default', 'select_choices_json_default', 'is_active')


# 2. AgentAdmin (на основе UserAdmin)
@admin.register(Agent)
class AgentAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 
                    'agent_role', 'display_projects', 'is_active')
    list_filter = BaseUserAdmin.list_filter + ('agent_role', 'projects',)
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    # Используем существующие fieldsets из BaseUserAdmin и добавляем свои
    custom_fieldsets = list(BaseUserAdmin.fieldsets)
    custom_fieldsets.append(
        ('Роль и Проекты Сотрудника', {'fields': ('agent_role', 'projects')})
    )
    fieldsets = tuple(custom_fieldsets)
    
    # Для формы добавления, если нужно сразу указывать (опционально, можно настроить позже)
    custom_add_fieldsets = list(BaseUserAdmin.add_fieldsets)
    # Находим секцию с username и добавляем туда наши поля, или создаем новую
    # Это пример, как можно добавить в первую секцию (обычно с username, password)
    # if custom_add_fieldsets:
    #     first_fieldset_fields = list(custom_add_fieldsets[0][1]['fields'])
    #     first_fieldset_fields.extend(('agent_role', 'projects'))
    #     custom_add_fieldsets[0] = (custom_add_fieldsets[0][0], {'fields': tuple(first_fieldset_fields)})
    # else: # Если add_fieldsets пуст или его нет, создаем свою структуру
    custom_add_fieldsets.append(
        ('Роль и Проекты (при создании)', {'fields': ('agent_role', 'projects')})
    )
    add_fieldsets = tuple(custom_add_fieldsets)
    
    filter_horizontal = ('projects', 'groups', 'user_permissions') # groups и user_permissions из BaseUserAdmin

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
        return obj.agents.count() # Используем related_name='agents' из Agent.projects
    count_agents.short_description = "Кол-во сотрудников"

    def count_categories(self, obj):
        return obj.ticket_categories.count() # Используем related_name='ticket_categories' из TicketCategory.project
    count_categories.short_description = "Кол-во категорий"

    def count_tickets(self, obj):
        return obj.tickets.count() # Используем related_name='tickets' из Ticket.project
    count_tickets.short_description = "Кол-во тикетов"

# 4. Инлайн для CustomFormField (связь Категории и Шаблона Поля) на странице TicketCategory
class CustomFormFieldForCategoryInline(admin.TabularInline):
    model = CustomFormField
    extra = 1
    fields = ('field_template', 'label_override', 'is_required_in_category', 'order_in_category', 'is_active_in_category', 'help_text_override')
    autocomplete_fields = ['field_template'] # Для удобного выбора из библиотеки полей
    verbose_name = "Поле формы из библиотеки"
    verbose_name_plural = "Поля формы для этой категории (из библиотеки)"
    ordering = ('order_in_category',)

# 5. TicketCategoryAdmin с инлайном для кастомных полей
@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'description', 'count_configured_fields')
    search_fields = ('name', 'project__name')
    list_filter = ('project',)
    ordering = ('project', 'name',)
    inlines = [CustomFormFieldForCategoryInline] # Используем новый инлайн

    def count_configured_fields(self, obj):
        return obj.custom_form_fields.count() # Используем related_name='custom_form_fields'
    count_configured_fields.short_description = "Кол-во настроенных полей"

# 6. CustomFormFieldAdmin (для детального редактирования связи Категория-ШаблонПоля, если нужно)
# Обычно управляется через инлайн в TicketCategoryAdmin, но можно оставить для прямого доступа.
@admin.register(CustomFormField)
class CustomFormFieldAdmin(admin.ModelAdmin):
    list_display = ('get_field_template_label', 'category_with_project', 'is_required_in_category', 'order_in_category', 'is_active_in_category')
    list_filter = ('category__project', 'category', 'field_template__field_type', 'is_required_in_category', 'is_active_in_category')
    search_fields = ('field_template__label_default', 'field_template__name', 'category__name', 'category__project__name')
    list_editable = ('is_required_in_category', 'order_in_category', 'is_active_in_category')
    ordering = ('category__project', 'category', 'order_in_category')
    autocomplete_fields = ['category', 'field_template']
    
    fieldsets = (
        (None, {
            'fields': ('category', 'field_template')
        }),
        ('Настройки для этой категории', {
            'fields': ('label_override', 'help_text_override', 'is_required_in_category', 'order_in_category', 'is_active_in_category')
        }),
    )
    # Убираем get_fieldsets, который был для select_choices_json, так как это теперь в FieldTemplate
    
    def get_field_template_label(self, obj):
        return obj.effective_label # Используем свойство из модели
    get_field_template_label.short_description = 'Метка поля (эффективная)'
    get_field_template_label.admin_order_field = 'field_template__label_default'

    def category_with_project(self, obj):
        return f"{obj.category.name} ({obj.category.project.name})"
    category_with_project.short_description = "Категория (Проект)"
    category_with_project.admin_order_field = 'category__name' # или category__project__name

# 7. TicketStatusAdmin
@admin.register(TicketStatus)
class TicketStatusAdmin(admin.ModelAdmin):
    list_display = (
        'name', 
        'code', 
        'color',  # Поле для редактирования цвета
        'is_default_status', 
        'is_resolved_status', 
        'is_closed_status', 
        'order', 
        'color_display' # Метод для красивого отображения
    )
    list_editable = (
        'order', 
        'color', # Редактируем само поле color
        'is_default_status', 
        'is_resolved_status', 
        'is_closed_status'
    )
    ordering = ('order',)
    fields = ('name', 'code', 'color', 'is_default_status', 'is_resolved_status', 'is_closed_status', 'order')

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
    readonly_fields = ('uploaded_at',)
    verbose_name_plural = "Вложения к этому комментарию"
    
    # Поле 'ticket' для Attachment будет заполняться программно во view, если вложение к комментарию
    # Поэтому здесь его можно не показывать или сделать readonly/скрытым.
    # Убедимся, что Attachment.ticket может быть null=True, blank=True.
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Если нужно скрыть поле 'ticket' в инлайне комментариев
        # formset.form.base_fields['ticket'].widget = admin.widgets.HiddenInput()
        # formset.form.base_fields['ticket'].required = False 
        return formset

# 10. CommentAdmin
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('ticket_link', 'author_name_display_admin', 'short_body', 'is_internal', 'created_at_formatted_comment')
    list_filter = ('is_internal', 'created_at', 'author_agent', 'ticket__project', 'ticket__ticket_id_display')
    search_fields = ('body', 'author_name_display', 'ticket__title', 'ticket__ticket_id_display', 'ticket__project__name')
    readonly_fields = ('created_at',)
    list_select_related = ('ticket', 'ticket__project', 'author_agent')
    fieldsets = (
        (None, {'fields': ('ticket', 'author_agent', 'author_name_display', 'body', 'is_internal')}),
        ('Даты (только чтение)', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    inlines = [AttachmentInlineForComment]

    def ticket_link(self, obj):
        if obj.ticket:
            link = reverse("admin:tickets_ticket_change", args=[obj.ticket.id])
            project_name = obj.ticket.project.name if obj.ticket.project else "N/A"
            return format_html('<a href="{}">{} (Проект: {})</a>', link, obj.ticket.ticket_id_display or f"Тикет ID {obj.ticket.id}", project_name)
        return "N/A"
    ticket_link.short_description = "Тикет"
    ticket_link.admin_order_field = 'ticket__ticket_id_display'

    def author_name_display_admin(self, obj):
        # author_name_display заполняется в модели Comment.save()
        return obj.author_name_display or (obj.author_agent.username if obj.author_agent else "Система/Аноним")
    author_name_display_admin.short_description = "Автор"
    # Сортировка по этому полю может быть сложной, если оно комбинация.
    # admin_order_field = 'author_name_display' 

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
        'reporter_name', 'assignee', 'created_at_formatted'
    )
    list_filter = ('project', 'status', 'priority', 'category', 'assignee', 'created_at')
    search_fields = (
        'ticket_id_display', 'title', 'description', 
        'reporter_name', 'reporter_email', 
        'project__name', 'category__name',
        'custom_form_data' # Поиск по JSON полю
    )
    readonly_fields = ('ticket_id_display', 'created_at', 'updated_at', 'resolved_at', 'closed_at', 'custom_form_data_display')
    list_select_related = ('project', 'status', 'priority', 'category', 'assignee')
    autocomplete_fields = ['project', 'category', 'assignee'] # Удобный выбор
    
    fieldsets = (
        ('Основная информация', {'fields': ('ticket_id_display', 'project', 'title', 'description')}),
        ('Данные заявителя', {'fields': (
            'reporter_name', 'reporter_email', 'reporter_phone', 
            'reporter_building', 'reporter_room', 'reporter_department'
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
        # Эта функция должна быть обновлена, чтобы брать метки из CustomFormField.effective_label
        # и имена полей из CustomFormField.name (которое берется из FieldTemplate.name)
        if obj.custom_form_data and isinstance(obj.custom_form_data, dict) and obj.category:
            # Получаем все настроенные поля для категории этого тикета
            configured_fields = obj.category.custom_form_fields.select_related('field_template').all()
            labels_and_types = {
                cf.name: {'label': cf.effective_label, 'type': cf.field_type} 
                for cf in configured_fields
            }
            
            items = []
            for field_name_from_json, value in obj.custom_form_data.items():
                field_info = labels_and_types.get(field_name_from_json)
                label = field_info['label'] if field_info else field_name_from_json.replace('_', ' ').capitalize()
                # Можно добавить форматирование для boolean, date и т.д. если нужно
                items.append(f"<b>{format_html(label)}:</b> {format_html(value)}")
            return format_html("<br>".join(items))
        return "Нет данных"
    custom_form_data_display.short_description = "Данные доп. полей (кастомных)"

# 12. AttachmentAdmin
@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        'filename_admin', 'ticket_link_admin', 'comment_id_admin', 
        'uploaded_by_display_admin', 'uploaded_at_formatted_attach'
    )
    list_filter = ('uploaded_at', 'uploaded_by_agent', 'ticket__project', 'ticket', 'comment')
    search_fields = ('file', 'ticket__ticket_id_display', 'ticket__project__name', 'comment__body')
    readonly_fields = ('uploaded_at',)
    # Убедимся, что все связи, используемые в list_display и фильтрах, есть в list_select_related
    list_select_related = ('ticket', 'ticket__project', 'comment', 'comment__ticket', 'comment__ticket__project', 'uploaded_by_agent')
    fields = ('file', 'ticket', 'comment', 'uploaded_by_agent', 'uploaded_by_name_display', 'uploaded_at')
    autocomplete_fields = ['ticket', 'comment', 'uploaded_by_agent']


    def filename_admin(self, obj):
        return os.path.basename(obj.file.name) if obj.file else "N/A"
    filename_admin.short_description = "Имя файла"
    filename_admin.admin_order_field = 'file'

    def ticket_link_admin(self, obj):
        ticket_to_display = None
        prefix = ""
        if obj.ticket:
            ticket_to_display = obj.ticket
        elif obj.comment and obj.comment.ticket:
            ticket_to_display = obj.comment.ticket
            prefix = "(к комм.) "
        
        if ticket_to_display:
            link = reverse("admin:tickets_ticket_change", args=[ticket_to_display.id])
            project_name = ticket_to_display.project.name if ticket_to_display.project else "N/A"
            return format_html('{}<a href="{}">{} (Проект: {})</a>', prefix, link, ticket_to_display.ticket_id_display or f"Тикет ID {ticket_to_display.id}", project_name)
        return "—" 
    ticket_link_admin.short_description = "Тикет (вложение)"
    
    def comment_id_admin(self, obj):
        if obj.comment:
            ticket_info_parts = []
            if obj.comment.ticket:
                ticket_info_parts.append(f"тикет: {obj.comment.ticket.ticket_id_display or obj.comment.ticket.id}")
                if obj.comment.ticket.project:
                    ticket_info_parts.append(f"Проект: {obj.comment.ticket.project.name}")
            ticket_info_str = ", ".join(ticket_info_parts)
            return f"ID: {obj.comment.id} ({ticket_info_str})" if ticket_info_str else f"ID: {obj.comment.id}"
        return "—"
    comment_id_admin.short_description = "Комментарий (ID)"
    comment_id_admin.admin_order_field = 'comment__id'

    def uploaded_by_display_admin(self, obj):
        # uploaded_by_name_display заполняется в модели Attachment.save()
        return obj.uploaded_by_name_display or (obj.uploaded_by_agent.username if obj.uploaded_by_agent else "N/A")
    uploaded_by_display_admin.short_description = "Кем загружено"

    def uploaded_at_formatted_attach(self, obj):
        return obj.uploaded_at.strftime("%d.%m.%Y %H:%M")
    uploaded_at_formatted_attach.short_description = "Дата загрузки"
    uploaded_at_formatted_attach.admin_order_field = 'uploaded_at'