from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

# @register.filter
# def get_candidate(candidates_dict, candidate_id):
#     return candidates_dict.get(int(candidate_id))


@register.filter
def get_candidate(dictionary, candidate_id):
    try:
        return dictionary.get(int(candidate_id))
    except (ValueError, TypeError):
        return None

@register.filter
def percentage(part, whole):
    try:
        return round((float(part) / float(whole)) * 100)
    except (ValueError, ZeroDivisionError):
        return 0

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

@register.filter
def candidate_id(dictionary, key):
    for candidate_id, candidate in dictionary.items():
        if str(candidate_id) == str(key):
            return candidate
    return None