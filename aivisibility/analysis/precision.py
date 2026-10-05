"""Settings for how many random repetitions the analysis uses.

Each number answers "how many repeats is enough?". They live here so
they are explained once, not hidden as magic defaults.
"""

# Bootstrap resamples per confidence interval (CI).
# Rule of thumb: at least 1000 (Efron & Tibshirani, 1993).
# With 200 the CI width wobbles ~7-8% just from resampling; with 1000 it is
# ~3-5%. More than 1000 helps little and costs more time.
BOOTSTRAP_RESAMPLES = 1000

# Allowed random noise (in percentage points) in the average CI half-width
# on a convergence curve. Our target is 5 pp, so 0.5 pp (a tenth of it)
# is small enough not to change any conclusion.
MC_TOLERANCE_PP = 0.5

# Limits for how many random subsamples we take for each n.
# MIN: with too few draws the noise estimate itself is unreliable.
MIN_SUBSAMPLES = 30
# MAX: time limit if the tolerance is never reached. Rarely hit.
MAX_SUBSAMPLES = 2000
