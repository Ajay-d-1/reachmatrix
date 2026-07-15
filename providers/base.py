from abc import ABC, abstractmethod
from typing import TypedDict, Literal, List


class CompetitorResult(TypedDict):
    name: str
    domain: str
    source: Literal["llm_verified", "llm_unverified"]
    confidence: Literal["high", "medium", "low"]


class CompetitorDiscoveryProvider(ABC):
    @abstractmethod
    def find_competitors(
        self, domain: str, company_name: str, industry: str
    ) -> List[CompetitorResult]:
        ...


class PersonResult(TypedDict):
    name: str
    title: str
    company: str
    domain: str
    linkedin_url: str
    email: str
    email_verified: bool
    provider: Literal["prospeo", "hunter"]


class PeopleSearchProvider(ABC):
    @abstractmethod
    def search_people(
        self, domain: str, seniority: List[str]
    ) -> List[PersonResult]:
        ...
