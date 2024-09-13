import datetime
from collections import defaultdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .AvailabilityFetcher import AvailabilityFetcher, Result
from .utils import date_range

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0",  # noqa
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "X-Requested-With": "XMLHttpRequest",
    "DNT": "1",
    "Connection": "keep-alive",
    "Referer": "https://{slug}.bukly.com/",
    "Cookie": "BUKLY=77o1lliukj9fb3hh92h7rh5pc5",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Priority": "u=0",
}


URL = (
    "https://{slug}.bukly.com/en-us/hotels/ajax_widget?slug={slug}"
    "&day={date:%Y-%m-%d}&dir=next"
)
DETAIL_URL = (
    "https://{slug}.bukly.com/en-us/hotel/{date:%Y-%m-%d}/{end:%Y-%m-%d}/"
)


def month_abbrev_to_number(abbrev):
    datetime_object = datetime.datetime.strptime(abbrev, "%b")
    return datetime_object.month


class APIClient:
    def __init__(self, booking_id: str):
        self.booking_id = booking_id  # slug

    def get_half_month_availability(
        self, date: datetime.date
    ) -> list[datetime.date]:
        """
        Fetches the half month availability for a date from the API.

        Returns
        -------
        list[datetime.date]
            List of dates with availability.
        """
        url = URL.format(slug=self.booking_id, date=date)

        try:
            _headers = _HEADERS.copy()
            _headers["Referer"] = _headers["Referer"].format(
                slug=self.booking_id
            )
            response = requests.get(url, headers=_headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            table = soup.find("table")

            # Extract the header information
            headers = []
            for th in table.find_all("th"):
                year = date.year
                month_abbrev = th.find("span", class_="month")
                day = th.find("span", class_="day")
                if day:
                    month = month_abbrev_to_number(month_abbrev.text)
                    date = datetime.date(year, month, int(day.text))
                    headers.append(date)

            # Extract the rows
            rows = []
            for tr in table.find_all("tr")[1:]:  # Skip the header row
                cells = tr.find_all("td")
                row = [cell.text.strip() for cell in cells]
                row = row[1:]  # skip name
                rows.append(row)

            candidate = []
            for datum, *vals in zip(headers, *rows):
                if any(vals):
                    candidate.append(datum)

            return candidate

        except Exception as e:
            print(e)
            pass

        return []

    def get_detailed_availability(self, date: datetime.date) -> dict[int, int]:
        end = date + datetime.timedelta(days=1)
        url = DETAIL_URL.format(slug=self.booking_id, date=date, end=end)
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Find all divs that appear to contain hotel room information
        result: dict[int, int] = defaultdict(int)
        hotel_rooms = soup.find_all("div", {"class": "hotel-room__sub"})

        for hotel_room in hotel_rooms:
            _ = hotel_room.find(
                "h4", {"class": "hotel-room__sub-title"}
            ).text.strip()  # room name

            # Locate the number of beds from hidden input elements
            beds_input = hotel_room.find(
                "input", {"name": lambda x: x and "beds" in x}
            )
            max_beds = (
                beds_input.get("value") if beds_input else "Not specified"
            )

            # Locate the select element for room quantity
            qty_select = hotel_room.find(
                "select", {"name": lambda x: x and "qty" in x}
            )
            if qty_select:
                # Extract available quantities from option elements
                quantities = [
                    option.text for option in qty_select.find_all("option")
                ]
                qty = ", ".join(quantities)
            else:
                qty = "0"  # not specified

            # Find the maximum quantity that can be booked.
            max_qty = max([int(char) for char in qty if char.isdigit()])

            if "room" in qty:
                # If the quantity is specified in terms of rooms, we can
                # only book the entire room.
                result[int(max_beds)] += max_qty
            else:
                # Otherwise, we can book individual beds.
                result[1] += max_qty

        return dict(result)


class Bulky(AvailabilityFetcher):
    def __init__(self, booking_id: str):
        self._booking_id = booking_id
        self._client = APIClient(booking_id)

    def _get_total_availability(
        self, start: datetime.date, end: datetime.date
    ) -> list[datetime.date]:
        """
        Gets the total global availability for a given date range. Repeatedly
        calls the global availability API to get the availability for 30 days.

        Returns
        -------
        list[datetime.date]
            A list of dates with availability.
        """
        availability = []
        current = start
        while current <= end:
            data = self._client.get_half_month_availability(current)
            availability.extend(data)
            current += datetime.timedelta(days=15)

        return availability

    def get_availability(
        self,
        start: datetime.date,
        end: datetime.date,
        cache: Optional[dict[datetime.date, Result]] = None,
    ) -> dict[datetime.date, Result]:
        availability: dict[datetime.date, Result] = {}
        total = self._get_total_availability(start, end)

        for date in date_range(start, end):
            if date in total:
                rooms = self._client.get_detailed_availability(date)
            else:
                rooms = {}

            num_available = sum(k * v for k, v in rooms.items())
            availability[date] = Result(
                {
                    "num_available": num_available,
                    "rooms": rooms,
                }
            )

        return availability


if __name__ == "__main__":
    fetcher = Bulky("scotoni")
    start = datetime.date(2024, 9, 14)
    end = datetime.date(2024, 10, 15)
    data = fetcher.get_availability(start, end)
