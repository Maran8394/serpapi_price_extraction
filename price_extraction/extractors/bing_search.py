import spacy
import re
from price_extraction.extractors.constant_keywords import CurrencySymbols
import numpy as np

from price_extraction.extractors.utils import get_amount


class BingExtraction(object):
    def __init__(self, query: str, response_data: dict, use_nlp: bool = False):
        self.query = query
        self.data: dict = response_data
        self.results = set()
        self.use_nlp = use_nlp
        self.nlp_model = spacy.load("en_core_web_sm")
        self.extracted_costs: set[str] = set()
        self.shipping_costs: set[str] = set()
        self.results: list = []

    @staticmethod
    def levenshtein_distance(s1, s2):
        dp = np.zeros((len(s1) + 1, len(s2) + 1))

        for i in range(len(s1) + 1):
            for j in range(len(s2) + 1):
                if i == 0:
                    dp[i][j] = j
                elif j == 0:
                    dp[i][j] = i
                elif s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i][j - 1],  # Insert
                                       dp[i - 1][j],  # Remove
                                       dp[i - 1][j - 1])  # Replace

        # similarity percentage
        max_length = max(len(s1), len(s2))
        similarity_percentage = (1 - dp[-1][-1] / max_length) * 100
        return similarity_percentage

    def extract_shipping_charge(self, text):
        pattern = r'(\S+\s+){0,2}' + re.escape("shipping") + r'(\s+\S+){0,2}'
        matches = re.finditer(pattern, text)
        for match in matches:
            prefix = match.group(0).strip()
            suffix = text[match.end():].strip()
            prefix_amt = self.extract_price(prefix)
            suffix_amt = self.extract_price(suffix)
            if prefix_amt is not None:
                self.shipping_costs.add(prefix_amt)
            if suffix_amt is not None:
                self.shipping_costs.add(suffix_amt)

    @staticmethod
    def extract_price(text):
        pattern = r"(s\$|\$|\$sgd)(?P<price>\d+)"
        match = re.search(pattern, text)
        if match:
            return match.group()
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
            return []

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
                price_list.append(f"{str(extracted_currency)} {extracted_price_start} - {extracted_price_end}")
            else:
                price_list.append(f"{str(extracted_currency)} {extracted_price_start}")
        return price_list if price_list else None

    def __extraction(self, txt, nlp=False):
        if txt:
            txt = txt.lower()
            if "shipping" in txt:
                self.extract_shipping_charge(txt)
            extracted_str = self.nlp_extraction(txt) if nlp else self.__get_price(txt)
            if extracted_str is not None:
                self.extracted_costs.update(extracted_str)

    def sorted_results(self):
        return {
            "min": min(self.results) if self.results else 0,
            "max": max(self.results) if self.results else 0,
        }

    def start_extraction(self):
        organic_results: list = self.data.get("organic_results")
        ads: list = self.data.get("ads")
        answer_box: dict = self.data.get("answer_box")

        # Organic results
        if organic_results:
            for or_item in organic_results:
                title = or_item.get("title")
                snippet = or_item.get("snippet")

                self.__extraction(title, nlp=self.use_nlp)
                self.__extraction(snippet, nlp=self.use_nlp)

        # Ads
        if ads:
            for ad_item in ads:
                ad_item_title = ad_item.get("title")
                ad_item_price = ad_item.get("price")
                ad_item_details = ad_item.get("details")
                # ad_item_store = ad_item.get("store")

                if type(ad_item_title) == dict:
                    visible = ad_item_title.get("visible")
                    similarity_perc = self.levenshtein_distance(self.query, visible)
                    hidden_txt = ad_item_title.get('hidden')
                elif type(ad_item_title) == str:
                    similarity_perc = self.levenshtein_distance(self.query, ad_item_title.lower())
                    hidden_txt = None
                else:
                    similarity_perc = None
                    hidden_txt = None

                if similarity_perc is not None and int(similarity_perc) > 40:
                    if hidden_txt is not None:
                        self.__extraction(hidden_txt, nlp=self.use_nlp)

                if ad_item_details:
                    if ad_item_details.lower() != "used":
                        if ad_item_price is not None:
                            any_currency = any(currency in ad_item_price for currency in CurrencySymbols.singapore)
                            if any_currency:
                                self.extracted_costs.add(ad_item_price.lower())

        if answer_box:
            answer_box_title = answer_box.get("title")
            answer_box_snippet = answer_box.get("snippet")
            answer_box_result = answer_box.get("result")
            answer_box_highlighted_snippets: list = answer_box.get("highlighted_snippets")

            self.__extraction(answer_box_title, nlp=self.use_nlp)
            self.__extraction(answer_box_snippet, nlp=self.use_nlp)
            self.__extraction(answer_box_result, nlp=self.use_nlp)

            for highlighted_snippet in answer_box_highlighted_snippets:
                self.__extraction(highlighted_snippet, nlp=self.use_nlp)

        subtracted_costs = self.extracted_costs.difference(self.shipping_costs)

        for subtracted_cost in subtracted_costs:
            extracted_amt = get_amount(subtracted_cost)
            if extracted_amt:
                self.results.append(extracted_amt)

        return self.results
