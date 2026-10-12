from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from .core import CONFIG, LIMIT, TEXT_LIMIT, tool, write_bytes


def validate_url(url: str, private: bool = False) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Expected HTTP(S) URL without embedded credentials")
    if not private:
        allowed = CONFIG.get("network_allowed_hosts", [])
        if allowed and parsed.hostname not in allowed:
            raise ValueError("Host is not in network_allowed_hosts")
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Private or reserved network addresses require explicit service configuration")
    return url


def request(method: str, url: str, *, headers=None, body=None, private=False, redirects=False) -> dict:
    current = url
    with httpx.Client(timeout=httpx.Timeout(20, connect=8), trust_env=False) as client:
        for hop in range(6):
            validate_url(current, private)
            with client.stream(method, current, headers=headers, json=body) as response:
                if redirects and response.is_redirect:
                    if hop == 5:
                        raise ValueError("Too many redirects")
                    current = urljoin(current, response.headers["location"])
                    continue
                payload = bytearray()
                for chunk in response.iter_bytes():
                    payload.extend(chunk)
                    if len(payload) > LIMIT:
                        raise ValueError("Response exceeds max_file_bytes")
                return {"status": response.status_code, "url": str(response.url),
                        "content_type": response.headers.get("content-type", ""),
                        "encoding": response.encoding or "utf-8", "bytes": bytes(payload)}
    raise ValueError("Request failed")


@tool("web", network=True)
def web_fetch(url: str, extract_text: bool = True) -> dict:
    """Fetch a public HTTP(S) page, following validated redirects; optionally strip HTML markup."""
    response = request("GET", url, redirects=True, private=bool(CONFIG.get("web_allow_private_network", False)))
    text = response.pop("bytes").decode(response.pop("encoding"), errors="replace")
    if extract_text and "html" in response["content_type"].lower():
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        response["title"] = soup.title.get_text(strip=True) if soup.title else ""
        text = soup.get_text("\n", strip=True)
    return {**response, "text": text[:TEXT_LIMIT], "truncated": len(text) > TEXT_LIMIT}


@tool("web", write=True, network=True)
def web_download(url: str, destination: str, overwrite: bool = False) -> dict:
    """Download a bounded public HTTP(S) response to an explicit allowed file."""
    response = request("GET", url, redirects=True, private=bool(CONFIG.get("web_allow_private_network", False)))
    if not 200 <= response["status"] < 300:
        raise ValueError(f"Download returned HTTP {response['status']}")
    return {**write_bytes(destination, response["bytes"], overwrite), "status": response["status"]}


@tool("integrations")
def services_list() -> dict:
    """List configured REST integrations and whether their token environment variables are available."""
    rows = []
    for name, service in CONFIG.get("services", {}).items():
        token_env = service.get("token_env")
        rows.append({"name": name, "description": service.get("description", ""),
                     "methods": service.get("methods", ["GET"]),
                     "configured": not token_env or bool(os.environ.get(token_env))})
    return {"services": rows}


@tool("integrations", write=True, destructive=True, network=True)
def service_request(service: str, path: str = "", method: str = "GET", body: dict | None = None) -> dict:
    """Call a configured REST service using a relative path and allowed method; credentials stay server-side."""
    settings = CONFIG.get("services", {}).get(service)
    if not settings:
        raise ValueError("Unknown service; add it to settings.json")
    method = method.upper()
    if method not in settings.get("methods", ["GET"]):
        raise ValueError("Method is not enabled for this service")
    if path.startswith(("/", "\\")) or urlsplit(path).scheme or "\\" in path:
        raise ValueError("path must be relative to the configured base URL")
    base = settings["base_url"].rstrip("/") + "/"
    url = urljoin(base, path)
    if (urlsplit(base).scheme, urlsplit(base).netloc) != (urlsplit(url).scheme, urlsplit(url).netloc):
        raise ValueError("Service origin cannot change")
    headers = dict(settings.get("headers", {}))
    token_env = settings.get("token_env")
    if token_env:
        token = os.environ.get(token_env)
        if not token:
            raise ValueError(f"Missing environment variable {token_env}")
        headers[settings.get("token_header", "Authorization")] = settings.get("token_prefix", "Bearer ") + token
    response = request(method, url, headers=headers, body=body,
                       private=bool(settings.get("allow_private_network", False)))
    text = response.pop("bytes").decode(response.pop("encoding"), errors="replace")
    # A service response can echo credentials. Do not return the configured token.
    if token_env:
        text = text.replace(token, "[REDACTED]")
    return {**response, "text": text[:TEXT_LIMIT], "truncated": len(text) > TEXT_LIMIT}
