"""Croatian calendar and seasonal environment for a full-year simulation.

Everything here is a modelling assumption, not a measurement. The seasonal
curves are shaped to reproduce Zagreb monthly means and typical Croatian mains
water temperatures; the behavioural consequences of day type are estimates.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum

# --------------------------------------------------------------- public holidays


def easter_sunday(year: int) -> dt.date:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def public_holidays(year: int) -> set[dt.date]:
    """Croatian public holidays (neradni dani)."""
    easter = easter_sunday(year)
    return {
        dt.date(year, 1, 1),  # Nova godina
        dt.date(year, 1, 6),  # Sveta tri kralja
        easter,  # Uskrs
        easter + dt.timedelta(days=1),  # Uskrsni ponedjeljak
        easter + dt.timedelta(days=60),  # Tijelovo
        dt.date(year, 5, 1),  # Praznik rada
        dt.date(year, 5, 30),  # Dan drzavnosti
        dt.date(year, 6, 22),  # Dan antifasisticke borbe
        dt.date(year, 8, 5),  # Dan pobjede
        dt.date(year, 8, 15),  # Velika Gospa
        dt.date(year, 11, 1),  # Svi sveti
        dt.date(year, 11, 18),  # Dan sjecanja
        dt.date(year, 12, 25),  # Bozic
        dt.date(year, 12, 26),  # Sveti Stjepan
    }


def school_holidays(year: int) -> list[tuple[dt.date, dt.date]]:
    """Approximate Croatian school holidays (children at home during the day)."""
    easter = easter_sunday(year)
    return [
        (dt.date(year, 1, 1), dt.date(year, 1, 7)),  # zimski
        (dt.date(year, 2, 17), dt.date(year, 2, 21)),  # proljetni
        (easter - dt.timedelta(days=3), easter + dt.timedelta(days=2)),
        (dt.date(year, 6, 21), dt.date(year, 8, 31)),  # ljetni
        (dt.date(year, 12, 24), dt.date(year, 12, 31)),
    ]


# --------------------------------------------------------------------- day types


class DayType(Enum):
    WORKDAY = "radni"
    WFH = "rad_od_doma"
    SATURDAY = "subota"
    SUNDAY = "nedjelja"
    HOLIDAY = "praznik"
    AWAY = "odsutni"


@dataclass(frozen=True)
class DayContext:
    date: dt.date
    day_type: DayType
    school_holiday: bool
    day_of_year: int

    @property
    def relaxed(self) -> bool:
        """Late start: nobody has to be anywhere in the morning."""
        return self.day_type in (
            DayType.SATURDAY,
            DayType.SUNDAY,
            DayType.HOLIDAY,
        )


# ------------------------------------------------------------ seasonal curves


def inlet_temp_c(day_of_year: int) -> float:
    """Mains water: ~8 C in late February, ~18 C in late August, smooth."""
    import math

    return 13.0 - 5.0 * math.cos(2.0 * math.pi * (day_of_year - 52) / 365.0)


def outdoor_temp_c(day_of_year: int) -> float:
    """Zagreb daily mean: ~1.5 C mid-January, ~23.5 C mid-July."""
    import math

    return 12.5 - 11.0 * math.cos(2.0 * math.pi * (day_of_year - 15) / 365.0)


def ambient_temp_c(day_of_year: int, unheated: bool) -> float:
    """Temperature of the space the tank stands in."""
    outdoor = outdoor_temp_c(day_of_year)
    if unheated:
        # damped and offset: a cellar or an unheated bathroom
        return 0.75 * outdoor + 0.25 * 15.0
    # heated flat: nearly constant, a little warmer in summer
    return 21.0 + 0.35 * max(0.0, outdoor - 12.0)


def shower_seasonal_factor(day_of_year: int) -> float:
    """People linger a little longer in a winter shower. Small effect."""
    import math

    return 1.0 + 0.08 * math.cos(2.0 * math.pi * (day_of_year - 15) / 365.0)


# ------------------------------------------------------------------- year build


def build_year(
    year: int,
    rng,
    wfh_days_per_week: float = 0.0,
    annual_leave_weeks: float = 2.0,
    winter_break_days: int = 0,
    weekend_only: bool = False,
) -> list[DayContext]:
    """Classify every day of the year for one household."""
    holidays = public_holidays(year)
    breaks = school_holidays(year)
    start = dt.date(year, 1, 1)
    n_days = (dt.date(year + 1, 1, 1) - start).days

    away: set[dt.date] = set()
    if annual_leave_weeks > 0:
        # main summer holiday, starting somewhere in July or August
        length = int(round(annual_leave_weeks * 7))
        first = dt.date(year, 7, 1) + dt.timedelta(days=int(rng.integers(0, 45)))
        away |= {first + dt.timedelta(days=i) for i in range(length)}
    if winter_break_days > 0:
        first = dt.date(year, 12, 24) + dt.timedelta(days=int(rng.integers(0, 4)))
        away |= {first + dt.timedelta(days=i) for i in range(winter_break_days)}

    days: list[DayContext] = []
    for i in range(n_days):
        date = start + dt.timedelta(days=i)
        doy = date.timetuple().tm_yday
        in_school_break = any(a <= date <= b for a, b in breaks)

        if weekend_only and date.weekday() < 4 and date not in holidays:
            day_type = DayType.AWAY
        elif date in away:
            day_type = DayType.AWAY
        elif date in holidays:
            day_type = DayType.HOLIDAY
        elif date.weekday() == 5:
            day_type = DayType.SATURDAY
        elif date.weekday() == 6:
            day_type = DayType.SUNDAY
        elif rng.random() < wfh_days_per_week / 5.0:
            day_type = DayType.WFH
        else:
            day_type = DayType.WORKDAY

        days.append(DayContext(date, day_type, in_school_break, doy))
    return days
