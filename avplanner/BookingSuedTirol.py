import datetime
from collections import defaultdict
from datetime import timedelta

import requests

from avplanner.RateLimiter import RateLimiter
from avplanner.utils import date_range

# Get room types
BASE_URL = (
    "https://api.bookingsuedtirol.com/widgets/v6/properties/{booking_id}/"
)
ROOMS_URL = BASE_URL + "rooms?lang=en"
QUERY = "?from={start:%Y-%m-%d}&to={end:%Y-%m-%d}&guestCount={guest_count}&guests={guests}&lang=en"
AVAILABILITIES_URL = BASE_URL + "availabilities" + QUERY
DETAILS_URL = BASE_URL + "offers" + QUERY


def _format_guests(num_guests: int) -> str:
    return str([[18] * num_guests])


class APIClient:
    """
    MonTMB API client to get availability for a given date.
    """

    def __init__(self, booking_id: int):
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

            # TODO should probably also check min because people can get those rooms.
            return {room["room_id"]: room["occupancy"]["max"] for room in data}

        except requests.RequestException as e:
            print(f"Request error: {e}")

        return {}

    @RateLimiter(max_calls=1, period=5)
    def get_detailed_availability(
        self, date: datetime.date, guest_count: int
    ) -> dict[datetime.date, dict[int, int]]:
        # get "rooms"; for each room "room_id" and "room_free"
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
    ) -> dict[datetime.date, int]:
        """
        Returns the dates with possible availability for the given date range
        and guest count.
        """
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

            return {
                datetime.datetime.strptime(item["date"], "%Y-%m-%d").date()
                for item in data
            }

        except requests.RequestException as e:
            print(f"Request error: {e}")
        except ValueError as e:
            print(f"JSON parsing error: {e}")

        return {}


class BookingSuedTirol:
    """
    Fetcher for BookingSuedTirol systems.

    Logic
    -----
    # TODO

    Notes
    -----
    Pretty hard rate limits.
    """

    def __init__(self, booking_id: int):
        self._booking_id = booking_id
        self._client = APIClient(booking_id)

    def get_availability(
        self, start: datetime.date, end: datetime.date
    ) -> dict[datetime.date, int]:
        availability = {}
        room_types = self._client.get_room_types()

        check = defaultdict(list)
        for num_guests in range(1, 5):
            dates = self._client.get_global_availability(
                start, end, num_guests
            )
            for date in dates:
                check[date].append(num_guests)

        for date in date_range(start, end):
            rooms = {}  # room_id: num_rooms_available
            for num_guests in check[date]:
                rooms |= self._client.get_detailed_availability(
                    date, num_guests
                )

            rooms_ = {
                room_types[k]: v for k, v in rooms.items()
            }  # room_size: num_rooms_available
            num_available = sum(k * v for k, v in rooms_.items())  # total beds
            availability[date] = {
                "num_available": num_available,
                "rooms": rooms_,
            }

        return availability


if __name__ == "__main__":
    # booking_id = 10716
    booking_id = 13308
    booking_id = 10716
    fetcher = BookingSuedTirol(booking_id)
    # data = fetcher.get_rooms()
    client = APIClient(booking_id)
    start = datetime.datetime(2024, 9, 10).date()
    end = start + timedelta(days=30)
    data = fetcher.get_availability(start, end)
