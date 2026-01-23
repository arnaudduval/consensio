from django import forms
from .models import Elector, Election, Candidate, ConflictOfInterest

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