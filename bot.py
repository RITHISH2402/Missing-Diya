
import json
import os
from urllib.parse import urlparse

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

BOT_TIMEOUT_MS = 8000
APP_PORT = int(os.environ.get("PORT", "5000"))
BASE_URL = f"http://127.0.0.1:{APP_PORT}"


def is_allowed_challenge_url(url):
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "http"
            and parsed.hostname == "127.0.0.1"
            and parsed.port == APP_PORT
            and parsed.username is None
            and parsed.password is None
            and parsed.path == "/search"
        )
    except (ValueError, TypeError):
        return False


def handle_allowed_request(route):
    request = route.request

    try:
        parsed = urlparse(request.url)
        same_origin = (
            parsed.scheme == "http"
            and parsed.hostname == "127.0.0.1"
            and parsed.port == APP_PORT
            and parsed.username is None
            and parsed.password is None
        )

        is_search = (
            same_origin
            and parsed.path == "/search"
            and request.method == "GET"
        )

        is_callback = (
            same_origin
            and parsed.path == "/challenge/callback"
            and request.method == "POST"
        )

        if is_search or is_callback:
            route.continue_()
        else:
            route.abort()

    except (ValueError, TypeError):
        route.abort()


def visit_as_archivist(url, token=None):
    if not is_allowed_challenge_url(url) or not token:
        return {
            "ok": False,
            "message": "The archivist only visits valid archive searches.",
        }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)

            try:
                context = browser.new_context(
                    accept_downloads=False,
                    service_workers="block",
                )

                context.route("**/*", handle_allowed_request)
                page = context.new_page()

                page.add_init_script(
                    script=(
                        "Object.defineProperty(window, "
                        "'__ARCHIVIST_TOKEN__', {value: "
                        + json.dumps(token)
                        + ", configurable: false});"
                    )
                )

                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=BOT_TIMEOUT_MS,
                )

                if response is None:
                    return {
                        "ok": False,
                        "message": "The archive returned no response.",
                    }

                page.wait_for_timeout(1500)

                return {
                    "ok": True,
                    "message": "The archivist has inspected the archive.",
                    "status_code": response.status,
                }

            finally:
                browser.close()

    except PlaywrightTimeoutError:
        return {
            "ok": False,
            "message": "The archive took too long to respond.",
        }

    except Exception as exc:
        print(f"Archivist error: {type(exc).__name__}: {exc}")
        return {
            "ok": False,
            "message": "The archivist could not inspect that record.",
        }


if __name__ == "__main__":
    print("Testing archivist module; submit a report through the app.")

