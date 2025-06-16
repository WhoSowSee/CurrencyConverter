"""
Консольная версия конвертера валют
Использование:
    .\сonverterCLI.exe [сумма] [флаги]
    .\сonverterCLI.exe [флаги] [сумма]

При запуске без аргументов, программа запросит сумму для конвертации.

Флаги:
    -r, --reverse        Для обычной конвертации: RUB -> UAH
    -s, --steam          Расчет для Steam (исходная валюта RUB)
    -sr, --steam-reverse Расчет для Steam (исходная валюта UAH). Включает режим Steam
    -m, --manual-rate    Установить курс UAH/RUB вручную. Если курс не указан, запросит ввод
    -h, --help           Показать справку

Примеры:
    # 100 UAH -> RUB (обычная) и 100 UAH -> Steam (флаг -sr)
    .\сonverterCLI.exe 100 -sr

    # Конвертировать 100 по курсу 2.5, указанному вручную
    .\сonverterCLI.exe -m 2.5

    # Запустить с запросом ручного ввода курса
   .\сonverterCLI.exe 100 -m
"""

WHITE = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"


try:
    import sys
    import argparse
    from core import CurrencyConverterCore
    import os
except KeyboardInterrupt:
    print(f"{MAGENTA}Работа программы завершена")
    sys.exit()

CONSOLE_COMMAND_CLEAR = 'cls' if os.name == 'nt' else 'clear'


def clear_screen() -> None:
    os.system(CONSOLE_COMMAND_CLEAR)


def print_help():
    print(__doc__.strip())


def get_numeric_input(prompt: str) -> float:
    while True:
        try:
            input_text = input(prompt + ": ").strip().replace(',', '.')
            if not input_text:
                print(f"{YELLOW}Пустой ввод. Попробуйте еще раз{WHITE}")
                continue
            value = float(input_text)
            if value <= 0:
                print(f"{YELLOW}Значение должно быть больше нуля{WHITE}")
                continue
            return value
        except ValueError:
            print(f"{YELLOW}Некорректный ввод. Введите число{WHITE}")
        except (EOFError, KeyboardInterrupt):
            print(f"{MAGENTA}\nВыход из программы")
            sys.exit(0)


def format_currency_result(result: dict) -> str:
    rate_info = f"1 UAH = {round(result['rate'], 3)} RUB"
    return f"{result['amount']} {result['from_currency']} = {result['result']} {result['to_currency']} ({rate_info})"


def format_steam_result(result: dict) -> str:
    if result['from_currency'] == 'UAH':
        return f"{result['amount']} UAH ({result['rub_amount']} RUB) ⇒ {result['steam_result']} Steam RUB | Комиссия: {result['commission_amount']} RUB ({result['commission']}%)"
    else:
        return f"{result['amount']} RUB ⇒ {result['steam_result']} Steam RUB | Комиссия: {result['commission_amount']} RUB ({result['commission']}%)"


def wait_for_exit():
    try:
        input(f"\n{BLUE}Нажмите Enter, чтобы выйти...{WHITE}")
    except (EOFError, KeyboardInterrupt):
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Консольный конвертер валют UAH/RUB с поддержкой Steam",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        'amount',
        nargs='?',
        default=None,
        type=float,
        help='Сумма для конвертации',
    )
    parser.add_argument(
        '-r',
        '--reverse',
        action='store_true',
        help='Для обычной конвертации: исходная валюта RUB',
    )
    parser.add_argument(
        '-s',
        '--steam',
        action='store_true',
        help='Расчет для Steam (исходная валюта RUB)',
    )
    parser.add_argument(
        '-sr',
        '--steam-reverse',
        action='store_true',
        help='Расчет для Steam (исходная валюта UAH). Этот флаг включает режим Steam',
    )

    parser.add_argument(
        '-m',
        '--manual-rate',
        nargs='?',
        const='prompt_user',
        default=None,
        help='Установить курс UAH/RUB вручную. Если курс не указан, запросит ввод',
    )

    parser.add_argument(
        '-h', '--help', action='store_true', help='Показать эту справку'
    )

    args = parser.parse_args()

    if args.help:
        print_help()
        wait_for_exit()
        return

    print("🔄 Инициализация конвертера...")
    converter = CurrencyConverterCore()
    rate_was_set_manually = False

    if args.manual_rate is not None:
        rate_to_set = None
        if args.manual_rate == 'prompt_user':
            print("\n✍️ Запрошен ручной ввод курса")
            rate_to_set = get_numeric_input("Введите курс (UAH к RUB)")
        else:
            try:
                rate_to_set = float(args.manual_rate)
                if rate_to_set <= 0:
                    print(
                        f"{YELLOW}❌ Ошибка: Курс должен быть положительным числом{WHITE}"
                    )
                    wait_for_exit()
                    return
            except ValueError:
                print(
                    f"{RED}❌ Ошибка: {YELLOW}'{args.manual_rate}'{RED} не является корректным числом для курса{WHITE}"
                )
                wait_for_exit()
                return

        if rate_to_set is not None:
            converter.set_manual_rate(rate_to_set)
            rate_was_set_manually = True

    if not rate_was_set_manually:
        if not converter.initialize():
            print(f"{RED}❌ Ошибка инициализации конвертера{RED}")
            wait_for_exit()
            return

        status = converter.get_status_info()
        if status['rate_source'] == 'default':
            print("\n⚠️ Не удалось получить курс: нет сети и кэша")
            print(
                f"   Будет использован курс по умолчанию: {status['current_rate']}"
            )
            try:
                choice = (
                    input("   Хотите ввести курс вручную? (y/N): ")
                    .strip()
                    .lower()
                )
                if choice in ('y', 'yes', 'д', 'да'):
                    manual_rate = get_numeric_input("Введите курс (UAH к RUB)")
                    converter.set_manual_rate(manual_rate)
            except (EOFError, KeyboardInterrupt):
                print(f"\n{MAGENTA}Выход из программы")
                sys.exit(0)

    status = converter.get_status_info()
    status_emoji = "🟢" if status['is_online'] else "🔴"
    status_text = 'Онлайн' if status['is_online'] else 'Офлайн'
    details_info = ""
    if status['rate_source'] == 'api':
        details_info = " | Актуальные данные"
    elif status['rate_source'] == 'cache' and status['cache_age']:
        details_info = f" | Кэш: {status['cache_age']}"
    elif status['rate_source'] == 'manual':
        details_info = " | Ручной ввод"
    elif status['rate_source'] == 'default':
        details_info = " | Данные по умолчанию"

    print(f"\n{status_emoji} Статус: {status_text}{details_info}")
    if status['rate_display']:
        print(f"📈 Курс: {status['rate_display']}")
    print()

    amount = args.amount
    if amount is None:
        prompt = (
            "Введите сумму в рублях"
            if args.reverse
            else "Введите сумму в гривнах"
        )
        amount = get_numeric_input(prompt)

    regular_result = converter.convert_currency(amount, reverse=args.reverse)
    if 'error' in regular_result:
        print(f"{RED}❌ {regular_result['error']}{WHITE}")
        wait_for_exit()
        return

    print(f"💱 {format_currency_result(regular_result)}")

    if args.steam or args.steam_reverse:
        steam_result = converter.convert_to_steam(
            amount, from_uah=args.steam_reverse
        )
        if 'error' in steam_result:
            print(
                f"{RED}❌ Ошибка в расчете Steam: {steam_result['error']}{WHITE}"
            )
        else:
            print(f"🎮 {format_steam_result(steam_result)}")

    wait_for_exit()


if __name__ == "__main__":
    try:
        clear_screen()
        main()
    except KeyboardInterrupt:
        print(f"{MAGENTA}Работа программы завершена")
        sys.exit()
