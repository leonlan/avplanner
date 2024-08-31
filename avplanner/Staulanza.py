import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .AvailabilityFetcher import AvailabilityFetcher, Result
from .RateLimiter import RateLimiter
from .utils import date_range

QUERY = "?prm={month}&chm=0#TabDisp"
DETAIL_SUFFIX = "Booking/EN/prenotazione1.php"
HUTS_OTHER_SUFFIX = ["tissi", "lagazuoi"]

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0",  # noqa
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",  # noqa
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
    "TE": "trailers",
}


MAX_ROOMS = 8


class APIClient:
    def __init__(self, calendar_url: str):
        self._calendar_url = calendar_url  # disponibilita.php

    def get_month_availability(
        self, date: datetime.date
    ) -> list[datetime.date]:
        """
        Fetches the availability for a specific month from the API.
        """
        url = (self._calendar_url + QUERY).format(month=date.month)

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # Extracts the dates with green availability.
            div_disponibilita = soup.find("div", class_="disponibilita")
            libero_dates = div_disponibilita.find_all("td", class_="libero")
            avail = [date.text for date in libero_dates]

            # Returns the list of dates with green availability.
            return [date.replace(day=int(date_str)) for date_str in avail]

        except Exception as e:
            print(e)
            return []

    @RateLimiter(max_calls=4, period=1)
    def get_detailed_availability(
        self, date: datetime.date, num_guests: int = 1
    ):
        """
        Fetches the detailed availability for a specific date from the API.
        """
        if any(hut in self._calendar_url for hut in HUTS_OTHER_SUFFIX):
            SUFFIX = "EN/prenotazione1.php"
        else:
            SUFFIX = DETAIL_SUFFIX

        url = _get_base(self._calendar_url) + SUFFIX

        end = date + datetime.timedelta(days=1)
        payload = {
            "arrivo": date.strftime("%d-%m-%Y"),
            "partenza": end.strftime("%d-%m-%Y"),
            "persone": num_guests,
        }

        try:
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            quadro_camere = soup.find_all("div", class_="quadroCamere")
            rooms = {}

            for room in quadro_camere:
                room_name = room.find("p").text.strip()

                if select_element := room.find("select"):
                    options = select_element.find_all("option")
                    max_value = max(int(option["value"]) for option in options)
                    rooms[room_name] = max_value

            return rooms

        except Exception:
            return {}


class Staulanza(AvailabilityFetcher):
    def __init__(self, base_url: str):
        self._base_url = base_url
        self._client = APIClient(base_url)

    def get_availability(
        self,
        start: datetime.date,
        end: datetime.date,
        cache: Optional[dict[datetime.date, Result]] = None,
    ) -> dict[datetime.date, Result]:
        """
        Gets the availability for a given date range.
        """
        availability = {}
        total = self._client.get_month_availability(start)

        for date in date_range(start, end):
            rooms: dict[int, int] = {}
            if date in total:
                # Keep fetching detailed availability until no new data is
                # found, or until the maximum number of rooms is reached.
                for idx in range(1, MAX_ROOMS + 1):
                    res = self._client.get_detailed_availability(date, idx)
                    rooms |= res
                    if not res:  # no new availability
                        break

            # TODO room sizes are not considered but it is not clear how to get
            # them from the API
            num_available = sum(rooms.values())

            availability[date] = Result(
                {
                    "num_available": num_available,
                    "rooms": rooms,
                }
            )

        return availability


def _get_base(url: str) -> str:
    match url:
        case url if ".com" in url:
            return url.split(".com")[0] + ".com/"
        case url if ".it" in url:
            return url.split(".it")[0] + ".it/"
        case _:
            raise ValueError("Invalid URL: does not contain .com or .it")
