import asyncio
import aiohttp
import logging
from pymongo import MongoClient

# 🎯 Configuración de logs estilizados
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# 🎯 Configuración de MongoDB
MONGO_URI = "mongodb+srv://sa:Eduardo25@notifinance.zp3mm.mongodb.net"
DB_NAME = "NT"
COLLECTION_NAME = "alerts"
API_URL = "https://api-twelve-613d.onrender.com/get_current_price?symbol={}&crypto=true"

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    logging.info("✅ Conectado a MongoDB → Base de datos: NT | Colección: alerts")
except Exception as e:
    logging.error(f"❌ Error al conectar a MongoDB: {e}")
    exit(1)

async def fetch_price(session, symbol):
    """Obtiene el precio actual de la criptomoneda de forma asíncrona."""
    try:
        async with session.get(API_URL.format(symbol)) as response:
            data = await response.json()
            if 'price' in data:
                price = float(data['price'])
            elif 'current_price' in data:
                price = float(data['current_price'])
            else:
                logging.warning(f"⚠️ Respuesta inválida para {symbol}: {data}")
                return symbol, None
            
            logging.info(f"📊 {symbol} → Precio actual: ${price:,.2f}")
            return symbol, price
    except Exception as e:
        logging.error(f"❌ Error obteniendo precio de {symbol}: {e}")
        return symbol, None

async def send_notification(session, alert, current_price):
    """Envía la notificación de forma asíncrona."""
    notification_url = alert.get("notificationData")
    if not notification_url:
        logging.warning(f"⚠️ No hay URL de notificación para {alert['cryptoSymbol']} (Usuario {alert['userId']})")
        return

    alert_message = (
        f"🚀 **ALERTA DE PRECIO ACTIVADA TU CRYPTO A SIDO VENDIDA** 🚀\n"
        f"👤 Usuario: {alert['username']}\n"
        f"💰 Criptomoneda: {alert['cryptoSymbol']}\n"
        f"📈 Precio actual: ${current_price:,.4f}\n"
        f"🎯 Umbral: {'Por encima' if alert['condition'] else 'Por debajo'} de ${alert['targetPrice']:,.4f}\n"
    )
    payload = {"content": alert_message}

    headers = {
        "Authorization": "Bearer NotifinanceTK",
        "Content-Type": "application/json"
    }

    try:
        async with session.post(notification_url, json=payload, headers=headers) as resp:
            if resp.status in [200, 204]:
                collection.update_one(
                    {"_id": alert["_id"]},
                    {
                        "$set": {
                            "isActive": False,
                           "isFulfilled": True,
                            "updatedAt": asyncio.get_event_loop().time()
                        }
                    }
                )
                logging.info(f"✅ Notificación enviada para {alert['cryptoSymbol']} - Usuario {alert['userId']}")
            else:
                logging.error(f"❌ Error al enviar notificación: {resp.status} - {await resp.text()}")
    except Exception as e:
        logging.error(f"❌ Error al conectar con la URL de notificación: {e}")

async def process_alerts():
    """Procesa alertas activas en MongoDB."""
    logging.info("\n🔄 ----------------------------------------- 🔄")
    logging.info("📡 Buscando alertas activas en la base de datos...")

    active_alerts = list(collection.find({"isActive": True}))
    if not active_alerts:
        logging.info("⏳ No hay alertas activas en este momento.")
        return

    logging.info(f"📢 {len(active_alerts)} alertas activas encontradas.")

    alerts_group = {}
    for alert in active_alerts:
        symbol = alert["cryptoSymbol"]
        alerts_group.setdefault(symbol, []).append(alert)

    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(fetch_price(session, symbol)) for symbol in alerts_group]
        prices = await asyncio.gather(*tasks)

        notification_tasks = []
        for symbol, current_price in prices:
            if current_price is None:
                continue
            for alert in alerts_group[symbol]:
                target_price = alert["targetPrice"]
                condition = alert["condition"]
                if (condition and current_price > target_price) or (not condition and current_price < target_price):
                    logging.info(f"🚨 ALERTA ACTIVADA: {symbol} (Usuario {alert['userId']}) → ${current_price:,.4f} {'>' if condition else '<'} ${target_price:,.4f}")
                    notification_tasks.append(asyncio.create_task(send_notification(session, alert, current_price)))

        if notification_tasks:
            await asyncio.gather(*notification_tasks)

async def main_loop():
    """Bucle principal de monitoreo de alertas."""
    logging.info("\n🚀 Iniciando el monitoreo de alertas...\n")
    while True:
        await process_alerts()
        logging.info("⏳ Esperando 10 segundos antes de la próxima verificación...\n")
        await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main_loop())
