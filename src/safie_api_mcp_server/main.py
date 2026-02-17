import os
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import httpx
from mcp.server.fastmcp import FastMCP, Image
from pydantic import AwareDatetime, BaseModel, Field

BASE_URL = "https://openapi.safie.link"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
API_KEY = os.environ.get("API_KEY")

mcp = FastMCP("Safie API")


class DeviceSetting(BaseModel):
    name: str = Field(None, description="ユーザーが設定したデバイスの名称")


class DeviceModel(BaseModel):
    description: str = Field(description="デバイスのモデル名")


class DeviceStatus(BaseModel):
    video_streaming: bool = Field(description="デバイスが現在、接続中であるか否か")


class DeviceInfo(BaseModel):
    device_id: str = Field(description="デバイスID")
    serial: str = Field(description="シリアル番号")
    setting: DeviceSetting = Field(description="デバイスの設定情報")
    status: DeviceStatus = Field(description="デバイスのステータス")
    model: DeviceModel = Field(description="デバイスのモデル情報")


class DevicesMediaInfo(BaseModel):
    timestamp: datetime = Field(description="メディア開始日時")
    duration: int = Field(description="メディア記録時間 [ミリ秒]")


class GPSStatus(StrEnum):
    ACTIVE = "active"
    ON = "on"
    OFF = "off"


class Location(BaseModel):
    latitude: float | None = Field(
        None, description="緯度（位置情報が取得できない場合はnull）"
    )
    longitude: float | None = Field(
        None, description="経度（位置情報が取得できない場合はnull）"
    )


class DeviceLocation(BaseModel):
    gps_status: GPSStatus = Field(
        description="GPSの状態。off: GPS機能が無効化されている、on: GPS機能が有効化されているが、位置を測位できていない、active: GPS機能が有効化されており、位置を測位できている",
    )
    location: Location = Field(description="位置情報")


class StandardEventType(StrEnum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    MOTION = "motion"
    SOUND = "sound"
    PERSON = "person"


class DevicesStandardEventsInfo(BaseModel):
    type: StandardEventType = Field(description="イベント種別")
    timestamp: datetime = Field(description="イベント登録時刻")

class DeveicesAreaCountSettingsInfo(BaseModel):
    setting_id: int = Field(description="検知エリアID")
    setting_name: str = Field(description="検知エリア名")

class DeveicesAreaCountResulsInfo(BaseModel):
    detected_on: datetime = Field(description="検知時刻")
    setting_id: int = Field(description="検知エリアID")
    setting_name: str = Field(description="検知エリア名")
    stay_time: int = Field(description="滞在時間")

class DeveicesLineCountSettingsInfo(BaseModel):
    setting_id: int = Field(description="検知ラインID")
    setting_name: str = Field(description="検知ライン名")
    direction: str = Field(description="通過方向")

class DeveicesLineCountResulsInfo(BaseModel):
    detected_on: datetime = Field(description="検知時刻")
    setting_id: int = Field(description="検知ラインID")
    setting_name: str = Field(description="検知ライン名")
    direction: str = Field(description="通過方向")

class DeveicesPeopleDetectionSettingsInfo(BaseModel):
    setting_id: int = Field(description="検知エリアID")
    setting_name: str = Field(description="検知エリア名")

class DeveicesPeopleDetectionResulsInfo(BaseModel):
    detected_on: datetime = Field(description="検知時刻")
    setting_id: int = Field(description="検知ラインID")
    setting_name: str = Field(description="検知ライン名")

def _get_auth_headers():
    if ACCESS_TOKEN is not None:
        return {"Authorization": "Bearer " + ACCESS_TOKEN}
    elif API_KEY is not None:
        return {"Safie-API-Key": API_KEY}

    raise ValueError("env ACCESS_TOKEN or API_KEY must be set")


@mcp.tool()
def list_devices(
    item_id: int | None = Field(
        description="デバイスに設定されているオプションによる絞り込み", default=None
    ),
) -> list[DeviceInfo]:
    """
    アクセス権限のあるデバイスの一覧を取得します
    """
    devices, offset, limit, has_next = [], 0, 100, True
    while has_next:
        r = httpx.get(
            url=BASE_URL + "/v2/devices",
            headers=_get_auth_headers(),
            params={
                "offset": offset,
                "limit": limit,
                **({"item_id": item_id} if item_id is not None else {}),
            },
        )
        r.raise_for_status()
        response = r.json()
        has_next = response["has_next"]
        offset += response["count"]

        devices += [DeviceInfo.model_validate(d) for d in response["list"]]

    return devices


@mcp.tool()
def get_device_image(
    device_id: str = Field(description="デバイスID"),
    timestamp: AwareDatetime | None = Field(
        description="取得したい画像の時刻 (タイムゾーン情報を含める必要がある)",
        default=None,
    ),
) -> Image:
    """
    指定されたデバイスから画像を取得します
    timestampを指定しない場合、API実行時点の最新画像が取得できます
    """
    r = httpx.get(
        url=BASE_URL + f"/v2/devices/{device_id}/image",
        headers=_get_auth_headers(),
        params={"timestamp": timestamp.isoformat()} if timestamp is not None else {},
    )
    r.raise_for_status()
    return Image(data=r.content, format="jpeg")


@mcp.tool()
def list_device_media(
    device_id: str = Field(description="デバイスID"),
    start: AwareDatetime = Field(
        description="取得範囲の開始時間 (タイムゾーン情報を含める必要がある)"
    ),
    end: AwareDatetime = Field(
        description="取得範囲の終了時間 (タイムゾーン情報を含める必要がある. また現在時刻から1分以上前の時刻である必要がある)"
    ),
) -> list[DevicesMediaInfo]:
    """
    指定されたデバイスで録画されている映像（メディア）の一覧を取得します
    timestampを指定しない場合、API実行時点の最新画像が取得できます

    制限:
    - start/endの取得最大範囲は 1日（86400秒）です
    """
    if not start.tzinfo == end.tzinfo:
        raise ValueError("start and end must be in the same timezone")

    current_timestamp = datetime.now(tz=timezone.utc)
    if end + timedelta(minutes=1) > current_timestamp:
        raise ValueError(
            "The end time must be at least 1 minute before the current time"
        )

    duration = (end - start).total_seconds()
    if (duration < 60) or (86400 < duration):
        raise ValueError("The duration must be between 1 minute and 1 day")

    r = httpx.get(
        url=BASE_URL + f"/v2/devices/{device_id}/media",
        headers=_get_auth_headers(),
        params={"start": start.isoformat(), "end": end.isoformat()},
    )
    r.raise_for_status()
    return [DevicesMediaInfo.model_validate(m) for m in r.json()["list"]]


@mcp.tool()
def get_device_location(
    device_id: str = Field(description="デバイスID"),
) -> DeviceLocation:
    """
    指定されたデバイスの現在のGPS位置情報を取得します。GPSに対応していないデバイスでは利用できません
    デバイスに手動設定された位置情報を取得することはできません
    """
    r = httpx.get(
        url=BASE_URL + f"/v2/devices/{device_id}/location", headers=_get_auth_headers()
    )
    r.raise_for_status()
    return DeviceLocation.model_validate(r.json())


@mcp.tool()
def get_device_thumbnail(device_id: str = Field(description="デバイスID")) -> Image:
    """
    指定されたデバイスの最新サムネイルを取得します
    """
    r = httpx.get(
        url=BASE_URL + f"/v2/devices/{device_id}/thumbnail",
        headers=_get_auth_headers(),
    )
    r.raise_for_status()
    return Image(data=r.content, format="jpeg")


@mcp.tool()
def list_device_standard_events(
    device_id: str = Field(description="デバイスID"),
    start: AwareDatetime = Field(
        description="取得範囲の開始時間 (タイムゾーン情報を含める必要がある)"
    ),
    end: AwareDatetime = Field(
        description="取得範囲の終了時間 (タイムゾーン情報を含める必要がある. また現在時刻から1分以上前の時刻である必要がある)"
    ),
    event_types: list[StandardEventType] | None = Field(
        description="取得するイベントの種類", default=None
    ),
) -> list[DevicesStandardEventsInfo]:
    """
    指定されたデバイスの標準イベント情報一覧を取得します

    「標準イベント」とは以下の5つのイベントの総称です
    - 接続検知
    - 切断検知
    - モーション検知
    - サウンド検知
    - 人検知

    制限:
    - start/endの取得最大範囲は 1日（86400秒）です
    """
    if not start.tzinfo == end.tzinfo:
        raise ValueError("start and end must be in the same timezone")

    current_timestamp = datetime.now(tz=timezone.utc)
    if end + timedelta(minutes=1) > current_timestamp:
        raise ValueError(
            "The end time must be at least 1 minute before the current time"
        )

    duration = (end - start).total_seconds()
    if (duration < 60) or (86400 < duration):
        raise ValueError("The duration must be between 1 minute and 1 day")

    events, offset, limit, has_next = [], 0, 100, True
    while has_next:
        r = httpx.get(
            url=BASE_URL + f"/v2/devices/{device_id}/standard_events",
            headers=_get_auth_headers(),
            params={
                "start": start.isoformat(),
                "end": end.isoformat(),
                "offset": offset,
                "limit": limit,
                **({"event_types": event_types} if event_types is not None else {}),
            },
        )
        r.raise_for_status()
        response = r.json()
        has_next = len(response["list"]) == limit
        offset += len(response["list"])

        events += [
            DevicesStandardEventsInfo.model_validate(e) for e in response["list"]
        ]

    return events

@mcp.tool()
def get_device_area_count_settings(
    device_id: str = Field(description="デバイスID"),
) -> list[DeveicesAreaCountSettingsInfo]:
    """
    指定されたデバイスの立ち入りカウントのエリア設定一覧を取得します
    """

    results, offset, limit, has_next = [], 0, 100, True
    while has_next:
        r = httpx.get(
            url=BASE_URL + f"/v2/aiapp/people_count/devices/{device_id}/area_count/settings",
            headers=_get_auth_headers(),
            params={
                "offset": offset,
                "limit": limit
            },
        )
        r.raise_for_status()
        response = r.json()
        has_next = len(response["list"]) == limit
        offset += len(response["list"])

        results += [
            DeveicesAreaCountSettingsInfo.model_validate(e) for e in response["list"]
        ]

    return results


@mcp.tool()
def get_device_area_count_result(
    device_id: str = Field(description="デバイスID"),
    start: AwareDatetime = Field(
        description="取得範囲の開始時間 (タイムゾーン情報を含める必要がある)"
    ),
    end: AwareDatetime = Field(
        description="取得範囲の終了時間 (タイムゾーン情報を含める必要がある. また現在時刻から1分以上前の時刻である必要がある)"
    ),
) -> list[DeveicesAreaCountResulsInfo]:
    """
    指定されたデバイスの立ち入りカウント結果を取得します

    制限:
    - start/endの取得最大範囲は 1日（86400秒）です
    """
    if not start.tzinfo == end.tzinfo:
        raise ValueError("start and end must be in the same timezone")

    current_timestamp = datetime.now(tz=timezone.utc)
    if end + timedelta(minutes=1) > current_timestamp:
        raise ValueError(
            "The end time must be at least 1 minute before the current time"
        )

    duration = (end - start).total_seconds()
    if (duration < 60) or (86400 < duration):
        raise ValueError("The duration must be between 1 minute and 1 day")

    results, offset, limit, has_next = [], 0, 100, True
    while has_next:
        r = httpx.get(
            url=BASE_URL + f"/v2/aiapp/people_count/devices/{device_id}/area_count/results",
            headers=_get_auth_headers(),
            params={
                "start": start.isoformat(),
                "end": end.isoformat(),
                "offset": offset,
                "limit": limit
            },
        )
        r.raise_for_status()
        response = r.json()
        has_next = len(response["list"]) == limit
        offset += len(response["list"])

        results += [
            DeveicesAreaCountResulsInfo.model_validate(e) for e in response["list"]
        ]

    return results

@mcp.tool()
def get_device_line_count_settings(
    device_id: str = Field(description="デバイスID"),
) -> list[DeveicesLineCountSettingsInfo]:
    """
    指定されたデバイスの通過人数カウントのエリア設定一覧を取得します
    """

    results, offset, limit, has_next = [], 0, 100, True
    while has_next:
        r = httpx.get(
            url=BASE_URL + f"/v2/aiapp/people_count/devices/{device_id}/line_count/settings",
            headers=_get_auth_headers(),
            params={
                "offset": offset,
                "limit": limit
            },
        )
        r.raise_for_status()
        response = r.json()
        has_next = len(response["list"]) == limit
        offset += len(response["list"])

        results += [
            DeveicesLineCountSettingsInfo.model_validate(e) for e in response["list"]
        ]

    return results

@mcp.tool()
def get_device_line_count_result(
    device_id: str = Field(description="デバイスID"),
    start: AwareDatetime = Field(
        description="取得範囲の開始時間 (タイムゾーン情報を含める必要がある)"
    ),
    end: AwareDatetime = Field(
        description="取得範囲の終了時間 (タイムゾーン情報を含める必要がある. また現在時刻から1分以上前の時刻である必要がある)"
    ),
) -> list[DeveicesLineCountResulsInfo]:
    """
    指定されたデバイスの通過人数カウント結果を取得します

    制限:
    - start/endの取得最大範囲は 1日（86400秒）です
    """
    if not start.tzinfo == end.tzinfo:
        raise ValueError("start and end must be in the same timezone")

    current_timestamp = datetime.now(tz=timezone.utc)
    if end + timedelta(minutes=1) > current_timestamp:
        raise ValueError(
            "The end time must be at least 1 minute before the current time"
        )

    duration = (end - start).total_seconds()
    if (duration < 60) or (86400 < duration):
        raise ValueError("The duration must be between 1 minute and 1 day")

    results, offset, limit, has_next = [], 0, 100, True
    while has_next:
        r = httpx.get(
            url=BASE_URL + f"/v2/aiapp/people_count/devices/{device_id}/line_count/results",
            headers=_get_auth_headers(),
            params={
                "start": start.isoformat(),
                "end": end.isoformat(),
                "offset": offset,
                "limit": limit
            },
        )
        r.raise_for_status()
        response = r.json()
        has_next = len(response["list"]) == limit
        offset += len(response["list"])

        results += [
            DeveicesLineCountResulsInfo.model_validate(e) for e in response["list"]
        ]

    return results

@mcp.tool()
def get_device_people_detection_settings(
    device_id: str = Field(description="デバイスID"),
) -> list[DeveicesPeopleDetectionSettingsInfo]:
    """
    指定されたデバイスの立ち入り人検知のエリア設定一覧を取得します
    """

    results, offset, limit, has_next = [], 0, 100, True
    while has_next:
        r = httpx.get(
            url=BASE_URL + f"/v2/aiapp/people_count/devices/{device_id}/people_detection/settings",
            headers=_get_auth_headers(),
            params={
                "offset": offset,
                "limit": limit
            },
        )
        r.raise_for_status()
        response = r.json()
        has_next = len(response["list"]) == limit
        offset += len(response["list"])

        results += [
            DeveicesPeopleDetectionSettingsInfo.model_validate(e) for e in response["list"]
        ]

    return results


@mcp.tool()
def get_device_people_detection_result(
    device_id: str = Field(description="デバイスID"),
    start: AwareDatetime = Field(
        description="取得範囲の開始時間 (タイムゾーン情報を含める必要がある)"
    ),
    end: AwareDatetime = Field(
        description="取得範囲の終了時間 (タイムゾーン情報を含める必要がある. また現在時刻から1分以上前の時刻である必要がある)"
    ),
) -> list[DeveicesPeopleDetectionResulsInfo]:
    """
    指定されたデバイスの立ち入り人検知結果を取得します

    制限:
    - start/endの取得最大範囲は 1日（86400秒）です
    """
    if not start.tzinfo == end.tzinfo:
        raise ValueError("start and end must be in the same timezone")

    current_timestamp = datetime.now(tz=timezone.utc)
    if end + timedelta(minutes=1) > current_timestamp:
        raise ValueError(
            "The end time must be at least 1 minute before the current time"
        )

    duration = (end - start).total_seconds()
    if (duration < 60) or (86400 < duration):
        raise ValueError("The duration must be between 1 minute and 1 day")

    results, offset, limit, has_next = [], 0, 100, True
    while has_next:
        r = httpx.get(
            url=BASE_URL + f"/v2/aiapp/people_count/devices/{device_id}/people_detection/results",
            headers=_get_auth_headers(),
            params={
                "start": start.isoformat(),
                "end": end.isoformat(),
                "offset": offset,
                "limit": limit
            },
        )
        r.raise_for_status()
        response = r.json()
        has_next = len(response["list"]) == limit
        offset += len(response["list"])

        results += [
            DeveicesPeopleDetectionResulsInfo.model_validate(e) for e in response["list"]
        ]

    return results


def run():
    if ACCESS_TOKEN is None and API_KEY is None:
        raise ValueError("env ACCESS_TOKEN or API_KEY must be set")

    mcp.run()
