import os
import sys
import logging
import asyncio
from pathlib import Path

# Add local path resolver
sys.path.insert(0, str(Path(__file__).resolve().parent))

logger = logging.getLogger("SentinelBananaManager")
logging.basicConfig(level=logging.INFO)

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-genai SDK not available. SentinelBananaManager operating in stub/mock mode.")

class SentinelBananaManager:
    """
    Nano Banana Pro Actuator.
    Generates high-definition visual assets using Google's generative image matrix.
    """
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if GENAI_AVAILABLE and self.api_key:
            # Configure GenAI client securely via env variables
            self.client = genai.Client(api_key=self.api_key)
            self.initialized = True
        else:
            self.client = None
            self.initialized = False

    async def generate_slide_visual(self, prompt: str) -> dict:
        """
        Generate a 16:9 slide visual asset from a C-Suite directive.
        Returns the raw image bytes and status payload.
        """
        if not self.initialized:
            logger.warning("[STUB] operating under image stub fallback. Prompt: '%s'", prompt)
            return {
                "status": "success",
                "mode": "stub",
                "image_bytes": b"mock_png_image_bytes_here",
                "mime_type": "image/png",
                "url": "https://placehold.co/1024x576/0f0f1a/ffffff/png?text=Nano+Banana+Visual"
            }

        # Targeted model: gemini-3-pro-image (with fallback to production imagen-3.0-generate-002)
        model_name = "gemini-3-pro-image"
        
        # Wrap the API call in an async-friendly running task
        def _execute_api_call(target_model):
            return self.client.models.generate_images(
                model=target_model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                    output_mime_type="image/png"
                )
            )

        try:
            logger.info("Directing prompt to Nano Banana Pro (%s)...", model_name)
            response = await asyncio.to_thread(_execute_api_call, model_name)
            generated_image = response.generated_images[0]
            image_bytes = generated_image.image.image_bytes
            
            return {
                "status": "success",
                "image_bytes": image_bytes,
                "mime_type": "image/png",
                "mode": "live"
            }
        except Exception as e:
            logger.warning("gemini-3-pro-image request failed: %s. Initiating fallback to imagen-3.0-generate-002...", e)
            try:
                response = await asyncio.to_thread(_execute_api_call, "imagen-3.0-generate-002")
                generated_image = response.generated_images[0]
                image_bytes = generated_image.image.image_bytes
                
                return {
                    "status": "success",
                    "image_bytes": image_bytes,
                    "mime_type": "image/png",
                    "mode": "live_fallback"
                }
            except Exception as e_fallback:
                logger.error("All image generation pipelines failed: %s", e_fallback)
                raise RuntimeError(f"IMAGE_GENERATION_FAILED: Pipeline exception: {e_fallback}")

if __name__ == "__main__":
    print("Testing SentinelBananaManager...")
    manager = SentinelBananaManager()
    print("Initialized status:", manager.initialized)
