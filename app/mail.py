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
from app.order_status import ORDER_STATUS_CUSTOMER_NOTES, order_status_label

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
    return f"₡{value.quantize(Decimal('0.01')):,.2f}"


def build_order_email(
    *,
    order_id: int | None = None,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    delivery_address: str | None,
    notes: str | None,
    delivery_option: str | None = None,
    delivery_label: str | None = None,
    delivery_fee: Decimal | None = None,
    discount_code: str | None = None,
    discount_amount: Decimal | None = None,
    loyalty_reward: str | None = None,
    loyalty_discount_amount: Decimal | None = None,
    lines: list[OrderLine],
) -> tuple[str, str, str]:
    subtotal = sum((line.line_total for line in lines), Decimal("0"))
    fee = delivery_fee if delivery_fee is not None else Decimal("0")
    discount = discount_amount if discount_amount is not None else Decimal("0")
    loyalty_discount = loyalty_discount_amount if loyalty_discount_amount is not None else Decimal("0")
    total = subtotal - discount - loyalty_discount + fee
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
    delivery_label = delivery_label or DELIVERY_LABELS.get(delivery_option or "", delivery_option or "—")
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
        + (f"Descuento ({discount_code}): -{_money(discount)}\n" if discount > 0 and discount_code else "")
        + (
            f"Fidelidad ({loyalty_reward}): -{_money(loyalty_discount)}\n"
            if loyalty_reward and loyalty_discount > 0
            else (f"Fidelidad: {loyalty_reward}\n" if loyalty_reward else "")
        )
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
      {f'<strong>Descuento ({escape(discount_code)}):</strong> -{_money(discount)}<br>' if discount > 0 and discount_code else ''}
      {f'<strong>Fidelidad ({escape(loyalty_reward)}):</strong> -{_money(loyalty_discount)}<br>' if loyalty_reward and loyalty_discount > 0 else (f'<strong>Fidelidad:</strong> {escape(loyalty_reward)}<br>' if loyalty_reward else '')}
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
    delivery_label: str | None = None,
    delivery_fee: Decimal | None = None,
    discount_code: str | None = None,
    discount_amount: Decimal | None = None,
    loyalty_reward: str | None = None,
    loyalty_discount_amount: Decimal | None = None,
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
        delivery_label=delivery_label,
        delivery_fee=delivery_fee,
        discount_code=discount_code,
        discount_amount=discount_amount,
        loyalty_reward=loyalty_reward,
        loyalty_discount_amount=loyalty_discount_amount,
        lines=lines,
    )
    send_email(
        to_addr=settings.order_notify_email,
        subject=subject,
        text=text,
        html=html,
        reply_to=customer_email,
        purpose="order",
    )


def send_order_status_email(
    *,
    order_id: int,
    customer_name: str,
    customer_email: str,
    status: str,
    total: Decimal,
) -> None:
    settings = get_settings()
    label = order_status_label(status)
    note = ORDER_STATUS_CUSTOMER_NOTES.get(status, "")
    account_url = f"{settings.frontend_url.rstrip('/')}/cuenta#pedidos"
    subject = f"Pedido #{order_id} — {label}"
    text = (
        f"Hola {customer_name},\n\n"
        f"El estado de tu pedido #{order_id} ahora es: {label}.\n"
        f"{note}\n\n"
        f"Total: {_money(total)}\n"
        f"Puedes ver el detalle en tu cuenta:\n{account_url}\n\n"
        "Floristería Yada\n"
    )
    html = f"""
    <p>Hola {escape(customer_name)},</p>
    <p>El estado de tu pedido <strong>#{order_id}</strong> ahora es: <strong>{escape(label)}</strong>.</p>
    <p>{escape(note)}</p>
    <p>Total: {_money(total)}</p>
    <p><a href="{escape(account_url)}">Ver mis pedidos</a></p>
    <p>Floristería Yada</p>
    """
    send_email(
        to_addr=customer_email,
        subject=subject,
        text=text,
        html=html,
        purpose="order status",
    )


def send_contact_message_email(
    *, name: str, email: str, phone: str = "", body: str, message_id: int | None = None
) -> None:
    settings = get_settings()
    ref = f"#{message_id} — " if message_id is not None else ""
    subject = f"Nuevo mensaje de contacto {ref}{name}"
    id_line = f"Mensaje: #{message_id}\n" if message_id is not None else ""
    text = (
        "Se recibió un mensaje desde la página de contacto.\n\n"
        f"{id_line}"
        f"Nombre: {name}\n"
        f"Correo: {email}\n"
        f"Teléfono: {phone or '—'}\n\n"
        f"{body}\n"
    )
    html = f"""
    <p>Se recibió un mensaje desde la página de contacto.</p>
    <p>
      {f'<strong>Mensaje:</strong> #{message_id}<br>' if message_id is not None else ''}
      <strong>Nombre:</strong> {escape(name)}<br>
      <strong>Correo:</strong> {escape(email)}<br>
      <strong>Teléfono:</strong> {escape(phone or '—')}
    </p>
    <p>{escape(body).replace(chr(10), '<br>')}</p>
    """
    send_email(
        to_addr=settings.order_notify_email,
        subject=subject,
        text=text,
        html=html,
        reply_to=email,
        purpose="contact",
    )


def send_password_reset_email(*, to_addr: str, full_name: str, reset_url: str) -> None:
    subject = "Restablecer tu contraseña — Floristería Yada"
    text = (
        f"Hola {full_name},\n\n"
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta.\n"
        f"Abre este enlace (válido por una hora):\n{reset_url}\n\n"
        "Si no pediste este cambio, puedes ignorar este correo.\n"
    )
    html = f"""
    <p>Hola {escape(full_name)},</p>
    <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta en Floristería Yada.</p>
    <p><a href="{escape(reset_url)}">Restablecer contraseña</a></p>
    <p>El enlace caduca en una hora. Si no pediste este cambio, ignora este correo.</p>
    """
    send_email(to_addr=to_addr, subject=subject, text=text, html=html, purpose="password reset")


def send_email(
    *,
    to_addr: str,
    subject: str,
    text: str,
    html: str,
    reply_to: str | None = None,
    purpose: str = "email",
) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        if settings.debug:
            logger.warning("SMTP is not configured; %s was not delivered.\nTo: %s\n%s\n%s", purpose, to_addr, subject, text)
            return
        raise problem(503, "Mail not configured", "Email cannot be sent until SMTP is configured.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from or settings.smtp_user or to_addr
    message["To"] = to_addr
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            print(settings.smtp_user, settings.smtp_password, to_addr, settings.smtp_use_tls)
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.exception("Failed to send %s email", purpose)
        raise problem(502, "Mail error", "The email could not be sent. Please try again.") from exc
