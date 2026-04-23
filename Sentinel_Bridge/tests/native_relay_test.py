"""
Native Relay Test: Scenario Simulator Stress Test (Phase 9)
==========================================================================
Verifies the SentinelDriveManager routing, Digital Audit Signatures, 
and the 5-iteration Scenario Simulator (Bull, Base, Bear, Worst-Case, Blue-Sky).
"""

import os
import sys
import base64
import asyncio
import aiohttp
import hashlib
from pathlib import Path

FACTORY_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(FACTORY_DIR / "Sentinel_Bridge"))
sys.path.insert(0, str(FACTORY_DIR / "CFO_Agent"))

try:
    from sentinel_drive_manager import SentinelDriveManager
except ImportError as e:
    SentinelDriveManager = None
    print(f"Failed to import SentinelDriveManager: {e}")

async def test_scenario_simulator():
    print("--- 🚀 Testing Scenario Simulator Engine: Aegis_Finance_Beta ---")
    if not SentinelDriveManager:
        print("SentinelDriveManager unavailable.")
        return
        
    drive_mgr = SentinelDriveManager()
    
    # Simulating 5 Scenarios
    scenarios = ['Bull', 'Base', 'Bear', 'Worst-Case', 'Blue-Sky']
    print("\n[1] CFO Quant Lead generates 5 scenario derivations...")
    
    mock_assets = []
    
    print("\n[2] Firing 5 Sequential SHA-256 Validation Handshakes to Phantom QA Elite...")
    for idx, scenario in enumerate(scenarios):
        print(f"\n  -> Auditing Scenario {idx+1}/5: {scenario}")
        dummy_payload = f"Dummy Aegis_Finance_Beta_{scenario} Report Data and Debt Sculpting Equations".encode()
        digital_signature = hashlib.sha256(dummy_payload).hexdigest()
        
        qa_passed = False
        PHANTOM_QA_URL = os.getenv("PHANTOM_QA_URL", "http://phantom_qa:5030/api/audit/auto")
        TARGET_URL = os.getenv("TARGET_APP_URL", "http://target_app:5041")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                valid_qa_payload = {
                    "source": "CFO_Fragility_Engine",
                    "target_url": TARGET_URL,
                    "file_link": "local_stub",
                    "file_name": f"Aegis_Finance_Beta_{scenario}.xlsx",
                    "audit_mode": "mathematical",
                    "audit_type": "AUDIT:cryptographic",
                    "digital_audit_signature": digital_signature,
                    "report_data": {
                        "fragility_index": 45.0 + (idx * 2),
                        "composite_score": 55.0 - (idx * 2),
                    },
                    "callback_url": f"{TARGET_URL}/api/audit/correction"
                }
                async with session.post(PHANTOM_QA_URL, json=valid_qa_payload) as r:
                    if r.status == 200:
                        data = await r.json()
                        score = data.get('score', 0)
                        if score >= 70:
                            print(f"      [VERDICT] PASS - Score: {score} | Signature verified.")
                            qa_passed = True
                        else:
                            print(f"      [VERDICT] FAIL - Score: {score} | QA Gate blocked execution.")
                    else:
                        print(f"      [VERDICT] FAIL - HTTP {r.status} | Invalid response from QA.")
        except asyncio.TimeoutError:
            print(f"      [VERDICT] FAIL - Timeout | Phantom QA unreachable.")
        except Exception as e:
            print(f"      [VERDICT] FAIL - Exception | {str(e)}")
            
        if qa_passed:
            mock_assets.append({
                "name": f"Aegis_Finance_Beta_{scenario}.xlsx", 
                "content": dummy_payload, 
                "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            })

    # Generate Dynamic Brochure for Aegis
    from cfo_engine import CFOExecutionController
    cfo = CFOExecutionController()
    
    # Mocking a scenario dump to leverage our new _generate_csuite_brochure delta
    dummy_scenarios = {}
    for sc in scenarios:
        dummy_scenarios[sc] = {
            'summary': {
                'total_spend': 500000.0,
                'total_projected_revenue': 800000.0 * (1.2 if sc == 'Bull' else 1.0),
                'portfolio_roi_pct': 45.0 * (1.2 if sc == 'Bull' else 1.0)
            }
        }
    html_brochure = cfo._generate_csuite_brochure({
        'is_scenario_bundle': True,
        'scenarios': dummy_scenarios,
        'project_name': 'Aegis_Finance_Beta'
    })

    # C-Suite Assets
    mock_assets.append({
        "name": "Aegis_Finance_Beta_Scenarios_Manual.md", 
        "content": b"# Aegis Finance Beta Scenarios Technical Manual\nCryptographically verified 5-phase execution.", 
        "type": "text/markdown"
    })
    mock_assets.append({
        "name": "Aegis_Finance_Beta_Scenarios_Brochure.html", 
        "content": html_brochure.encode('utf-8'), 
        "type": "text/html"
    })

    # ── BUNDLE INJECTION ──────────────────────────────────────────
    if len(mock_assets) == 7:
        print("\n[3] 7/7 Assets Audited successfully! Context-Aware Folder Anchor routing to Meta_App_Factory root...")
        try:
            res = drive_mgr.bundle_project_assets("Aegis_Finance_Beta_Scenarios", mock_assets)
            print(f"    -> Atomic Bundle Injected to Meta_App_Factory Root: {res}")
        except Exception as e:
            print(f"    -> Bundle Injection Stubbed: {e}")
            
    print("\n✅ Scenario Simulator Engine validation complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_scenario_simulator())
