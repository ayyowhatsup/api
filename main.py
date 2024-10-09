"""
Main module for the FastAPI application.
"""

import logging
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

# # Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# # Middleware to log request and response data


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware function to log details of incoming HTTP requests and their responses.
    Args:
        request (Request): The incoming HTTP request.
        call_next (Callable): The next middleware or route handler to be called.
    Returns:
        Response: The HTTP response from the next middleware or route handler.
    Logs:
        - Timestamp of the request.
        - Client IP address.
        - HTTP method of the request.
        - URL of the request.
        - Query parameters of the request.
        - Status code of the response.
    """
    ip = request.client.host
    method = request.method
    url = str(request.url)
    query_params = dict(request.query_params)
    timestamp = datetime.utcnow().isoformat()

    response = await call_next(request)

    logger.info(
        "%s - %s - %s %s - Query Params: %s - Response Status: %d",
        timestamp,
        ip,
        method,
        url,
        query_params,
        response.status_code
    )

    return response

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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_url = info_dict.get('url', '')
            if not video_url:
                raise ApiException(data={
                    "message": "No video URL found",
                    "code": "no_video_url_found",
                    "status": 400
                })
            return {
                "data": {
                    "url": video_url
                },
                "code": "success",
                "message": "Request was successful"
            }
    except Exception as e:
        raise ApiException({"status": 400, "message": str(e)}) from e


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

    Returns:
        JSONResponse: A JSON response with a 404 status code and a message indicating that the resource was not found.
    """
    return JSONResponse(
        status_code=404,
        content={"message": "Not found", "code": "not_found"}
    )


@app.exception_handler(RequestValidationError)
def handle_validation_error(_request, exc):
    """
    Handles validation errors by returning a JSON response with a 400 status code.

    Args:
        _request: The request object (not used in this function).
        exc: The exception that was raised during validation.

    Returns:
        JSONResponse: A response object containing the error message and a "bad_request" code.
    """
    return JSONResponse(
        status_code=400,
        content={"message": str(exc), "code": "bad_request"}
    )
