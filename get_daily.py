import csv
import datetime
from dataclasses import dataclass

from avplanner import AvailabilityFetcher, BookingSuedTirol, Bulky, Staulanza


@dataclass
class Hut:
    name: str
    booking_type: str
    booking_id: str


@dataclass
class Availability:
    hut_name: str
    booking_date: datetime.date
    num_available: int
    rooms: dict[str, int]


def _get_fetcher(hut: Hut) -> AvailabilityFetcher:
    if hut.booking_type == "bulky":
        return Bulky(hut.booking_id)
    elif hut.booking_type == "staulanza":
        return Staulanza(hut.booking_id)
    elif hut.booking_type == "bookingsuedtirol":
        return BookingSuedTirol(hut.booking_id)
    else:
        raise ValueError(f"Unknown hut: {hut.name}")


def load_huts():
    LOC = "data/huts.csv"
    huts = []
    with open(LOC, "r") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("booking_id") == "":
                continue

            hut = Hut(
                name=row["name"],
                booking_type=row["booking_type"],
                booking_id=row["booking_id"],
            )
            huts.append(hut)

    return huts


def get_daily(cache=None):
    """
    Get the availability for all huts.
    """
    start_date = datetime.date(2024, 9, 15)
    end_date = datetime.date(2024, 9, 26)

    for hut in load_huts():
        if hut.booking_type != "staulanza":
            continue

        fetcher = _get_fetcher(hut)
        cache = cache if cache else {}
        results = fetcher.get_availability(start_date, end_date, cache)

        for booking_date, result in results.items():
            num_available = result["num_available"]
            rooms = result["rooms"]
            availability = Availability(
                hut.name, booking_date, num_available, rooms
            )

            print(availability)

    return "done"


if __name__ == "__main__":
    get_daily()
