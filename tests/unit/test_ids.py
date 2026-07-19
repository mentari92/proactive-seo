import uuid

import pytest
from proactive_core.ids import InvalidPublicId, decode_id, encode_id


def test_public_id_round_trip_and_type_safety() -> None:
    value = uuid.uuid4()
    encoded = encode_id(value, "usr")
    assert encoded.startswith("usr_")
    assert decode_id(encoded, "usr") == value
    with pytest.raises(InvalidPublicId):
        decode_id(encoded, "org")
