from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.utils import timezone
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from collections import defaultdict
import statistics
from .models import Election, Vote, Invitation, ConflictOfInterest, ElectorGroup, ElectorGroupMembership
from .services import generate_ballot_paper, register_votes
from .forms import ElectorForm, ElectionForm, CandidateForm, ConflictOfInterestForm, ElectorGroupForm, AddElectorToGroupForm
from .decorators import admin_required
from .services import generate_tokens_for_election



def is_staff(user):
    return user.is_staff


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
    if request.method == 'POST':
        form = ElectorForm(request.POST)
        if form.is_valid():
            electeur = form.save()
            print(electeur)
            messages.success(request, "L'électeur a été ajouté avec succès !")
            return redirect('add_elector')
    else:
        form  = ElectorForm()

    return render(request, 'elections/add_elector.html', {'form': form})

@login_required
@user_passes_test(is_staff)
def add_election(request):
    elector_groups = ElectorGroup.objects.all()

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
    if request.method == 'POST':
        form = CandidateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Le candidat a été ajouté avec succès !")
            return redirect('add_candidate')
    else:
        form = CandidateForm()

    return render(request, 'elections/add_candidate.html', {'form': form})

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

def calculate_median_grade(candidate_votes):
    """Calcule la note médiane selon la méthode officielle du jugement majoritaire."""
    notes_order = {'E': 0, 'TB': 1, 'B': 2, 'P': 3, 'R': 4}

    # Extraire et trier les notes
    notes = sorted([notes_order[vote.note] for vote in candidate_votes])

    if not notes:
        return None

    n = len(notes)

    # Cas impair : électeur médian est à la position n//2
    if n % 2 == 1:
        return notes[n // 2]
    # Cas pair : électeur médian est à la position N = n//2 (0-based index = N-1)
    else:
        return notes[(n // 2) - 1]

def resolve_tie_recursive(tie_group, vote_details, candidates_dict, depth=0):
    """Résout un ex-aequo en utilisant la méthode récursive officielle."""
    if len(tie_group) == 1:
        return {tie_group[0]: depth}

    # Pour chaque candidat, obtenir ses votes
    candidates_votes = {}
    for candidate_id in tie_group:
        candidates_votes[candidate_id] = vote_details[candidate_id]

    # Trouver la mention majoritaire pour chaque candidat
    majority_mentions = {}
    for candidate_id, votes in candidates_votes.items():
        note_counts = defaultdict(int)
        for vote in votes:
            note_counts[vote.note] += 1

        # Trouver la note avec le plus de votes (majoritaire)
        if note_counts:
            majority_note = max(note_counts.items(), key=lambda x: x[1])[0]
            majority_mentions[candidate_id] = majority_note
        else:
            majority_mentions[candidate_id] = None

    # Grouper les candidats par mention majoritaire
    mention_groups = defaultdict(list)
    for candidate_id, mention in majority_mentions.items():
        mention_groups[mention].append(candidate_id)

    # Si tous les candidats ont la même mention majoritaire, on passe à l'étape suivante
    if len(mention_groups) == 1:
        # Trouver l'électeur médian pour chaque candidat
        median_voters = {}
        for candidate_id in tie_group:
            votes = candidates_votes[candidate_id]
            n = len(votes)
            if n > 0:
                # Trouver l'électeur médian (celui qui a déterminé la mention majoritaire)
                # Pour cela, on trouve le premier vote qui correspond à la mention majoritaire
                # en partant du milieu
                notes_order = {'E': 0, 'TB': 1, 'B': 2, 'P': 3, 'R': 4}
                sorted_votes = sorted([notes_order[vote.note] for vote in votes])
                median_note = majority_mentions[candidate_id]
                median_note_value = notes_order[median_note]

                # Trouver l'indice du premier vote égal à median_note_value
                median_index = sorted_votes.index(median_note_value)

                # Retirer ce vote pour la prochaine itération
                new_votes = votes[:median_index] + votes[median_index+1:]
                vote_details[candidate_id] = new_votes

        # Appel récursif
        return resolve_tie_recursive(tie_group, vote_details, candidates_dict, depth + 1)

    # Sinon, les candidats sont départagés par leur mention majoritaire
    resolution = {}
    rank = 0
    for mention in sorted(mention_groups.keys(), key=lambda x: {'E': 0, 'TB': 1, 'B': 2, 'P': 3, 'R': 4}[x]):
        for candidate_id in mention_groups[mention]:
            resolution[candidate_id] = rank
        rank += 1

    return resolution

def resolve_ties(sorted_candidates, vote_details, candidates_dict):
    """Résout les ex-aequo en utilisant la méthode officielle."""
    final_ranking = []
    tie_breakdown = []
    current_rank = 1
    i = 0

    while i < len(sorted_candidates):
        current_median = sorted_candidates[i][1]
        tie_group = [sorted_candidates[i][0]]  # Stocker uniquement les IDs

        # Trouver tous les candidats avec la même médiane
        j = i + 1
        while j < len(sorted_candidates) and sorted_candidates[j][1] == current_median:
            tie_group.append(sorted_candidates[j][0])
            j += 1

        if len(tie_group) > 1:
            # Résoudre l'ex-aequo avec la méthode récursive
            resolution = resolve_tie_recursive(tie_group, vote_details, candidates_dict)

            tie_breakdown.append({
                'candidates': [candidates_dict[c_id] for c_id in tie_group],
                'median': current_median,
                'resolution': resolution
            })

            # Trier selon la résolution
            sorted_tie_group = sorted(tie_group, key=lambda x: resolution.get(x, 0))
            final_ranking.extend([(candidates_dict[c_id], current_rank + k) for k, c_id in enumerate(sorted_tie_group)])
            current_rank += len(tie_group)
        else:
            final_ranking.append((candidates_dict[tie_group[0]], current_rank))
            current_rank += 1

        i = j

    return final_ranking, tie_breakdown

def results_election(request, election_id):
    election = get_object_or_404(Election, id=election_id)

    if not election.is_closed:
        messages.error(request, "Cette élection n'est pas encore fermée. Les résultats ne sont pas disponibles.")
        return redirect('detail_election', election_id=election.id)

    # Récupérer tous les votes
    votes = Vote.objects.filter(candidate__election=election).select_related('candidate')

    # Créer un dictionnaire pour mapper les IDs aux objets Candidate
    candidates_dict = {candidate.id: candidate for candidate in election.candidates.all()}

    # Préparer les données pour le template
    results = {}
    medians = {}
    vote_details = defaultdict(list)

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

        # Calculer la médiane
        median = calculate_median_grade(candidate_votes)
        medians[candidate.id] = median if median is not None else float('inf')

    # Trier les candidats par médiane
    sorted_candidates = sorted(medians.items(), key=lambda x: x[1])

    # Gérer les ex-aequo
    final_ranking, tie_breakdown = resolve_ties(sorted_candidates, vote_details, candidates_dict)

    # Préparer les données pour les bulletins
    ballots = defaultdict(list)
    for vote in votes:
        ballots[vote.ballot_token].append({
            'candidate': vote.candidate.name,
            'note': vote.get_note_display()
        })

    print(f'{results = }')
    print(f'{tie_breakdown = }')

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

    return render(request, 'elections/detail_election.html', {'election': election, 'conflicts_matrix': conflicts_matrix})

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