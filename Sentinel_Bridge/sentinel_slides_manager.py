import os
import sys
import json
import logging
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

try:
    from fernet_vault import FernetVault
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False

logger = logging.getLogger("SentinelSlidesManager")
logging.basicConfig(level=logging.INFO)

class SentinelSlidesManager:
    """
    Native Workspace Actuator.
    Autonomous cloning of presentation templates and sub-atomic tag replacement.
    Pulls credentials securely from the FernetVault.
    """
    
    def __init__(self, credentials_dict=None):
        if credentials_dict is None:
            if VAULT_AVAILABLE:
                vault = FernetVault()
                creds_raw = vault.retrieve("google_drive_service_account") or vault.retrieve("google_workspace_sa")
                if creds_raw:
                    try:
                        credentials_dict = json.loads(creds_raw)
                        logger.info("Successfully loaded Google credentials from FernetVault.")
                    except json.JSONDecodeError:
                        logger.error("Failed to parse Google credentials JSON from vault.")
                else:
                    logger.warning("No 'google_drive_service_account' key found in FernetVault.")
            else:
                logger.warning("FernetVault not available. Cannot auto-load credentials.")

        if credentials_dict:
            self.scopes = [
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/presentations'
            ]
            self.creds = Credentials.from_service_account_info(
                credentials_dict, 
                scopes=self.scopes
            )
            self.slides_service = build('slides', 'v1', credentials=self.creds)
            self.drive_service = build('drive', 'v3', credentials=self.creds)
            self.initialized = True
        else:
            logger.warning("SentinelSlidesManager initialized in STUB mode (No credentials).")
            self.slides_service = None
            self.drive_service = None
            self.initialized = False

    def clone_template(self, template_id: str, output_name: str) -> str:
        """
        Duplicate a master presentation template using Drive API.
        """
        if not self.initialized:
            logger.info(f"[STUB] Cloned template {template_id} to new file: '{output_name}'")
            return f"stub_presentation_{hash(template_id + output_name)}"
            
        try:
            body = {'name': output_name}
            cloned_file = self.drive_service.files().copy(
                fileId=template_id, 
                body=body
            ).execute()
            
            cloned_id = cloned_file.get('id')
            logger.info(f"Cloned template '{template_id}' successfully. New ID: '{cloned_id}'")
            return cloned_id
        except Exception as e:
            logger.error(f"Failed to clone template {template_id}: {e}")
            raise RuntimeError(f"WORKSPACE_CLONE_ERROR: Template duplication failed: {e}")

    def apply_mutations(self, presentation_id: str, mutations: list) -> dict:
        """
        Execute sub-atomic text replacement via slides batchUpdate API.
        mutations structure: [{"replace_tag": "{{TAG}}", "injection_value": "VALUE"}, ...]
        """
        if not self.initialized:
            logger.info(f"[STUB] Applied mutations to presentation {presentation_id}:")
            for m in mutations:
                logger.info(f"   → Replace '{m.get('replace_tag')}' with '{m.get('injection_value')}'")
            return {"status": "success", "presentation_id": presentation_id, "mode": "stub"}

        try:
            requests = []
            for mutation in mutations:
                requests.append({
                    'replaceAllText': {
                        'containsText': {
                            'text': mutation["replace_tag"],
                            'matchCase': True
                        },
                        'replaceText': mutation["injection_value"]
                    }
                })

            if not requests:
                logger.warning("No mutations provided to apply.")
                return {"status": "success", "message": "No mutations requested."}

            response = self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id, 
                body={'requests': requests}
            ).execute()
            
            logger.info(f"Successfully applied {len(mutations)} sub-atomic mutations to presentation {presentation_id}.")
            return {
                "status": "success",
                "presentation_id": presentation_id,
                "mutations_applied": len(mutations),
                "api_response": response
            }
        except Exception as e:
            logger.error(f"Failed to apply mutations to presentation {presentation_id}: {e}")
            raise RuntimeError(f"WORKSPACE_MUTATION_ERROR: Slides batchUpdate failed: {e}")

    def inject_image_to_slide(self, presentation_id: str, slide_object_id: str, image_url: str) -> dict:
        """
        Injects a generated visual asset (using a public URL) directly into the targeted slide.
        Utilizes slides createImage batchUpdate request.
        """
        if not self.initialized:
            logger.info(f"[STUB] Injecting image '{image_url}' to slide '{slide_object_id}' inside presentation '{presentation_id}'")
            return {"status": "success", "mode": "stub", "image_url": image_url}

        try:
            import uuid
            image_id = f"image_{uuid.uuid4().hex[:8]}"
            requests = [
                {
                    'createImage': {
                        'objectId': image_id,
                        'url': image_url,
                        'elementProperties': {
                            'pageObjectId': slide_object_id,
                            'size': {
                                'height': {'magnitude': 270, 'unit': 'PT'},
                                'width': {'magnitude': 480, 'unit': 'PT'}
                            },
                            'transform': {
                                'scaleX': 1, 'scaleY': 1,
                                'translateX': 120, 'translateY': 150,
                                'unit': 'PT'
                            }
                        }
                    }
                }
            ]

            response = self.slides_service.presentations().batchUpdate(
                presentationId=presentation_id, 
                body={'requests': requests}
            ).execute()
            
            logger.info(f"Successfully injected image into slide {slide_object_id} for presentation {presentation_id}.")
            return {
                "status": "success",
                "presentation_id": presentation_id,
                "image_object_id": image_id,
                "api_response": response
            }
        except Exception as e:
            logger.error(f"Failed to inject image into slide {slide_object_id}: {e}")
            raise RuntimeError(f"WORKSPACE_IMAGE_ERROR: Slides batchUpdate createImage failed: {e}")

    def actuate_blueprint(self, blueprint: dict) -> dict:
        """
        Full actuation lifecycle from a single Workspace_Blueprint.json structure.
        """
        template_id = blueprint.get("master_template_id")
        output_filename = blueprint.get("output_filename", "Generated_Presentation")
        mutations = blueprint.get("mutations", [])
        
        # 1. Duplicate
        cloned_id = self.clone_template(template_id, output_filename)
        
        # 2. Mutate
        res = self.apply_mutations(cloned_id, mutations)
        
        # 3. Formulate output web view link
        if self.initialized:
            res["web_link"] = f"https://docs.google.com/presentation/d/{cloned_id}/view"
        else:
            res["web_link"] = f"https://docs.google.com/presentation/d/{cloned_id}_stub/view"
            
        return res

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sentinel Slides Manager CLI")
    parser.add_argument("--test-run", action="store_true", help="Run in stub/test mode to verify configuration")
    args = parser.parse_args()
    
    manager = SentinelSlidesManager()
    if args.test_run:
        print("Running slides manager verification...")
        print("Initialization status:", manager.initialized)
