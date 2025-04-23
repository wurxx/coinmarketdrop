import aiohttp
from time import *
import asyncio
import bs4
import json
import logging
from config import *
import hmac
import hashlib
import datetime
from urllib.parse import urlencode
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)



bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))


with open("a.json") as f:
    alertH = json.loads(f.read())

async def coinWork(coin, Mex, MexTicker):    
    Coin = None
    async with aiohttp.ClientSession() as s:
            async with s.get(f"https://coinmarketcap.com/currencies/{coin['slug']}") as r:
                html = await r.text()
    if html == '':logging.error(f'Ошибка при получении монеты coinmarketcap.com/currencies/{coin['slug']}');return
    soup = bs4.BeautifulSoup(html, 'html.parser')

    script_tag = soup.find("script", id="__NEXT_DATA__")
    json_text = script_tag.string
    data = json.loads(json_text) #данные монеты
    contract = None
    for x in data['props']['pageProps']['detailRes']['detail']['urls']['explorer']:
        
        if 'https://bscscan.com/token/' in x:
            contract = x.split('/')[-1]
            break
        if 'https://app.nansen.ai/' in x:
            contract = x.split('tokenAddress=')[-1]
            break
        if 'https://chiliscan.com/token/' in x:
            contract = x.split('/')[-1]
            break
        if 'https://explorer.chiliz.com/tokens' in x:
            contract = x.split('/')[-2]
            break
        if 'https://scrollscan.com/token' in x:
            contract = x.split('/')[-1]
            break
        if 'https://explorer.aptoslabs.com/account/' in x:
            contract = x.split('/')[-1]
            break
    for m in Mex: 
        contractMex = m['networkList'][0].get('contract')
        if contractMex == None:continue
        contractMex = contractMex.split(':')[0]
        if contract==contractMex:
            Coin = {'mex':m, 'cc':coin}
    if not Coin:return
    
    for c in MexTicker:
        if Coin['mex']['coin'].lower() == c['symbol'].split('_')[0].lower():
            # print(Coin['mex'], c)
            await alert(Coin)
            return
   
async def fetch_mexc_prices():
    """Получение цен с MEXC с повторными попытками."""
    logging.debug("Запрос MEXC ticker: URL=https://contract.mexc.com/api/v1/contract/ticker")
    async with aiohttp.ClientSession() as s:
        for attempt in range(3):
            try:
                async with s.get("https://contract.mexc.com/api/v1/contract/ticker") as d:
                    if d.status == 200:
                        data = (await d.json()).get('data', [])
                        logging.info("Успешно получены данные MEXC ticker")
                        return data
                    logging.warning(f"MEXC ticker вернул статус {d.status}")
            except Exception as e:
                logging.warning(f"Ошибка MEXC ticker (попытка {attempt + 1}): {e}")
            await asyncio.sleep(2)
        logging.error("Не удалось получить данные MEXC ticker после 3 попыток")
        return []
    
async def fetch_mexc_data():
    """Получение данных конфигурации MEXC."""
    params = {'timestamp': int(time() * 1000)}
    query_string = urlencode(sorted(params.items()))
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = signature
    headers = {
        'X-MEXC-APIKEY': access_key
    }
    
    logging.debug(f"Запрос MEXC config: URL=https://api.mexc.com/api/v3/capital/config/getall, params={params}, query_string={query_string}, signature={signature}, headers={headers}")
    
    async with aiohttp.ClientSession() as s:
        for attempt in range(3):
            try:
                async with s.get("https://api.mexc.com/api/v3/capital/config/getall", params=params, headers=headers) as d:
                    if d.status == 200:
                        logging.info("Успешно получены данные MEXC config")
                        return await d.json()
                    response_text = await d.text()
                    logging.warning(f"MEXC config вернул статус {d.status}: {response_text}")
            except Exception as e:
                logging.warning(f"Ошибка MEXC config (попытка {attempt + 1}): {e}")
            await asyncio.sleep(2)
        logging.error("Не удалось получить данные MEXC config после 3 попыток")
        return []
    
async def main():
    while True:
        coins = []
        for i in range(1, 5):
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(f'https://api.coinmarketcap.com/data-api/v3/token-unlock/listing?start={i}&limit=100&sort=next_unlocked_date&direction=desc&enableSmallUnlocks=false') as r:
                        coins.extend((await r.json())['data']['tokenUnlockList'])
            except Exception as e:logging.error(f"Ошибка при получения всех монет с coinmarketcap {e}")
        print(len(coins))
        Mex = await fetch_mexc_data()
        MexTicker = await fetch_mexc_prices()
        for coin in coins:
            try:asyncio.create_task(coinWork(coin, Mex, MexTicker))
            except Exception as e:logging.error(f'Ошибка при работе с токеном {coin, e}')
            # break
            # await asyncio.sleep(1)
        
        await asyncio.sleep(7200)


async def normalNum(n:str):
    
    prfx = ''
    n = int(float(n)*10)/10
    
    if n<1000:prfx = ''
    elif 1000<=n<=1000_000:prfx='к';n/=1000
    elif 1000_000<n:prfx='млн';n/=1000000
    elif 1000_000_000<n:prfx='млрд';n/=1000000000
    n = int(float(n)*10)/10
    if str(n).split('.')[-1]=='0':n = int(n)
    
    
    return f"{n}{prfx}"

async def alert(Coin:dict):

    try:Coin['cc']['quotes'][0]['price']
    except:return
    async with aiohttp.ClientSession() as s:
            async with s.get(f'https://api.coinmarketcap.com/data-api/v3/token-unlock/allocations?cryptoId={Coin['cc']['cryptoId']}') as r: 
                Allocation = (await r.json())['data']['tokenAllocations']
    alctxt = ''
    liquidity = ''
    
    for k in Allocation:
        
        # if k['allocationName'] == 'Public Sale':
        #     alctxt+=f"\nCommunity: {str(k['unlockedPercent'])[:4]}% ({await normalNum(str(Coin['cc']['nextUnlocked']['tokenAmount']*k['unlockedPercent']/100))})"
            
        if k['allocationName'] == 'Core Team' or k['allocationName'] == 'Team':
            alctxt+=f"\nКоманда: {str(k['unlockedPercent'])[:4]}% ({await normalNum(str(Coin['cc']['nextUnlocked']['tokenAmount']*k['unlockedPercent']/100))})"
        elif k['allocationName'] == 'Public Round' or k['allocationName'] == 'Public Sale':
            alctxt+=f"\nПубличный раунд: {str(k['unlockedPercent'])[:4]}% ({await normalNum(str(Coin['cc']['nextUnlocked']['tokenAmount']*k['unlockedPercent']/100))})"
        elif k['allocationName'] == 'Private Round':
            alctxt+=f"\nПриватный раунд: {str(k['unlockedPercent'])[:4]}% ({await normalNum(str(Coin['cc']['nextUnlocked']['tokenAmount']*k['unlockedPercent']/100))})"
        elif k['allocationName'] == 'Marketing':
            alctxt+=f"\nМаркетинг: {str(k['unlockedPercent'])[:4]}% ({await normalNum(str(Coin['cc']['nextUnlocked']['tokenAmount']*k['unlockedPercent']/100))})"
        elif 'eco' in k['allocationName'].lower():
            alctxt+=f"\nЭКО: {str(k['unlockedPercent'])[:4]}% ({await normalNum(str(Coin['cc']['nextUnlocked']['tokenAmount']*k['unlockedPercent']/100))})"
        elif 'airdrop' in k['allocationName'].lower():
            alctxt+=f"\nAirDrop: {str(k['unlockedPercent'])[:4]}% ({await normalNum(str(Coin['cc']['nextUnlocked']['tokenAmount']*k['unlockedPercent']/100))})"
        
        if k['allocationName'] == 'Liquidity':liquidity = f"Liquidity: {str(k['unlockedPercent'])[:4]}%"
    if 'Публичный раунд' not in alctxt:return
    for k in ['AirDrop', 'Приватный раунд', 'Маркетинг', 'Команда']:
        if k not in alctxt:alctxt+=f"\n{k}: Нет данных"

    msg = f'''✅ <b>РАЗЛОК ТОКЕНА ${Coin['mex']['coin']}</b>

— Время: {datetime.datetime.fromtimestamp(int(Coin['cc']['nextUnlocked']['date'])/1000).strftime("%m-%d %H:%M")}
— Тотал саплай: {await normalNum(str(Coin['cc']['totalSupply']))}
— Circulating саплай: {await normalNum(str(Coin['cc']['circulatingSupply']))}
— Предстоит к разблокированию: {await normalNum(str(Coin['cc']['nextUnlocked']['tokenAmount']))}

<b>Из них:</b>
{alctxt}

<b>Информация о проекте:</b>

M-Cap: {Coin['cc']['quotes'][0]['marketCap']}     {liquidity}
FDV: {await normalNum(str(Coin['cc']['quotes'][0]['fullyDilluttedMarketCap']))}         Price now: {str(Coin['cc']['quotes'][0]['price'])[:8]}$ 

<b>— Остальное о разлоке</b> - <a href='https://coinmarketcap.com/currencies/{Coin['cc']['slug']}'>ссылка</a>

'''
    # await bot.send_message(ADMIN_ID, msg)
    # return
    if  int(Coin['cc']['nextUnlocked']['date'])/1000 - int(time())>172800*10:return
   
    tn = Coin['mex']['name']
    if tn not in alertH:
        m= await bot.send_message(CHANNEL_ID, msg)
        alertH[tn] = {"msgId":m.message_id, "unlockDate":int(Coin["cc"]['nextUnlocked']['date'])/1000}
        with open('a.json', 'w') as f:
            json.dump(alertH, f)
    else:
        if alertH[tn]['unlockDate'] != int(Coin["cc"]['nextUnlocked']['date'])/1000:
            m= await bot.send_message(CHANNEL_ID, msg)
            alertH[tn] = {"msgId":m.message_id, "unlockDate":int(Coin["cc"]['nextUnlocked']['date'])/1000}


        
if __name__ == '__main__':asyncio.run(main())
