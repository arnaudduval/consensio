from django import forms
from .models import Elector, Election, Candidate, ConflictOfInterest, ElectorGroup

class ElectorForm(forms.ModelForm):
    class Meta:
        model = Elector
        fields = ['name', 'email']

class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ['title', 'description', 'start_date', 'end_date', 'is_active', 'electors']
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'class': 'datetimepicker'}),
            'end_date': forms.DateTimeInput(attrs={'class': 'datetimepicker'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'electors': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }

class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['name', 'election']

class ConflictOfInterestForm(forms.ModelForm):
    class Meta:
        model = ConflictOfInterest
        fields = ['elector', 'candidate']

class ElectorGroupForm(forms.ModelForm):
    class Meta:
        model = ElectorGroup
        fields = ['name', 'description']

class AddElectorToGroupForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=ElectorGroup.objects.all(),
        label="Groupe",
        empty_label="Sélectionnez un groupe"
    )
    electors = forms.ModelMultipleChoiceField(
        queryset=Elector.objects.all().order_by('name'),  # Tri par nom pour plus de clarté
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        label="Électeurs à ajouter",
    )
