"""
CMO Agent — Brand Visual Generator (Nano Banana)
═══════════════════════════════════════════════════
AI-powered brand concept visualization using Gemini's
native image generation (gemini-2.5-flash-image).

Generates brand boards, logo concepts, and product
mockups from brand identity JSON.
"""

import os
import uuid
import base64
from pathlib import Path
from google import genai
from google.genai import types

# Folder for generated images
META_ROOT = Path(__file__).parent.parent.parent
GENERATED_DIR = META_ROOT / "frontend" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ── Chat sessions for multi-turn refinement ─────────────
_active_chats = {}  # project_name -> chat object


def _build_brand_prompt(identity: dict, mockup_type: str = "brand_board") -> str:
    """Build a detailed image generation prompt from brand identity."""
    name = identity.get("company_name", "Brand")
    tagline = identity.get("tagline", "")
    archetype = identity.get("brand_personality", {}).get("archetype", "")
    colors = identity.get("visual_identity", {}).get("color_palette", {})
    fonts = identity.get("visual_identity", {}).get("typography", {})
    tone = identity.get("tone_of_voice", {}).get("summary", "")
    positioning = identity.get("positioning_statement", "")

    color_desc = ", ".join([f"{k}: {v}" for k, v in colors.items()]) if colors else "elegant dark palette"
    heading_font = fonts.get("heading_font", "modern sans-serif")
    body_font = fonts.get("body_font", "clean sans-serif")

    prompts = {
        "brand_board": f"""Create a professional brand board / brand identity presentation for "{name}".

The brand board should be a single, beautifully designed image that includes:
- The brand name "{name}" displayed as a clean, modern logo at the top center
- The tagline "{tagline}" underneath in elegant typography
- A color palette strip showing these exact colors: {color_desc}
- Typography samples using the style of {heading_font} for headings and {body_font} for body text
- A small product mockup or lifestyle image in the bottom section that represents the brand
- Clean, white or dark background with generous whitespace

Brand personality: {archetype}
Brand positioning: {positioning}
Tone: {tone}

Style: Minimalist, premium design agency presentation. Think Pentagram or Collins.
Make it look like a real design deliverable, not a generic template.
No placeholder text — use actual brand content.""",

        "logo_concept": f"""Design a professional, modern logo for a brand called "{name}".

Brand context:
- Tagline: "{tagline}"
- Brand archetype: {archetype}
- Brand colors: {color_desc}
- Font style: {heading_font}
- Positioning: {positioning}

Create a clean, scalable logo on a solid background.
The logo should be memorable, distinctive, and professional.
Show the logo mark and wordmark together.
Style: Contemporary, premium, suitable for a startup or DTC brand.
No generic clip art — make it unique and ownable.""",

        "product_packaging": f"""Create a professional product packaging mockup for "{name}".

The product is related to: {positioning}
Brand colors: {color_desc}
Typography: {heading_font} for headings, {body_font} for details
Tagline: "{tagline}"

Show premium packaging (box, pouch, or container) with:
- The brand name "{name}" prominently displayed
- Clean, modern design using the brand colors
- The tagline visible on the packaging
- Photorealistic product photography style

Style: High-end DTC brand packaging. Think premium, Instagram-worthy.
Shot on a clean background with soft studio lighting.""",
    }

    return prompts.get(mockup_type, prompts["brand_board"])


async def generate_brand_visual(
    identity: dict,
    mockup_type: str = "brand_board",
    project_name: str = "default",
    user_feedback: str = None,
) -> dict:
    """
    Generate a brand concept image using Gemini's native image generation.

    Args:
        identity: Brand identity JSON from brand_architect.py
        mockup_type: "brand_board", "logo_concept", or "product_packaging"
        project_name: For chat session tracking
        user_feedback: Optional refinement feedback from user

    Returns:
        dict with image_url, description, and metadata
    """
    client = get_client()
    chat_key = f"{project_name}_{mockup_type}"

    try:
        if user_feedback and chat_key in _active_chats:
            # ── Multi-turn refinement ─────────────────────
            chat = _active_chats[chat_key]
            prompt = f"""Based on my feedback, please regenerate the brand visual.

My feedback: {user_feedback}

Keep the same brand identity but incorporate my changes.
Generate a new, improved version of the brand visual."""

            response = chat.send_message(prompt)

        else:
            # ── First generation ──────────────────────────
            prompt = _build_brand_prompt(identity, mockup_type)

            # Create a chat for multi-turn editing
            chat = client.chats.create(
                model="gemini-2.5-flash-image",
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    temperature=0.8,
                ),
            )

            response = chat.send_message(prompt)
            _active_chats[chat_key] = chat

        # ── Process response ──────────────────────────
        image_url = None
        description = ""

        for part in response.parts:
            if part.text is not None:
                description += part.text
            elif part.inline_data is not None:
                # Save image to disk
                img_id = str(uuid.uuid4())[:8]
                filename = f"brand_{mockup_type}_{img_id}.png"
                filepath = GENERATED_DIR / filename

                # Save the image bytes
                image_data = part.inline_data.data
                with open(filepath, "wb") as f:
                    f.write(image_data)

                image_url = f"/generated/{filename}"

        if not image_url:
            return {
                "error": "No image generated — model returned text only",
                "description": description,
                "mockup_type": mockup_type,
            }

        return {
            "image_url": image_url,
            "description": description.strip(),
            "mockup_type": mockup_type,
            "brand_name": identity.get("company_name", ""),
            "session_active": True,
        }

    except Exception as e:
        error_msg = str(e)
        # Handle specific Gemini errors
        if "RESOURCE_EXHAUSTED" in error_msg:
            return {"error": "Image generation rate limit reached. Please wait a moment and try again."}
        if "not found" in error_msg.lower() or "not supported" in error_msg.lower():
            return {"error": f"Image generation model not available: {error_msg[:150]}. Try a different model."}
        return {
            "error": f"Image generation failed: {error_msg[:200]}",
            "mockup_type": mockup_type,
        }


def clear_chat_session(project_name: str, mockup_type: str = None):
    """Clear a multi-turn chat session to start fresh."""
    if mockup_type:
        key = f"{project_name}_{mockup_type}"
        _active_chats.pop(key, None)
    else:
        keys = [k for k in _active_chats if k.startswith(project_name)]
        for k in keys:
            del _active_chats[k]
