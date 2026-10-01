from app.services.activation_code import generate_activation_code, verify_activation_code


def test_verify_accepts_matching_code():
    code, code_hash = generate_activation_code()
    assert verify_activation_code(code, code_hash) is True


def test_verify_rejects_wrong_code():
    _, code_hash = generate_activation_code()
    assert verify_activation_code("not-the-right-code", code_hash) is False


def test_verify_rejects_hash_from_different_code():
    _, hash_a = generate_activation_code()
    code_b, _ = generate_activation_code()
    assert verify_activation_code(code_b, hash_a) is False
