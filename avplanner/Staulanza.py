import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .AvailabilityFetcher import AvailabilityFetcher, Result
from .utils import date_range

QUERY = "?prm={month}&chm=0#TabDisp"
DETAIL_SUFFIX = "Booking/EN/prenotazione1.php"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",
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


class APIClient:
    def __init__(self, base_url: str):
        self._base_url = base_url

    def get_month_availability(self, date: datetime.date) -> dict:
        """
        Fetches the availability for a specific month from the API.
        """
        url = (self._base_url + QUERY).format(month=date.month)

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # Extracts the dates with green availability.
            div_disponibilita = soup.find("div", class_="disponibilita")
            libero_dates = div_disponibilita.find_all("td", class_="libero")
            dates_libero = [date.text for date in libero_dates]

            # Returns the list of dates with green availability.
            return [
                date.replace(day=int(date_str)) for date_str in dates_libero
            ]

        except Exception as e:
            print(e)
            return {}

    def get_detailed_availability(self, date: datetime.date):
        """
        Fetches the detailed availability for a specific date from the API.
        """
        if "tissi" in self._base_url:
            # edge case for tissi hut
            SUFFIX = "EN/prenotazione1.php"
        else:
            SUFFIX = DETAIL_SUFFIX

        url = _get_base(self._base_url) + SUFFIX

        end = date + datetime.timedelta(days=1)
        payload = {
            "arrivo": date.strftime("%d-%m-%Y"),
            "partenza": end.strftime("%d-%m-%Y"),
            "persone": "1",  # TODO dormitories max value is limited by this
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

            # TODO figure out how to get the max value for each room
            # for room_name, max_value in rooms.items():
            #     print(f"Room: {room_name}, Maximum Beds: {max_value}")

            # TODO need to try max value by making posts for larger values
            # Start with one, keep increasing.
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
        cache = cache or {}
        for date in date_range(start, end):
            if date in total:
                detail = self._client.get_detailed_availability(date)
                num_available = sum(detail.values())
            else:
                detail = {}
                num_available = 0

            availability[date] = {
                "num_available": num_available,
                "rooms": detail,
            }

        return availability


def main():
    pass


def _get_base(url: str) -> str:
    if ".com" in url:
        return url.split(".com")[0] + ".com/"
    elif ".it" in url:
        return url.split(".it")[0] + ".it/"
    else:
        raise ValueError("Invalid URL.")


if __name__ == "__main__":
    # base_url = "https://rifugiolagazuoi.com/EN/disponibilita.php"
    base_url = "https://www.staulanza.it/Booking/EN/disponibilita.php"
    base_url = "https://www.rifugiocoldai.com/Booking/index_en.php"
    base_url = "https://www.crodadalago.it/Booking/IT/disponibilita.php"
    base_url = "https://www.rifugiotissi.com/EN/disponibilita.php"
    detail_suffix = "EN/prenotazione1.php"
    base_url = "https://rifugiovazzoler.com/Booking/EN/disponibilita.php"
    client = APIClient(base_url)
    # https://www.rifugiotissi.com/EN/prenotazione1.php
    print(client.get_detailed_availability(datetime.date(2024, 9, 17)))
