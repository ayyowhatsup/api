"""
Main module for the FastAPI application.
"""

import os
from datetime import datetime
from typing import Union

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import HttpUrl, BaseModel
from starlette.requests import Request
import yt_dlp

load_dotenv()

ydl_opts = {
    'skip_download': True,
    'quiet': True,
}

app = FastAPI()

ydl_opts = {
    'skip_download': True,
    'quiet': True,
}

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add TrustedHost middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)


@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    """
    Middleware to validate the presence of an API key in the query parameters.

    Args:
        request (Request): The incoming HTTP request.
        call_next (Callable): The next middleware or route handler to be called.

    Returns:
        Response: The HTTP response from the next middleware or route handler.
    """
    api_key = request.query_params.get("api_key")
    expected_api_keys = os.getenv("ALLOW_API_KEYS", "").split(",")

    if not api_key or api_key not in expected_api_keys:
        return JSONResponse(
            status_code=403,
            content={"message": "Forbidden: Invalid or missing API key",
                     "code": "invalid_api_key"}
        )

    response = await call_next(request)
    return response


class ApiException(Exception):
    """
    Custom exception class for API errors.

    Attributes:
        message (str): Error message.
        code (str): Error code.
        status (int): HTTP status code.
    """

    def __init__(self, data: dict[str, str]):
        self.message = data.get(
            "message") if "message" in data.keys() else "Unexpected error!"
        self.code = data.get("code") if "code" in data.keys(
        ) else 'internal_server_error'
        self.status = data.get("status") if "status" in data.keys() else 500


class URLModel(BaseModel):
    """
    URLModel is a Pydantic model that validates a given URL.

    Attributes:
        url (HttpUrl): A valid HTTP URL.
    """
    url: HttpUrl


@app.get("/v1/yt-dlp")
def get_yt_dlp_download_link(url: Union[HttpUrl, None] = None):
    """
    Extracts the direct download link of a YouTube video using yt-dlp.

    Args:
        url (Union[HttpUrl, None]): The URL of the YouTube video. If None, the function will not process any URL.

    Returns:
        dict: A dictionary containing the direct download link of the video with the key 'url'.
    """

    if not url:
        raise ApiException({"message": "URL is required",
                           "code": "url_required", "status": 400})
    try:
        # Validate URL
        url = str(URLModel(url=url).url)
    except Exception as e:
        raise ApiException(
            {"message": "Invalid URL", "code": "invalid_url", "status": 400}) from e

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url, download=False)
            video_url = info_dict.get('url', '')
            if not video_url:
                raise Exception("No video URL found")

            return {
                "data": {
                    "url": video_url
                },
                "code": "success",
                "message": "Request was successful"
            }
        except Exception as e:
            raise ApiException({
                "message": str(e),
                "code": "video_url_extraction_error",
                "status": 400
            }) from e


@ app.exception_handler(ApiException)
def handle_api_exception(_request, exc: ApiException):
    """
    Handles exceptions raised by the API and returns a JSON response.

    Args:
        _request: The request object (not used in the function but required by the framework).
        exc (ApiException): The exception object containing status, message, and code.

    Returns:
        JSONResponse: A JSON response with the status code, message, and code from the exception.
    """
    return JSONResponse(
        status_code=exc.status,
        content={"message": exc.message, "code": exc.code}
    )


@ app.exception_handler(404)
def handle_404_exception(_request, _exc):
    """
    Handle 404 Not Found exceptions.

    Args:
        _request: The request object that triggered the exception.
        exc: The exception instance.
    """
    raise ApiException({"message": "Resource not found",
                       "code": "not_found", "status": 404})


@app.exception_handler(RequestValidationError)
def handle_validation_error(_request, exc):
    """
    Handles validation errors by returning a JSON response with a 400 status code.

    Args:
        _request: The request object (not used in this function).
        exc: The exception that was raised during validation.
    """
    raise ApiException({"message": str(exc),
                       "code": "bad_request", "status": 400})
