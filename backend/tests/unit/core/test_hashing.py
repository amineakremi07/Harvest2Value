import pytest
from pydantic import BaseModel

from app.core.hashing import canonical_json, sha256_of
from app.core.ids import new_id


def test_key_order_does_not_change_the_hash() -> None:
    assert sha256_of({"a": 1, "b": {"x": 1, "y": 2}}) == sha256_of({"b": {"y": 2, "x": 1}, "a": 1})


def test_integral_floats_hash_like_ints() -> None:
    assert sha256_of({"kg": 5000.0}) == sha256_of({"kg": 5000})
    assert sha256_of({"price": 2.4}) != sha256_of({"price": 2.40001})


def test_list_order_matters() -> None:
    assert sha256_of([1, 2]) != sha256_of([2, 1])


def test_booleans_are_not_turned_into_numbers() -> None:
    assert canonical_json({"flag": True}) == '{"flag":true}'


def test_pydantic_models_hash_like_their_json() -> None:
    class Item(BaseModel):
        name: str
        kg: float

    assert sha256_of(Item(name="olives", kg=10)) == sha256_of({"kg": 10, "name": "olives"})


def test_nan_is_rejected() -> None:
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_new_id_is_unique_uuid4_text() -> None:
    a, b = new_id(), new_id()
    assert a != b and len(a) == 36 and a[14] == "4"
