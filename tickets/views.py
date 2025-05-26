# tickets/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django import forms
from django.db.models import Q, Case, When, IntegerField
from datetime import datetime, timedelta

from .models import (
    Ticket, Comment, Attachment, TicketStatus, TicketCategory,
    TicketPriority, Agent, CustomFormField, Project, FieldTemplate,
    Feedback # Добавили модель Feedback
)
from .forms import (
    TicketCreateForm, AgentCommentForm, TicketUpdateStatusForm,
    TicketUpdatePriorityForm,
    TicketReassignAgentForm, SelectTicketCategoryForm,
    TicketUpdateProjectForm, TicketFilterForm,
    UserCommentForm, TicketReturnToWorkForm, # Для check_ticket_status
    MyTicketsStatusFilterForm, # Для страницы "Мои заявки"
    FeedbackForm # Добавили форму для Feedback
)

# Вспомогательная функция для IP
def get_client_ip(request):
    x_forward_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forward_for:
        ip = x_forward_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

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
        selected_category = TicketCategory.objects.select_related('project').prefetch_related('custom_form_fields__field_template').get(pk=category_id)
    except TicketCategory.DoesNotExist:
        messages.error(request, "Выбранная категория не найдена.")
        return redirect('tickets:select_ticket_category')

    if not selected_category.project:
        messages.error(request, f"Категория '{selected_category.name}' не привязана к проекту. Обратитесь к администратору.")
        return redirect('tickets:select_ticket_category')
    
    if not selected_category.project.is_active:
        messages.error(request, f"Проект '{selected_category.project.name}', к которому относится категория '{selected_category.name}', не активен. Обратитесь к администратору.")
        return redirect('tickets:select_ticket_category')

    form_kwargs = {}
    if request.method == 'POST':
        form_kwargs['data'] = request.POST
        form_kwargs['files'] = request.FILES
    
    form = TicketCreateForm(**form_kwargs) 
    
    custom_fields_definitions = selected_category.custom_form_fields.filter(is_active_in_category=True).select_related('field_template').order_by('order_in_category')
    
    for field_def in custom_fields_definitions:
        field_kwargs_custom = {
            'label': field_def.effective_label, 
            'required': field_def.is_required_in_category,
            'help_text': field_def.effective_help_text
        }
        widget_attrs = {}
        field_name = field_def.name
        field_type = field_def.field_type

        if field_type == 'char': widget_attrs['class'] = 'form-control'; form.fields[field_name] = forms.CharField(widget=forms.TextInput(attrs=widget_attrs), **field_kwargs_custom)
        elif field_type == 'text': widget_attrs['class'] = 'form-control'; form.fields[field_name] = forms.CharField(widget=forms.Textarea(attrs=widget_attrs), **field_kwargs_custom)
        elif field_type == 'email': widget_attrs['class'] = 'form-control'; form.fields[field_name] = forms.EmailField(widget=forms.EmailInput(attrs=widget_attrs), **field_kwargs_custom)
        elif field_type == 'int': widget_attrs['class'] = 'form-control'; form.fields[field_name] = forms.IntegerField(widget=forms.NumberInput(attrs=widget_attrs), **field_kwargs_custom)
        elif field_type == 'bool': widget_attrs['class'] = 'form-check-input'; form.fields[field_name] = forms.BooleanField(widget=forms.CheckboxInput(attrs=widget_attrs), **field_kwargs_custom)
        elif field_type == 'date': widget_attrs.update({'class': 'form-control', 'type': 'date'}); form.fields[field_name] = forms.DateField(widget=forms.DateInput(attrs=widget_attrs, format='%Y-%m-%d'), **field_kwargs_custom)
        elif field_type == 'file': widget_attrs['class'] = 'form-control-file'; form.fields[field_name] = forms.FileField(widget=forms.ClearableFileInput(attrs=widget_attrs), **field_kwargs_custom)
        elif field_type == 'select' and field_def.effective_select_choices_json:
            widget_attrs['class'] = 'form-select'
            try:
                choices = list(field_def.effective_select_choices_json.items())
                if not field_def.is_required_in_category: choices.insert(0, ('', '---------')) 
                form.fields[field_name] = forms.ChoiceField(choices=choices, widget=forms.Select(attrs=widget_attrs), **field_kwargs_custom)
            except Exception as e: print(f"Ошибка парсинга JSON для поля {field_name} в категории {selected_category.name}: {e}")

    if request.method == 'POST':
        if form.is_valid(): 
            ticket = form.save(commit=False)
            ticket.project = selected_category.project 
            ticket.category = selected_category
            ticket.reporter_ip_address = get_client_ip(request)

            try:
                default_status = TicketStatus.objects.get(is_default_status=True)
                ticket.status = default_status
            except TicketStatus.DoesNotExist: messages.error(request, "Ошибка: не найден статус по умолчанию."); return redirect('tickets:select_ticket_category')
            except TicketStatus.MultipleObjectsReturned: messages.error(request, "Ошибка: несколько статусов по умолчанию."); return redirect('tickets:select_ticket_category')

            standard_model_field_names = [f.name for f in Ticket._meta.get_fields() if not f.is_relation]
            custom_data_for_json_field = {}
            file_field_names = [f_def.name for f_def in custom_fields_definitions if f_def.field_type == 'file']

            for field_name_from_form, value_from_form in form.cleaned_data.items():
                if field_name_from_form in ['reporter_name', 'reporter_email']:
                    if field_name_from_form == 'reporter_name': ticket.reporter_name = value_from_form
                    if field_name_from_form == 'reporter_email': ticket.reporter_email = value_from_form
                    continue
                if field_name_from_form in file_field_names: continue

                if field_name_from_form in standard_model_field_names:
                    setattr(ticket, field_name_from_form, value_from_form)
                else:
                    is_defined_custom_non_file_field = any(cfield.name == field_name_from_form for cfield in custom_fields_definitions)
                    if is_defined_custom_non_file_field:
                        custom_data_for_json_field[field_name_from_form] = value_from_form
            
            ticket.custom_form_data = custom_data_for_json_field
            ticket.save() 

            for field_def in custom_fields_definitions:
                if field_def.field_type == 'file':
                    field_name = field_def.name
                    uploaded_file_object = form.cleaned_data.get(field_name)
                    if uploaded_file_object:
                        Attachment.objects.create(ticket=ticket, file=uploaded_file_object, uploaded_by_name_display=ticket.reporter_name)
            
            return redirect('tickets:ticket_creation_success', ticket_pk=ticket.pk)
        else: 
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
            context_for_error = {
                'form': form,
                'selected_category': selected_category, 
                'page_title': f"Заявка для категории '{selected_category.name}' (Проект: {selected_category.project.name})"
            }
            return render(request, 'tickets/create_ticket.html', context_for_error)
    
    context = {
        'form': form, 
        'selected_category': selected_category, 
        'page_title': f"Заявка для категории '{selected_category.name}' (Проект: {selected_category.project.name})"
    }
    return render(request, 'tickets/create_ticket.html', context)

def ticket_creation_success_view(request, ticket_pk):
    ticket = get_object_or_404(Ticket.objects.select_related('project', 'category'), pk=ticket_pk)
    ticket_track_url = request.build_absolute_uri(
        reverse('tickets:check_ticket_status') + f"?ticket_number={ticket.ticket_id_display}&reporter_email={ticket.reporter_email}"
    )
    page_title = f"Заявка #{ticket.ticket_id_display} успешно создана!"
    context = {
        'ticket': ticket,
        'ticket_track_url': ticket_track_url,
        'page_title': page_title,
    }
    return render(request, 'tickets/ticket_creation_success.html', context)

def check_ticket_status_view(request):
    ticket_instance = None; error_message = None
    comments_list = []; attachments_list = []
    custom_fields_display = []
    standard_ticket_fields = [f.name for f in Ticket._meta.get_fields() if not f.is_relation]
    user_comment_form = UserCommentForm()
    return_to_work_form = TicketReturnToWorkForm()
    can_return_to_work = False
    ticket_number_query = request.GET.get('ticket_number', request.POST.get('ticket_number_for_action', '')).strip()
    reporter_email_query = request.GET.get('reporter_email', request.POST.get('reporter_email_for_action', '')).strip()

    if ticket_number_query and reporter_email_query:
        try:
            ticket_instance = Ticket.objects.select_related(
                'project', 'status', 'priority', 'category', 'assignee'
            ).prefetch_related(
                'comments__attachments', 'attachments', 'category__custom_form_fields__field_template'
            ).get(ticket_id_display__iexact=ticket_number_query, reporter_email__iexact=reporter_email_query)
            
            comments_list = ticket_instance.comments.filter(is_internal=False).order_by('created_at')
            attachments_list = ticket_instance.attachments.filter(comment__isnull=True).order_by('uploaded_at')
            
            if ticket_instance.category and hasattr(ticket_instance.category, 'custom_form_fields') and ticket_instance.custom_form_data:
                for field_config in ticket_instance.category.custom_form_fields.filter(is_active_in_category=True).select_related('field_template').order_by('order_in_category'):
                    field_name = field_config.name
                    if field_name not in standard_ticket_fields and field_name in ticket_instance.custom_form_data:
                        custom_fields_display.append({'label': field_config.effective_label,'value': ticket_instance.custom_form_data[field_name]})
            
            if ticket_instance.status and ticket_instance.status.code == 'resolved':
                can_return_to_work = True
        except Ticket.DoesNotExist:
            if request.method == 'GET' and (request.GET.get('ticket_number') or request.GET.get('reporter_email')):
                 error_message = "Заявка с таким номером и email не найдена."
        except Exception as e: error_message = f"Произошла ошибка при поиске заявки: {e}"

    if request.method == 'POST':
        action_taken = False
        if not ticket_instance:
            messages.error(request, "Не удалось найти заявку для выполнения действия. Пожалуйста, проверьте номер заявки и email.")
            return redirect(reverse('tickets:check_ticket_status') + f"?ticket_number={ticket_number_query}&reporter_email={reporter_email_query}")

        if 'submit_user_comment' in request.POST:
            user_comment_form = UserCommentForm(request.POST, request.FILES)
            if user_comment_form.is_valid():
                client_ip = get_client_ip(request)
                display_name_for_user_comment = f"Пользователь, IP {client_ip}" if client_ip else "Пользователь"
                new_comment = Comment(ticket=ticket_instance, author_name_display=display_name_for_user_comment, body=user_comment_form.cleaned_data['body'], is_internal=False, author_ip_address=client_ip)
                new_comment.save()
                attachment_file = user_comment_form.cleaned_data.get('attachment_file')
                if attachment_file:
                    Attachment.objects.create(comment=new_comment, ticket=ticket_instance, file=attachment_file, uploaded_by_name_display=display_name_for_user_comment)
                messages.success(request, "Ваш комментарий успешно добавлен.")
                action_taken = True
            else: messages.error(request, "Пожалуйста, исправьте ошибки в форме комментария.")
        
        elif 'submit_return_to_work' in request.POST and can_return_to_work:
            return_to_work_form = TicketReturnToWorkForm(request.POST)
            if return_to_work_form.is_valid():
                try:
                    needs_rework_status = TicketStatus.objects.get(code='needs_rework')
                    old_status_name = ticket_instance.status.name
                    ticket_instance.status = needs_rework_status
                    ticket_instance.resolved_at = None; ticket_instance.closed_at = None
                    ticket_instance.save()
                    reopen_reason = return_to_work_form.cleaned_data['reopen_comment']
                    Comment.objects.create(ticket=ticket_instance,author_name_display=ticket_instance.reporter_name, body=f"Заявка возвращена в работу пользователем (статус изменен с '{old_status_name}' на '{needs_rework_status.name}').\nПричина: {reopen_reason}", is_internal=False, author_ip_address=get_client_ip(request))
                    messages.success(request, f"Заявка #{ticket_instance.ticket_id_display} возвращена в работу.")
                    action_taken = True
                except TicketStatus.DoesNotExist: messages.error(request, "Ошибка: не найден статус 'Требуется доработка'. Обратитесь к администратору.")
                except Exception as e: messages.error(request, f"Произошла ошибка при возврате заявки в работу: {e}")
            else: messages.error(request, "Пожалуйста, укажите причину возврата заявки в работу.")

        if action_taken:
            return redirect(reverse('tickets:check_ticket_status') + f"?ticket_number={ticket_number_query}&reporter_email={reporter_email_query}")

    context = {
        'ticket': ticket_instance, 'comments': comments_list, 'attachments': attachments_list,
        'error_message': error_message, 'ticket_number_query': ticket_number_query, 'reporter_email_query': reporter_email_query,
        'custom_fields_display': custom_fields_display, 'user_comment_form': user_comment_form,
        'return_to_work_form': return_to_work_form, 'can_return_to_work': can_return_to_work,
        'page_title': f"Статус заявки #{ticket_number_query}" if ticket_number_query else "Проверка статуса заявки"
    }
    return render(request, 'tickets/check_ticket_status.html', context)

def feedback_form_view(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tickets:feedback_success')
    else:
        form = FeedbackForm()
    context = {'form': form, 'page_title': "Форма жалоб и предложений"}
    return render(request, 'tickets/feedback_form.html', context)

def feedback_success_view(request):
    context = {'page_title': "Обращение отправлено"}
    return render(request, 'tickets/feedback_success.html', context)

# -----------------------------------------------------------------------------
# ПРЕДСТАВЛЕНИЯ ДЛЯ АГЕНТОВ
# -----------------------------------------------------------------------------
@staff_member_required
def agent_dashboard_view(request):
    agent = request.user; context = {'agent_name': agent.get_full_name() or agent.username,}; return render(request, 'tickets/agent_dashboard.html', context)

@staff_member_required
def check_new_tickets_api_view(request):
    current_agent = request.user
    relevant_tickets_qs = Ticket.objects.select_related('project', 'status', 'category')
    is_privileged_user = current_agent.is_superuser or getattr(current_agent, 'agent_role', None) == 'system_admin'
    if not is_privileged_user:
        agent_projects = current_agent.projects.filter(is_active=True)
        if agent_projects.exists(): relevant_tickets_qs = relevant_tickets_qs.filter(project__in=agent_projects)
        else: return JsonResponse({'new_tickets_count': 0, 'tickets': [], 'latest_ticket_id': None, 'current_server_time_iso': timezone.now().isoformat()})
    since_id_str = request.GET.get('since_id'); since_timestamp_str = request.GET.get('since_timestamp')
    new_tickets_query = Q()
    if since_id_str and since_id_str.isdigit(): new_tickets_query = Q(pk__gt=int(since_id_str))
    elif since_timestamp_str:
        try:
            since_timestamp = datetime.fromisoformat(since_timestamp_str.replace("Z", "+00:00"))
            if timezone.is_naive(since_timestamp): since_timestamp = timezone.make_aware(since_timestamp, timezone.utc)
            new_tickets_query = Q(created_at__gt=since_timestamp)
        except ValueError: pass
    else: new_tickets_query = Q(created_at__gte=timezone.now() - timedelta(minutes=5))
    
    new_tickets = relevant_tickets_qs.filter(new_tickets_query).order_by('-created_at') if new_tickets_query else relevant_tickets_qs.none()
    tickets_data_to_send = new_tickets[:5] 
    latest_ticket_id_in_batch = tickets_data_to_send.first().pk if tickets_data_to_send.exists() else None
    if not latest_ticket_id_in_batch and since_id_str and since_id_str.isdigit(): latest_ticket_id_in_batch = int(since_id_str)
    data = {
        'new_tickets_count': new_tickets.count(),
        'tickets': [{'id': t.pk, 'ticket_id_display': t.ticket_id_display, 'title': t.title, 'project': t.project.name if t.project else 'N/A', 'category': t.category.name if t.category else 'N/A', 'status_name': t.status.name if t.status else 'N/A', 'created_at_iso': t.created_at.isoformat(), 'url': reverse('tickets:agent_ticket_detail', kwargs={'ticket_pk': t.pk})} for t in tickets_data_to_send],
        'latest_ticket_id': latest_ticket_id_in_batch,
        'current_server_time_iso': timezone.now().isoformat()
    }
    return JsonResponse(data)

@staff_member_required
def agent_ticket_list_view(request):
    current_agent = request.user
    queryset = Ticket.objects.select_related('project', 'status', 'priority', 'assignee', 'category').all()
    is_privileged_display_user = current_agent.is_superuser or getattr(current_agent, 'agent_role', None) == 'system_admin'
    if not is_privileged_display_user:
        agent_projects = current_agent.projects.filter(is_active=True)
        if agent_projects.exists(): queryset = queryset.filter(project__in=agent_projects)
        else:
            queryset = Ticket.objects.none()
            if not request.GET: messages.info(request, "Вы не привязаны ни к одному активному проекту.")
    filter_form = TicketFilterForm(request.GET or None, user=current_agent)
    apply_show_active = filter_form.fields['show_active'].initial
    apply_show_completed = filter_form.fields['show_completed'].initial
    apply_show_only_new = filter_form.fields['show_only_new'].initial
    if filter_form.is_bound:
        if filter_form.is_valid():
            apply_show_active = filter_form.cleaned_data.get('show_active')
            apply_show_completed = filter_form.cleaned_data.get('show_completed')
            apply_show_only_new = filter_form.cleaned_data.get('show_only_new')
            search_query = filter_form.cleaned_data.get('search_query'); project_filter = filter_form.cleaned_data.get('project')
            category_filter = filter_form.cleaned_data.get('category'); status_filter_val = filter_form.cleaned_data.get('status') 
            priority_filter = filter_form.cleaned_data.get('priority'); assignee_filter = filter_form.cleaned_data.get('assignee')
            if search_query: queryset = queryset.filter(Q(ticket_id_display__icontains=search_query) | Q(title__icontains=search_query) | Q(description__icontains=search_query) | Q(reporter_name__icontains=search_query) | Q(reporter_email__icontains=search_query))
            if project_filter: queryset = queryset.filter(project=project_filter)
            if category_filter: queryset = queryset.filter(category=category_filter)
            if priority_filter: queryset = queryset.filter(priority=priority_filter)
            if assignee_filter: queryset = queryset.filter(assignee=assignee_filter)
            if apply_show_only_new:
                try: queryset = queryset.filter(status=TicketStatus.objects.get(code='new'))
                except TicketStatus.DoesNotExist: messages.warning(request, "Статус 'Новая' (код 'new') не найден.")
            elif status_filter_val: queryset = queryset.filter(status=status_filter_val)
            else: 
                q_status_filter = Q()
                if apply_show_active and not apply_show_completed: q_status_filter = Q(status__is_closed_status=False)
                elif not apply_show_active and apply_show_completed: q_status_filter = Q(status__is_closed_status=True)
                elif not apply_show_active and not apply_show_completed: queryset = queryset.none() 
                if q_status_filter: queryset = queryset.filter(q_status_filter)
    else: 
        if apply_show_only_new:
             try: queryset = queryset.filter(status=TicketStatus.objects.get(code='new'))
             except TicketStatus.DoesNotExist: messages.warning(request, "Статус 'Новая' (код 'new') не найден.")
        elif apply_show_active and not apply_show_completed: queryset = queryset.filter(status__is_closed_status=False)
        elif not apply_show_active and apply_show_completed: queryset = queryset.filter(status__is_closed_status=True)
        elif not apply_show_active and not apply_show_completed: queryset = queryset.none()
    try:
        new_status = TicketStatus.objects.get(code='new')
        queryset = queryset.annotate(is_new_status_order=Case(When(status=new_status, then=0), default=1, output_field=IntegerField()))
        ticket_list = queryset.distinct().order_by('is_new_status_order', '-created_at')
    except TicketStatus.DoesNotExist:
        messages.warning(request, "Статус 'Новых' заявок (код 'new') не найден. Применена стандартная сортировка.")
        ticket_list = queryset.distinct().order_by('-created_at')
    page_title = 'Список заявок' 
    if not is_privileged_display_user and hasattr(current_agent, 'projects'):
        user_project_names = [p.name for p in current_agent.projects.all() if p.is_active]
        if len(user_project_names) == 1: page_title = f'Заявки по проекту: {user_project_names[0]}'
        elif len(user_project_names) > 1: page_title = f'Заявки по вашим проектам'
    context = {'ticket_list': ticket_list, 'page_title': page_title, 'filter_form': filter_form}
    return render(request, 'tickets/agent_ticket_list.html', context)

@staff_member_required
def agent_my_tickets_view(request):
    current_agent = request.user
    queryset = Ticket.objects.filter(assignee=current_agent).select_related('project', 'status', 'priority', 'category')
    status_filter_form = MyTicketsStatusFilterForm(request.GET or None)
    apply_show_active = status_filter_form.fields['show_active'].initial
    apply_show_completed = status_filter_form.fields['show_completed'].initial
    if status_filter_form.is_bound:
        if status_filter_form.is_valid():
            apply_show_active = status_filter_form.cleaned_data.get('show_active')
            apply_show_completed = status_filter_form.cleaned_data.get('show_completed')
    q_status_filter = Q()
    if apply_show_active and not apply_show_completed: q_status_filter = Q(status__is_closed_status=False)
    elif not apply_show_active and apply_show_completed: q_status_filter = Q(status__is_closed_status=True)
    elif not apply_show_active and not apply_show_completed: queryset = queryset.none() 
    if q_status_filter: queryset = queryset.filter(q_status_filter)
    try:
        new_status = TicketStatus.objects.get(code='new')
        queryset = queryset.annotate(is_new_status_order=Case(When(status=new_status, then=0), default=1, output_field=IntegerField()))
        ticket_list = queryset.distinct().order_by('is_new_status_order', '-created_at')
    except TicketStatus.DoesNotExist: ticket_list = queryset.distinct().order_by('-created_at')
    context = {'ticket_list': ticket_list, 'page_title': 'Мои назначенные заявки', 'status_filter_form': status_filter_form, 'is_my_tickets_page': True}
    return render(request, 'tickets/agent_ticket_list.html', context)

@staff_member_required
def agent_ticket_detail_view(request, ticket_pk):
    ticket = get_object_or_404(Ticket.objects.select_related('project', 'status', 'priority', 'category', 'assignee').prefetch_related('comments__author_agent', 'comments__attachments', 'attachments', 'category__custom_form_fields__field_template'), pk=ticket_pk)
    current_agent = request.user
    is_django_superuser = current_agent.is_superuser
    is_helpdesk_system_admin = hasattr(current_agent, 'agent_role') and current_agent.agent_role == 'system_admin'
    is_privileged_user = is_django_superuser or is_helpdesk_system_admin
    can_view_ticket = is_privileged_user or (ticket.project and ticket.project in current_agent.projects.filter(is_active=True))
    if not can_view_ticket:
        messages.error(request, "У вас нет доступа к этому тикету или проекту."); return redirect('tickets:agent_ticket_list') 
    is_agent_in_ticket_project = ticket.project and ticket.project in current_agent.projects.all()
    is_manager_of_ticket_project = is_agent_in_ticket_project and hasattr(current_agent, 'is_project_manager') and current_agent.is_project_manager
    can_see_status_form = is_privileged_user or is_manager_of_ticket_project
    can_change_priority = is_manager_of_ticket_project or is_privileged_user
    can_reassign_ticket = False; assignable_agents_qs = Agent.objects.none()
    if (is_manager_of_ticket_project or is_privileged_user) and ticket.project:
        can_reassign_ticket = True
        assignable_agents_qs = Agent.objects.filter(is_active=True, projects=ticket.project).exclude(pk=ticket.assignee_id if ticket.assignee_id else 0).distinct().order_by('username') # Добавил if ticket.assignee_id else 0
    can_take_ticket = ticket.assignee is None and is_agent_in_ticket_project and ticket.project.is_active
    can_change_project = False
    if not ticket.status.is_closed_status:
        if is_privileged_user or (ticket.assignee == current_agent and is_agent_in_ticket_project) or is_manager_of_ticket_project: can_change_project = True
    can_close_this_ticket = False
    if ticket.status.is_resolved_status and not ticket.status.is_closed_status and (ticket.assignee == current_agent or is_manager_of_ticket_project or is_privileged_user): can_close_this_ticket = True
    comment_form_to_render = AgentCommentForm(); status_form_to_render = TicketUpdateStatusForm(initial={'status': ticket.status}) if can_see_status_form else None
    priority_form_to_render = TicketUpdatePriorityForm(initial={'priority': ticket.priority}) if can_change_priority else None
    reassign_agent_form_to_render = TicketReassignAgentForm(instance=ticket, assignable_agents=assignable_agents_qs) if can_reassign_ticket else None
    project_form_to_render = TicketUpdateProjectForm(initial={'project': ticket.project}) if can_change_project else None

    if request.method == 'POST':
        action_taken = False
        if 'submit_comment' in request.POST:
            action_taken = True; comment_form = AgentCommentForm(request.POST, request.FILES)
            if comment_form.is_valid():
                new_comment = comment_form.save(commit=False); new_comment.ticket = ticket; new_comment.author_agent = current_agent
                new_comment.is_internal = comment_form.cleaned_data.get('is_internal', False)
                new_comment.author_ip_address = get_client_ip(request) # Сохраняем IP агента
                new_comment.save()
                uploaded_file = comment_form.cleaned_data.get('attachment_file_comment')
                if uploaded_file: Attachment.objects.create(comment=new_comment, ticket=ticket, file=uploaded_file, uploaded_by_agent=current_agent)
                messages.success(request, "Комментарий успешно добавлен.")
            else: messages.error(request, "Ошибка при добавлении комментария."); comment_form_to_render = comment_form
        
        elif 'submit_status' in request.POST and can_see_status_form:
            action_taken = True; status_form = TicketUpdateStatusForm(request.POST, instance=ticket)
            if status_form.is_valid():
                new_status_obj = status_form.cleaned_data['status']; comment_for_status_change = request.POST.get('comment_for_status_change', '').strip()
                if (new_status_obj.is_resolved_status or new_status_obj.is_closed_status) and not comment_for_status_change:
                    messages.error(request, "Для установки этого статуса необходимо оставить комментарий.")
                    status_form_to_render = status_form
                else:
                    old_status_name = ticket.status.name; status_form.save(); msg_body = f"Статус изменен с '{old_status_name}' на '{ticket.status.name}'."
                    if comment_for_status_change: msg_body += f"\nКомментарий: {comment_for_status_change}"
                    Comment.objects.create(ticket=ticket, author_agent=current_agent, body=msg_body, is_internal=True)
                    messages.success(request, f"Статус заявки обновлен на '{ticket.status.name}'.")
            else: messages.error(request, "Ошибка при обновлении статуса."); status_form_to_render = status_form

        elif 'submit_priority' in request.POST and can_change_priority:
            action_taken = True; priority_form = TicketUpdatePriorityForm(request.POST, instance=ticket)
            if priority_form.is_valid():
                old_priority_name = ticket.priority.name if ticket.priority else "не был назначен"; priority_form.save()
                new_priority_name = ticket.priority.name if ticket.priority else "снят"
                messages.success(request, f"Приоритет изменен с '{old_priority_name}' на '{new_priority_name}'.")
                Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Приоритет изменен на: {new_priority_name} (предыдущий: {old_priority_name})",is_internal=True)
            else: messages.error(request, "Ошибка при обновлении приоритета."); priority_form_to_render = priority_form

        elif 'submit_project' in request.POST and can_change_project:
            action_taken = True; project_form = TicketUpdateProjectForm(request.POST, instance=ticket)
            if project_form.is_valid():
                old_project_name = ticket.project.name; new_project_obj = project_form.cleaned_data['project']
                ticket.assignee = None; project_form.save()
                messages.success(request, f"Проект заявки изменен с '{old_project_name}' на '{new_project_obj.name}'. Исполнитель сброшен.")
                Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Заявка перенаправлена из проекта '{old_project_name}' в проект '{new_project_obj.name}'. Исполнитель сброшен.", is_internal=True)
            else: messages.error(request, "Ошибка при изменении проекта."); project_form_to_render = project_form

        elif 'submit_reassign_agent' in request.POST and can_reassign_ticket:
            action_taken = True
            post_assignable_agents_qs = Agent.objects.none()
            if (is_manager_of_ticket_project or is_privileged_user) and ticket.project:
                post_assignable_agents_qs = Agent.objects.filter(is_active=True, projects=ticket.project).exclude(pk=ticket.assignee_id if ticket.assignee_id else 0).distinct().order_by('username')
            reassign_agent_form = TicketReassignAgentForm(request.POST, instance=ticket, assignable_agents=post_assignable_agents_qs)
            if reassign_agent_form.is_valid():
                old_assignee_obj = Ticket.objects.get(pk=ticket.pk).assignee 
                old_assignee_name = old_assignee_obj.get_full_name() or old_assignee_obj.username if old_assignee_obj else "не был назначен"
                reassign_agent_form.save(); new_assignee_obj = ticket.assignee
                new_assignee_name = new_assignee_obj.get_full_name() or new_assignee_obj.username if new_assignee_obj else "снято назначение"
                messages.success(request, f"Исполнитель изменен с '{old_assignee_name}' на '{new_assignee_name}'.")
                Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Исполнитель изменен на: {new_assignee_name} (предыдущий: {old_assignee_name}).", is_internal=True)
            else: messages.error(request, "Ошибка при назначении исполнителя."); reassign_agent_form_to_render = reassign_agent_form
        
        elif 'take_ticket' in request.POST and can_take_ticket:
            action_taken = True
            if ticket.assignee is not None: messages.error(request, "Заявка уже кем-то назначена.")
            else:
                ticket.assignee = current_agent; target_status_code = '80'
                try:
                    new_status = TicketStatus.objects.get(code=target_status_code)
                    old_status_name = ticket.status.name; ticket.status = new_status; ticket.save()
                    messages.success(request, f"Вы взяли заявку #{ticket.ticket_id_display} в работу. Статус изменен на '{new_status.name}'.")
                    Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Агент взял заявку в работу. Статус изменен с '{old_status_name}' на '{new_status.name}'.", is_internal=True)
                except TicketStatus.DoesNotExist: ticket.save(); messages.warning(request, f"Вы взяли заявку #{ticket.ticket_id_display} в работу, но статус с кодом '{target_status_code}' не найден."); Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Агент взял заявку в работу. (Статус '{target_status_code}' не найден).", is_internal=True)
                except Exception as e: ticket.save(); messages.error(request, f"Ошибка при смене статуса: {e}."); Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Агент взял заявку в работу. (Ошибка при смене статуса).", is_internal=True)

        elif 'action_resolve_ticket' in request.POST:
            action_taken = True
            if ticket.assignee == current_agent and not ticket.status.is_resolved_status and not ticket.status.is_closed_status:
                comment_body = request.POST.get('comment_for_action', '').strip()
                if not comment_body: messages.error(request, "Необходимо указать комментарий к решению.")
                else:
                    try:
                        new_status = TicketStatus.objects.get(code='resolved')
                        old_status_name = ticket.status.name; ticket.status = new_status; ticket.save()
                        Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Заявка помечена как 'Решена'. Статус изменен с '{old_status_name}' на '{new_status.name}'.\nРешение: {comment_body}", is_internal=False)
                        messages.success(request, f"Заявка #{ticket.ticket_id_display} помечена как 'Решена'.")
                    except TicketStatus.DoesNotExist: messages.error(request, "Ошибка: Статус 'resolved' не найден.")
                    except Exception as e: messages.error(request, f"Произошла ошибка: {e}")
            else: messages.error(request, "У вас нет прав или заявка уже решена/закрыта.")

        elif 'action_close_with_remarks_ticket' in request.POST:
            action_taken = True
            if ticket.assignee == current_agent and not ticket.status.is_closed_status:
                comment_body = request.POST.get('comment_for_action', '').strip()
                if not comment_body: messages.error(request, "Для 'Закрыть с замечанием' нужен комментарий.")
                else:
                    try:
                        new_status = TicketStatus.objects.get(code='closed_remarks')
                        old_status_name = ticket.status.name; ticket.status = new_status; ticket.save()
                        Comment.objects.create(ticket=ticket, author_agent=current_agent, body=f"Заявка закрыта с замечанием. Статус изменен с '{old_status_name}' на '{new_status.name}'.\nЗамечание: {comment_body}", is_internal=False)
                        messages.success(request, f"Заявка #{ticket.ticket_id_display} закрыта с замечанием.")
                    except TicketStatus.DoesNotExist: messages.error(request, "Ошибка: Статус 'closed_remarks' не найден.")
                    except Exception as e: messages.error(request, f"Произошла ошибка: {e}")
            else: messages.error(request, "У вас нет прав или заявка уже закрыта.")

        elif 'action_close_ticket' in request.POST:
            action_taken = True
            if can_close_this_ticket:
                comment_body = request.POST.get('comment_for_action', '').strip()
                try:
                    new_status = TicketStatus.objects.get(code='closed')
                    old_status_name = ticket.status.name; ticket.status = new_status; ticket.save()
                    body_for_comment = f"Заявка закрыта. Статус изменен с '{old_status_name}' на '{new_status.name}'."
                    if comment_body: body_for_comment += f"\nКомментарий при закрытии: {comment_body}"
                    Comment.objects.create(ticket=ticket, author_agent=current_agent, body=body_for_comment, is_internal=True)
                    messages.success(request, f"Заявка #{ticket.ticket_id_display} закрыта.")
                except TicketStatus.DoesNotExist: messages.error(request, "Ошибка: Статус 'closed' не найден.")
                except Exception as e: messages.error(request, f"Произошла ошибка: {e}")
            else: messages.error(request, "Нет прав для закрытия или заявка не решена/уже закрыта.")
        
        if action_taken: return redirect('tickets:agent_ticket_detail', ticket_pk=ticket.pk)

    all_comments = ticket.comments.select_related('author_agent', 'ticket__project').prefetch_related('attachments').all().order_by('-created_at')
    user_and_agent_comments = []; ticket_history_log = []
    system_log_phrases = ["Статус изменен на:", "Агент взял заявку в работу", "Приоритет изменен на:", "Исполнитель изменен на:", "Заявка перенаправлена из проекта", "Заявка помечена как 'Решена'", "Заявка закрыта", "Заявка закрыта с замечанием"]
    for comment in all_comments:
        if comment.is_internal and any(phrase in comment.body for phrase in system_log_phrases): ticket_history_log.append(comment)
        else: user_and_agent_comments.append(comment)
    
    ticket_attachments_list = ticket.attachments.filter(comment__isnull=True).order_by('uploaded_at')
    custom_fields_display = []
    standard_ticket_fields = [f.name for f in Ticket._meta.get_fields() if not f.is_relation]
    if ticket.category and hasattr(ticket.category, 'custom_form_fields') and ticket.custom_form_data:
        for field_config in ticket.category.custom_form_fields.filter(is_active_in_category=True).select_related('field_template').order_by('order_in_category'): 
            field_name = field_config.name
            if field_name not in standard_ticket_fields and field_name in ticket.custom_form_data:
                custom_fields_display.append({'label': field_config.effective_label, 'value': ticket.custom_form_data[field_name]})
    
    context = {
        'ticket': ticket, 'comments_list': user_and_agent_comments, 'ticket_history_log': ticket_history_log,
        'ticket_attachments_list': ticket_attachments_list, 'comment_form': comment_form_to_render,
        'status_form': status_form_to_render, 'priority_form': priority_form_to_render,
        'project_form': project_form_to_render, 'assign_agent_form': reassign_agent_form_to_render,
        'can_see_status_form': can_see_status_form, 'can_change_priority': can_change_priority, 
        'can_reassign_ticket': can_reassign_ticket, 'can_take_ticket': can_take_ticket, 
        'can_change_project': can_change_project, 'can_close_this_ticket': can_close_this_ticket, 
        'custom_fields_display': custom_fields_display,
        'page_title': f"Заявка #{ticket.ticket_id_display} (Проект: {ticket.project.name})",
    }
    return render(request, 'tickets/agent_ticket_detail.html', context)