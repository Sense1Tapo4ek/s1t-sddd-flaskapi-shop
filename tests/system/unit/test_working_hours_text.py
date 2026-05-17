import pytest

from system.domain.settings_agg import DaySchedule, SiteSettings


def _make_settings(**schedule_overrides) -> SiteSettings:
    """
    Build a SiteSettings with all days closed by default.
    Caller can override specific days with DaySchedule instances.
    """
    base_schedule = {d: None for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    base_schedule.update(schedule_overrides)
    return SiteSettings(
        id=1,
        phone="+375291234567",
        email="shop@example.com",
        address="Minsk",
        coords_lat=53.9,
        coords_lon=27.56,
        instagram="",
        telegram_bot_token="",
        telegram_chat_id="",
        working_hours_schedule=base_schedule,
    )


_ALL_DAY = DaySchedule(opens_at="09:00", closes_at="21:00")
_SAT_DAY = DaySchedule(opens_at="10:00", closes_at="20:00")
_BREAK_DAY = DaySchedule(
    opens_at="09:00", closes_at="21:00", break_start="13:00", break_end="14:00"
)


@pytest.mark.unit
class TestWorkingHoursText:
    def test_all_days_same_open(self):
        """
        Given all seven days have the same open schedule,
        When reading working_hours_text,
        Then a single group covering Mon–Sun is returned.
        """
        # Arrange
        settings = _make_settings(
            mon=_ALL_DAY, tue=_ALL_DAY, wed=_ALL_DAY, thu=_ALL_DAY,
            fri=_ALL_DAY, sat=_ALL_DAY, sun=_ALL_DAY,
        )

        # Act
        text = settings.working_hours_text

        # Assert
        assert text == "Пн–Вс: 09:00–21:00"

    def test_weekdays_one_weekend_other_sun_closed(self):
        """
        Given Mon–Fri same schedule, Sat different, Sun closed,
        When reading working_hours_text,
        Then three groups are rendered separated by semicolons.
        """
        # Arrange
        settings = _make_settings(
            mon=_ALL_DAY, tue=_ALL_DAY, wed=_ALL_DAY, thu=_ALL_DAY,
            fri=_ALL_DAY, sat=_SAT_DAY, sun=None,
        )

        # Act
        text = settings.working_hours_text

        # Assert
        assert text == "Пн–Пт: 09:00–21:00; Сб: 10:00–20:00; Вс: выходной"

    def test_all_closed(self):
        """
        Given all seven days are None (closed),
        When reading working_hours_text,
        Then the result is exactly 'Закрыто'.
        """
        # Arrange
        settings = _make_settings()  # all None by default

        # Act
        text = settings.working_hours_text

        # Assert
        assert text == "Закрыто"

    def test_with_break_renders_two_intervals(self):
        """
        Given Mon–Fri have a lunch break,
        When reading working_hours_text,
        Then each open interval and break interval are rendered separated by comma.
        """
        # Arrange
        settings = _make_settings(
            mon=_BREAK_DAY, tue=_BREAK_DAY, wed=_BREAK_DAY,
            thu=_BREAK_DAY, fri=_BREAK_DAY,
        )

        # Act
        text = settings.working_hours_text

        # Assert
        assert text == "Пн–Пт: 09:00–13:00, 14:00–21:00; Сб–Вс: выходной"

    def test_single_day_open_others_closed(self):
        """
        Given only Monday is open and the rest are closed,
        When reading working_hours_text,
        Then Mon gets no dash (single-day group), remaining days form a closed group.
        """
        # Arrange
        settings = _make_settings(mon=_ALL_DAY)

        # Act
        text = settings.working_hours_text

        # Assert
        assert text == "Пн: 09:00–21:00; Вт–Вс: выходной"

    def test_single_day_in_middle_open(self):
        """
        Given only Wednesday is open and surrounding days are closed,
        When reading working_hours_text,
        Then groups split correctly around the open day.
        """
        # Arrange
        settings = _make_settings(wed=_ALL_DAY)

        # Act
        text = settings.working_hours_text

        # Assert
        assert text == "Пн–Вт: выходной; Ср: 09:00–21:00; Чт–Вс: выходной"

    def test_mixed_groups_non_contiguous_same_schedule(self):
        """
        Given Mon and Wed have the same schedule but Tue is closed,
        When reading working_hours_text,
        Then Mon and Wed are NOT merged (not consecutive).
        """
        # Arrange
        settings = _make_settings(mon=_ALL_DAY, wed=_ALL_DAY)

        # Act
        text = settings.working_hours_text

        # Assert
        assert text == "Пн: 09:00–21:00; Вт: выходной; Ср: 09:00–21:00; Чт–Вс: выходной"

    def test_update_working_hours_schedule_replaces_fully(self):
        """
        Given a SiteSettings with a schedule,
        When calling update(working_hours_schedule=new_schedule),
        Then the schedule is fully replaced (not merged).
        """
        # Arrange
        settings = _make_settings(mon=_ALL_DAY, tue=_ALL_DAY)

        new_schedule = {d: None for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        new_schedule["sat"] = _SAT_DAY

        # Act
        settings.update(working_hours_schedule=new_schedule)

        # Assert
        assert settings.working_hours_schedule["mon"] is None
        assert settings.working_hours_schedule["sat"] is _SAT_DAY
        assert settings.working_hours_text == "Пн–Пт: выходной; Сб: 10:00–20:00; Вс: выходной"
