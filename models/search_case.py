from dataclasses import dataclass
from typing import Literal


Variant = Literal["A", "B"]
IdType = Literal["address_id", "house_id"]
AddressSource = Literal["old", "v2"]
ExpectedResult = Literal["found", "not_found"]


@dataclass(frozen=True)
class SearchCase:
    case_id: str
    site: str
    url_type: str
    form: str
    variant: Variant
    region: str
    region_id: int
    street_query: str
    expected_street: str
    house_query: str
    expected_house: str
    expected_id: int
    expected_id_type: IdType
    address_source: AddressSource
    dataset: str
    expected_lead_form_type: str = ""
    expected_order_site: str = ""
    form_title: str = ""
    phone: str = "9999999999"
    success_url_markers: list[str] | None = None
    is_adjacent: bool = False
    expected_result: ExpectedResult = "found"

    @property
    def address_version(self) -> str:
        return "v2" if self.address_source == "v2" else "v1"

    @property
    def pytest_id(self) -> str:
        if self.case_id.startswith(f"{self.site}__"):
            return self.case_id
        return f"{self.site}__{self.url_type}__{self.form}__{self.variant}__{self.case_id}"
