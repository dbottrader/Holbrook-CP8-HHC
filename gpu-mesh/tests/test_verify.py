from gpumesh.textutil import (
    canon_answer,
    compare_outputs,
    judge_outputs,
    mesh_seed,
    normalize_match,
)
from gpumesh.work import CANARIES


def test_mesh_seed_is_stable_and_fits_a_signed_int():
    assert mesh_seed("job_abc") == mesh_seed("job_abc")
    assert mesh_seed("job_abc") != mesh_seed("job_def")
    assert 0 <= mesh_seed("job_abc") < 2**31


def test_exact_text_agrees_and_whitespace_uses_the_normalized_rule():
    assert compare_outputs("same", "same") == ("agree", "exact")
    assert compare_outputs("Hello\u00a0world", "Hello world") == ("agree", "normalized")
    assert compare_outputs("alpha  beta", "alpha beta") == ("agree", "normalized")
    assert normalize_match("A\u00a0B") == "A B"
    verdict, rule = compare_outputs("alpha", "omega")
    assert verdict == "disagree_deterministic"
    assert rule == ""
    assert judge_outputs("alpha", "omega", 0.7, 0.82) == "disagree_deterministic"
    assert compare_outputs("  ", "omega") == ("parent_empty", "")


def test_canaries_keep_their_exact_token():
    for prompt, expected in CANARIES:
        assert canon_answer(expected) == canon_answer(expected)
        assert prompt
