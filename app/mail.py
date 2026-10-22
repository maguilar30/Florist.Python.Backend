from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from decimal import Decimal
from email.message import EmailMessage
from html import escape

from app.config import get_settings
from app.delivery import DELIVERY_LABELS
from app.errors import problem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderLine:
    name: str
    quantity: int
    unit_price: Decimal
    in_stock: bool

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


def _money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01'))}"


def build_order_email(
    *,
    order_id: int | None = None,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    delivery_address: str | None,
    notes: str | None,
    delivery_option: str | None = None,
    delivery_fee: Decimal | None = None,
    lines: list[OrderLine],
) -> tuple[str, str, str]:
    subtotal = sum((line.line_total for line in lines), Decimal("0"))
    fee = delivery_fee if delivery_fee is not None else Decimal("0")
    total = subtotal + fee
    ref = f"#{order_id} — " if order_id is not None else ""
    subject = f"Nuevo pedido {ref}{customer_name} — {_money(total)}"

    item_lines = []
    html_rows = []
    for line in lines:
        stock = "" if line.in_stock else " (agotado en catálogo)"
        item_lines.append(
            f"- {line.quantity} x {line.name} @ {_money(line.unit_price)} = {_money(line.line_total)}{stock}"
        )
        html_rows.append(
            "<tr>"
            f"<td>{escape(line.name)}</td>"
            f"<td>{line.quantity}</td>"
            f"<td>{_money(line.unit_price)}</td>"
            f"<td>{_money(line.line_total)}</td>"
            f"<td>{'Sí' if line.in_stock else 'No'}</td>"
            "</tr>"
        )

    notes_text = notes.strip() if notes else "—"
    address_text = delivery_address.strip() if delivery_address else "—"
    delivery_label = DELIVERY_LABELS.get(delivery_option or "", delivery_option or "—")
    order_line = f"Pedido: #{order_id}\n" if order_id is not None else ""
    text = (
        "Se recibió una solicitud de pedido desde la tienda.\n\n"
        f"{order_line}"
        f"Cliente: {customer_name}\n"
        f"Correo: {customer_email}\n"
        f"Teléfono: {customer_phone}\n"
        f"Entrega: {delivery_label} ({_money(fee)})\n"
        f"Dirección: {address_text}\n"
        f"Notas: {notes_text}\n\n"
        "Artículos:\n"
        + "\n".join(item_lines)
        + f"\n\nSubtotal: {_money(subtotal)}\n"
        + f"Envío: {_money(fee)}\n"
        + f"Total: {_money(total)}\n"
        "El cliente espera que lo contacten para coordinar el pago.\n"
    )
    html = f"""
    <p>Se recibió una solicitud de pedido desde la tienda.</p>
    <p>
      {f'<strong>Pedido:</strong> #{order_id}<br>' if order_id is not None else ''}
      <strong>Cliente:</strong> {escape(customer_name)}<br>
      <strong>Correo:</strong> {escape(customer_email)}<br>
      <strong>Teléfono:</strong> {escape(customer_phone)}<br>
      <strong>Entrega:</strong> {escape(delivery_label)} ({_money(fee)})<br>
      <strong>Dirección:</strong> {escape(address_text)}<br>
      <strong>Notas:</strong> {escape(notes_text)}
    </p>
    <table border="1" cellpadding="6" cellspacing="0">
      <thead>
        <tr><th>Producto</th><th>Cant.</th><th>Precio</th><th>Total</th><th>En stock</th></tr>
      </thead>
      <tbody>
        {''.join(html_rows)}
      </tbody>
    </table>
    <p>
      <strong>Subtotal:</strong> {_money(subtotal)}<br>
      <strong>Envío:</strong> {_money(fee)}<br>
      <strong>Total:</strong> {_money(total)}
    </p>
    <p>El cliente espera que lo contacten para coordinar el pago.</p>
    """
    return subject, text, html


def send_order_notification(
    *,
    order_id: int | None = None,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    delivery_address: str | None = None,
    notes: str | None,
    delivery_option: str | None = None,
    delivery_fee: Decimal | None = None,
    lines: list[OrderLine],
) -> None:
    settings = get_settings()
    subject, text, html = build_order_email(
        order_id=order_id,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        delivery_address=delivery_address,
        notes=notes,
        delivery_option=delivery_option,
        delivery_fee=delivery_fee,
        lines=lines,
    )
    to_addr = settings.order_notify_email

    if not settings.smtp_host:
        if settings.debug:
            logger.warning("SMTP is not configured; order email was not delivered.\nTo: %s\n%s\n%s", to_addr, subject, text)
            return
        raise problem(503, "Mail not configured", "Order email cannot be sent until SMTP is configured.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from or settings.smtp_user or to_addr
    message["To"] = to_addr
    message["Reply-To"] = customer_email
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.exception("Failed to send order email")
        raise problem(502, "Mail error", "The order email could not be sent. Please try again.") from exc
