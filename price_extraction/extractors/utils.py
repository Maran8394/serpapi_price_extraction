import re
from price_extraction.extractors.constant_keywords import CurrencySymbols

def __split_currency_price(text: str) -> tuple[str, str] | None:
    pattern = fr'([^\d.,]+)([\d,]+(?:\.\d{2})?)'
    match = re.match(pattern, text)

    if match:
        currency_symbol = match.group(1).strip()
        price = match.group(2)
        return currency_symbol, price
    else:
        return None


def get_amount(text):
    if text:
        splited = __split_currency_price(text)
        if splited:
            currency = splited[0]
            if currency.lower() in CurrencySymbols.singapore:
                int_amt = float(str(splited[1]).replace(",", ""))
            else:
                int_amt = None
            return int_amt
        else:
            return None
    else:
        return None
