from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('delete-election/<int:election_id>/', views.delete_election, name='delete_election'),
    path('elections/<int:election_id>/results/', views.results_election, name='results_election'),
    path('elections/<int:election_id>/vote/<uuid:token>/', views.vote_election, name='vote_election'),
    path('confirmation/<uuid:token>/', views.confirmation_vote, name='confirmation_vote'),
    path('add-elector/', views.add_elector, name='add_elector'),
    path('add-election/', views.add_election, name='add_election'),
    path('add-candidate/', views.add_candidate, name='add_candidate'),
    path('add-conflict-of-interest/', views.add_conflict_of_interest, name='add_conflict_of_interest'),
    path('elections/<int:election_id>/', views.detail_election, name='detail_election'),
    path('elections/<int:election_id>/public/', views.public_detail_election, name='public_detail_election'),
    path('elections/<int:election_id>/send-invitations/', views.send_invitations, name='send_invitations'),
    path('elections/<int:election_id>/close/', views.close_election, name='close_election'),
    path('elections/<int:election_id>/toggle-conflict/', views.toggle_conflict_of_interest, name='toggle_conflict_of_interest'),
    path('elections/<int:election_id>/delete-elector/', views.delete_elector, name='delete_elector'),
    path('elections/<int:election_id>/delete-candidate/', views.delete_candidate, name='delete_candidate'),
    path('manage-groups/', views.manage_groups, name='manage_groups'),

]