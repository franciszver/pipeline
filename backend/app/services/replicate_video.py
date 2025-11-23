"""
Replicate API Video Generation Service

Generates video clips using Replicate's hosted models.
Default: Minimax video-01 (~$0.035 per 5s video)
"""
import asyncio
import httpx
import replicate
from typing import Optional, Dict, Any

from app.config import get_settings


class ReplicateVideoService:
    """Service for generating videos using Replicate's API."""

    # Available models on Replicate
    MODELS = {
        "minimax": "minimax/video-01",  # Cheapest ~$0.035/5s
        "kling": "kwaivgi/kling-v1.5-pro",  # Higher quality ~$0.15/5s
        "luma": "luma/dream-machine",  # High quality ~$0.20/5s
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Replicate video service.

        Args:
            api_key: Replicate API key. If not provided, reads from settings.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # If api_key is provided, use it; otherwise get from orchestrator (prioritizes .env for local dev)
        if api_key:
            self.api_key = api_key
        else:
            # Use orchestrator's function to get key (prioritizes .env for local dev)
            from app.services.orchestrator import _get_replicate_api_key
            self.api_key = _get_replicate_api_key()
        
        if not self.api_key:
            logger.error("REPLICATE_API_KEY not configured in ReplicateVideoService")
            raise ValueError("REPLICATE_API_KEY not configured")
        
        # Strip whitespace and quotes to prevent authentication issues
        self.api_key = self.api_key.strip()
        # Remove surrounding quotes if present (common .env file issue)
        if (self.api_key.startswith('"') and self.api_key.endswith('"')) or \
           (self.api_key.startswith("'") and self.api_key.endswith("'")):
            self.api_key = self.api_key[1:-1].strip()

        # Validate key format (should start with r8_)
        if not self.api_key.startswith("r8_"):
            key_preview = f"{self.api_key[:5]}...{self.api_key[-3:]}" if len(self.api_key) > 8 else f"{self.api_key[:5]}..."
            logger.error(f"REPLICATE_API_KEY has invalid format! Expected to start with 'r8_', preview: {key_preview}, length: {len(self.api_key)})")
            raise ValueError(f"REPLICATE_API_KEY has invalid format. Expected to start with 'r8_'")

        # Create Replicate client with explicit API token (like other agents do)
        self.client = replicate.Client(api_token=self.api_key)
        key_preview = f"{self.api_key[:5]}...{self.api_key[-3:]}" if len(self.api_key) > 8 else f"{self.api_key[:5]}..."
        logger.info(f"ReplicateVideoService initialized with API key (preview: {key_preview}, length: {len(self.api_key)})")

    async def generate_video(
        self,
        prompt: str,
        model: str = "minimax",
        duration: int = 5,
        seed: Optional[int] = None,
    ) -> str:
        """
        Generate a video from a text prompt.

        Args:
            prompt: Text description of the video to generate
            model: Model to use ("minimax", "kling", "luma")
            duration: Approximate video duration (model-dependent)
            seed: Optional random seed for reproducibility

        Returns:
            URL of the generated video
        """
        model_id = self.MODELS.get(model, self.MODELS["minimax"])

        # Run in thread to avoid blocking
        output = await asyncio.to_thread(
            self._run_prediction,
            model_id,
            prompt,
            duration,
            seed
        )

        return output

    def _run_prediction(self, model_id: str, prompt: str, duration: int, seed: Optional[int] = None) -> str:
        """
        Run the prediction synchronously.

        Args:
            model_id: Replicate model identifier
            prompt: Text prompt
            duration: Video duration
            seed: Optional random seed for reproducibility

        Returns:
            URL of the generated video
        """
        # Build input based on model
        if "minimax" in model_id:
            input_data = {
                "prompt": prompt,
                "prompt_optimizer": True,
            }
            # Add seed if provided (Minimax supports seed)
            if seed is not None:
                input_data["seed"] = seed
        elif "kling" in model_id:
            input_data = {
                "prompt": prompt,
                "duration": duration,
                "aspect_ratio": "16:9",
            }
            # Add seed if provided (Kling supports seed)
            if seed is not None:
                input_data["seed"] = seed
        elif "luma" in model_id:
            input_data = {
                "prompt": prompt,
                "aspect_ratio": "16:9",
            }
            # Luma may not support seed - only add if provided
            if seed is not None:
                input_data["seed"] = seed
        else:
            input_data = {
                "prompt": prompt,
            }
            if seed is not None:
                input_data["seed"] = seed

        import logging
        logger = logging.getLogger(__name__)
        
        # Log the API key being used (for debugging authentication errors)
        if self.api_key:
            key_preview = f"{self.api_key[:5]}...{self.api_key[-3:]}" if len(self.api_key) > 8 else f"{self.api_key[:5]}..."
            logger.info(f"Using REPLICATE_API_KEY for model {model_id}: {key_preview} (length: {len(self.api_key)})")
        else:
            logger.error("REPLICATE_API_KEY is None or empty when calling Replicate API")

        # Run the model using the client instance (explicit API token)
        try:
            output = self.client.run(model_id, input=input_data)
        except Exception as e:
            # Log the key again on error for debugging
            if self.api_key:
                key_preview = f"{self.api_key[:5]}...{self.api_key[-3:]}" if len(self.api_key) > 8 else f"{self.api_key[:5]}..."
                logger.error(f"Replicate API error with key: {key_preview} (length: {len(self.api_key)}, starts with: {self.api_key[:5]}...)")
            else:
                logger.error("Replicate API error with key: None or empty")
            raise

        # Handle different output formats
        if isinstance(output, str):
            return output
        elif isinstance(output, list) and len(output) > 0:
            return output[0]
        elif hasattr(output, 'url'):
            return output.url
        else:
            # Try to iterate (FileOutput objects)
            for item in output:
                if isinstance(item, str):
                    return item
                elif hasattr(item, 'url'):
                    return item.url
            raise RuntimeError(f"Unexpected output format: {output}")

    async def generate_video_from_image(
        self,
        prompt: str,
        image_url: str,
        model: str = "minimax",
        seed: Optional[int] = None,
    ) -> str:
        """
        Generate a video from an image and text prompt.

        Args:
            prompt: Text description of the motion/action
            image_url: URL of the source image
            model: Model to use
            seed: Optional random seed for reproducibility

        Returns:
            URL of the generated video
        """
        model_id = self.MODELS.get(model, self.MODELS["minimax"])

        output = await asyncio.to_thread(
            self._run_image_to_video,
            model_id,
            prompt,
            image_url,
            seed
        )

        return output

    def _run_image_to_video(self, model_id: str, prompt: str, image_url: str, seed: Optional[int] = None) -> str:
        """
        Run image-to-video prediction synchronously.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if "minimax" in model_id:
            input_data = {
                "prompt": prompt,
                "first_frame_image": image_url,
            }
            if seed is not None:
                input_data["seed"] = seed
        elif "kling" in model_id:
            input_data = {
                "prompt": prompt,
                "start_image": image_url,
                "aspect_ratio": "16:9",
            }
            if seed is not None:
                input_data["seed"] = seed
        else:
            input_data = {
                "prompt": prompt,
                "image": image_url,
            }
            if seed is not None:
                input_data["seed"] = seed

        # Log the API key being used (for debugging authentication errors)
        if self.api_key:
            key_preview = f"{self.api_key[:5]}...{self.api_key[-3:]}" if len(self.api_key) > 8 else f"{self.api_key[:5]}..."
            logger.info(f"Using REPLICATE_API_KEY for image-to-video model {model_id}: {key_preview} (length: {len(self.api_key)})")
        else:
            logger.error("REPLICATE_API_KEY is None or empty when calling Replicate API for image-to-video")

        # Run the model using the client instance (explicit API token)
        try:
            output = self.client.run(model_id, input=input_data)
        except Exception as e:
            # Log the key again on error for debugging
            if self.api_key:
                key_preview = f"{self.api_key[:5]}...{self.api_key[-3:]}" if len(self.api_key) > 8 else f"{self.api_key[:5]}..."
                logger.error(f"Replicate API error (image-to-video) with key: {key_preview} (length: {len(self.api_key)}, starts with: {self.api_key[:5]}...)")
            else:
                logger.error("Replicate API error (image-to-video) with key: None or empty")
            raise

        # Handle output format
        if isinstance(output, str):
            return output
        elif isinstance(output, list) and len(output) > 0:
            return output[0]
        elif hasattr(output, 'url'):
            return output.url
        else:
            for item in output:
                if isinstance(item, str):
                    return item
                elif hasattr(item, 'url'):
                    return item.url
            raise RuntimeError(f"Unexpected output format: {output}")


async def generate_scene_videos(
    script: Dict[str, Any],
    api_key: Optional[str] = None,
    model: str = "minimax",
    progress_callback: Optional[callable] = None
) -> Dict[str, str]:
    """
    Generate videos for all script sections.

    Args:
        script: Script data with visual_prompt for each section
        api_key: Replicate API key
        model: Model to use ("minimax", "kling", "luma")
        progress_callback: Async callback for progress updates

    Returns:
        Dictionary mapping section names to video URLs
    """
    service = ReplicateVideoService(api_key)
    sections = ["hook", "concept", "process", "conclusion"]
    video_urls = {}

    for i, section in enumerate(sections):
        section_data = script.get(section, {})
        visual_prompt = section_data.get("visual_prompt", "")

        if not visual_prompt:
            # Fallback: generate prompt from text
            text = section_data.get("text", "")
            visual_prompt = f"Cinematic scene: {text[:200]}"

        if progress_callback:
            await progress_callback(f"Generating video {i+1}/4: {section}...")

        try:
            video_url = await service.generate_video(
                prompt=visual_prompt,
                model=model
            )
            video_urls[section] = video_url

        except Exception as e:
            raise RuntimeError(f"Failed to generate video for {section}: {e}")

    return video_urls
