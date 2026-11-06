
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.agentdeal.negotiation import Deal, negotiate


deal = Deal(
    product="Wireless Headphones",
    buyer_budget=100.00,
    seller_minimum=75.00,
    buyer_offer=60.00,
    seller_offer=110.00,
    delivery_days=3,
    max_delivery_days=7,
)

result = negotiate(deal)

print("\n=== AGENTDEAL NEGOTIATION ===")
print("Product:", result.product)
print("Status:", result.status)
print("Agreed price:", result.agreed_price)
print("Rounds:", result.round_number)

for event in result.history:
    print(event)
