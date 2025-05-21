# tickets/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, Http404 
from django.contrib.auth.decorators import login_required 
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic.base import RedirectView
from django import forms

from .models import (
    Ticket, Comment, Attachment, TicketStatus, TicketCategory, 
    TicketPriority, Agent, CustomFormField
)
from .forms import (
    TicketCreateForm, AgentCommentForm, TicketUpdateStatusForm, 
    TicketUpdatePriorityForm, TicketUpdateCategoryForm, # Убери TicketUpdateCategoryForm если решил ее не использовать
    TicketReassignAgentForm, SelectTicketCategoryForm
)
import json

# -----------------------------------------------------------------------------
# ПРЕДСТАВЛЕНИЯ ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ
# -----------------------------------------------------------------------------
def select_ticket_category_view(request):
    if request.method == 'POST':
        form = SelectTicketCategoryForm(request.POST)
        if form.is_valid():
            category = form.cleaned_data['category']
            return redirect('tickets:create_ticket_for_category', category_id=category.pk)
    else:
        form = SelectTicketCategoryForm()
    context = {'form': form, 'page_title': "Шаг 1: Выбор категории заявки"}
    return render(request, 'tickets/select_ticket_category.html', context)

def create_ticket_view(request, category_id):
    try:
        selected_category = TicketCategory.objects.prefetch_related('custom_fields').get(pk=category_id)
    except TicketCategory.DoesNotExist:
        messages.error(request, "Выбранная категория не найдена.")
        return redirect('tickets:select_ticket_category')

    form_kwargs = {'initial': {}}
    if request.method == 'POST':
        form_kwargs['data'] = request.POST
        form_kwargs['files'] = request.FILES
    form = TicketCreateForm(**form_kwargs) 
    
    custom_fields_definitions = selected_category.custom_fields.filter(is_active=True).order_by('order')
    for field_def in custom_fields_definitions:
        field_kwargs_custom = {'label': field_def.label, 'required': field_def.is_required, 'help_text': field_def.help_text_custom}
        widget_attrs = {'class': 'form-control'}
        if field_def.field_type == 'char': form.fields[field_def.name] = forms.CharField(widget=forms.TextInput(attrs=widget_attrs), **field_kwargs_custom)
        elif field_def.field_type == 'text': form.fields[field_def.name] = forms.CharField(widget=forms.Textarea(attrs=widget_attrs), **field_kwargs_custom)
        elif field_def.field_type == 'email': form.fields[field_def.name] = forms.EmailField(widget=forms.EmailInput(attrs=widget_attrs), **field_kwargs_custom)
        elif field_def.field_type == 'int': form.fields[field_def.name] = forms.IntegerField(widget=forms.NumberInput(attrs=widget_attrs), **field_kwargs_custom)
        elif field_def.field_type == 'bool': form.fields[field_def.name] = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), **field_kwargs_custom)
        elif field_def.field_type == 'date': form.fields[field_def.name] = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), **field_kwargs_custom)
        elif field_def.field_type == 'select' and field_def.select_choices_json:
            try:
                choices = list(field_def.select_choices_json.items())
                if not field_def.is_required: choices.insert(0, ('', '---------')) 
                form.fields[field_def.name] = forms.ChoiceField(choices=choices, widget=forms.Select(attrs=widget_attrs), **field_kwargs_custom)
            except Exception as e: print(f"Ошибка парсинга JSON для поля {field_def.name}: {e}")
        if request.method == 'POST' and field_def.name in request.POST and field_def.name not in form.cleaned_data :
             if field_def.field_type == 'bool': form.fields[field_def.name].initial = request.POST.get(field_def.name) == 'on' # Для чекбоксов
             else: form.fields[field_def.name].initial = request.POST.get(field_def.name)

    if request.method == 'POST':
        if form.is_valid(): 
            ticket = form.save(commit=False) # Получаем объект тикета из стандартных полей формы
            # Устанавливаем стандартные поля, которые не были в основной форме, но определены как CustomFormField.is_standard
            for field_def in custom_fields_definitions:
                if field_def.is_standard and field_def.name in form.cleaned_data:
                    setattr(ticket, field_def.name, form.cleaned_data[field_def.name])
            
            ticket.category = selected_category
            try: default_status = TicketStatus.objects.get(is_default_status=True); ticket.status = default_status
            except TicketStatus.DoesNotExist: messages.error(request, "Ошибка: не найден статус по умолчанию."); return redirect('tickets:select_ticket_category')
            except TicketStatus.MultipleObjectsReturned: messages.error(request, "Ошибка: несколько статусов по умолчанию."); return redirect('tickets:select_ticket_category')
            
            custom_data_for_ticket = {}
            for field_def in custom_fields_definitions:
                if not field_def.is_standard and field_def.name in form.cleaned_data: # Только НЕ стандартные в JSON
                    if field_def.field_type == 'bool': custom_data_for_ticket[field_def.name] = form.cleaned_data.get(field_def.name, False)
                    else: custom_data_for_ticket[field_def.name] = form.cleaned_data[field_def.name]
            ticket.custom_form_data = custom_data_for_ticket
            
            ticket.save()
            uploaded_file = form.cleaned_data.get('attachment_file')
            if uploaded_file: Attachment.objects.create(ticket=ticket, file=uploaded_file, uploaded_by_name_display=ticket.reporter_name if hasattr(ticket, 'reporter_name') else "Заявитель")
            messages.success(request, f"Заявка #{ticket.ticket_id_display} для '{selected_category.name}' создана!")
            return redirect('tickets:select_ticket_category')
        else: messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    context = {'form': form, 'selected_category': selected_category, 'page_title': f"Заявка для '{selected_category.name}'"}
    return render(request, 'tickets/create_ticket.html', context)

def check_ticket_status_view(request):
    # ... (код без изменений, но убедись, что custom_fields_display формируется) ...
    ticket_instance = None; error_message = None; ticket_number = request.GET.get('ticket_number', '').strip()
    reporter_email = request.GET.get('reporter_email', '').strip(); comments_list = []; attachments_list = []
    custom_fields_display = []
    if ticket_number and reporter_email:
        try:
            ticket_instance = Ticket.objects.prefetch_related(
                'comments__attachments', 'attachments', 'category__custom_fields'
            ).get(ticket_id_display__iexact=ticket_number, reporter_email__iexact=reporter_email)
            comments_list = ticket_instance.comments.filter(is_internal=False).order_by('created_at')
            attachments_list = ticket_instance.attachments.filter(comment__isnull=True).order_by('uploaded_at')
            if ticket_instance.category and ticket_instance.custom_form_data:
                for field_def in ticket_instance.category.custom_fields.filter(is_active=True, is_standard=False).order_by('order'): # Показываем только НЕ стандартные из JSON
                    if field_def.name in ticket_instance.custom_form_data:
                        custom_fields_display.append({'label': field_def.label, 'value': ticket_instance.custom_form_data[field_def.name]})
        except Ticket.DoesNotExist: error_message = "Заявка с таким номером и email не найдена."
        except Exception as e: error_message = f"Произошла ошибка при поиске заявки: {e}" 
    context = {'ticket': ticket_instance, 'comments': comments_list, 'attachments': attachments_list,
        'error_message': error_message, 'ticket_number_query': ticket_number, 'reporter_email_query': reporter_email,
        'custom_fields_display': custom_fields_display}
    return render(request, 'tickets/check_ticket_status.html', context)

# -----------------------------------------------------------------------------
# ПРЕДСТАВЛЕНИЯ ДЛЯ АГЕНТОВ
# -----------------------------------------------------------------------------
@staff_member_required
def agent_dashboard_view(request):
    agent = request.user; context = {'agent_name': agent.get_full_name() or agent.username,}; return render(request, 'tickets/agent_dashboard.html', context)

@staff_member_required
def agent_ticket_list_view(request):
    current_agent = request.user; queryset = Ticket.objects.select_related('status', 'priority', 'assignee', 'category')
    agent_support_line = getattr(current_agent, 'support_line', None)
    if current_agent.role == 'super_admin': ticket_list = queryset.order_by('-created_at')
    elif agent_support_line is not None: ticket_list = queryset.filter(ticket_level=agent_support_line).order_by('-created_at')
    else: ticket_list = Ticket.objects.none()
    context = {'ticket_list': ticket_list, 'page_title': 'Все заявки',}; return render(request, 'tickets/agent_ticket_list.html', context)

@staff_member_required
def agent_my_tickets_view(request):
    current_agent = request.user; queryset = Ticket.objects.filter(assignee=current_agent).select_related('status', 'priority', 'assignee', 'category')
    agent_support_line = getattr(current_agent, 'support_line', None)
    if current_agent.role == 'super_admin': ticket_list = queryset.order_by('-created_at')
    elif agent_support_line is not None: ticket_list = queryset.filter(ticket_level=agent_support_line).order_by('-created_at')
    else: ticket_list = Ticket.objects.none()
    context = {'ticket_list': ticket_list, 'page_title': 'Мои заявки',}; return render(request, 'tickets/agent_ticket_list.html', context)

@staff_member_required
def agent_ticket_detail_view(request, ticket_pk):
    ticket = get_object_or_404(
        Ticket.objects.select_related('status', 'priority', 'category', 'assignee').prefetch_related(
            'comments__author_agent', 'comments__attachments', 'attachments', 'category__custom_fields'), 
        pk=ticket_pk)
    current_agent = request.user; current_user_role = current_agent.role
    agent_support_line = getattr(current_agent, 'support_line', None)

    can_change_priority = current_user_role in ['manager_l1', 'manager_l2', 'super_admin']
    assignable_agents = Agent.objects.none(); can_reassign_ticket = False
    if current_user_role == 'manager_l1' and agent_support_line == 1: assignable_agents = Agent.objects.filter(is_active=True, support_line=1).exclude(pk=current_agent.pk)
    elif current_user_role == 'manager_l2' and agent_support_line == 2: assignable_agents = Agent.objects.filter(is_active=True, support_line=2).exclude(pk=current_agent.pk)
    elif current_user_role == 'super_admin': assignable_agents = Agent.objects.filter(is_active=True).exclude(pk=current_agent.pk)
    if assignable_agents.exists(): can_reassign_ticket = True
    
    can_take_ticket = ticket.assignee is None
    if current_user_role == 'super_admin':
        can_escalate_to_l2 = (ticket.ticket_level == 1); can_de_escalate_to_l1 = (ticket.ticket_level == 2)
    else:
        can_escalate_to_l2 = (ticket.assignee == current_agent and current_user_role in ['agent_l1', 'manager_l1'] and ticket.ticket_level == 1)
        can_de_escalate_to_l1 = (ticket.assignee == current_agent and current_user_role in ['agent_l2', 'manager_l2'] and ticket.ticket_level == 2)

    comment_form_to_render = AgentCommentForm(); status_form_to_render = TicketUpdateStatusForm(initial={'status': ticket.status})
    priority_form_to_render = TicketUpdatePriorityForm(initial={'priority': ticket.priority}) if can_change_priority else None
    # category_form_to_render = TicketUpdateCategoryForm(initial={'category': ticket.category}) # Убрали
    reassign_agent_form_to_render = TicketReassignAgentForm(instance=ticket, assignable_agents=assignable_agents.order_by('username')) if can_reassign_ticket else None

    if request.method == 'POST':
        # Блок submit_comment
        if 'submit_comment' in request.POST:
            comment_form = AgentCommentForm(request.POST, request.FILES)
            if comment_form.is_valid():
                new_comment = comment_form.save(commit=False); new_comment.ticket = ticket; new_comment.author_agent = current_agent
                new_comment.is_internal = comment_form.cleaned_data.get('is_internal', False); new_comment.save()
                uploaded_file = comment_form.cleaned_data.get('attachment_file_comment')
                if uploaded_file:
                    try: Attachment.objects.create(comment=new_comment, ticket=ticket, file=uploaded_file, uploaded_by_agent=current_agent)
                    except Exception as e: messages.error(request, f"Комментарий добавлен, но ошибка при сохранении вложения: {e}")
                messages.success(request, "Комментарий успешно добавлен.")
                return redirect('tickets:agent_ticket_detail', ticket_pk=ticket.pk)
            else: messages.error(request, "Ошибка при добавлении комментария."); comment_form_to_render = comment_form
        
        # Блок submit_status
        elif 'submit_status' in request.POST:
            status_form = TicketUpdateStatusForm(request.POST, instance=ticket)
            if status_form.is_valid():
                status_form.save(); messages.success(request, f"Статус заявки обновлен на '{ticket.status.name}'.")
                Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Статус изменен на: {ticket.status.name}", is_internal=True)
                return redirect('tickets:agent_ticket_detail', ticket_pk=ticket.pk)
            else: messages.error(request, "Ошибка при обновлении статуса."); status_form_to_render = status_form

        # Блок submit_priority
        elif 'submit_priority' in request.POST:
            current_can_change_priority = current_agent.role in ['manager_l1', 'manager_l2', 'super_admin'] # Перепроверка
            if not current_can_change_priority: messages.error(request, "У вас нет прав для изменения приоритета.")
            else:
                priority_form = TicketUpdatePriorityForm(request.POST, instance=ticket)
                if priority_form.is_valid():
                    old_priority_name = ticket.priority.name if ticket.priority else "не был назначен"; priority_form.save()
                    new_priority_name = ticket.priority.name if ticket.priority else "снят"
                    messages.success(request, f"Приоритет изменен с '{old_priority_name}' на '{new_priority_name}'.")
                    Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Приоритет изменен на: {new_priority_name} (предыдущий: {old_priority_name})",is_internal=True)
                    return redirect('tickets:agent_ticket_detail', ticket_pk=ticket.pk)
                else: messages.error(request, "Ошибка при обновлении приоритета."); priority_form_to_render = priority_form
        
        # Блок submit_category (если бы он был)
        # elif 'submit_category' in request.POST: ...

        # Блок submit_reassign_agent
        elif 'submit_reassign_agent' in request.POST:
            post_assignable_agents = Agent.objects.none(); post_can_reassign_ticket = False
            if hasattr(current_agent, 'support_line'):
                agent_line_post = current_agent.support_line
                if current_user_role == 'manager_l1' and agent_line_post == 1: post_assignable_agents = Agent.objects.filter(is_active=True, support_line=1).exclude(pk=current_agent.pk)
                elif current_user_role == 'manager_l2' and agent_line_post == 2: post_assignable_agents = Agent.objects.filter(is_active=True, support_line=2).exclude(pk=current_agent.pk)
            if current_user_role == 'super_admin': post_assignable_agents = Agent.objects.filter(is_active=True).exclude(pk=current_agent.pk)
            if post_assignable_agents.exists(): post_can_reassign_ticket = True
            if not post_can_reassign_ticket: messages.error(request, "У вас нет прав для переназначения или нет доступных агентов.")
            else:
                reassign_agent_form = TicketReassignAgentForm(request.POST, instance=ticket, assignable_agents=post_assignable_agents.order_by('username'))
                if reassign_agent_form.is_valid():
                    old_assignee_obj = Ticket.objects.get(pk=ticket.pk).assignee 
                    old_assignee_name = old_assignee_obj.get_full_name() or old_assignee_obj.username if old_assignee_obj else "не был назначен"
                    reassign_agent_form.save(); new_assignee_obj = ticket.assignee
                    new_assignee_name = new_assignee_obj.get_full_name() or new_assignee_obj.username if new_assignee_obj else "снято назначение"
                    messages.success(request, f"Исполнитель изменен с '{old_assignee_name}' на '{new_assignee_name}'.")
                    Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Исполнитель изменен на: {new_assignee_name} (предыдущий: {old_assignee_name}).", is_internal=True)
                    return redirect('tickets:agent_ticket_detail', ticket_pk=ticket.pk)
                else: messages.error(request, "Ошибка при назначении исполнителя."); reassign_agent_form_to_render = reassign_agent_form
        
        # Блоки take_ticket, escalate_to_l2, de_escalate_to_l1 (как в последней рабочей версии)
        elif 'take_ticket' in request.POST:
            if ticket.assignee is not None: messages.error(request, "Заявка уже кем-то назначена.")
            else:
                ticket.assignee = current_agent; ticket.save()
                messages.success(request, f"Вы взяли заявку #{ticket.ticket_id_display} в работу.")
                Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Агент взял заявку в работу.", is_internal=True)
            return redirect('tickets:agent_ticket_detail', ticket_pk=ticket.pk)
        elif 'escalate_to_l2' in request.POST:
            perform_escalation = (current_user_role == 'super_admin' and ticket.ticket_level == 1) or \
                               (ticket.assignee == current_agent and current_user_role in ['agent_l1', 'manager_l1'] and ticket.ticket_level == 1)
            if not perform_escalation: messages.error(request, "Действие эскалации не разрешено.")
            else:
                old_level = ticket.get_ticket_level_display(); ticket.ticket_level = 2; old_assignee_for_log = ticket.assignee
                ticket.assignee = None; ticket.save(); new_level = ticket.get_ticket_level_display()
                assignee_info = f" (был назначен на {old_assignee_for_log.get_full_name() if old_assignee_for_log else 'неизвестного'})" if old_assignee_for_log else ""
                messages.success(request, f"Заявка #{ticket.ticket_id_display} передана на {new_level}.")
                Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Заявка передана на {new_level}{assignee_info}.", is_internal=True)
            return redirect('tickets:agent_ticket_detail', ticket_pk=ticket.pk)
        elif 'de_escalate_to_l1' in request.POST:
            perform_de_escalation = (current_user_role == 'super_admin' and ticket.ticket_level == 2) or \
                                  (ticket.assignee == current_agent and current_user_role in ['agent_l2', 'manager_l2'] and ticket.ticket_level == 2)
            if not perform_de_escalation: messages.error(request, "Действие деэскалации не разрешено.")
            else:
                old_level = ticket.get_ticket_level_display(); ticket.ticket_level = 1; old_assignee_for_log = ticket.assignee
                ticket.assignee = None; ticket.save(); new_level = ticket.get_ticket_level_display()
                assignee_info = f" (был назначен на {old_assignee_for_log.get_full_name() if old_assignee_for_log else 'неизвестного'})" if old_assignee_for_log else ""
                messages.success(request, f"Заявка #{ticket.ticket_id_display} возвращена на {new_level}.")
                Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Заявка возвращена на {new_level}{assignee_info}.", is_internal=True)
            return redirect('tickets:agent_ticket_detail', ticket_pk=ticket.pk)

    all_comments = ticket.comments.select_related('author_agent', 'ticket').prefetch_related('attachments').all().order_by('-created_at')
    user_and_agent_comments = []; ticket_history_log = []
    for comment in all_comments:
        is_system_log = comment.is_internal and ("Статус изменен на:" in comment.body or "Агент взял заявку в работу" in comment.body or "Приоритет изменен на:" in comment.body or "Категория изменена на:" in comment.body or "Исполнитель изменен на:" in comment.body or "Заявка передана на" in comment.body or "Заявка возвращена на" in comment.body)
        if is_system_log: ticket_history_log.append(comment)
        else: user_and_agent_comments.append(comment)
    ticket_attachments_list = ticket.attachments.filter(comment__isnull=True).order_by('uploaded_at')
    custom_fields_display = []
    if ticket.category and ticket.custom_form_data:
        for field_def in ticket.category.custom_fields.filter(is_active=True, is_standard=False).order_by('order'): 
            if field_def.name in ticket.custom_form_data:
                custom_fields_display.append({'label': field_def.label, 'value': ticket.custom_form_data[field_def.name]})
    
    context = {
        'ticket': ticket, 'comments_list': user_and_agent_comments, 'ticket_history_log': ticket_history_log,
        'ticket_attachments_list': ticket_attachments_list, 'comment_form': comment_form_to_render,
        'status_form': status_form_to_render, 'priority_form': priority_form_to_render,
        # 'category_form': category_form_to_render, # Убрали
        'assign_agent_form': reassign_agent_form_to_render,
        'can_change_priority': can_change_priority, 'can_reassign_ticket': can_reassign_ticket,
        'can_take_ticket': can_take_ticket, 'can_escalate_to_l2': can_escalate_to_l2,
        'can_de_escalate_to_l1': can_de_escalate_to_l1, 
        'custom_fields_display': custom_fields_display,
        'page_title': f"Заявка #{ticket.ticket_id_display}",
    }
    return render(request, 'tickets/agent_ticket_detail.html', context)