import pytest

from shared.helpers.security import generate_recovery_code


@pytest.mark.unit
class TestGenerateRecoveryCode:
    def test_returns_six_digits(self):
        """
        Given default length,
        When generate_recovery_code is called,
        Then result is a 6-character all-digit string.
        """
        code = generate_recovery_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_zero_padded(self):
        """
        Given length=6,
        When the random value would produce fewer than 6 digits,
        Then the result is left-padded with zeros.
        """
        # Force a small value through secrets.randbelow by sampling many times
        # and checking that at least structurally all results are 6 chars.
        codes = {generate_recovery_code() for _ in range(50)}
        assert all(len(c) == 6 for c in codes)
        assert all(c.isdigit() for c in codes)

    def test_custom_length(self):
        """
        Given length=4,
        When generate_recovery_code(4) is called,
        Then result has exactly 4 digits.
        """
        code = generate_recovery_code(length=4)
        assert len(code) == 4
        assert code.isdigit()

    def test_not_always_same(self):
        """
        Given two independent calls,
        When generate_recovery_code is called twice,
        Then results differ (with overwhelming probability).
        """
        codes = {generate_recovery_code() for _ in range(20)}
        assert len(codes) > 1

    def test_zero_length_raises(self):
        """
        Given length=0,
        When generate_recovery_code(0) is called,
        Then ValueError is raised.
        """
        with pytest.raises(ValueError, match="length must be >= 1"):
            generate_recovery_code(length=0)

    def test_negative_length_raises(self):
        """
        Given length=-1,
        When generate_recovery_code(-1) is called,
        Then ValueError is raised.
        """
        with pytest.raises(ValueError, match="length must be >= 1"):
            generate_recovery_code(length=-1)
