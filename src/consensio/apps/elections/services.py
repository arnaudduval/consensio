from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import PermissionDenied
import uuid
from .models import Vote, ConflictOfInterest, Candidate, Invitation

def send_vote_invitation(elector, election, token):
    vote_link = f"{settings.BASE_SITE_URL}/elections/{election.id}/vote/{token}"
    subject = f"Invitation à voter : {election.title}"
    message = f"Bonjour {elector.name},\n\nVous êtres invité à voter pour l'élection '{election.title}'.\n\nLien pour voter : {vote_link}\n\nVotre jeton de vote : {token}\n\nCordialement,\nL'équipe consensio"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [elector.email])
    return vote_link

def generate_tokens_for_election(election):
    invitations = []
    for elector in election.electors.all():
        invitation = Invitation.objects.create(election=election)

        # Get conflicts of interest for elector
        conflicts = ConflictOfInterest.objects.filter(elector=elector, candidate__election=election)
        conflicts_dict = {str(conflict.candidate.id): True for conflict in conflicts}
        invitation.conflicts = conflicts_dict
        invitation.save()

        send_vote_invitation(elector, election, invitation.ballot_token)
        invitations.append(invitation)

    return invitations

def generate_ballot_paper(elector, election):
    candidates = Candidate.objects.filter(election=election)
    ballot_paper = []
    for candidate in candidates:
        if not ConflictOfInterest.objects.filter(elector=elector, candidate=candidate).exists():
            ballot_paper.append(candidate)

    return ballot_paper

def register_votes(token, votes):
    for canditate_id, note in votes.items():
        candidate = Candidate.objects.get(id=canditate_id)
        # Verify if a vote is already existing for this token
        if Vote.objects.filter(ballot_token=token, candidate=candidate).exists():
            raise PermissionDenied(f"Un vote existe déjà pour le candidat {candidate.name} avec ce jeton.")
        Vote.objects.create(
            ballot_token=token,
            candidate=candidate,
            note=note
        )


