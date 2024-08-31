import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .AvailabilityFetcher import AvailabilityFetcher, Result

_headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0",  # noqa
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "X-Requested-With": "XMLHttpRequest",
    "DNT": "1",
    "Connection": "keep-alive",
    "Referer": "https://rifugioaverau.bukly.com/",
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


def month_abbrev_to_number(abbrev):
    datetime_object = datetime.datetime.strptime(abbrev, "%b")
    return datetime_object.month


class APIClient:
    def __init__(self, booking_id: str):
        self.booking_id = booking_id  # slug

    def get_month_availability(
        self, date: datetime.date
    ) -> list[datetime.date]:
        """
        Fetches the availability for a specific month from the API.

        Returns
        -------
        list[datetime.date]
            List of dates with availability.
        """
        url = URL.format(slug=self.booking_id, date=date)

        try:
            response = requests.get(url, headers=_headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            table = soup.find("table")

            # Extract the header information
            headers = []
            for th in table.find_all("th"):
                day = th.find("span", class_="day")
                month = th.find("span", class_="month")
                year = date.year
                if day:
                    headers.append(
                        datetime.date(
                            year,
                            month_abbrev_to_number(month.text),
                            int(day.text),
                        )
                    )

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

    def get_detailed_availability(self, date: datetime.date):
        end = date + datetime.timedelta(days=1)
        url = "https://rifugioaverau.bukly.com/en-us/hotel/{date:%Y-%m-%d}/{end:%Y-%m-%d}/"
        url = "https://scotoni.bukly.com/en-us/hotel/{date:%Y-%m-%d}/{end:%Y-%m-%d}/"
        url = url.format(date=date, end=end)
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Find all divs that appear to contain hotel room information
        hotel_rooms = soup.find_all("div", {"class": "hotel-room__sub"})

        for hotel_room in hotel_rooms:
            # Get the hotel room name
            title = hotel_room.find(
                "h4", {"class": "hotel-room__sub-title"}
            ).text.strip()

            # Locate the number of beds from hidden input elements
            beds_input = hotel_room.find(
                "input", {"name": lambda x: x and "beds" in x}
            )
            beds = beds_input.get("value") if beds_input else "Not specified"

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
                qty = "Not specified"

            print(f"Room Title: {title}")
            print(f"Number of Beds: {beds}")
            print(f"Available Quantities: {qty}")
            print("-" * 40)


class Bulky(AvailabilityFetcher):
    def __init__(self, booking_id: str):
        self._booking_id = booking_id
        self._client = APIClient(booking_id)

    def get_availability(
        self,
        start: datetime.date,
        end: datetime.date,
        cache: Optional[dict[datetime.date, Result]] = None,
    ) -> dict[datetime.date, Result]:
        availability: dict[datetime.date, Result] = {}  # TODO
        return availability


if __name__ == "__main__":
    client = APIClient("rifugioaverau")
    client = APIClient("scotoni")
    start = datetime.date(2024, 10, 2)
    client.get_month_availability(start)
    client.get_detailed_availability(start)
