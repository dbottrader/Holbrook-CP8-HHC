from gpumesh.textutil import canon_answer, judge_outputs, similarity
from gpumesh.work import CANARIES
from gpumesh_node.runtime import fallback_text


def test_similarity_ignores_case_and_space():
    assert similarity("MESH_OK", "  mesh_ok\n") == 1
    assert similarity("hello there", "totally different") < 0.5
    assert similarity("", "x") == 0


def test_judge_penalizes_only_deterministic_disagreement():
    assert judge_outputs("same", "same", 0, 0.82) == "agree"
    assert judge_outputs("alpha", "omega", 0, 0.82) == "disagree_deterministic"
    assert judge_outputs("alpha", "omega", 0.7, 0.82) == "disagree_sampling"
    assert judge_outputs("  ", "omega", 0, 0.82) == "parent_empty"


def test_cpu_fallback_answers_canaries_and_is_stable():
    messages = [{"role": "user", "content": "Say hello in one sentence."}]
    assert fallback_text(messages, 64) == fallback_text(list(messages), 64)
    for prompt, expected in CANARIES:
        assert canon_answer(fallback_text([{"role": "user", "content": prompt}], 16)) == canon_answer(expected)
