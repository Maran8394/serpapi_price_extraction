from price_extraction.extractors.constant_keywords import ConstantKeywords,CurrencySymbols
import re
import spacy


class GoogleExtraction(object):
    def __init__(self, country, product, query, response_data: dict, use_nlp: bool = False):
        self.country = country
        self.product = product
        self.query = query
        self.data: dict = response_data
        self.results = set()
        self.appended_ids = []
        self.use_nlp = use_nlp
        self.nlp_model = spacy.load("en_core_web_sm")

    @staticmethod
    def match_currency(text, currency_list):
        pattern = r"\b" + "|".join(re.escape(currency.lower()) for currency in currency_list) + r"\b"
        match = re.search(pattern, text.lower())
        return match is not None

    @staticmethod
    def __split_currency_price(text: str) -> tuple[str, str] | None:
        pattern = fr'([^\d.,]+)([\d,]+(?:\.\d{2})?)'
        match = re.match(pattern, text)

        if match:
            currency_symbol = match.group(1).strip()
            price = match.group(2)
            return currency_symbol, price
        else:
            return None

    @staticmethod
    def remove_special_characters(text):
        special_chars_pattern = r'[^\w\s\.]'
        text_without_special_chars = re.sub(special_chars_pattern, '', text)
        return text_without_special_chars.strip()

    @staticmethod
    def __get_price(text: str) -> str | None:
        pattern = fr'\b({"|".join(re.escape(symbol) for symbol in CurrencySymbols.singapore)})\s*[\$]?\s*([\d,]+(?:\.\d{2})?)(?:\s*-\s*[\$]?\s*([\d,]+(?:\.\d{2})?))?'
        matches = re.finditer(pattern, text, re.IGNORECASE)
        price_list = []
        for match in matches:
            extracted_currency = match.group(1)
            extracted_price_start = match.group(2)
            extracted_price_end = match.group(3)
            if extracted_price_end:
                price_list.append(f"{str(extracted_currency).upper()} {extracted_price_start} - {extracted_price_end}")
            else:
                price_list.append(f"{str(extracted_currency).upper()} {extracted_price_start}")

        return price_list if price_list else None

    @staticmethod
    def extract_price_amount(data):
        price_pattern = r"\b(\d{1,3}(?:,\d{3})*)(?:\.\d{2})?\b"

        if isinstance(data, list) and len(data) == 1:
            match = re.match(price_pattern, data[0])
            if match:
                abs_amount = float(match.group(1).replace(",", ""))
                return abs_amount

        return None

    def get_amount(self, text):
        if text:
            splited = self.__split_currency_price(text)
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

    def nlp_extraction(self, text):
        if text:
            doc = self.nlp_model(text)
            prices = []
            for token in doc:
                if token.text.startswith(tuple(CurrencySymbols.singapore)):
                    price_text = token.text
                    next_token_index = token.i + 1
                    while next_token_index < len(doc) and doc[next_token_index].like_num:
                        price_text += " " + doc[next_token_index].text
                        next_token_index += 1
                    prices.append(price_text)
            return prices
        else:
            return None

    def sorted_results(self):
        return {
            "min": min(self.results),
            "max": max(self.results),
        }

    def __extract_and_add(self, price, extract: bool = True):
        if extract:
            extracted_price = self.__get_price(price)
        else:
            extracted_price = [f"S$ {price}"]

        if extracted_price:
            for count, price in enumerate(extracted_price):
                splitted = self.__split_currency_price(price)
                int_price = float(str(splitted[1]).replace(",", ""))
                self.results.add(int_price)

    def start_extraction(self):
        questions: list = self.data.get("related_questions")
        organic_results: list = self.data.get("organic_results")

        for ques_dict in questions:
            question = str(ques_dict.get("question")).lower()
            snippet = str(ques_dict.get("snippet")).lower()

            if ConstantKeywords.how_much in question:
                price_symbol = [item for item in CurrencySymbols.singapore if str(item).lower() in snippet]
                if price_symbol:
                    self.__extract_and_add(snippet)

        for count, organic_result in enumerate(organic_results):

            rich_snippet = organic_result.get("rich_snippet")
            title = str(organic_result.get("title")).lower()
            snippet_highlighted_words = str(organic_result.get("snippet_highlighted_words")).lower()
            snippets = str(organic_result.get("snippet")).lower()

            if not self.use_nlp:
                price_symbol_in_title = [item for item in CurrencySymbols.singapore if str(item).lower() in title]
                price_symbol_in_snippet_highlighted_words = [item for item in CurrencySymbols.singapore if
                                                             str(item).lower() in snippet_highlighted_words]
                price_symbol_in_snippets = [item for item in CurrencySymbols.singapore if str(item).lower() in snippets]

                if price_symbol_in_title:
                    self.__extract_and_add(title)
                if price_symbol_in_snippet_highlighted_words:
                    self.__extract_and_add(snippet_highlighted_words)
                if price_symbol_in_snippets:
                    self.__extract_and_add(snippets)

                if rich_snippet:
                    if type(rich_snippet) is dict:
                        for key, value in rich_snippet.items():
                            if type(value) is dict:
                                for inner_key, inner_val in value.items():

                                    if type(inner_val) is list:
                                        for string in inner_val:
                                            trimmed_text = self.remove_special_characters(string)
                                            self.__extract_and_add(trimmed_text.lower())

                                    elif type(inner_val) is dict:
                                        currency = inner_val.get("currency")
                                        if currency and self.match_currency(currency, CurrencySymbols.singapore):
                                            price = inner_val.get("price")
                                            if price:
                                                self.results.add(float(price))
            else:
                # Rich snippets
                if rich_snippet:
                    if type(rich_snippet) is dict:
                        for key, value in rich_snippet.items():
                            if type(value) is dict:
                                for inner_key, inner_val in value.items():

                                    if type(inner_val) is list:
                                        for string in inner_val:
                                            trimmed_text = self.remove_special_characters(string)
                                            rich_snippet_ex = self.nlp_extraction(trimmed_text.lower())
                                            for amt in rich_snippet_ex:
                                                am = self.get_amount(amt)
                                                self.results.add(am)
                                    elif type(inner_val) is dict:
                                        currency = inner_val.get("currency")
                                        if currency and self.match_currency(currency, CurrencySymbols.singapore):
                                            price = inner_val.get("price")
                                            if price:
                                                self.results.add(float(price))
                snippets_ex = self.nlp_extraction(snippets)
                for amt in snippets_ex:
                    am = self.get_amount(amt)
                    self.results.add(am)
        return self.results
