from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class Elector(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name


class Election(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    electors = models.ManyToManyField(Elector, related_name='elections')
    invitations_sent_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

    def close(self):
        self.is_closed = True
        self.closed_at = timezone.now()
        if self.closed_at < self.end_date:
            self.end_date = self.closed_at
        self.save()

class Candidate(models.Model):
    name = models.CharField(max_length=200)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')

    def __str__(self):
        return self.name

class ConflictOfInterest(models.Model):
    elector = models.ForeignKey(Elector, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.elector} est en conflit d'intérêt avec {self.candidate}."

class Vote(models.Model):
    NOTES = [
        ('E', 'Excellent'),
        ('TB', 'Très bien'),
        ('B', 'Bien'),
        ('P', 'Passable'),
        ('R', 'À rejeter')
    ]
    ballot_token = models.UUIDField(default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    note = models.CharField(max_length=2, choices=NOTES)
    vote_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('ballot_token', 'candidate')     # An elector can only vote once for a candidate

    def __str__(self):
        return f"Vote pour {self.candidate} : {self.note} (jeton : {self.ballot_token})"

class Invitation(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    ballot_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_used = models.BooleanField(default=False)
    # Store conflicts of interest as a dict {candidate_id: True/False}
    # Anonymisation : relation elector/invitation is not stored in database
    conflicts = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Invitation pour {self.election.title} (token: {self.ballot_token})"
