# tickets/forms.py
from django import forms
from .models import (
    Ticket, Agent, Comment, 
    TicketCategory, TicketStatus, TicketPriority, Project,
    Feedback # Добавлен импорт для Feedback
)

# ------------------- Форма для Шага 1: Выбор Категории Тикета -------------------
class SelectTicketCategoryForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=TicketCategory.objects.filter(
            project__is_active=True, 
            is_active=True
        ).select_related('project').order_by('project__name', 'name'),
        label="Выберите категорию вашей проблемы",
        empty_label=None, 
        widget=forms.RadioSelect(attrs={'class': 'form-check-input-stacked'}), # Уточни класс, если он не стандартный Bootstrap
        help_text="От выбора категории зависит, какие поля вам нужно будет заполнить далее."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].label_from_instance = lambda obj: f"{obj.name} (Проект: {obj.project.name})"

# ------------------- Форма для Шага 2: Создание Тикета (базовая часть) -------------------
class TicketCreateForm(forms.ModelForm):
    reporter_name = forms.CharField(
        label='Ваше ФИО', 
        required=True, 
        widget=forms.TextInput(attrs={'placeholder': 'Иванов Иван Иванович', 'class': 'form-control'})
    )
    reporter_email = forms.EmailField(
        label='Ваш Email (для уведомлений)', 
        required=True, 
        widget=forms.EmailInput(attrs={'placeholder': 'ivan.ivanov@example.com', 'class': 'form-control'})
    )
    
    class Meta:
        model = Ticket
        fields = ['reporter_name', 'reporter_email']
        labels = {} 
        widgets = {} 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Динамические поля добавляются во views.py

# ------------------- Формы для Агентов на странице деталей тикета -------------------
class AgentCommentForm(forms.ModelForm):
    is_internal = forms.BooleanField(
        label="Внутренний комментарий (виден только агентам)", 
        required=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    attachment_file_comment = forms.FileField(
        label="Прикрепить файл к комментарию (необязательно)", 
        required=False, 
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )
    class Meta:
        model = Comment
        fields = ['body', 'is_internal', 'attachment_file_comment']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Введите текст вашего комментария...', 'class': 'form-control'}),
        }
        labels = {
            'body': 'Текст комментария',
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['body'].required = True

class TicketUpdateStatusForm(forms.ModelForm):
    status = forms.ModelChoiceField(
        queryset=TicketStatus.objects.all().order_by('order', 'name'), 
        label="Новый статус", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta: 
        model = Ticket
        fields = ['status']

class TicketUpdatePriorityForm(forms.ModelForm):
    priority = forms.ModelChoiceField(
        queryset=TicketPriority.objects.all().order_by('order', 'name'), 
        label="Новый приоритет", 
        widget=forms.Select(attrs={'class': 'form-select'}), 
        required=False
    )
    class Meta: 
        model = Ticket
        fields = ['priority']

class TicketReassignAgentForm(forms.ModelForm):
    assignee = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        label="Новый исполнитель", 
        required=True, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta: 
        model = Ticket
        fields = ['assignee']
        
    def __init__(self, *args, **kwargs):
        assignable_agents_queryset = kwargs.pop('assignable_agents', Agent.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = assignable_agents_queryset
        if not assignable_agents_queryset.exists():
            self.fields['assignee'].empty_label = "Нет доступных исполнителей"
            self.fields['assignee'].widget.attrs['disabled'] = True

class TicketUpdateProjectForm(forms.ModelForm):
    project = forms.ModelChoiceField(
        queryset=Project.objects.filter(is_active=True).order_by('name'),
        label="Новый проект",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = Ticket
        fields = ['project']

# ------------------- Форма Фильтров для Общего Списка Тикетов Агента -------------------
class TicketFilterForm(forms.Form):
    search_query = forms.CharField(
        label="Поиск",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'ID, тема, заявитель...', 'class': 'form-control form-control-sm'})
    )
    project = forms.ModelChoiceField(
        label="Проект",
        queryset=Project.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="Все проекты",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    category = forms.ModelChoiceField(
        label="Категория",
        queryset=TicketCategory.objects.all().order_by('project__name', 'name'),
        required=False,
        empty_label="Все категории",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    status = forms.ModelChoiceField(
        label="Статус",
        queryset=TicketStatus.objects.all().order_by('order', 'name'),
        required=False,
        empty_label="Все статусы",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    priority = forms.ModelChoiceField(
        label="Приоритет",
        queryset=TicketPriority.objects.all().order_by('order', 'name'),
        required=False,
        empty_label="Все приоритеты",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    assignee = forms.ModelChoiceField(
        label="Исполнитель",
        queryset=Agent.objects.filter(is_active=True).order_by('username'),
        required=False,
        empty_label="Любой исполнитель",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    show_active = forms.BooleanField(
        label="Активные",
        required=False,
        initial=True, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_show_active'})
    )
    show_completed = forms.BooleanField(
        label="Завершенные",
        required=False,
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_show_completed'})
    )
    show_only_new = forms.BooleanField(
        label="Только новые",
        required=False,
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_show_only_new'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)

        if user:
            is_privileged_filter_user = user.is_superuser or \
                                       (hasattr(user, 'agent_role') and user.agent_role in ['system_admin', 'project_manager'])

            if not is_privileged_filter_user:
                self.fields['show_only_new'].initial = True
                self.fields['show_active'].initial = False
                self.fields['show_completed'].initial = False
            
            if not (user.is_superuser or getattr(user, 'agent_role', None) == 'system_admin'):
                user_projects = user.projects.filter(is_active=True)
                self.fields['project'].queryset = user_projects
                
                if user_projects.exists():
                    self.fields['category'].queryset = TicketCategory.objects.filter(
                        project__in=user_projects, is_active=True
                    ).select_related('project').order_by('project__name', 'name')
                    self.fields['assignee'].queryset = Agent.objects.filter(
                        is_active=True, projects__in=user_projects
                    ).distinct().order_by('username')
                else:
                    self.fields['category'].queryset = TicketCategory.objects.none()
                    self.fields['assignee'].queryset = Agent.objects.none()
            else: 
                 self.fields['category'].queryset = TicketCategory.objects.filter(
                    project__is_active=True, is_active=True
                 ).select_related('project').order_by('project__name', 'name')
                 self.fields['assignee'].queryset = Agent.objects.filter(is_active=True).order_by('username')
        else: 
            self.fields['project'].queryset = Project.objects.none()
            self.fields['category'].queryset = TicketCategory.objects.none()
            self.fields['assignee'].queryset = Agent.objects.none()
            
        self.fields['category'].label_from_instance = lambda obj: f"{obj.name} ({obj.project.name})"
        self.fields['project'].label_from_instance = lambda obj: obj.name
        self.fields['assignee'].label_from_instance = lambda obj: obj.get_full_name() or obj.username

    def clean(self):
        cleaned_data = super().clean()
        show_only_new = cleaned_data.get('show_only_new')

        if show_only_new:
            cleaned_data['show_active'] = False
            cleaned_data['show_completed'] = False
            cleaned_data['status'] = None 
        
        return cleaned_data

# ------------------- Формы для страницы проверки статуса тикета пользователем -------------------
class UserCommentForm(forms.Form):
    body = forms.CharField(
        label="Ваш комментарий",
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Введите ваш комментарий...', 'class': 'form-control'}),
        required=True
    )
    attachment_file = forms.FileField(
        label="Прикрепить файл (необязательно)",
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file', 'style': 'margin-top: 5px;'})
    )

class TicketReturnToWorkForm(forms.Form):
    reopen_comment = forms.CharField(
        label="Причина возврата в работу (обязательно)",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Опишите, что нужно доработать...', 'class': 'form-control'}),
        required=True
    )

# ------------------- Форма Фильтров для "Моих заявок" Агента -------------------
class MyTicketsStatusFilterForm(forms.Form):
    show_active = forms.BooleanField(
        label="Активные",
        required=False,
        initial=True, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    show_completed = forms.BooleanField(
        label="Завершенные",
        required=False,
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

# ------------------- Форма для Жалоб и Предложений -------------------
class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['feedback_type', 'name', 'email', 'subject', 'message']
        widgets = {
            'feedback_type': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Иванов Иван (или оставьте пустым для анонимности)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'user@example.com (необязательно)'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Тема вашего обращения'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Подробно опишите вашу жалобу или предложение...'}),
        }
        labels = { # Можно переопределить метки, если стандартные из модели не подходят
            'name': "Ваше имя (или анонимно)",
            'email': "Ваш Email (для возможной обратной связи, необязательно)",
            'feedback_type': "Тип вашего обращения",
            'subject': "Тема",
            'message': "Сообщение",
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False