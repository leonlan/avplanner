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
    fetch_date: datetime.date
    booking_date: datetime.date
    num_available: int
    rooms: dict[int, int]


def _get_fetcher(hut: Hut) -> AvailabilityFetcher:
    match hut.booking_type:
        case "bulky":
            return Bulky(hut.booking_id)
        case "staulanza":
            return Staulanza(hut.booking_id)
        case "bookingsuedtirol":
            return BookingSuedTirol(hut.booking_id)
        case _:
            raise ValueError(f"Unknown hut: {hut.name}")


def load_huts():
    LOC = "data/huts.csv"
    huts = []
    with open(LOC, "r") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["booking_type"] not in [
                "staulanza",
                # "bookingsuedtirol",
            ]:
                continue

            hut = Hut(
                name=row["name"],
                booking_type=row["booking_type"],
                booking_id=row["booking_id"],
            )
            huts.append(hut)

    return huts


def get_daily(start: datetime.date, end: datetime.date, cache=None):
    """
    Get the availability for all huts.
    """
    availabilities = []
    today = datetime.date.today()

    for hut in load_huts():
        fetcher = _get_fetcher(hut)
        cache = cache if cache else {}
        results = fetcher.get_availability(start, end, cache)

        for booking_date, result in results.items():
            num_available = result["num_available"]
            rooms = result["rooms"]
            availabilities.append(
                Availability(
                    hut.name, today, booking_date, num_available, rooms
                )
            )

    return availabilities


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default="data/daily.csv")
    parser.add_argument(
        "--start",
        type=lambda s: datetime.datetime.strptime(s, "%Y-%m-%d").date(),
        required=True,
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end",
        type=lambda s: datetime.datetime.strptime(s, "%Y-%m-%d").date(),
        required=True,
        help="End date in YYYY-MM-DD format",
    )
    args = parser.parse_args()

    availabilities = get_daily(args.start, args.end)
    with open(args.out, "a") as fh:
        writer = csv.DictWriter(fh, fieldnames=Availability.__annotations__)
        for availability in availabilities:
            writer.writerow(availability.__dict__)
