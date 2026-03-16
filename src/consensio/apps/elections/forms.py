from django import forms
from django.core.exceptions import ValidationError
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter available elections
        self.fields['election'].queryset = Election.objects.filter(is_closed=False, invitations_sent_at__isnull=True)

    def clean_election(self):
        election = self.cleaned_data.get('election')
        if election and (election.is_closed or election.invitations_sent_at is not None):
            raise ValidationError("Vous ne pouvez pas ajouter de candidat à une élection fermée ou pour laquelle les invitations ont déjà été envoyées.")
        return election

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

class CSVImportElectorForm(forms.Form):
    csv_file = forms.FileField(label="Fichier CSV", help_text="Sélectionner un fichier CSV contenant les électeurs")
    group_choice = forms.ChoiceField(
        label="Ajouter les électeurs à",
        choices=[
            ('new', 'Un Nouveau groupe (spécifier le nom ci-dessous)'),
            ('existing', 'Un groupe existant'),
        ],
        widget=forms.RadioSelect,
        initial="new"
    )
    new_group_name = forms.CharField(
        label="Nom du nouveau groupe",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nom du groupe'})
    )
    existing_group = forms.ModelChoiceField(
        label="Groupe existant",
        queryset=ElectorGroup.objects.all(),
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        group_choice = cleaned_data.get('group_choice')
        new_group_name = cleaned_data.get('new_group_name')
        existing_group = cleaned_data.get('existing_group')

        if group_choice == 'new' and not new_group_name:
            self.add_error('new_group_name', "Veuillez spécifier un nom pour le nouveau groupe")
        elif group_choice == 'existing' and not existing_group:
            self.add_error('existing_group', "Veuillez sélectionner un groupe existant.")

        return cleaned_data


class CSVImportCandidateForm(forms.Form):
    csv_file = forms.FileField(label="FichierCSV", help_text="Sélectionnez un fichier CSV contenant les candidats.")
    election = forms.ModelChoiceField(
        label="Élection",
        queryset=Election.objects.filter(is_closed=False, invitations_sent_at__isnull=True),
        empty_label="Sélectionnez une élection"
    )

    def clean_election(self):
        election = self.cleaned_data.get('election')
        if election and (election.is_closed or election.invitations_sent_at is not None):
            raise forms.ValidationError("Vous ne pouvez pas ajouter de candidats à une élection fermée ou pour laquelle les invitations ont déjà été envoyées.")
        return election

class AddElectorForm(forms.Form):
    # Form used to add an elector to an already existing election
    elector = forms.ModelChoiceField(
        label="Électeur",
        queryset=Elector.objects.none(),      # Will be filled in __init__
        empty_label="Sélectionnez un électeur"
    )

    def __init__(self, *args, election=None, **kwargs):
        super().__init__(*args, **kwargs)
        if election:
            # Exclude electors already in election
            current_electors = election.electors.all()
            self.fields['elector'].queryset = Elector.objects.exclude(id__in=current_electors)
