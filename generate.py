import os
import re
import sys
from datetime import datetime
from typing import NotRequired, TypedDict

import pytz
import requests
from ics import Calendar, Event

ENV_TFNSW_OPENDATA_API_KEY = "TFNSW_OPENDATA_API_KEY"

SYDNEY_TIME = pytz.timezone("Australia/Sydney")

MODE_BUSES = "buses"
MODE_FERRIES = "ferries"
MODE_LIGHT_RAIL = "lightrail"
MODE_METRO = "metro"
MODE_NSW_TRAINS = "nswtrains"
MODE_REGIONAL_BUSES = "regionbuses"
MODE_SYDNEY_TRAINS = "sydneytrains"


class Translation(TypedDict):
    text: str
    language: str


class ActivePeriod(TypedDict):
    start: str
    end: NotRequired[str]


class InformedEntity(TypedDict):
    agencyId: str
    routeId: str
    directionId: int


class TextWithTranslation(TypedDict):
    translation: list[Translation]


class Alert(TypedDict):
    activePeriod: list[ActivePeriod]
    informedEntity: list[InformedEntity]
    cause: str
    effect: str
    headerText: TextWithTranslation
    descriptionText: TextWithTranslation
    url: TextWithTranslation


class AlertEntity(TypedDict):
    id: str
    alert: Alert


class Header(TypedDict):
    gtfsRealtimeVersion: str
    incrementality: str
    timestamp: int


class GetAlertsResponse(TypedDict):
    header: Header
    entity: list[AlertEntity]


ALERTS_API = "https://api.transport.nsw.gov.au/v2/gtfs/alerts"


def fetchAlerts(transportType: str) -> GetAlertsResponse:
    apiKey = os.getenv(ENV_TFNSW_OPENDATA_API_KEY)
    if not apiKey:
        raise Exception(f"{ENV_TFNSW_OPENDATA_API_KEY} is missing")
    try:
        url = f"{ALERTS_API}/{transportType}?format=json"
        response = requests.get(url, headers={"authorization": f"apikey {apiKey}"})
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        print(response.text, file=sys.stderr)
        raise


def getEnglishText(text: TextWithTranslation) -> str | None:
    for translation in text["translation"]:
        if translation["language"] == "en":
            return translation["text"]


def getActivePeriod(alert: Alert) -> tuple[datetime, datetime] | None:
    for period in alert["activePeriod"]:
        start = period["start"]
        end = period.get("end", start)
        activePeriodStart = datetime.fromtimestamp(int(start)).astimezone(SYDNEY_TIME)
        activePeriodEnd = datetime.fromtimestamp(int(end)).astimezone(SYDNEY_TIME)
        return activePeriodStart, activePeriodEnd


def getDatesFromDescription(alert: Alert) -> tuple[datetime, datetime] | None:
    descriptionText = getEnglishText(alert["descriptionText"])
    if not descriptionText:
        return None

    # Regex to parse dates like "Saturday 6 December" or "Saturday 6 and Sunday 7 December"
    pattern = (
        r"(Saturday|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday)\s+"
        + r"(\d{1,2})"
        + r"(?:\s*(?:and|&)\s*"
        + r"(Saturday|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday)?\s*"
        + r"(\d{1,2})?)?\s*"
        + r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    )
    matches = re.findall(pattern, descriptionText)
    if not matches:
        return None

    dates: list[datetime] = []

    for m in matches:
        weekday1, day1, weekday2, day2, month = m

        day1 = int(day1)
        year = datetime.now().year
        dt1 = datetime.strptime(f"{day1} {month} {year}", "%d %B %Y")
        dt1 = SYDNEY_TIME.localize(dt1)
        dates.append(dt1)

        if weekday2 and day2:
            day2 = int(day2)
            dt2 = datetime.strptime(f"{day2} {month} {year}", "%d %B %Y")
            dt2 = SYDNEY_TIME.localize(dt2)
            dates.append(dt2)

    if not dates:
        return None

    return min(dates), max(dates)


def isRelevant(alert: Alert) -> bool:
    return alert["effect"] == "MODIFIED_SERVICE"


def getAffectedRoutes(alert: Alert) -> list[str]:
    routes: set[str] = set()
    for entity in alert["informedEntity"]:
        if "routeId" in entity:
            # Treat route IDs like IWL_2d as IWL, no need to keep the suffix.
            routes.add(entity["routeId"].split("_")[0])
    return list(routes)


def saveCalendarFile(calendar: Calendar, transportMode: str, route: str):
    dirname = transportMode
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", route)
    os.makedirs(dirname, exist_ok=True)
    with open(os.path.join(dirname, filename), "w") as f:
        f.writelines(calendar.serialize_iter())


def logSkippedAlert(entity: AlertEntity):
    headerText = getEnglishText(entity["alert"]["headerText"])
    print(f'Skipped: id={entity["id"]}, headerText="{headerText}"')


def main():
    mode = MODE_SYDNEY_TRAINS
    alertsData = fetchAlerts(mode)
    calendarsByRoute: dict[str, Calendar] = {}

    for entity in alertsData["entity"]:
        alert = entity["alert"]
        if not isRelevant(alert):
            logSkippedAlert(entity)
            continue

        headerText = getEnglishText(alert["headerText"])
        if not headerText:
            logSkippedAlert(entity)
            continue

        timeRange = getDatesFromDescription(alert)
        if not timeRange:
            timeRange = getActivePeriod(alert)
        if not timeRange:
            logSkippedAlert(entity)
            continue

        event = Event()
        event.uid = entity["id"]
        event.name = headerText
        event.begin, event.end = timeRange
        event.description = getEnglishText(alert["descriptionText"])
        event.location = getEnglishText(alert["url"])

        for route in getAffectedRoutes(alert):
            if route not in calendarsByRoute:
                calendarsByRoute[route] = Calendar()
            calendarsByRoute[route].events.add(event)

    for route, calendar in calendarsByRoute.items():
        saveCalendarFile(calendar, mode, route)


if __name__ == "__main__":
    main()
