from django.contrib import admin
from .models import Elector, Election, Candidate, ConflictOfInterest, Vote

@admin.register(Elector)
class ElectorAdmin(admin.ModelAdmin):
    list_display = ('name', 'email')
    search_fields = ('name', 'email')

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'start_date', 'end_date', 'is_active')
    search_fields = ('title',)
    filter_horizontal = ('electors',)

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'election')
    search_fields = ('name',)
    list_filter = ('election',)

@admin.register(ConflictOfInterest)
class ConflictOfInterestAdmin(admin.ModelAdmin):
    list_display = ('elector', 'candidate')
    search_fields = ('elector__name', 'candidate__name')
    list_filter = ('elector', 'candidate')

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('ballot_token', 'candidate', 'note', 'vote_date')
    search_fields = ('ballot_token', 'candidate__name')
    list_filter = ('candidate', 'note')


