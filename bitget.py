import aiohttp
import asyncio
from aiohttp_socks import ProxyConnector
from typing import List, Dict, Optional
from decimal import Decimal

class BitgetFundingRateFetcher:
    BASE_URL = "https://api.bitget.com/api/v2/mix/market/current-fund-rate"
    PRICE_URL = "https://api.bitget.com/api/v2/mix/market/symbol-price?productType=usdt-futures&symbol="
    def __init__(self, symbol: str, proxy: Optional[str] = None):
        symbol = symbol.replace('_', '')
        self.symbol = symbol
        self.proxy = proxy

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        history_url = f"https://api.bitget.com/api/v2/mix/market/history-fund-rate?symbol={token}&productType=usdt-futures&pageSize=4"
        async with session.get(history_url) as response:
            response.raise_for_status()
            data = await response.json()
            result = {}
            if len(data['data'])>3:
                for i in range(0, 4):
                    fund_rate = data['data'][i]['fundingRate']
                    result[Decimal(fund_rate).normalize() * 100] = data['data'][i]['fundingTime']
                return result

    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> Dict:
        url = f"{self.BASE_URL}?symbol={self.symbol}&productType=usdt-futures"
        price_url = f"{self.PRICE_URL}{self.symbol}"
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
            async with session.get(price_url) as response:
                response.raise_for_status()
                data_price = await response.json()
            if 'data' in data and 'price' in data_price['data'][0]:
                funding_rate = Decimal(f"{data['data'][0]['fundingRate']}")
                return {
                    "ex": "Bitget",
                    "symbol": self.symbol,
                    "fundingRate": str(funding_rate.normalize()*100),
                    "price": data_price['data'][0]['price']
                }
            else:
                return {
                    "ex": "Bitget",
                    "symbol": self.symbol,
                    "fundingRate": "Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }
        except aiohttp.ClientError as e:
            return {
                "ex": "Bitget",
                "symbol": self.symbol,
                "fundingRate": "Not supported",
                "price": "Not supported"
                # "fundingRate": 0.3
            }


def load_data(filename: str) -> List[str]:
    with open(filename, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


# async def main():
#     symbols = load_data("coins.txt")  # Файл с монетами, каждая на новой строке
#     proxies = load_data("proxies.txt")  # Файл с прокси, каждая на новой строке
#
#     if not symbols:
#         print("No symbols found in coins.txt")
#         return
#     if not proxies:
#         print("No proxies found in proxies.txt")
#         return
#
#     batch_size = 20
#     tasks = []
#     sessions = []
#
#     for i, symbol in enumerate(symbols):
#         proxy_index = (i // batch_size) % len(proxies)
#         proxy = proxies[proxy_index]
#
#         connector = ProxyConnector.from_url(proxy) if proxy else aiohttp.TCPConnector()
#         session = aiohttp.ClientSession(connector=connector)
#         sessions.append(session)
#         symbol = symbol.replace('_', '')
#         fetcher = BitgetFundingRateFetcher(symbol, proxy)
#         tasks.append(fetcher.fetch_funding_rate(session))
#
#     results = await asyncio.gather(*tasks)
#
#     for session in sessions:
#         await session.close()
#
#     for result in results:
#         print(result)
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
