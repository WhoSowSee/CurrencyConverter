import requests
import urllib.parse
from typing import Optional, Union
import time
import json
import os
from dataclasses import dataclass, asdict
from functools import lru_cache
from datetime import datetime
import logging
import socket

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def format_number(num: Union[int, float]) -> Union[int, float]:
    if isinstance(num, float) and num.is_integer():
        return int(num)
    return num


@dataclass
class CacheEntry:
    value: float
    timestamp: float

    def is_expired(self, duration: int) -> bool:
        return time.time() - self.timestamp > duration

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class CommissionData:

    result: int
    commission: float
    commission_amount: float


class PersistentCache:

    def __init__(self, cache_file="currency_cache.json"):
        self.cache_file = cache_file
        self.default_data = {
            "exchange_rate": {"value": 2, "timestamp": 0},
            "steam_rates": {},
            "last_update": None,
        }

    def load_cache(self) -> dict:
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if self._validate_cache_structure(data):
                        logger.info("Кэш успешно загружен из файла")
                        return data
                    else:
                        logger.warning(
                            "Некорректная структура кэша, используем значения по умолчанию"
                        )
                        return self.default_data.copy()
            else:
                logger.info(
                    "Файл кэша не найден, используем значения по умолчанию"
                )
                return self.default_data.copy()
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша: {e}")
            return self.default_data.copy()

    def save_cache(self, data: dict):
        try:
            data["last_update"] = datetime.now().isoformat()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша: {e}")

    def _validate_cache_structure(self, data: dict) -> bool:
        if not all(key in data for key in ['exchange_rate', 'steam_rates']):
            return False
        if not isinstance(data['exchange_rate'], dict):
            return False
        if not all(
            key in data['exchange_rate'] for key in ['value', 'timestamp']
        ):
            return False
        return True


class NetworkChecker:
    @staticmethod
    def is_internet_available(timeout: float = 1.0) -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=timeout)
            return True
        except (socket.timeout, socket.error, OSError):
            try:
                socket.create_connection(("1.1.1.1", 53), timeout=timeout)
                return True
            except (socket.timeout, socket.error, OSError):
                return False


class APIClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            }
        )

    def get_exchange_rate(self) -> Optional[float]:
        try:
            response = self.session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js", timeout=2
            )
            response.raise_for_status()
            data = response.json()
            rates = data['Valute']
            return rates['UAH']['Value'] / rates['UAH']['Nominal']
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка получения курса валют: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка обработки данных курса валют: {e}")
            return None

    def get_steam_amount(
        self, amount: float, currency: str = "RUB"
    ) -> Optional[float]:
        if not NetworkChecker.is_internet_available(timeout=0.5):
            logger.info("Пропуск запроса к API Steam: нет подключения к сети")
            return None

        params = {
            "p": "4100297",
            "a": str(amount).replace('.', ','),
            "c": currency,
            "x": "<response></response>",
            "rnd": time.time(),
        }
        try:
            url = f"https://plati.market/asp/price_options.asp?{urllib.parse.urlencode(params)}"
            response = self.session.get(
                url, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=2
            )
            response.raise_for_status()
            data = response.json()
            if data.get("err") not in ["0", None]:
                return None
            amount_steam = data.get("cnt")
            return (
                float(amount_steam.replace(',', '.'))
                if isinstance(amount_steam, str)
                else amount_steam
            )
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка получения данных Steam: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка обработки данных Steam: {e}")
            return None


class CacheManager:
    def __init__(self):
        self.persistent_cache = PersistentCache()
        self.cache_data = self.persistent_cache.load_cache()
        self.rate_cache_duration = 600
        self.steam_cache_duration = 180
        self.offline_rate_duration = 86400

    def reload_from_disk(self):
        logger.info("Принудительная перезагрузка кэша с диска")
        self.cache_data = self.persistent_cache.load_cache()

    def get_rate(self, allow_offline: bool = True) -> Optional[float]:
        rate_data = self.cache_data.get('exchange_rate', {})
        timestamp = rate_data.get('timestamp', 0)
        value = rate_data.get('value')
        if not timestamp or not value:
            return None
        if time.time() - timestamp < self.rate_cache_duration:
            return value
        if (
            allow_offline
            and time.time() - timestamp < self.offline_rate_duration
        ):
            return value
        if allow_offline and not NetworkChecker.is_internet_available():
            return value
        return None

    def set_rate(self, rate: float):
        self.cache_data['exchange_rate'] = {
            'value': rate,
            'timestamp': time.time(),
        }
        self.persistent_cache.save_cache(self.cache_data)

    def get_steam_amount(self, key: str) -> Optional[float]:
        steam_data = self.cache_data.get('steam_rates', {}).get(key)
        if not steam_data:
            return None
        entry = CacheEntry.from_dict(steam_data)
        if not entry.is_expired(self.steam_cache_duration):
            return entry.value
        else:
            if key in self.cache_data['steam_rates']:
                del self.cache_data['steam_rates'][key]
                self.persistent_cache.save_cache(self.cache_data)
        return None

    def set_steam_amount(self, key: str, amount: float):
        if 'steam_rates' not in self.cache_data:
            self.cache_data['steam_rates'] = {}
        entry = CacheEntry(amount, time.time())
        self.cache_data['steam_rates'][key] = entry.to_dict()
        self._cleanup_steam_cache()
        self.persistent_cache.save_cache(self.cache_data)

    def _cleanup_steam_cache(self):
        steam_rates = self.cache_data.get('steam_rates', {})
        expired_keys = [
            key
            for key, entry_data in steam_rates.items()
            if CacheEntry.from_dict(entry_data).is_expired(
                self.steam_cache_duration
            )
        ]
        for key in expired_keys:
            del self.cache_data['steam_rates'][key]

    def get_cache_age_info(self) -> Optional[str]:
        rate_data = self.cache_data.get('exchange_rate', {})
        timestamp = rate_data.get('timestamp')
        if not timestamp or timestamp == 0:
            return None
        time_diff = datetime.now() - datetime.fromtimestamp(timestamp)
        seconds = time_diff.total_seconds()
        if seconds < 1:
            return "0 сек назад"
        if seconds < 60:
            return f"{int(seconds)} сек назад"
        if seconds < 3600:
            return f"{int(seconds // 60)} мин назад"
        if seconds < 86400:
            return f"{int(seconds // 3600)} ч назад"
        return f"{time_diff.days} дн назад"


class SteamCalculator:
    FALLBACK_DATA = [
        (30, 29),
        (45, 43),
        (50, 47),
        (75, 71),
        (100, 94),
        (150, 141),
        (250, 234),
        (350, 328),
        (500, 468),
        (700, 655),
        (1000, 935),
        (1200, 1122),
        (1500, 1402),
        (2200, 2057),
        (3000, 2804),
        (5000, 4673),
        (8000, 7477),
        (15000, 14019),
    ]

    def __init__(self, api_client: APIClient, cache_manager: CacheManager):
        self.api_client = api_client
        self.cache_manager = cache_manager

    def calculate_commission(
        self, amount: float, is_online: bool
    ) -> CommissionData:
        result = self._get_steam_amount_with_cache(amount, is_online)
        commission = (amount - result) / amount if amount > 0 else 0
        return CommissionData(
            result=int(result),
            commission=round(commission, 4),
            commission_amount=round(amount - result, 2),
        )

    def _get_steam_amount_with_cache(
        self, amount: float, is_online: bool
    ) -> float:
        cache_key = f"{amount}_RUB"
        cached_amount = self.cache_manager.get_steam_amount(cache_key)
        if cached_amount is not None:
            return cached_amount
        if is_online:
            api_amount = self.api_client.get_steam_amount(amount)
            if api_amount is not None:
                self.cache_manager.set_steam_amount(cache_key, api_amount)
                return api_amount
        return self._calculate_fallback(amount)

    @lru_cache(maxsize=128)
    def _calculate_fallback(self, amount: float) -> float:
        for pay, get in self.FALLBACK_DATA:
            if pay == amount:
                return get
        if amount < 30:
            return round(amount * (29.0 / 30.0), 0)
        if amount > 15000:
            return round(amount * (14019.0 / 15000.0), 0)
        for i in range(len(self.FALLBACK_DATA) - 1):
            pay1, get1 = self.FALLBACK_DATA[i]
            pay2, get2 = self.FALLBACK_DATA[i + 1]
            if pay1 <= amount <= pay2:
                ratio = (amount - pay1) / (pay2 - pay1)
                return round(get1 + ratio * (get2 - get1), 0)
        return round(amount * 0.935, 0)


class CurrencyConverterCore:
    def __init__(self):
        self.api_client = APIClient()
        self.cache_manager = CacheManager()
        self.steam_calculator = SteamCalculator(
            self.api_client, self.cache_manager
        )
        self.current_rate: Optional[float] = None
        self.is_online: bool = False
        self.rate_source: str = (
            "uninitialized"  # 'api', 'cache', 'default', 'manual'
        )

    def initialize(self) -> bool:
        self.is_online = NetworkChecker.is_internet_available(timeout=1.0)

        if self.is_online:
            new_rate = self.api_client.get_exchange_rate()
            if new_rate:
                self.cache_manager.set_rate(new_rate)
                self.current_rate = new_rate
                self.rate_source = "api"
                return True
            else:
                self.is_online = False

        cached_rate = self.cache_manager.get_rate(allow_offline=True)
        if cached_rate:
            self.current_rate = cached_rate
            self.rate_source = "cache"
            return True

        self.current_rate = self.cache_manager.persistent_cache.default_data[
            'exchange_rate'
        ]['value']
        self.rate_source = "default"
        return True

    def set_manual_rate(self, rate: float):
        self.current_rate = rate
        self.rate_source = "manual"
        logger.info(f"Курс установлен вручную: {rate}")

    def convert_currency(self, amount: float, reverse: bool = False) -> dict:
        if not self.current_rate:
            return {"error": "Курс валют недоступен"}

        if reverse:
            result = round(amount / self.current_rate, 2)
            return {
                "amount": amount,
                "result": result,
                "from_currency": "RUB",
                "to_currency": "UAH",
                "rate": self.current_rate,
            }
        else:
            result = round(amount * self.current_rate, 2)
            return {
                "amount": amount,
                "result": result,
                "from_currency": "UAH",
                "to_currency": "RUB",
                "rate": self.current_rate,
            }

    def convert_to_steam(self, amount: float, from_uah: bool = False) -> dict:
        if not self.current_rate:
            return {"error": "Курс валют недоступен"}

        # В ручном режиме считаем, что мы онлайн для расчетов комиссии
        is_effectively_online = self.is_online or self.rate_source == 'manual'

        if from_uah:
            rub_amount = round(amount * self.current_rate, 2)
            data = self.steam_calculator.calculate_commission(
                rub_amount, is_effectively_online
            )
            return {
                "amount": amount,
                "from_currency": "UAH",
                "rub_amount": rub_amount,
                "steam_result": data.result,
                "commission": format_number(round(data.commission * 100, 2)),
                "commission_amount": format_number(data.commission_amount),
                "rate": self.current_rate,
            }
        else:
            data = self.steam_calculator.calculate_commission(
                amount, is_effectively_online
            )
            return {
                "amount": amount,
                "from_currency": "RUB",
                "steam_result": data.result,
                "commission": format_number(round(data.commission * 100, 2)),
                "commission_amount": format_number(data.commission_amount),
            }

    def get_status_info(self) -> dict:
        cache_age = self.cache_manager.get_cache_age_info()
        rate_display = None
        if self.current_rate:
            rate_display = (
                f"1 UAH = {round(self.current_rate, 3)} RUB | "
                f"1 RUB = {round(1 / self.current_rate, 3)} UAH"
            )

        return {
            "is_online": self.is_online,
            "current_rate": self.current_rate,
            "cache_age": cache_age,
            "rate_source": self.rate_source,
            "rate_display": rate_display,
        }
