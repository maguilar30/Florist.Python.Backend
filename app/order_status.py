ORDER_STATUSES = (
    "payment_pending",
    "paid",
    "preparing",
    "ready_for_pickup",
    "out_for_delivery",
    "delivered",
    "cancelled",
)

DEFAULT_ORDER_STATUS = "payment_pending"
COMPLETED_ORDER_STATUS = "delivered"

ORDER_STATUS_LABELS: dict[str, str] = {
    "payment_pending": "Pago pendiente",
    "paid": "Pagado",
    "preparing": "En preparación",
    "ready_for_pickup": "Listo para recoger",
    "out_for_delivery": "En camino",
    "delivered": "Entregado",
    "cancelled": "Cancelado",
}

ORDER_STATUS_CUSTOMER_NOTES: dict[str, str] = {
    "payment_pending": "Estamos esperando la confirmación del pago.",
    "paid": "Recibimos tu pago. Pronto comenzaremos a preparar tu pedido.",
    "preparing": "Estamos preparando tu arreglo floral.",
    "ready_for_pickup": "Tu pedido ya está listo para recoger en tienda.",
    "out_for_delivery": "Tu pedido va en camino a la dirección de entrega.",
    "delivered": "Tu pedido fue entregado. ¡Gracias por comprar en Floristería Yada!",
    "cancelled": "Este pedido fue cancelado. Si tienes dudas, responde este correo.",
}


def order_status_label(status: str) -> str:
    return ORDER_STATUS_LABELS.get(status, status)
