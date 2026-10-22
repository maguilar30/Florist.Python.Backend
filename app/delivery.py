from decimal import Decimal

DELIVERY_OPTIONS: dict[str, Decimal] = {
    "pickup": Decimal("0.00"),
    "up_to_2km": Decimal("5.00"),
    "up_to_5km": Decimal("10.00"),
    "over_5km": Decimal("20.00"),
}

DELIVERY_LABELS: dict[str, str] = {
    "pickup": "Recoger en tienda",
    "up_to_2km": "Entrega hasta 2 km",
    "up_to_5km": "Entrega hasta 5 km",
    "over_5km": "Entrega a más de 5 km",
}

DEFAULT_DELIVERY_OPTION = "pickup"


def delivery_fee_for(option: str) -> Decimal:
    try:
        return DELIVERY_OPTIONS[option]
    except KeyError:
        raise ValueError(f"Unknown delivery option: {option}") from None
