from datetime import timedelta

MIN_EASE = 1.3


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def schedule_after_review(is_correct: bool, ease: float, interval_days: int):
    """
    Retourne (new_ease, new_interval_days, due_delta).
    Algo SM-2 simplifié.
    """
    if is_correct:
        # succès : on remonte légèrement l'ease
        ease = clamp(ease + 0.05, MIN_EASE, 3.0)
        if interval_days == 0:
            interval_days = 1
        elif interval_days == 1:
            interval_days = 2
        else:
            interval_days = int(round(interval_days * ease))
        return ease, interval_days, timedelta(days=interval_days)
    else:
        # échec : on redescend l'ease et on revoit bientôt
        ease = clamp(ease - 0.20, MIN_EASE, 3.0)
        return ease, 0, timedelta(minutes=10)
