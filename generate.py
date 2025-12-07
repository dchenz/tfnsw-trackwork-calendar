import os
import sys
from typing import NotRequired, TypedDict

import requests

ENV_TFNSW_OPENDATA_API_KEY = "TFNSW_OPENDATA_API_KEY"

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


if __name__ == "__main__":
    alerts = fetchAlerts(MODE_SYDNEY_TRAINS)
    print(alerts)
