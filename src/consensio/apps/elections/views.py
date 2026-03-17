from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.utils import timezone
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from collections import defaultdict
import statistics
import csv
import io
from .models import Election, Elector, Vote, Invitation, ConflictOfInterest, ElectorGroup, ElectorGroupMembership, Candidate
from .services import generate_ballot_paper, register_votes
from .forms import ElectorForm, ElectionForm, CandidateForm, ConflictOfInterestForm, ElectorGroupForm, AddElectorToGroupForm, CSVImportElectorForm, CSVImportCandidateForm, AddElectorForm
from .decorators import admin_required
from .services import generate_tokens_for_election



def is_staff(user):
    return user.is_staff


@login_required
@user_passes_test(is_staff, login_url='/accounts/login/')
def delete_election(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    if request.method == 'POST':
        election.delete()
        messages.success(request, f"L'élection '{election.title}' a été supprimée avec succès.")
    return redirect('index')

def index(request):
    now = timezone.now()

    open_elections = Election.objects.filter(
        models.Q(end_date__gt=now) | models.Q(is_closed=False),
        is_active=True
    ).exclude(is_closed=True).distinct()

    closed_elections = Election.objects.filter(
        models.Q(end_date__lte=now) | models.Q(is_closed=True)
    ).distinct()

    context = {
        'open_elections': open_elections,
        'closed_elections': closed_elections,
        'is_staff': request.user.is_staff,
    }
    return render(request, 'elections/index.html', context)


def vote_election(request, election_id, token):
    election = Election.objects.get(id=election_id)

    # Test if election is closed
    if election.is_closed or timezone.now() > election.end_date:
        messages.error(request, "Cette élection est terminée. Il n'est plus possible de voter.")
        return redirect('index')

    # Verify if token is valid for this election
    try:
        invitation = Invitation.objects.get(election=election, ballot_token=token, is_used=False)
    except Invitation.DoesNotExist:
        messages.error(request, "Jeton de vote invalide ou déjà utilisé.")
        return redirect('index')

    # Verify if elector has already voted
    if Vote.objects.filter(ballot_token=invitation.ballot_token).exists():
        messages.warning(request, "Vous avez déjà voté pour cette élection.")
        return redirect('confirmation_vote', token=token)


    if request.method == 'POST':
        # Traiter le vote
        for candidate in election.candidates.all():
            note = request.POST.get(f'note_{candidate.id}')
            if note:
                # Vérifier si l'électeur est en conflit avec ce candidat
                if invitation.conflicts and str(candidate.id) in invitation.conflicts:
                    continue  # Ignorer ce vote (conflit d'intérêt)

                Vote.objects.create(
                    ballot_token=token,
                    candidate=candidate,
                    note=note
                )

        messages.success(request, "Votre vote a été enregistré avec succès.")
        return redirect('confirmation_vote', token=token)

    # Generate ballot paper
    ballot_paper = []
    for candidate in election.candidates.all():
        # Vérifier si l'électeur est en conflit avec ce candidat
        in_conflict = invitation.conflicts and str(candidate.id) in invitation.conflicts
        ballot_paper.append({
            'candidate': candidate,
            'in_conflict': in_conflict
        })

    return render(request, 'elections/ballot_paper.html', {
        'election': election,
        'token': token,
        'ballot_paper': ballot_paper
    })

def confirmation_vote(request, token):
    votes = Vote.objects.filter(ballot_token=token)
    return render(request, 'elections/confirmation.html', {'votes': votes, 'token': token})

@login_required
@user_passes_test(is_staff)
def add_elector(request):
    # Initialize forms
    form  = ElectorForm(prefix='single')
    csv_form = CSVImportElectorForm(prefix='csv')

    if request.method == 'POST':
        # Manually add an elector
        if 'add_single_elector' in request.POST:
            form = ElectorForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "L'électeur a été ajouté avec succès !")
                return redirect('add_elector')

        # CSV import
        elif 'import_csv' in request.POST:
            csv_form = CSVImportElectorForm(request.POST, request.FILES, prefix='csv')
            if csv_form.is_valid():
                csv_file = csv_form.cleaned_data['csv_file']
                group_choice = csv_form.cleaned_data['group_choice']
                new_group_name = csv_form.cleaned_data['new_group_name']
                existing_group = csv_form.cleaned_data['existing_group']

                # Set target group
                if group_choice == 'new':
                    group, created = ElectorGroup.objects.get_or_create(name=new_group_name)
                    if created:
                        messages.info(request, f"Le groupe {new_group_name} a été créé.")
                else:
                    group = existing_group

                # Read CSV file
                try:
                    csv_data = csv_file.read().decode('utf-8')
                    csv_reader = csv.reader(io.StringIO(csv_data), delimiter=';')
                    # Ignore first line (header)
                    next(csv_reader, None)
                    added_count = 0
                    duplicate_count = 0
                    error_count = 0

                    for row in csv_reader:
                        if len(row) < 2:
                            error_count += 1
                            continue

                        name, email = row[0].strip(), row[1].strip().lower()

                        # Verify if elector already exists
                        elector, created = Elector.objects.get_or_create(email=email, defaults={'name': name})

                        if created:
                            added_count += 1
                        else:
                            duplicate_count += 1
                            if elector.name != name:
                                elector.name = name
                                elector.save()

                        # Add elector to group
                        ElectorGroupMembership.objects.get_or_create(elector=elector, group=group)

                    messages.success(request, f"{added_count} nouveaux électeurs ajoutés avec succès.")

                    if duplicate_count > 0:
                        messages.warning(request, f"{duplicate_count} électeurs étaient déjà présents dans la base de données. Ils ont été ajoutés au groupe.")
                    if error_count > 0:
                        messages.error(request), f"{error_count} lignes du fichier CSV étaient invalides et ont été ignorées."
                except Exception as e:
                    messages.error(request, f"Erreur lors de la lecture du fichier CSV : {str(e)}")

                return redirect('add_elector')


            else:
                messages.error(request, "Erreur dans le formulaire d'importation CSV.")


    return render(request, 'elections/add_elector.html',
                  {'form': form, 'csv_form': csv_form})

@login_required
@user_passes_test(is_staff)
def add_election(request):
    elector_groups = ElectorGroup.objects.prefetch_related('electorgroupmembership_set__elector').all()

    if request.method == 'POST':
        form = ElectionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "L'élection a été ajoutée avec succès !")
            return redirect('add_election')
    else:
        form = ElectionForm()

    return render(request, 'elections/add_election.html', {'form': form, 'elector_groups': elector_groups})

@login_required
@user_passes_test(is_staff)
def add_candidate(request):
    # Initialize forms
    form = CandidateForm()
    csv_form = CSVImportCandidateForm()

    if request.method == 'POST':
        # Manuelly add a candidate
        if 'add_single_candidate' in request.POST:
            form = CandidateForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Le candidat a été ajouté avec succès !")
                return redirect('add_candidate')

        # CSV import
        else:
            csv_form = CSVImportCandidateForm(request.POST, request.FILES)
            if csv_form.is_valid():
                csv_file = csv_form.cleaned_data['csv_file']
                election = csv_form.cleaned_data['election']

                try:
                    csv_data = csv_file.read().decode('utf-8')
                    csv_reader = csv.reader(io.StringIO(csv_data), delimiter=';')

                    # Ignore fisrt line (header)
                    next(csv_reader, None)

                    added_count = 0
                    duplicate_count = 0
                    error_count = 0

                    for row in csv_reader:
                        if len(row) < 1:
                            error_count += 1
                            continue

                        name = row[0].strip()

                        # Verify if candidate already exists
                        if Candidate.objects.filter(name=name, election=election).exists():
                            duplicate_count += 1
                            continue

                        # Add candidate
                        Candidate.objects.create(name=name, election=election)
                        added_count += 1

                    messages.success(request, f"{added_count} nouveaux candidats ajoutés avec succès.")

                    if duplicate_count > 0:
                        messages.warning(request, f"{duplicate_count} candidats étaient déjà présents pour cette élection et n'ont pas été ajoutés.")
                    if error_count > 0:
                        messages.error(request, f"{error_count} ligens du fichier CSV étaient invalides et ont été ignorées.")

                except Exception as e:
                    messages.error(request, f"Erreur lors de la lecture du fichier CSV : {str(e)}")
                return redirect("add_candidate")

    return render(request, 'elections/add_candidate.html',
                  {'form': form, 'csv_form': csv_form})

@login_required
@user_passes_test(is_staff)
def add_conflict_of_interest(request):
    if request.method == 'POST':
        form = ConflictOfInterestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Le conflit d'intérêt a été ajouté avec succès !")
            return redirect('add_conflict_of_interest')
    else:
        form = ConflictOfInterestForm()

    return render(request, 'elections/add_conflict_of_interest.html', {'form': form})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from collections import defaultdict
from .models import Election, Vote, Candidate, ConflictOfInterest

def custom_logout(request):
    logout(request)
    return redirect('index')


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    next_page = reverse_lazy('index')


@login_required
@user_passes_test(is_staff)
def send_invitations(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if election.invitations_sent_at is not None:
        messages.warning(request, "Les invitations ont déjà été envoyées pour cette élection.")
        return redirect('detail_election', election_id=election.id)

    generate_tokens_for_election(election)
    election.invitations_sent_at = timezone.now()
    election.save()

    messages.success(request, f"Les invitations à voter pour l'élections '{election.title}' ont été envoyées avec succès !")
    return redirect('detail_election', election_id=election.id)


def detail_election(request, election_id):
    if not request.user.is_staff:
        return redirect('public_detail_election', election_id=election_id)

    election = get_object_or_404(Election, id=election_id)
    conflicts = ConflictOfInterest.objects.filter(candidate__election=election)

    conflicts_matrix = {}
    for elector in election.electors.all():
        conflicts_matrix[elector.id] = {}
        for candidate in election.candidates.all():
            conflicts_matrix[elector.id][candidate.id] = conflicts.filter(elector=elector, candidate=candidate).exists()

    # Add an elector to election
    if request.method == 'POST' and 'add_elector' in request.POST:
        form = AddElectorForm(request.POST, election=election)
        if form.is_valid():
            elector = form.cleaned_data.get('elector')
            if elector not in election.electors.all():
                election.electors.add(elector)
                messages.success(request, f"L'électeur {elector.name} a été ajouté avec succès à l'élection.")
            else:
                messages.warning(request, f"L'électeur {elector.name} est déjà dans cette élection.")
            return redirect('detail_election', election_id=election.id)
    else:
        form = AddElectorForm(election=election)

    return render(request, 'elections/detail_election.html', {
        'election': election,
        'conflicts_matrix': conflicts_matrix,
        'form': form,
        'can_edit': not election.invitations_sent_at and not election.is_closed
    })


def public_detail_election(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    conflicts = ConflictOfInterest.objects.filter(candidate__election=election)

    conflicts_matrix = {}
    for elector in election.electors.all():
        conflicts_matrix[elector.id] = {}
        for candidate in election.candidates.all():
            conflicts_matrix[elector.id][candidate.id] = conflicts.filter(elector=elector, candidate=candidate).exists()

    print(conflicts_matrix)


    return render(request, 'elections/public_detail_election.html', {
        'election': election,
        'conflicts_matrix': conflicts_matrix
    })

@login_required
@user_passes_test(is_staff)
@require_POST
def toggle_conflict_of_interest(request, election_id):
    elector_id = request.POST.get('elector_id')
    candidate_id = request.POST.get('candidate_id')

    if not elector_id or not candidate_id:
        return JsonResponse({'success': False, 'error': 'Missing parameters'}, status=400)

    election = get_object_or_404(Election, id=election_id)

    if election.invitations_sent_at is not None:
        return JsonResponse({'success': False, 'error': 'Les invitations ont déjà été envoyées'}, status=400)

    elector = get_object_or_404(Elector, id=elector_id)
    candidate = get_object_or_404(Candidate, id=candidate_id, election=election)

    conflict, created = ConflictOfInterest.objects.get_or_create(elector=elector, candidate=candidate)

    if not created:
        conflict.delete()
        action = 'supprimé'
    else:
        action = 'ajouté'

    return JsonResponse({'success': True, 'action': action})

@login_required
@user_passes_test(is_staff)
def close_election(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if election.is_closed:
        messages.warning(request, "Cette élection est déjà fermée.")
        return redirect('detail_election', election_id=election.id)

    election.close()
    messages.success(request, f"L'élection '{election.title}' a été fermée avec succès.")
    return redirect('detail_election', election_id=election.id)

@login_required
@user_passes_test(is_staff)
@require_POST
def delete_elector(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if election.invitations_sent_at is not None:
        return JsonResponse({
            'success': False,
            'message': 'Les invitations ont déjà été envoyées, impossible de supprimer un électeur.'
        }, status=400)

    elector_id = request.POST.get('elector_id')
    if not elector_id:
        return JsonResponse({
            'success': False,
            'message': 'ID de l\'électeur manquant.'
        }, status=400)

    elector = get_object_or_404(Elector, id=elector_id)

    if elector in election.electors.all():
        election.electors.remove(elector)
        return JsonResponse({
            'success': True,
            'message': f"L'électeur {elector.name} a été supprimé avec succès."
        })
    else:
        return JsonResponse({
            'success': False,
            'message': "Cet électeur n'est pas dans cette élection."
        }, status=400)

@login_required
@user_passes_test(is_staff)
@require_POST
def delete_candidate(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if election.invitations_sent_at is not None:
        return JsonResponse({
            'success': False,
            'message': 'Les invitations ont déjà été envoyées, impossible de supprimer un candidat.'
        }, status=400)

    candidate_id = request.POST.get('candidate_id')
    if not candidate_id:
        return JsonResponse({
            'success': False,
            'message': 'ID du candidat manquant.'
        }, status=400)

    candidate = get_object_or_404(Candidate, id=candidate_id, election=election)
    candidate.delete()

    return JsonResponse({
        'success': True,
        'message': f"Le candidat {candidate.name} a été supprimé avec succès."
    })

@login_required
@user_passes_test(is_staff)
def manage_groups(request):
    # Create a group
    if request.method == 'POST' and 'create_group' in request.POST:
        group_form =ElectorGroupForm(request.POST)
        if group_form.is_valid():
            group_form.save()
            messages.success(request, "Le groupe a été créé avec succès !")
            return redirect('manage_groups')

    # Add electors to a group
    elif request.method == 'POST' and 'add_electors_to_group' in request.POST:
        add_form = AddElectorToGroupForm(request.POST)
        if add_form.is_valid():
            group = add_form.cleaned_data['group']
            electors = add_form.cleaned_data['electors']
            print('group', group)
            print('electors', electors)

            for elector in electors:
                # Verify if elector is not already in the group
                if not ElectorGroupMembership.objects.filter(elector=elector, group=group).exists():
                    ElectorGroupMembership.objects.create(elector=elector, group=group)
            messages.success(request, f"Les électeurs ont été ajoutés au groupe {group.name} avec succès !")
            return redirect('manage_groups')
    else:
        group_form = ElectorGroupForm()
        add_form = AddElectorToGroupForm()

    # Get all groups and their electors
    groups = ElectorGroup.objects.prefetch_related('electorgroupmembership_set').all()

    return render(request, 'elections/manage_groups.html', {
        'group_form': group_form,
        'add_form': add_form,
        'groups': groups,
    })

def calculate_median_grade(candidate_votes):
    """Calcule la note médiane selon la méthode officielle du jugement majoritaire."""
    notes_order = {'E': 0, 'TB': 1, 'B': 2, 'P': 3, 'R': 4}
    notes = sorted([notes_order[vote.note] for vote in candidate_votes])
    if not notes:
        return None
    n = len(notes)
    if n % 2 == 1:
        return notes[n // 2]
    else:
        return notes[(n // 2) - 1]

def results_election(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    if not election.is_closed:
        messages.error(request, "Cette élection n'est pas encore fermée. Les résultats ne sont pas disponibles.")
        return redirect('detail_election', election_id=election.id)

    # Récupérer tous les votes
    votes = Vote.objects.filter(candidate__election=election).select_related('candidate')

    # Préparer les données pour le template
    results = {}
    medians = {}
    vote_details = defaultdict(list)
    candidates_dict = {candidate.id: candidate for candidate in election.candidates.all()}

    for candidate in election.candidates.all():
        candidate_votes = votes.filter(candidate=candidate)
        note_counts = {
            'E': candidate_votes.filter(note='E').count(),
            'TB': candidate_votes.filter(note='TB').count(),
            'B': candidate_votes.filter(note='B').count(),
            'P': candidate_votes.filter(note='P').count(),
            'R': candidate_votes.filter(note='R').count(),
        }
        results[candidate] = note_counts
        vote_details[candidate.id] = list(candidate_votes)
        median = calculate_median_grade(candidate_votes)
        medians[candidate.id] = median if median is not None else float('inf')

    # Trier les candidats par médiane
    sorted_candidates = sorted(medians.items(), key=lambda x: x[1])

    # Gérer les ex-aequo
    final_ranking = []
    tie_breakdown = []
    current_rank = 1
    i = 0

    while i < len(sorted_candidates):
        current_median = sorted_candidates[i][1]
        tie_group = [sorted_candidates[i][0]]

        # Trouver tous les candidats avec la même médiane
        j = i + 1
        while j < len(sorted_candidates) and sorted_candidates[j][1] == current_median:
            tie_group.append(sorted_candidates[j][0])
            j += 1

        if len(tie_group) > 1:
            tie_breakdown.append({
                'candidates': [candidates_dict[c_id] for c_id in tie_group],
                'median': current_median,
            })
            # Tous les candidats du groupe ont le même rang
            for c_id in tie_group:
                final_ranking.append((candidates_dict[c_id], current_rank, True, len(tie_group)))
            current_rank += len(tie_group)
        else:
            final_ranking.append((candidates_dict[tie_group[0]], current_rank, False, 0))
            current_rank += 1

        i = j

    # Préparer les données pour les bulletins
    ballots = defaultdict(list)
    for vote in votes:
        ballots[vote.ballot_token].append({
            'candidate': vote.candidate.name,
            'note': vote.get_note_display()
        })

    return render(request, 'elections/results.html', {
        'election': election,
        'results': results,
        'medians': medians,
        'final_ranking': final_ranking,
        'tie_breakdown': tie_breakdown,
        'ballots': dict(ballots),
        'notes_info': {
            'E': {'label': 'Excellent', 'order': 0, 'color': 'success'},
            'TB': {'label': 'Très bien', 'order': 1, 'color': 'primary'},
            'B': {'label': 'Bien', 'order': 2, 'color': 'info'},
            'P': {'label': 'Passable', 'order': 3, 'color': 'warning'},
            'R': {'label': 'À rejeter', 'order': 4, 'color': 'danger'},
        },
        'notes_order': {'E': 0, 'TB': 1, 'B': 2, 'P': 3, 'R': 4},
        'notes_labels': {'0': 'Excellent', '1': 'Très bien', '2': 'Bien', '3': 'Passable', '4': 'À rejeter'},
        'candidates_dict': candidates_dict,
    })