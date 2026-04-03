import unittest
import os
import tempfile
import json
from datetime import datetime, timezone
from pydantic import ValidationError

from wisdom_vault import CorporateStandard, WisdomVault, get_wisdom_vault
from warroom_protocol import WarRoomReport

class TestWisdomVault(unittest.TestCase):

    def test_corporate_standard_defaults(self):
        std = CorporateStandard(
            standard_id="test-1",
            domain="tax",
            title="Test Standard",
            insight="This is an insight."
        )
        self.assertEqual(std.status, "pending")
        self.assertEqual(std.confidence, 0.8)
        self.assertEqual(std.applicability, "universal")
        self.assertEqual(std.approved_by, "")

    def test_corporate_standard_validation(self):
        with self.assertRaises(ValidationError):
            # Missing required fields
            CorporateStandard(title="Incomplete")

    def test_wisdom_vault_crud(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = os.path.join(tmpdir, "test_vault.json")
            vault = WisdomVault(vault_path)
            
            # Save
            std1 = CorporateStandard(
                standard_id="std1", domain="marketing", title="Insight 1", insight="Detail 1"
            )
            vault.save(std1)
            
            # Save a second
            std2 = CorporateStandard(
                standard_id="std2", domain="architecture", title="Insight 2", insight="Detail 2"
            )
            vault.save(std2)
            
            pendings = vault.get_pending()
            self.assertEqual(len(pendings), 2)
            
            # Approve
            vault.approve("std1")
            self.assertEqual(len(vault.get_pending()), 1)
            
            approved = vault.get_approved()
            self.assertEqual(len(approved), 1)
            self.assertEqual(approved[0].status, "approved")
            self.assertEqual(approved[0].approved_by, "COMMANDER")
            
            # Reject
            vault.reject("std2")
            self.assertEqual(len(vault.get_pending()), 0)
            
            # Get by domain
            self.assertEqual(len(vault.get_approved(domain="marketing")), 1)
            self.assertEqual(len(vault.get_approved(domain="tax")), 0)

    def test_inject_corporate_standards(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = WisdomVault(os.path.join(tmpdir, "test_vault.json"))
            
            # Add approved marketing standard
            vault.save(CorporateStandard(
                standard_id="s1", domain="marketing", title="Use TikTok", insight="Great for GenZ", status="approved"
            ))
            # Add pending marketing standard (should be ignored)
            vault.save(CorporateStandard(
                standard_id="s2", domain="marketing", title="Use FB", insight="Also good", status="pending"
            ))
            # Add approved financial standard
            vault.save(CorporateStandard(
                standard_id="s3", domain="financial", title="Cut costs", insight="Always", status="approved"
            ))
            
            # Test CMO injection
            cmo_block = vault.inject_corporate_standards("CMO")
            self.assertIn("Use TikTok", cmo_block)
            self.assertNotIn("Use FB", cmo_block)
            self.assertNotIn("Cut costs", cmo_block)
            self.assertIn("=== CORPORATE STANDARDS (1 applicable) ===", cmo_block)
            
            # Test CFO injection
            cfo_block = vault.inject_corporate_standards("CFO")
            self.assertIn("Cut costs", cfo_block)
            self.assertNotIn("Use TikTok", cfo_block)

            # Unknown agent
            self.assertEqual(vault.inject_corporate_standards("BOB"), "")

    def test_propose_from_report_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = WisdomVault(os.path.join(tmpdir, "test_vault.json"))
            
            report = WarRoomReport(
                project_id="P1",
                agent="CMO",
                phase="market_research",
                confidence=0.85,
                recommendation="PROCEED",
                detailed_report={
                    "executive_summary": "We should strongly target GenZ because they convert 3x higher."
                },
                summary_report="GenZ strategy is highly effective."
            )
            
            candidate = vault.propose_from_report(report)
            self.assertIsNotNone(candidate)
            self.assertEqual(candidate.status, "pending")
            self.assertEqual(candidate.domain, "marketing")
            self.assertEqual(candidate.source_agent, "CMO")
            self.assertIn("target GenZ", candidate.title)

    def test_propose_from_report_low_confidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = WisdomVault(os.path.join(tmpdir, "test_vault.json"))
            
            report = WarRoomReport(
                project_id="P1",
                agent="CFO",
                phase="financials",
                confidence=0.4, # Too low to propose standard
                recommendation="PROCEED",
                detailed_report={"strategic_direction": "Awesome idea."}
            )
            
            candidate = vault.propose_from_report(report)
            self.assertIsNone(candidate)

    def test_propose_from_report_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = WisdomVault(os.path.join(tmpdir, "test_vault.json"))
            vault.save(CorporateStandard(
                standard_id="existing", domain="marketing", title="We should strongly target GenZ because they convert 3x higher.", insight="Detail"
            ))
            
            report = WarRoomReport(
                project_id="P1",
                agent="CMO",
                phase="market_research",
                confidence=0.9,
                recommendation="PROCEED",
                detailed_report={
                    "executive_summary": "We should strongly target GenZ because they convert 3x higher."
                }
            )
            
            candidate = vault.propose_from_report(report)
            self.assertIsNone(candidate) # Blocked by duplicate title check

if __name__ == "__main__":
    unittest.main()
