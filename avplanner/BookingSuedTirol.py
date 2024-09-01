import datetime
from collections import defaultdict
from datetime import timedelta
from typing import Optional

import requests

from .AvailabilityFetcher import AvailabilityFetcher, Result
from .RateLimiter import RateLimiter
from .utils import date_range

# Get room types
BASE_URL = (
    "https://api.bookingsuedtirol.com/widgets/v6/properties/{booking_id}/"
)
ROOMS_URL = BASE_URL + "rooms?lang=en"
QUERY = "?from={start:%Y-%m-%d}&to={end:%Y-%m-%d}&guestCount={guest_count}&guests={guests}&lang=en"  # noqa
AVAILABILITIES_URL = BASE_URL + "availabilities" + QUERY
DETAILS_URL = BASE_URL + "offers" + QUERY


def _format_guests(num_guests: int) -> str:
    return str([[18] * num_guests])


class APIClient:
    """
    MonTMB API client to get availability for a given date.
    """

    def __init__(self, booking_id: str | int):
        self._booking_id = booking_id

    def get_room_types(self) -> dict[int, int]:
        """
        Get the room types and their room size (maximum occupancy).

        Returns
        -------
        dict[int, int]
            A dictionary mapping room type IDs to their room size.
        """
        url = ROOMS_URL.format(booking_id=self._booking_id)

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # TODO should probably also check min because people can get those
            # rooms with less people than capacity.
            return {room["room_id"]: room["occupancy"]["max"] for room in data}

        except requests.RequestException as e:
            print(f"Request error: {e}")

        return {}

    @RateLimiter(max_calls=1, period=5)
    def get_detailed_availability(
        self, date: datetime.date, guest_count: int
    ) -> dict[datetime.date, dict[int, int]]:
        """
        Get the detailed day availability for a specific date and guest count.

        Parameters
        ----------
        date: datetime.date
            The date to check availability for.
        guest_count: int
            The number of guests to check availability for, which determines
            the room types to show.

        Returns
        -------
        dict[datetime.date, dict[int, int]]
            A dictionary mapping room IDs to the number of available rooms.
        """
        url = DETAILS_URL.format(
            booking_id=self._booking_id,
            start=date,
            end=date + timedelta(days=1),
            guest_count=guest_count,
            guests=_format_guests(guest_count),
        )

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            return {
                room["room_id"]: room["room_free"] for room in data["rooms"]
            }
        except requests.RequestException as e:
            print(f"Request error: {e}")

        return {}

    @RateLimiter(max_calls=1, period=5)
    def get_global_availability(
        self,
        start: datetime.date,
        end: datetime.date,
        guest_count: int,
    ) -> list[datetime.date]:
        """
        Returns the dates with possible availability for the given date range
        and guest count.

        Parameters
        ----------
        start: datetime.date
            The start date to check availability for.
        end: datetime.date
            The end date to check availability for.
        guest_count: int
            The number of guests to check availability for.

        Returns
        -------
        list[datetime.date]
            A list of dates with availability.

        Raises
        ------
        ValueError
            If the date range is greater than 60 days.
        """
        if end - start > timedelta(days=60):
            raise ValueError("Date range must be less or equal than 60 days.")

        url = AVAILABILITIES_URL.format(
            booking_id=self._booking_id,
            start=start,
            end=end,
            guest_count=guest_count,
            guests=_format_guests(guest_count),
        )

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            return [
                datetime.datetime.strptime(item["date"], "%Y-%m-%d").date()
                for item in data
            ]

        except requests.RequestException as e:
            print(f"Request error: {e}")
        except ValueError as e:
            print(f"JSON parsing error: {e}")

        return []


class BookingSuedTirol(AvailabilityFetcher):
    """
    Fetcher for BookingSuedTirol systems.
    """

    def __init__(self, booking_id: str | int):
        self._booking_id = booking_id
        self._client = APIClient(booking_id)

    def _get_total_availability(
        self, start: datetime.date, end: datetime.date, num_guests: int
    ) -> list[datetime.date]:
        """
        Gets the total global availability for a given date range. Repeatedly
        calls the global availability API to get the availability for 60 days.

        Returns
        -------
        list[datetime.date]
            A list of dates with availability.
        """
        availability = []
        current = start
        while current <= end:
            data = self._client.get_global_availability(
                current, current + timedelta(days=60), num_guests
            )
            availability.extend(data)
            current += timedelta(days=61)  # +1 because end date is inclusive

        return availability

    def get_availability(
        self,
        start: datetime.date,
        end: datetime.date,
        cache: Optional[dict[datetime.date, Result]] = None,
    ) -> dict[datetime.date, Result]:
        """
        Fetches the availability for a given date range.
        """
        availability = {}

        # First use the global calendar to find which (date, num_guests)
        # combination has rooms.
        has_rooms = defaultdict(list)
        for num_guests in range(1, 5):
            dates = self._get_total_availability(start, end, num_guests)
            for date in dates:
                has_rooms[date].append(num_guests)

        # For each specific date find the room IDs that are available.
        room_types = self._client.get_room_types()  # room_id -> size
        for date in date_range(start, end):
            room2num: dict[int, int] = {}  # room_id: num_rooms_available
            for num_guests in has_rooms[date]:
                # Overriding here is OK because room availability is the same
                # regardless of the number of guests queried.
                room2num |= self._client.get_detailed_availability(
                    date, num_guests
                )

            rooms = {room_types[k]: v for k, v in room2num.items()}
            num_available = sum(k * v for k, v in rooms.items())
            availability[date] = Result(
                {
                    "num_available": num_available,
                    "rooms": rooms,
                }
            )

        return availability
