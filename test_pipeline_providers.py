import unittest
from unittest.mock import patch, MagicMock
from providers import (
    MistralDiscoveryProvider,
    ProspeoPeopleSearchProvider,
    HunterPeopleSearchProvider,
    CompetitorResult,
    PersonResult,
)


class TestPipelineProviders(unittest.TestCase):
    def setUp(self):
        self.discovery = MistralDiscoveryProvider(api_key="test_mistral_key", apollo_key="test_apollo_key")
        self.prospeo = ProspeoPeopleSearchProvider(api_key="test_prospeo_key")
        self.hunter = HunterPeopleSearchProvider(api_key="test_hunter_key")

    def test_extract_root_domain(self):
        self.assertEqual(self.discovery._extract_root_domain("https://www.zomato.com/bangalore/restaurants"), "zomato.com")
        self.assertEqual(self.discovery._extract_root_domain("http://sub.infosys.com?ref=123"), "infosys.com")
        self.assertEqual(self.discovery._extract_root_domain("stripe.com/docs"), "stripe.com")

    def test_names_match(self):
        self.assertTrue(self.discovery._names_match("Zomato Ltd", "zomato"))
        self.assertTrue(self.discovery._names_match("Tata Consultancy Services", "TCS"))
        self.assertFalse(self.discovery._names_match("Swiggy", "Infosys"))

    @patch("requests.head")
    def test_domain_verification_http(self, mock_head):
        # Mock successful HEAD response
        mock_head.return_value.status_code = 200
        self.assertTrue(self.discovery._verify_domain_http("zomato.com"))

        # Mock failed/non-existent domain
        mock_head.return_value.status_code = 404
        self.assertFalse(self.discovery._verify_domain_http("fakeinvalidxyzdomain.org"))

    @patch.object(MistralDiscoveryProvider, "_verify_domain_http")
    @patch.object(MistralDiscoveryProvider, "_enrich_seed")
    @patch("requests.post")
    def test_mistral_discovery_confidence_scoring(self, mock_post, mock_enrich, mock_verify):
        mock_verify.side_effect = lambda domain: domain == "zomato.com"  # zomato resolves, other doesn't
        mock_enrich.side_effect = lambda domain: ("Zomato", "Food Delivery") if domain == "zomato.com" else ("", "")

        # Mock Mistral response returning two competitors
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": '[{"name": "Zomato", "domain": "zomato.com"}, {"name": "FakeCompany", "domain": "fake.com"}]'
                }
            }]
        }
        mock_post.return_value = mock_resp

        results = self.discovery.find_competitors("swiggy.com", "Swiggy", "Food Delivery")
        self.assertEqual(len(results), 2)

        zomato = next(r for r in results if r["domain"] == "zomato.com")
        self.assertEqual(zomato["confidence"], "high")
        self.assertEqual(zomato["source"], "llm_verified")

        fake = next(r for r in results if r["domain"] == "fake.com")
        self.assertEqual(fake["confidence"], "low")
        self.assertEqual(fake["source"], "llm_unverified")

    @patch("requests.post")
    def test_prospeo_people_contract(self, mock_post):
        # Mock search response and enrich response
        mock_post.side_effect = [
            # 1. Search response
            MagicMock(status_code=200, json=lambda: {"results": [{"person": {"person_id": "p_123"}}]}),
            # 2. Enrich response
            MagicMock(status_code=200, json=lambda: {
                "person": {"full_name": "Deepinder Goyal", "current_job_title": "CEO", "linkedin_url": "https://linkedin.com/in/deepinder", "email": "deepinder@zomato.com"},
                "company": {"name": "Zomato", "domain": "zomato.com"}
            })
        ]

        contacts = self.prospeo.search_people("zomato.com")
        self.assertEqual(len(contacts), 1)
        c = contacts[0]
        self.assertEqual(c["name"], "Deepinder Goyal")
        self.assertEqual(c["email"], "deepinder@zomato.com")
        self.assertTrue(c["email_verified"])
        self.assertEqual(c["provider"], "prospeo")

    @patch("requests.get")
    def test_hunter_fallback_contract(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {
            "data": {
                "organization": "Zomato",
                "emails": [{
                    "value": "ceo@zomato.com",
                    "first_name": "Deepinder",
                    "last_name": "Goyal",
                    "position": "CEO",
                    "verification": {"status": "valid"},
                    "confidence": 95
                }]
            }
        })

        contacts = self.hunter.search_people("zomato.com")
        self.assertEqual(len(contacts), 1)
        c = contacts[0]
        self.assertEqual(c["email"], "ceo@zomato.com")
        self.assertTrue(c["email_verified"])
        self.assertEqual(c["provider"], "hunter")


if __name__ == "__main__":
    unittest.main()
