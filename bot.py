import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from PIL import Image, ImageOps
import pytesseract
from io import BytesIO

# Configuración básica de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Estados para las conversaciones
(MAIN_MENU, PRODUCTS, PAYMENT, FAQ, REFERRALS, WAITING_RECEIPT) = range(6)

# Diccionario simple para almacenar referencias (en una implementación real usarías una base de datos)
referrals = {}

# Cache para evitar duplicados
processed_photos = set()

# Configuración para botones fijos en escritorio
def create_reply_keyboard(buttons, one_time_keyboard=False):
    """Crea un teclado de respuesta con botones fijos donde se escribe"""
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=one_time_keyboard)

# Para los teclados inline que seguiremos usando en algunos casos
def create_inline_keyboard(buttons):
    """Crea un teclado con botones inline"""
    return InlineKeyboardMarkup(buttons)

# Función para validar texto extraído
def validate_receipt_text(text):
    keywords = [
        # Spanish keywords
        "BANCO", "PAYPAL", "TRANSFERENCIA", "DEPÓSITO",
        "OXXO", "SANTANDER", "BANAMEX", "CITIBANAMEX",
        "CAJERO", "COMPROBANTE", "RECIBO", "REFERENCIA",
        "ABONO", "PAGO", "OPERACIÓN EXITOSA", "IMPORTE TRANSFERIDO",
        "TRANSACCIÓN", "REMITENTE", "DESTINATARIO", "MONTO",
        "CANTIDAD", "CONFIRMACIÓN", "CUENTA", "RETIRO",
        "ESTADO DE CUENTA", "SALDO", "CRÉDITO", "DÉBITO",
        "TRANSFERENCIA BANCARIA", "GIRO", "REMESA", "NÚMERO DE OPERACIÓN",
        "PAGO PROCESADO", "APROBADO", "AUTORIZADO", "NÚMERO DE CONFIRMACIÓN",
        "TRANSFERENCIA ELECTRÓNICA", "BENEFICIARIO", "PAGADO", "COMPLETADO",
        "BITCOIN", "CRIPTOMONEDA", "BILLETERA", "MONEDERO DIGITAL",
        "INTERCAMBIO", "BBVA", "BANCOMER", "HSBC",
        "BANORTE", "SCOTIABANK", "INBURSA", "AFIRME",
        "BANJERCITO", "BANCOPPEL", "BANCO AZTECA", "SPEI",
        "CLABE", "TARJETA", "EFECTIVO", "MOVIMIENTO",
        "TERMINAL", "PUNTO DE VENTA", "TPV", "COMISIÓN",
        "CARGO", "ABONO", "FECHA VALOR", "CONCEPTO",
        "FOLIO", "CLAVE DE RASTREO", "ENVÍO", "RECEPCIÓN",
        
        # English keywords
        "TRANSACTION", "SENDER", "PAYMENT", "RECEIPT", 
        "TRANSFER", "BANK", "AMOUNT", "SUCCESSFUL",
        "CONFIRMATION", "REFERENCE", "ACCOUNT", "DEPOSIT",
        "WITHDRAWAL", "STATEMENT", "BALANCE", "CREDIT",
        "DEBIT", "WIRE TRANSFER", "MONEY ORDER", "REMITTANCE",
        "TRANSACTION ID", "PAYMENT PROCESSED", "APPROVED", "AUTHORIZED",
        "CONFIRMATION NUMBER", "ELECTRONIC TRANSFER", "ACH", "SWIFT",
        "ROUTING NUMBER", "BENEFICIARY", "PAID", "COMPLETED",
        "BITCOIN", "CRYPTO", "BLOCKCHAIN", "WALLET",
        "EXCHANGE", "BINANCE", "COINBASE", "TETHER"
    ]
    found_keywords = [keyword for keyword in keywords if keyword in text.upper()]
    if found_keywords:
        return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando inicial que muestra el menú principal."""
    user = update.effective_user
    
    # Verificar si el usuario fue referido por alguien
    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
        try:
            # Validar que el ID del referente sea numérico
            int(referrer_id)
            # Añadir al usuario actual a la lista de referidos del referente
            if referrer_id not in referrals:
                referrals[referrer_id] = []
            if str(user.id) not in referrals[referrer_id]:
                referrals[referrer_id].append(str(user.id))
                await update.message.reply_text(
                    f"🎁 ¡Has sido referido por un usuario VIP! Recibirás un 10% de descuento en tu primera compra. 🎁"
                )
        except ValueError:
            # Si el ID no es válido, ignoramos silenciosamente
            pass
    
    welcome_message = f"""
🌟 *¡BIENVENIDO A PREMIUM CARDS, {user.first_name}!* 🌟

Has accedido al servicio exclusivo de tarjetas premium con la mayor tasa de éxito del mercado.

✅ *¿QUÉ NOS DIFERENCIA?*
• Material verificado 100% live ✓
• Soporte 24/7 personalizado 🛎️
• Garantía de reemplazo en todas nuestras tarjetas 🔄
• Los mejores precios del mercado 💲
• Más de 5 años de experiencia en el sector 🏆

🔥 *OFERTA DE BIENVENIDA:* 15% de descuento en tu primera compra usando el código "WELCOME15" 🎉

⚠️ *IMPORTANTE:* Únete a nuestro canal de respaldo @RespaldoSAULGOODMAN para estar siempre conectado en caso de caídas.

Selecciona una opción para comenzar tu experiencia premium:
"""
    
    keyboard = [
        [KeyboardButton("🛒 Productos Premium"), KeyboardButton("💰 Pagar Ahora")],
        [KeyboardButton("❓ Preguntas Frecuentes"), KeyboardButton("👥 Programa de Referencias VIP")],
    ]
    
    reply_markup = create_reply_keyboard(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja los mensajes de texto del usuario (para los botones de respuesta)."""
    text = update.message.text
    
    # Menú principal
    if text == "🛒 Productos Premium":
        return await products_menu(update, context)
    elif text == "💰 Pagar Ahora":
        return await payment_menu(update, context)
    elif text == "❓ Preguntas Frecuentes":
        return await faq_menu(update, context)
    elif text == "👥 Programa de Referencias VIP":
        return await referrals_menu(update, context)
    elif text == "⬅️ Volver al Menú":
        return await main_menu(update, context)
    
    # Menús secundarios
    elif text == "🔥 Oferta Especial":
        return await special_offer(update, context)
    elif text == "📸 Enviar Comprobante":
        return await request_receipt(update, context)
    
    # Selección de productos
    elif text.startswith(("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "1️1️⃣")):
        return await product_selected(update, context)
    
    # Si no coincide con ningún botón, informar al usuario
    await update.message.reply_text(
        "⚠️ Comando no identificado. Por favor, presiona /start para iniciar el bot correctamente."
    )
    return MAIN_MENU

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa las fotos de comprobantes de pago."""
    if update.message.photo:
        user = update.message.from_user
        username = user.username or "Usuario sin username"
        photo = update.message.photo[-1].file_id

        if photo in processed_photos:
            await update.message.reply_text("⚠️ Este comprobante ya ha sido procesado. Por favor envía uno nuevo si necesitas realizar otro pago. 🔄")
            return WAITING_RECEIPT

        processed_photos.add(photo)
        await update.message.reply_text("✅ Comprobante recibido. Validando... Por favor espera un momento. 🕒")

        try:
            # Descargar y procesar la foto en memoria
            photo_file = await context.bot.get_file(photo)
            photo_stream = BytesIO()
            await photo_file.download_to_memory(photo_stream)

            # Procesar la imagen con PIL
            img = Image.open(photo_stream)
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)
            
            # Intentar extraer texto si Tesseract está configurado
            try:
                extracted_text = pytesseract.image_to_string(img, lang='spa')
                is_valid = validate_receipt_text(extracted_text)
            except Exception as tesseract_error:
                logging.warning(f"Error en Tesseract: {tesseract_error}")
                # Si falla Tesseract, asumimos que es válido
                is_valid = True

            # Guardar información del producto seleccionado
            product_info = ""
            if "selected_product" in context.user_data:
                product_info = f"\n📦 Producto: {context.user_data['selected_product']}"
                if "selected_price" in context.user_data:
                    product_info += f"\n💰 Precio: ${context.user_data['selected_price']} MXN"

            # Enviar al canal de administración
            await context.bot.send_photo(
                chat_id="-1002589488630",  # ID del canal donde se enviarán los comprobantes
                photo=photo,
                caption=f"📥 Nuevo comprobante de pago.\n👤 Usuario: {user.first_name} (@{username}).{product_info}\n🆔 ID: {user.id}"
            )
            
            await update.message.reply_text(
                "✅ ¡Comprobante recibido con éxito! Tu pago será procesado en breve y recibirás tu material. 🔥\n\n"
                "Un administrador se pondrá en contacto contigo pronto. ⏱️"
            )
            
            # Volver al menú principal
            return await main_menu(update, context)
            
        except Exception as e:
            logging.error(f"Error procesando comprobante: {e}")
            await update.message.reply_text(
                "❌ Error procesando el comprobante. Por favor asegúrate que la imagen sea clara y vuelve a intentarlo. "
                "Si el problema persiste, contacta al administrador. ⏳"
            )
            return WAITING_RECEIPT
    else:
        await update.message.reply_text(
            "📸 Por favor, envía una foto clara de tu comprobante de pago.\n\n"
            "Asegúrate de que se vean todos los detalles de la transacción."
        )
        return WAITING_RECEIPT

async def request_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Solicita al usuario que envíe un comprobante de pago."""
    await update.message.reply_text(
        "📸 *ENVÍO DE COMPROBANTE DE PAGO* 📸\n\n"
        "Por favor, envía una foto clara de tu comprobante de pago.\n\n"
        "✅ *CONSEJOS PARA UN PROCESAMIENTO RÁPIDO:*\n"
        "• Asegúrate de que se vean todos los detalles de la transacción\n"
        "• La imagen debe estar bien iluminada y enfocada\n"
        "• Incluye la fecha y hora de la transacción\n"
        "• Si es transferencia, asegúrate que se vea el número de referencia\n\n"
        "⏱️ Tu comprobante será procesado inmediatamente.",
        parse_mode='Markdown'
    )
    return WAITING_RECEIPT

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja las pulsaciones de botones inline (para casos específicos)."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "main_menu":
        await main_menu(update, context)
        return MAIN_MENU
    
    return MAIN_MENU

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú principal."""
    keyboard = [
        [KeyboardButton("🛒 Productos Premium"), KeyboardButton("💰 Pagar Ahora")],
        [KeyboardButton("❓ Preguntas Frecuentes"), KeyboardButton("👥 Programa de Referencias VIP")],
    ]
    
    reply_markup = create_reply_keyboard(keyboard)
    
    menu_text = """
📋 *MENÚ PRINCIPAL* 📋

Selecciona una opción:

🛒 *Productos Premium* - Ver nuestro catálogo de productos
💰 *Pagar Ahora* - Realizar un pago por un producto
❓ *Preguntas Frecuentes* - Resolver tus dudas
👥 *Programa de Referencias VIP* - Gana recompensas por referir amigos
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text="Volviendo al menú principal..."
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=menu_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text=menu_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    return MAIN_MENU

async def special_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra la oferta especial."""
    mensaje = """
🔥 *OFERTA ESPECIAL LIMITADA* 🔥

⚡ *PACK PREMIUM 10 TARJETAS AMEX*
   • Precio normal: $4,500 MXN
   • Precio oferta: $3,500 MXN
   • Ahorro: $1,000 MXN (22%)
   • Tasa de éxito: 95%
   • Incluye: Soporte 24/7 + Reemplazo garantizado

⏰ Esta oferta expira en 24 horas. ¡No esperes más!

👉 Selecciona "📸 Enviar Comprobante" para realizar tu pago y aprovechar esta promoción exclusiva.
"""
    
    keyboard = [
        [KeyboardButton("📸 Enviar Comprobante")],
        [KeyboardButton("⬅️ Volver al Menú")],
    ]
    
    reply_markup = create_reply_keyboard(keyboard)
    
    await update.message.reply_text(
        text=mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return PRODUCTS

async def payment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra las opciones de pago."""
    mensaje = """
💰 *MÉTODOS DE PAGO SEGUROS* 💰

Aceptamos los siguientes métodos de pago:

🔐 *CRIPTOMONEDAS (RECOMENDADO):*

• *Bitcoin (BTC):*
```
bc1qnctxqv5x3mkxts0wwjhrf7jfgkveskefgjzvxc
```

• *Tether (USDT):*
```
TVEzPvhRKiZJxDBDXyu5wBaYp6GNS3n13N
```

• *Dogecoin (DOGE):*
```
D8pxbdYEjE5gAdgu6iZ4PvuuMENFYhJLhx
```

• *Binance Coin (BNB):*
```
0x5b0d069c697637870FE9E44216039CdacBe65F22
```

💳 *TRANSFERENCIA BANCARIA:*

• *CUENTA:*
```
943393460018
```

• *CLABE:*
```
058597000070781636
```

• *TITULAR:*
```
Juan Jesús Salcido dominguez
```

• *DEPÓSITO OXXO (TARJETA):*
```
4741742972795879
```

⚠️ *IMPORTANTE*: 
• Envía foto del comprobante de pago usando el botón de abajo
• Especifica qué producto estás comprando
• Recibirás tu material en minutos tras confirmar el pago

🔒 *PROCESO DE COMPRA:*
1️⃣ Realiza tu pago
2️⃣ Envía comprobante con el botón de abajo
3️⃣ Recibe tu material en minutos
"""
    
    keyboard = [
        [KeyboardButton("📸 Enviar Comprobante")],
        [KeyboardButton("⬅️ Volver al Menú")],
    ]
    
    reply_markup = create_reply_keyboard(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=mensaje, parse_mode='Markdown')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Selecciona una opción:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text=mensaje, parse_mode='Markdown')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Selecciona una opción:",
            reply_markup=reply_markup
        )
    
    return PAYMENT

async def faq_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra las preguntas frecuentes."""
    mensaje = """
❓ *PREGUNTAS FRECUENTES* ❓

*¿Qué es el carding?*
El carding es el uso de información de tarjetas para realizar compras o transacciones en línea.

*¿Las tarjetas tienen garantía?*
Sí, todas nuestras tarjetas tienen garantía de reemplazo si no funcionan en las primeras 24 horas.

*¿El curso incluye material?*
Sí, todos nuestros cursos incluyen tarjetas para practicar. El curso básico incluye 3 tarjetas y el avanzado 7 tarjetas premium.

*¿Qué necesito para comenzar?*
Si eres principiante, recomendamos empezar con nuestro curso básico. Si ya tienes experiencia, puedes adquirir directamente nuestras tarjetas premium.

*¿Tienen soporte después de la compra?*
Sí, ofrecemos soporte técnico 24/7 para resolver cualquier duda o problema que puedas tener.

*¿Cómo sé que el material funciona?*
Nuestro material es verificado antes de ser enviado y tiene una tasa de éxito del 93%. Además, ofrecemos garantía de reemplazo.

*¿Cuánto tiempo tarda en llegar el material?*
El material se entrega de forma inmediata después de confirmar el pago, generalmente en menos de 5 minutos.

*¿Ofrecen descuentos por volumen?*
Sí, tenemos paquetes especiales con descuentos significativos para compras de 5, 10 o más tarjetas.
"""
    
    keyboard = [
        [KeyboardButton("💰 Pagar Ahora"), KeyboardButton("⬅️ Volver al Menú")],
    ]
    
    reply_markup = create_reply_keyboard(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=mensaje, parse_mode='Markdown')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Selecciona una opción:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text=mensaje, parse_mode='Markdown')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Selecciona una opción:",
            reply_markup=reply_markup
        )
    
    return FAQ

async def referrals_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el sistema de referidos mejorado."""
    user_id = str(update.effective_user.id)
    
    # Crear un enlace de referido único
    bot = await context.bot.get_me()
    referral_link = f"https://t.me/{bot.username}?start={user_id}"
    
    # Contar referidos
    user_referrals = len(referrals.get(user_id, []))
    
    mensaje = f"""
👑 *PROGRAMA DE REFERENCIAS VIP* 👑

Tu enlace personal de referido:
`{referral_link}`

Has referido a: *{user_referrals} personas*

*NUEVOS BENEFICIOS EXCLUSIVOS:*

🔹 *Nivel Bronce (3 referidos):*
   - 15% de descuento en tu próxima compra
   - Acceso a material exclusivo
   - 1 tarjeta VISA gratis

🔹 *Nivel Plata (7 referidos):*
   - 2 tarjetas premium gratis
   - 25% de descuento en el curso básico
   - Soporte prioritario 24/7
   - Acceso a grupo privado de tips

🔹 *Nivel Oro (15 referidos):*
   - 5 tarjetas premium gratis
   - 50% de descuento en cualquier curso
   - Acceso a grupo VIP de carding
   - Mentoría personalizada (1 hora)

🔹 *Nivel Diamante (25+ referidos):*
   - Curso completo GRATIS
   - 10 tarjetas premium gratis
   - Comisión del 15% por cada compra de tus referidos
   - Acceso a material exclusivo de alta gama
   - Mentoría VIP ilimitada por 1 mes

⚡ *PROMOCIÓN ESPECIAL*: Por tiempo limitado, cada nuevo referido te da una entrada a nuestro sorteo mensual de $1,000 USD en crypto.

💎 *BONO EXTRA*: Si alcanzas 50 referidos, recibirás un paquete completo valorado en $10,000 totalmente GRATIS.

Comparte tu enlace ahora y comienza a ganar.
"""
    
    # Para compartir el enlace, usamos un botón inline
    inline_keyboard = [
        [InlineKeyboardButton("📲 Compartir Enlace", switch_inline_query=f"Te invito a unirte con mi enlace: {referral_link}")]
    ]
    inline_markup = create_inline_keyboard(inline_keyboard)
    
    keyboard = [
        [KeyboardButton("⬅️ Volver al Menú")],
    ]
    reply_markup = create_reply_keyboard(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=mensaje, parse_mode='Markdown')
        # Enviamos el botón para compartir como un mensaje separado con teclado inline
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Haz clic para compartir tu enlace:",
            reply_markup=inline_markup
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="O vuelve al menú principal:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text=mensaje, parse_mode='Markdown')
        # Enviamos el botón para compartir como un mensaje separado con teclado inline
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Haz clic para compartir tu enlace:",
            reply_markup=inline_markup
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="O vuelve al menú principal:",
            reply_markup=reply_markup
        )
    
    return REFERRALS

async def products_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú de productos."""
    mensaje = """
🔥 *CATÁLOGO DE PRODUCTOS PREMIUM* 🔥

💳 *TARJETAS PREMIUM:*
1️⃣ AMEX Platinum 💎 - $450 MXN (95% éxito)
2️⃣ VISA Signature 🔵 - $400 MXN (93% éxito)
3️⃣ MasterCard Black ⚫ - $420 MXN (94% éxito)
4️⃣ Discover 🟠 - $380 MXN (90% éxito)

📦 *PACKS ESPECIALES:*
5️⃣ Pack 5 AMEX 📦 - $2,000 MXN (AHORRA $250)
6️⃣ Pack 10 AMEX 📦📦 - $3,500 MXN (AHORRA $1,000)
7️⃣ Pack Mixto 🔄 - $3,800 MXN (10 tarjetas variadas)

📚 *CURSOS Y MENTORÍA:*
8️⃣ Curso Básico 📚 - $1,500 MXN (Incluye 3 tarjetas)
9️⃣ Curso Avanzado 🎓 - $3,500 MXN (Incluye 7 tarjetas)
🔟 Mentoría 1:1 👨‍🏫 - $5,000 MXN (5 sesiones + material)

💵 *BILLETES CLONADOS:*
1️1️⃣ Billetes Clon Premium 💵 - Pasan Rayos UV y Plumón
   • $500 (cafés y azules)
   • $200 y $100
   
   📦 *PROMOCIONES BILLETES:*
   • $2,000 invertidos = $10,000 en billetes 💸
   • $5,000 invertidos = $23,000 en billetes 💰
   • $10,000 invertidos = $50,000 en billetes 🤑
   • Pedido mínimo para envío por DHL

⚡ *TODOS NUESTROS PRODUCTOS INCLUYEN:*
✅ Garantía de reemplazo
✅ Soporte técnico 24/7
✅ Entrega inmediata tras confirmación
✅ Material verificado y probado

🔥 *OFERTA ESPECIAL:* 15% DESCUENTO en tu primera compra con código "WELCOME15"

👇 *Selecciona un producto para ver más detalles*
"""
    
    keyboard = [
        [KeyboardButton("1️⃣ AMEX Platinum 💎"), KeyboardButton("2️⃣ VISA Signature 🔵")],
        [KeyboardButton("3️⃣ MasterCard Black ⚫"), KeyboardButton("4️⃣ Discover 🟠")],
        [KeyboardButton("5️⃣ Pack 5 AMEX 📦"), KeyboardButton("6️⃣ Pack 10 AMEX 📦📦")],
        [KeyboardButton("7️⃣ Pack Mixto 🔄"), KeyboardButton("8️⃣ Curso Básico 📚")],
        [KeyboardButton("9️⃣ Curso Avanzado 🎓"), KeyboardButton("🔟 Mentoría 1:1 👨‍🏫")],
        [KeyboardButton("1️1️⃣ Billetes Clon Premium 💵")],
        [KeyboardButton("🔥 Oferta Especial"), KeyboardButton("⬅️ Volver al Menú")],
    ]
    
    reply_markup = create_reply_keyboard(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=mensaje, parse_mode='Markdown')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Selecciona un producto para ver más detalles:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text=mensaje, parse_mode='Markdown')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Selecciona un producto para ver más detalles:",
            reply_markup=reply_markup
        )
    
    return PRODUCTS

async def product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de un producto específico."""
    product_text = update.message.text
    
    # Mapeo de productos a precios
    product_prices = {
        "1️⃣ AMEX Platinum 💎": 450,
        "2️⃣ VISA Signature 🔵": 400,
        "3️⃣ MasterCard Black ⚫": 420,
        "4️⃣ Discover 🟠": 380,
        "5️⃣ Pack 5 AMEX 📦": 2000,
        "6️⃣ Pack 10 AMEX 📦📦": 3500,
        "7️⃣ Pack Mixto 🔄": 3800,
        "8️⃣ Curso Básico 📚": 1500,
        "9️⃣ Curso Avanzado 🎓": 3500,
        "🔟 Mentoría 1:1 👨‍🏫": 5000,
        "1️1️⃣ Billetes Clon Premium 💵": 2000
    }
    
    # Obtener el precio del producto seleccionado
    if product_text in product_prices:
        product_name = product_text.split(" ", 1)[1] if " " in product_text else product_text
        price = product_prices[product_text]
        
        # Caso especial para billetes clonados
        if "Billetes Clon Premium" in product_text:
            mensaje = f"""
💵 *BILLETES CLON PREMIUM* 💵

🔍 *CARACTERÍSTICAS SUPERIORES:*
✅ Pasan prueba de Rayos UV ☢️
✅ Pasan prueba de Plumón detector 🖌️
✅ Alta calidad de impresión HD 🖨️
✅ Textura y peso similar al original 👌
✅ Marca de agua visible a contraluz 🔎

💰 *DENOMINACIONES DISPONIBLES:*
• $500 MXN (versiones café y azul) 🟤🔵
• $200 MXN (versión verde) 🟢
• $100 MXN (versión roja) 🔴

📦 *PROMOCIONES ESPECIALES* 🔥:
• $2,000 invertidos ➡️ $10,000 en billetes 💸 (x5 tu inversión)
• $5,000 invertidos ➡️ $23,000 en billetes 💰 (x4.6 tu inversión)
• $10,000 invertidos ➡️ $50,000 en billetes 🤑 (x5 tu inversión)

🚚 *ENVÍO Y LOGÍSTICA:*
• Pedido mínimo para envío por DHL ‼️
• Entrega discreta y segura en toda la República 📬
• Empaque especial anti-detección 🔒
• Seguimiento en tiempo real 📱

⚠️ *IMPORTANTE:*
• Puedes elegir combinación de billetes (cafés, azules o verdes)
• Pedidos mayores a $10,000 reciben envío GRATIS 🎁
• Disponibilidad inmediata ⚡
• Reposición garantizada en caso de pérdida postal 🔄

💳 *MÉTODOS DE PAGO ACEPTADOS:*

🔐 *CRIPTOMONEDAS (RECOMENDADO):*

• *Bitcoin (BTC):*
```
bc1qnctxqv5x3mkxts0wwjhrf7jfgkveskefgjzvxc
```

• *Tether (USDT):*
```
TVEzPvhRKiZJxDBDXyu5wBaYp6GNS3n13N
```

• *Dogecoin (DOGE):*
```
D8pxbdYEjE5gAdgu6iZ4PvuuMENFYhJLhx
```

• *Binance Coin (BNB):*
```
0x5b0d069c697637870FE9E44216039CdacBe65F22
```

🏦 *TRANSFERENCIA BANCARIA:*

• *CUENTA:*
```
943393460018
```

• *CLABE:*
```
058597000070781636
```

• *TITULAR:*
```
Juan Jesús Salcido dominguez
```

• *DEPÓSITO OXXO (TARJETA):*
```
4741742972795879
```

🔒 *PROCESO DE COMPRA SEGURO:*
1️⃣ Realiza tu pago por el monto deseado
2️⃣ Envía comprobante con el botón de abajo
3️⃣ Especifica denominaciones deseadas y dirección de envío
4️⃣ Recibe confirmación y código de seguimiento
5️⃣ Disfruta de tu producto premium

Para continuar con tu compra, realiza el pago y envía el comprobante 📸
"""
        else:
            # Mensaje normal para otros productos
            mensaje = f"""
🛒 *PRODUCTO SELECCIONADO:* {product_name}
💵 *PRECIO:* ${price} MXN

✅ *Si estás seguro de tu compra, realiza el pago y envía la foto del comprobante* 📸

Utiliza cualquiera de los siguientes métodos de pago:

🔐 *CRIPTOMONEDAS (RECOMENDADO):*

• *Bitcoin (BTC):*
```
bc1qnctxqv5x3mkxts0wwjhrf7jfgkveskefgjzvxc
```

• *Tether (USDT):*
```
TVEzPvhRKiZJxDBDXyu5wBaYp6GNS3n13N
```

• *Dogecoin (DOGE):*
```
D8pxbdYEjE5gAdgu6iZ4PvuuMENFYhJLhx
```

• *Binance Coin (BNB):*
```
0x5b0d069c697637870FE9E44216039CdacBe65F22
```

🏦 *TRANSFERENCIA BANCARIA:*

• *CUENTA:*
```
943393460018
```

• *CLABE:*
```
058597000070781636
```

• *TITULAR:*
```
Juan Jesús Salcido dominguez
```

• *DEPÓSITO OXXO (TARJETA):*
```
4741742972795879
```

⚠️ *IMPORTANTE*: 
• Envía foto del comprobante de pago usando el botón de abajo
• Especifica qué producto estás comprando
• Recibirás tu material en minutos tras confirmar el pago

🔒 *PROCESO DE COMPRA:*
1️⃣ Realiza tu pago
2️⃣ Envía comprobante con el botón de abajo
3️⃣ Recibe tu material en minutos
"""
        
        # Guardar la selección en el contexto del usuario
        context.user_data["selected_product"] = product_name
        context.user_data["selected_price"] = price
        
        keyboard = [
            [KeyboardButton("📸 Enviar Comprobante")],
            [KeyboardButton("⬅️ Volver al Menú")],
        ]
        
        reply_markup = create_reply_keyboard(keyboard)
        
        await update.message.reply_text(
            text=mensaje,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return PAYMENT
    else:
        await update.message.reply_text(
            "⚠️ Producto no reconocido. Por favor, selecciona una opción válida."
        )
        return await products_menu(update, context)

def main() -> None:
    """Inicia el bot."""
    try:
        # Token del bot obtenido de BotFather
        token = os.environ.get("TELEGRAM_TOKEN", "7476575828:AAGlDaQmH8w4rf0oLyTba8z6duJ91E4QFBo")
        application = Application.builder().token(token).build()
        
        # Manejador de conversación principal
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
                    CallbackQueryHandler(button_callback)
                ],
                PRODUCTS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
                    CallbackQueryHandler(button_callback)
                ],
                PAYMENT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
                    CallbackQueryHandler(button_callback)
                ],
                FAQ: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
                    CallbackQueryHandler(button_callback)
                ],
                REFERRALS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
                    CallbackQueryHandler(button_callback)
                ],
                WAITING_RECEIPT: [
                    MessageHandler(filters.PHOTO, handle_receipt),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
            },
            fallbacks=[CommandHandler("start", start)],
        )
        
        # Manejador para mensajes fuera de la conversación
        application.add_handler(conv_handler)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))
        
        # Manejador para errores
        application.add_error_handler(error_handler)
        
        # Inicia el bot
        logging.info("Bot iniciado correctamente")
        application.run_polling()
    except Exception as e:
        logging.error(f"Error al iniciar el bot: {e}")

async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto desconocidos fuera de la conversación."""
    await update.message.reply_text(
        "⚠️ Comando no identificado. Por favor, presiona /start para iniciar el bot correctamente."
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja errores y los registra."""
    logging.error(f"Error: {context.error} - Update: {update}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Ha ocurrido un error inesperado. Por favor, intenta nuevamente o contacta al administrador."
            )
    except Exception as e:
        logging.error(f"Error al manejar el error: {e}")

if __name__ == "__main__":
    main()