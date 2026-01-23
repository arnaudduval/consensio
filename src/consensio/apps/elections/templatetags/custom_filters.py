from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_candidate(candidates_dict, candidate_id):
    return candidates_dict.get(int(candidate_id))

# @register.filter
# def get_candidate(candidates, candidate_id):
#     for candidate in candidates:
#         if candidate.id == candidate_id:
#             return candidate
#     return None

@register.filter
def percentage(value, total):
    if total == 0:
        return 0
    return round((value / total) * 100)

@register.filter
def median_position(median, notes):
    notes_order = {'E': 0, 'TB': 1, 'B': 2, 'P': 3, 'R': 4}
    total = notes.E + notes.TB + notes.B + notes.P + notes.R

    if total == 0:
        return 0

    # Calculer la position cumulative
    cumulative = 0
    for note, count in [('E', notes.E), ('TB', notes.TB), ('B', notes.B), ('P', notes.P), ('R', notes.R)]:
        cumulative += count
        if notes_order[note] == median:
            # Position médiane = (cumulative - count/2) / total * 100
            return round(((cumulative - count/2) / total) * 100)

    return 0