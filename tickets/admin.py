# tickets/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin # Переименовал, чтобы не конфликтовать
from django.urls import reverse
from django.utils.html import format_html
import os

from .models import (
    Agent, Ticket, TicketCategory, TicketStatus, TicketPriority, 
    Comment, Attachment, CustomFormField # Добавили CustomFormField
)

# 1. AgentAdmin (на основе UserAdmin)
@admin.register(Agent) # Используем декоратор для регистрации
class AgentAdmin(BaseUserAdmin):
    # Добавляем 'role' и 'support_line' в отображение и фильтры
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'role', 'support_line', 'is_active')
    list_filter = BaseUserAdmin.list_filter + ('role', 'support_line',)
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    # Расширяем fieldsets для добавления наших кастомных полей
    # Сначала берем стандартные fieldsets из BaseUserAdmin
    fieldsets = list(BaseUserAdmin.fieldsets)  # Преобразуем в список, чтобы можно было добавлять
    # Добавляем нашу секцию с ролью и линией поддержки
    fieldsets.append(
        ('Роль и Линия поддержки', {'fields': ('role', 'support_line')})
    )
    
    # То же самое для add_fieldsets (форма добавления пользователя)
    add_fieldsets = list(BaseUserAdmin.add_fieldsets)
    # Убедимся, что 'role' и 'support_line' есть в форме добавления, если нужно
    # Обычно при добавлении указывают основные поля, а роль и линию потом редактируют.
    # Если нужно сразу, то надо найти подходящую секцию или создать новую.
    # Проще всего добавить их в ту же секцию, где username/password, или создать свою.
    # Для простоты, предположим, что они будут редактироваться после создания.
    # Если нужно на форме создания, это немного сложнее для UserAdmin.
    # Можно добавить так, если форма позволяет:
    # add_fieldsets += (
    #     (None, {'fields': ('role', 'support_line')}),
    # )
    # Проще всего будет добавить их через редактирование существующего пользователя.


# 2. Инлайн для CustomFormField на странице TicketCategory
class CustomFormFieldInline(admin.TabularInline): # или admin.StackedInline для другого вида
    model = CustomFormField
    extra = 1 # Количество пустых форм для добавления новых полей
    fields = ('label', 'name', 'field_type', 'is_required', 'order', 'help_text_custom', 'select_choices_json')
    # Можно упорядочить поля, как удобнее
    ordering = ('order',)

# 3. TicketCategoryAdmin с инлайном для кастомных полей
@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'count_custom_fields')
    search_fields = ('name',)
    ordering = ('name',)
    inlines = [CustomFormFieldInline] # Подключаем инлайн для кастомных полей

    def count_custom_fields(self, obj):
        return obj.custom_fields.count()
    count_custom_fields.short_description = "Кол-во кастомных полей"

# 4. Регистрация CustomFormField (если нужен прямой доступ к редактированию этих полей отдельно)
@admin.register(CustomFormField)
class CustomFormFieldAdmin(admin.ModelAdmin):
    list_display = ('label', 'name', 'category', 'field_type', 'is_required', 'order')
    list_filter = ('category', 'field_type', 'is_required')
    search_fields = ('label', 'name', 'category__name')
    list_editable = ('order', 'is_required')
    ordering = ('category', 'order')
    # Показываем select_choices_json только если field_type = 'select'
    # Это можно сделать через кастомный метод get_fieldsets или get_fields
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        # Базовый набор полей
        main_fields = ('category', 'label', 'name', 'field_type', 'is_required', 'order', 'help_text_custom')
        
        current_field_type = None
        if obj: # Если объект редактируется
            current_field_type = obj.field_type
        elif request.POST.get('field_type'): # Если объект создается и тип выбран
            current_field_type = request.POST.get('field_type')

        if current_field_type == 'select':
            return [(None, {'fields': main_fields + ('select_choices_json',)})]
        return [(None, {'fields': main_fields})]


# 5. TicketStatusAdmin
@admin.register(TicketStatus)
class TicketStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_default_status', 'is_resolved_status', 'is_closed_status', 'order')
    list_editable = ('order', 'is_default_status', 'is_resolved_status', 'is_closed_status')
    ordering = ('order',)

# 6. TicketPriorityAdmin
@admin.register(TicketPriority)
class TicketPriorityAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'color', 'color_display', 'order') # Добавили 'color'
    list_editable = ('order', 'color') # Теперь 'color' есть в list_display
    ordering = ('order',)

    def color_display(self, obj):
        if obj.color:
            return format_html(
                '<span style="background-color: {}; padding: 2px 8px; border-radius: 3px; color: white; text-shadow: 1px 1px 1px black;">{}</span>',
                obj.color, obj.color
            )
        return "-"
    color_display.short_description = "Цвет (Вид)" # Переименовал для ясности
    # color_display.admin_order_field = 'color' # Это было для сортировки по методу, но т.к. 'color' теперь в list_display, сортировка по нему будет работать автоматически

# 7. Инлайн для Attachment на странице Comment (оставляем как было)
class AttachmentInlineForComment(admin.TabularInline):
    model = Attachment
    extra = 1
    fields = ('file', 'uploaded_by_agent', 'uploaded_by_name_display', 'uploaded_at')
    readonly_fields = ('uploaded_at',)
    verbose_name_plural = "Вложения к этому комментарию"
    # Убираем автоматическое связывание с тикетом в этом инлайне, так как связь идет через комментарий
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "ticket":
            kwargs['queryset'] = Ticket.objects.none() # Скрываем поле 'ticket'
            # Или можно его вообще убрать из fields, если оно не нужно здесь
        return super().formfield_for_foreignkey(self, db_field, request, **kwargs)

# 8. CommentAdmin
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('ticket_link', 'author_name_display_admin', 'short_body', 'is_internal', 'created_at_formatted_comment')
    list_filter = ('is_internal', 'created_at', 'author_agent', 'ticket__ticket_id_display')
    search_fields = ('body', 'author_name_display', 'ticket__title', 'ticket__ticket_id_display')
    readonly_fields = ('created_at',)
    list_select_related = ('ticket', 'author_agent')
    fieldsets = (
        (None, {'fields': ('ticket', 'author_agent', 'author_name_display', 'body', 'is_internal')}),
        ('Даты (только чтение)', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    inlines = [AttachmentInlineForComment]

    def ticket_link(self, obj):
        if obj.ticket:
            link = reverse("admin:tickets_ticket_change", args=[obj.ticket.id])
            return format_html('<a href="{}">{}</a>', link, obj.ticket.ticket_id_display or f"Тикет ID {obj.ticket.id}")
        return "N/A"
    ticket_link.short_description = "Тикет"
    ticket_link.admin_order_field = 'ticket__ticket_id_display'

    def author_name_display_admin(self, obj):
        return obj.author_name_display or (obj.author_agent.username if obj.author_agent else "Система/Аноним")
    author_name_display_admin.short_description = "Автор"
    author_name_display_admin.admin_order_field = 'author_name_display' # или 'author_agent__username'

    def created_at_formatted_comment(self, obj):
        return obj.created_at.strftime("%d.%m.%Y %H:%M")
    created_at_formatted_comment.short_description = "Дата комментария"
    created_at_formatted_comment.admin_order_field = 'created_at'

    def short_body(self, obj):
        return (obj.body[:75] + '...') if len(obj.body) > 75 else obj.body
    short_body.short_description = "Текст (начало)"

# 9. TicketAdmin
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_id_display', 'title', 'status', 'priority', 'category', 'ticket_level',
        'reporter_name', 'assignee', 'created_at_formatted'
    )
    list_filter = ('status', 'priority', 'category', 'ticket_level', 'assignee', 'created_at')
    search_fields = (
        'ticket_id_display', 'title', 'description', 
        'reporter_name', 'reporter_email', 'custom_form_data' # Можно искать по JSON полю
    )
    readonly_fields = ('ticket_id_display', 'created_at', 'updated_at', 'resolved_at', 'closed_at', 'custom_form_data_display') # Добавил custom_form_data_display
    list_select_related = ('status', 'priority', 'category', 'assignee')
    
    fieldsets = (
        ('Основная информация', {'fields': ('ticket_id_display', 'title', 'description')}),
        ('Данные заявителя', {'fields': (
            'reporter_name', 'reporter_email', 'reporter_phone', 
            'reporter_building', 'reporter_room', 'reporter_department'
        )}),
        ('Классификация и статус', {'fields': ('status', 'priority', 'category', 'assignee', 'ticket_level')}),
        ('Дополнительные данные формы', {'fields': ('custom_form_data_display',), 'classes': ('collapse',)}), # Показываем кастомные данные
        ('Даты (только чтение)', {'fields': (
            'created_at', 'updated_at', 'resolved_at', 'closed_at'
        ), 'classes': ('collapse',)}),
    )
    # Для добавления инлайнов комментариев/вложений на страницу тикета:
    # class CommentInlineForTicket(admin.TabularInline): model = Comment; extra = 0 ...
    # class AttachmentInlineForTicket(admin.TabularInline): model = Attachment; extra = 0; fk_name = 'ticket' ...
    # inlines = [CommentInlineForTicket, AttachmentInlineForTicket]

    def created_at_formatted(self, obj):
        return obj.created_at.strftime("%d.%m.%Y %H:%M")
    created_at_formatted.short_description = "Дата создания"
    created_at_formatted.admin_order_field = 'created_at'

    def custom_form_data_display(self, obj):
        if obj.custom_form_data and isinstance(obj.custom_form_data, dict):
            # Получаем метки для кастомных полей из CustomFormField
            # Это может быть неэффективно, если полей много.
            # Лучше было бы кэшировать или оптимизировать, но для админки сойдет.
            labels = {field.name: field.label for field in obj.category.custom_fields.all()} if obj.category else {}
            
            items = []
            for key, value in obj.custom_form_data.items():
                label = labels.get(key, key.replace('_', ' ').capitalize()) # Используем сохраненную метку или генерируем
                items.append(f"<b>{format_html(label)}:</b> {format_html(value)}")
            return format_html("<br>".join(items))
        return "Нет данных"
    custom_form_data_display.short_description = "Данные доп. полей"

# 10. AttachmentAdmin
@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        'filename_admin', 'ticket_link_admin', 'comment_id_admin', 
        'uploaded_by_display_admin', 'uploaded_at_formatted_attach'
    )
    list_filter = ('uploaded_at', 'uploaded_by_agent', 'ticket', 'comment')
    search_fields = ('file', 'ticket__ticket_id_display', 'comment__body')
    readonly_fields = ('uploaded_at',)
    list_select_related = ('ticket', 'comment', 'uploaded_by_agent')
    fields = ('file', 'ticket', 'comment', 'uploaded_by_agent', 'uploaded_by_name_display', 'uploaded_at')

    def filename_admin(self, obj):
        return os.path.basename(obj.file.name) if obj.file else "N/A"
    filename_admin.short_description = "Имя файла"
    filename_admin.admin_order_field = 'file'

    def ticket_link_admin(self, obj):
        if obj.ticket:
            link = reverse("admin:tickets_ticket_change", args=[obj.ticket.id])
            return format_html('<a href="{}">{}</a>', link, obj.ticket.ticket_id_display or f"Тикет ID {obj.ticket.id}")
        return "—" 
    ticket_link_admin.short_description = "Тикет (вложение)"
    ticket_link_admin.admin_order_field = 'ticket__ticket_id_display'

    def comment_id_admin(self, obj):
        if obj.comment:
            ticket_info = f"(к тикету: {obj.comment.ticket.ticket_id_display})" if obj.comment.ticket else ""
            return f"ID: {obj.comment.id} {ticket_info}"
        return "—"
    comment_id_admin.short_description = "Комментарий (ID)"
    comment_id_admin.admin_order_field = 'comment__id'

    def uploaded_by_display_admin(self, obj):
        if obj.uploaded_by_agent:
            return obj.uploaded_by_agent.get_full_name() or obj.uploaded_by_agent.username
        return obj.uploaded_by_name_display or "N/A"
    uploaded_by_display_admin.short_description = "Кем загружено"

    def uploaded_at_formatted_attach(self, obj):
        return obj.uploaded_at.strftime("%d.%m.%Y %H:%M")
    uploaded_at_formatted_attach.short_description = "Дата загрузки"
    uploaded_at_formatted_attach.admin_order_field = 'uploaded_at'