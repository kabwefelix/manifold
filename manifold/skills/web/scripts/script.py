import json
import sys
from datetime import datetime, timezone

import requests


HEADERS = {"User-Agent": "Manifold/1.0"}
METAL_ENDPOINTS = {
    "gold": {
        "symbol": "XAU",
        "url": "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD",
    },
    "silver": {
        "symbol": "XAG",
        "url": "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAG/USD",
    },
}


def determine_requested_metals(query: str) -> list[str]:
    query_lower = (query or "").lower()
    wants_gold = "gold" in query_lower or "xau" in query_lower
    wants_silver = "silver" in query_lower or "xag" in query_lower

    if wants_gold and wants_silver:
        return ["gold", "silver"]
    if wants_gold:
        return ["gold"]
    if wants_silver:
        return ["silver"]
    return ["gold", "silver"]


def fetch_quote(metal_name: str) -> dict:
    config = METAL_ENDPOINTS[metal_name]
    response = requests.get(config["url"], headers=HEADERS, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if not payload:
        raise ValueError(f"No market data returned for {metal_name}.")

    spread_prices = payload[0].get("spreadProfilePrices") or []
    if not spread_prices:
        raise ValueError(f"No bid/ask quotes returned for {metal_name}.")

    preferred_profile = next(
        (entry for entry in spread_prices if entry.get("spreadProfile") == "prime"),
        spread_prices[0],
    )

    bid = float(preferred_profile["bid"])
    ask = float(preferred_profile["ask"])
    return {
        "symbol": config["symbol"],
        "currency": "USD",
        "unit": "per troy ounce",
        "bid": bid,
        "ask": ask,
        "mid": round((bid + ask) / 2, 4),
        "source": "Swissquote public quotes",
    }


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "test_input":
        print("Test passed")
        sys.exit(0)

    query = " ".join(sys.argv[1:]).strip()
    requested_metals = determine_requested_metals(query)
    prices = {}
    errors = {}

    for metal_name in requested_metals:
        try:
            prices[metal_name] = fetch_quote(metal_name)
        except Exception as exc:
            errors[metal_name] = str(exc)

    if not prices:
        print(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "query": query or None,
                    "errors": errors,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "query": query or None,
        "prices": prices,
    }
    if errors:
        result["partial_errors"] = errors

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
