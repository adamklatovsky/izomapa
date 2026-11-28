import math


def tenis_mrizka(L, W, kl=34.0, kw=17.0):
    """Kolik kurtů (podél, napříč) se vejde do plochy L × W (L ≥ W). Záporné první číslo = kurty natočené napříč
    (jejich délka podél W), pak (počet podél W, počet podél L)."""
    f = lambda a, b: (max(1, round(a / kl)), max(1, round(b / kw)))
    err = lambda a, b, n: abs(math.log(a / n[0] / kl)) + abs(math.log(b / n[1] / kw))
    p, q = f(L, W), f(W, L)
    return p if err(L, W, p) <= err(W, L, q) else (-q[0], q[1])
