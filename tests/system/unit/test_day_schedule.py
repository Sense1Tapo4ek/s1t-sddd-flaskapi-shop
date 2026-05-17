import pytest

from system.domain.settings_agg import DaySchedule, InvalidScheduleError


@pytest.mark.unit
class TestDayScheduleValidTime:
    def test_valid_full_day(self):
        """
        Given valid opens_at and closes_at without a break,
        When constructing DaySchedule,
        Then the object is created without error.
        """
        # Arrange / Act
        schedule = DaySchedule(opens_at="09:00", closes_at="21:00")

        # Assert
        assert schedule.opens_at == "09:00"
        assert schedule.closes_at == "21:00"
        assert schedule.break_start is None
        assert schedule.break_end is None

    def test_valid_with_break(self):
        """
        Given a break window entirely inside the open window,
        When constructing DaySchedule,
        Then the object is created without error.
        """
        # Arrange / Act
        schedule = DaySchedule(
            opens_at="09:00",
            closes_at="21:00",
            break_start="13:00",
            break_end="14:00",
        )

        # Assert
        assert schedule.break_start == "13:00"
        assert schedule.break_end == "14:00"

    def test_valid_boundary_midnight(self):
        """
        Given opens_at at 00:00 and closes_at at 23:59,
        When constructing DaySchedule,
        Then the object is created without error.
        """
        # Arrange / Act
        schedule = DaySchedule(opens_at="00:00", closes_at="23:59")

        # Assert
        assert schedule.opens_at == "00:00"
        assert schedule.closes_at == "23:59"


@pytest.mark.unit
class TestDayScheduleInvalidTimeFormat:
    @pytest.mark.parametrize(
        "bad_time",
        [
            "25:00",   # hour out of range
            "9:00",    # no leading zero
            "09:5",    # single-digit minutes
            "09:60",   # minutes out of range
            "9:5",     # both wrong
            "09-00",   # wrong separator
            "0900",    # no separator
            "",        # empty string
            "ab:cd",   # non-digits
        ],
    )
    def test_invalid_opens_at_format_raises(self, bad_time):
        """
        Given a malformed time string for opens_at,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(opens_at=bad_time, closes_at="21:00")

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"

    @pytest.mark.parametrize(
        "bad_time",
        [
            "25:00",
            "9:00",
            "09:5",
        ],
    )
    def test_invalid_closes_at_format_raises(self, bad_time):
        """
        Given a malformed time string for closes_at,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(opens_at="09:00", closes_at=bad_time)

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"


@pytest.mark.unit
class TestDayScheduleOpenCloseOrder:
    def test_opens_equals_closes_raises(self):
        """
        Given opens_at equal to closes_at,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised (empty interval).
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(opens_at="09:00", closes_at="09:00")

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"

    def test_opens_after_closes_raises(self):
        """
        Given opens_at after closes_at,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(opens_at="21:00", closes_at="09:00")

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"


@pytest.mark.unit
class TestDayScheduleBreakValidation:
    def test_break_start_without_end_raises(self):
        """
        Given break_start set but break_end is None,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(opens_at="09:00", closes_at="21:00", break_start="13:00")

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"

    def test_break_end_without_start_raises(self):
        """
        Given break_end set but break_start is None,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(opens_at="09:00", closes_at="21:00", break_end="14:00")

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"

    def test_break_inverted_raises(self):
        """
        Given break_start >= break_end,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(
                opens_at="09:00",
                closes_at="21:00",
                break_start="14:00",
                break_end="13:00",
            )

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"

    def test_break_start_equals_break_end_raises(self):
        """
        Given break_start equal to break_end (zero-length break),
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(
                opens_at="09:00",
                closes_at="21:00",
                break_start="13:00",
                break_end="13:00",
            )

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"

    def test_break_start_before_opens_raises(self):
        """
        Given break_start earlier than opens_at,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(
                opens_at="09:00",
                closes_at="21:00",
                break_start="08:00",
                break_end="10:00",
            )

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"

    def test_break_end_after_closes_raises(self):
        """
        Given break_end later than closes_at,
        When constructing DaySchedule,
        Then InvalidScheduleError is raised.
        """
        # Act
        with pytest.raises(InvalidScheduleError) as exc_info:
            DaySchedule(
                opens_at="09:00",
                closes_at="21:00",
                break_start="20:00",
                break_end="22:00",
            )

        # Assert
        assert exc_info.value.code == "INVALID_SCHEDULE"

    def test_break_outside_window_both_edges(self):
        """
        Given a break_start exactly at opens_at (break starts immediately),
        When constructing DaySchedule,
        Then it is accepted (opens_at <= break_start is satisfied).
        """
        # Arrange / Act — this edge is acceptable per spec
        schedule = DaySchedule(
            opens_at="09:00",
            closes_at="21:00",
            break_start="09:00",
            break_end="10:00",
        )

        # Assert
        assert schedule.break_start == "09:00"
