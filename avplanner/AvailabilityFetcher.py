import datetime
from abc import ABC, abstractmethod
from typing import Optional, TypedDict


class Result(TypedDict):
    num_available: int
    rooms: dict[int, int]  # room_size -> num_rooms


class AvailabilityFetcher(ABC):
    """
    Protocol for classes that fetch availability for a given date range.
    """

    @abstractmethod
    def get_availability(
        self,
        start: datetime.date,
        end: datetime.date,
        cache: Optional[dict[datetime.date, Result]] = None,
    ) -> dict[datetime.date, Result]:
        """
        Gets the availability for each day in the date range and returns a
        dictionary with dates as keys and a `Result` dictionary with the number
        of beds available and detailed room availability.

        Parameters
        ----------
        start_date: datetime.date
            The start date of the date range.
        end_date: datetime.date
            The end date of the date range (inclusive).
        cache: Optional[dict]
            A dictionary that contains the availability data for each day from
            previous fetches. This can be useful to avoid fetching the same
            data multiple times.
        """
        raise NotImplementedError
