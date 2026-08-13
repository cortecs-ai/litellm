from typing import Any, List, Optional, Union

import httpx

from litellm.llms.base_llm.chat.transformation import BaseLLMException
from litellm.llms.base_llm.image_generation.transformation import (
    BaseImageGenerationConfig,
)
from litellm.secret_managers.main import get_secret_str
from litellm.types.llms.openai import (
    AllMessageValues,
    OpenAIImageGenerationOptionalParams,
)
from litellm.types.utils import ImageObject, ImageResponse

from ..utils import OVHCloudException


class OVHCloudImageGenerationConfig(BaseImageGenerationConfig):
    def get_supported_openai_params(
        self, model: str
    ) -> List[OpenAIImageGenerationOptionalParams]:
        return ["n", "response_format", "size"]

    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
    ) -> dict:
        return {
            **optional_params,
            **{
                key: value
                for key, value in non_default_params.items()
                if key in self.get_supported_openai_params(model)
            },
        }

    def get_complete_url(
        self,
        api_base: Optional[str],
        api_key: Optional[str],
        model: str,
        optional_params: dict,
        litellm_params: dict,
        stream: Optional[bool] = None,
    ) -> str:
        base_url = (
            "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
            if api_base is None
            else api_base.rstrip("/")
        )
        return f"{base_url}/images/generations"

    def validate_environment(
        self,
        headers: dict,
        model: str,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> dict:
        resolved_api_key = api_key or get_secret_str("OVHCLOUD_API_KEY")
        return {
            "Authorization": f"Bearer {resolved_api_key}",
            "accept": "application/json",
            "Content-Type": "application/json",
            **headers,
        }

    def transform_image_generation_request(
        self,
        model: str,
        prompt: str,
        optional_params: dict,
        litellm_params: dict,
        headers: dict,
    ) -> dict:
        return {"model": model, "prompt": prompt, **optional_params}

    def transform_image_generation_response(
        self,
        model: str,
        raw_response: httpx.Response,
        model_response: ImageResponse,
        logging_obj: Any,
        request_data: dict,
        optional_params: dict,
        litellm_params: dict,
        encoding: Any,
        api_key: Optional[str] = None,
        json_mode: Optional[bool] = None,
    ) -> ImageResponse:
        try:
            response_data = raw_response.json()
        except ValueError as error:
            raise self.get_error_class(
                error_message=f"Invalid OVH image generation response: {error}",
                status_code=raw_response.status_code,
                headers=raw_response.headers,
            )

        data = response_data.get("data")
        if not isinstance(data, list):
            raise self.get_error_class(
                error_message="OVH image generation response did not contain image data.",
                status_code=502,
                headers=raw_response.headers,
            )

        images = [
            ImageObject(
                b64_json=image.get("b64_json"),
                url=image.get("url"),
                revised_prompt=image.get("revised_prompt"),
            )
            for image in data
            if isinstance(image, dict)
            and (image.get("b64_json") is not None or image.get("url") is not None)
        ]
        if not images:
            raise self.get_error_class(
                error_message="OVH image generation response did not contain a generated image.",
                status_code=502,
                headers=raw_response.headers,
            )

        model_response.data = images
        model_response.created = response_data.get("created", model_response.created)
        model_response._hidden_params = response_data
        return model_response

    def get_error_class(
        self, error_message: str, status_code: int, headers: Union[dict, httpx.Headers]
    ) -> BaseLLMException:
        return OVHCloudException(
            message=error_message,
            status_code=status_code,
            headers=headers,
        )
