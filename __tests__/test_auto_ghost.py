import os
import time
import requests
import traceback
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import Playwright

def test_auto_ghost(playwright: Playwright):
    start_time = time.time()
    
    # ── Dynamic Env Resolution (No Hardcoding) ──
    for p in [Path(__file__).parent, Path(__file__).parent.parent, Path(__file__).parent.parent.parent]:
        env_file = p / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break

    target_url = os.environ.get("CLO_AGENT_URL", "http://127.0.0.1:5080")
    qa_backend = os.environ.get("PHANTOM_QA_BACKEND")
    if not qa_backend:
        qa_port = os.environ.get("PHANTOM_QA_PORT", "5030")
        qa_backend = f"http://127.0.0.1:{qa_port}"

    verdict = "FAIL"
    score = 0
    resp_json = {}
    request_context = None

    try:
        # 1. Forcefully poll CLO_Agent health natively until an HTTP 200 is confirmed
        health_url = f"{target_url}/api/health"
        service_online = False
        
        for _ in range(30):
            try:
                response = requests.get(health_url, timeout=2.0)
                if response.status_code == 200 and response.json().get("status") == "online":
                    service_online = True
                    break
            except Exception:
                pass
            time.sleep(1.0)
            
        assert service_online, f"CLO_Agent's internal /api/health did not return online at {health_url}"

        # 2. Execute a localized API fuzzing payload directly against the agent's ingestion routers
        request_context = playwright.request.new_context(base_url=target_url)
        
        payload = {
            "template_name": "non_existent_template_fuzz",
            "data": {"key": "value"},
            "output_filename": "fuzz_output.txt"
        }
        
        response = request_context.post("/api/legal/analyze", data=payload)
        
        # Assert raw ASGI response envelope strictly matches the UNIFIED I/O SERIALIZATION ENVELOPE doctrine
        assert response.status in [200, 500]
        resp_json = response.json()
        
        if response.status == 200:
            assert resp_json.get("status") == "success"
            assert "output_path" in resp_json
        else:
            assert "detail" in resp_json or "error" in resp_json

        verdict = "PASS"
        score = 100

    except Exception as e:
        # Trap the failure securely inside the fail envelope to prevent secondary serialization crashes
        verdict = "FAIL"
        score = 0
        resp_json = {
            "status": "FAIL",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        # Re-raise to ensure the Pytest suite natively registers the failure
        raise e

    finally:
        # 3. Strictly POST the UNIFIED I/O SERIALIZATION ENVELOPE to the Phantom QA telemetry backend
        try:
            duration = round(time.time() - start_time, 2)
            report_payload = {
                "app_name": "CLO_Agent",
                "app_url": target_url,
                "verdict": verdict,
                "score": score,
                "duration": duration,
                "report_data": {
                    "verdict": verdict,
                    "score": score,
                    "duration": duration,
                    "response": resp_json
                }
            }
            # Guaranteed transmission to dynamic path
            requests.post(f"{qa_backend}/api/reports", json=report_payload, timeout=5.0)
        except Exception as post_err:
            print(f"Failed to post E2E telemetry back to QA backend: {post_err}")
            
        if request_context:
            request_context.dispose()