"""Sampling pins the node sends on every volunteer job.

These values live in this package so the join image, which ships
``gpumesh_node`` and not the coordinator, can import them. The same numbers
are repeated in ``gpumesh.textutil`` and in the public edge function.
``tests/test_pin_sync.py`` checks the three copies.
"""

DET_TEMPERATURE = 0
DET_TOP_K = 1
DET_TOP_P = 1.0
DET_REPEAT_PENALTY = 1.0
DET_NUM_CTX = 2048
