# Safie API MCP Server

Safie APIを利用してデバイスの情報取得や操作を行うためのMCP (Model Context Protocol) サーバ

> [!NOTE]
> 本実装はプレビュー版であり一部の機能のみを試験的に提供しています。 サポート対象外となりますのでご了承の上、お使いください。

## Requirements
- Python 3.10+, uv or docker

## Features
### Tools
- list_devices
  - デバイス一覧を取得します
- get_device_image
  - 指定されたデバイスから画像を取得します
- list_device_media
  - 指定されたデバイスで録画されている映像（メディア）の一覧を取得します
- get_device_location
  - 指定されたデバイスの現在のGPS位置情報を取得します
- get_device_thumbnail
  - 指定されたデバイスの最新サムネイルを取得します
- list_device_standard_events
  - 指定されたデバイスの標準イベント情報一覧を取得します

## Configuration

以下の環境変数のどちらかが設定されている必要があります

- `ACCESS_TOKEN`:　Safie Developers OAuth2認証アプリケーションで発行したOAuth2アクセストークン
- `API_KEY`: Safie Developers APIキー認証アプリケーションで発行したAPIキー

両方指定した場合、`ACCESS_TOKEN` が利用されます

## Usage

### With Claude Desktop

#### Using python/uv

Python 3.10+, uvが手元にインストールされている場合は以下の設定を追加することで利用できます

```json
{
  "mcpServers": {
    "Safie API": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "git+https://git@github.com/SafiePublic/safie-api-mcp-server.git",
        "safie-api-mcp-server"
      ],
      "env": {
        "ACCESS_TOKEN": "******"
      }
    }
  }
}
```

#### Using docker

Dockerを用いて利用する場合は、まず以下のようにイメージをビルドします

```shell
$ docker build -t safie-api-mcp-server .
```

その後、以下の設定を追加することで利用できます
```json
{
  "mcpServers": {
    "Safie API": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "ACCESS_TOKEN",
        "-e",
        "API_KEY",
        "safie-api-mcp-server"
      ],
      "env": {
        "ACCESS_TOKEN": "******"
      }
    }
  }
}
```
