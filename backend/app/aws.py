from typing import Any, LiteralString, Literal

import boto3
from app.config import settings


def get_aws_client(service_name: str) -> Any:
    return boto3.client(
        service_name=service_name,
        endpoint_url=settings.aws_endpoint_url,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key
    )
