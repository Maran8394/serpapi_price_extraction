from flask import  Blueprint, jsonify, request
from serpapi import GoogleSearch
from price_extraction.extractors.google_extractor import GoogleExtraction
bp = Blueprint("pages", __name__)

@bp.route('/google-search', methods = ['GET', 'POST']) 
def google_search():
    if(request.method == 'POST'): 
        data = request.json
    
        product = data.get('product')
        country = data.get('country')
        use_nlp = data.get('use_nlp', False)  
        query = f"location:${country} allinurl:sg {product} price in ($, SGD)"
        
        # SerpAPI Call
        params = {
            "api_key": "31f11f50a145bc35c52e27812000252c14e1c99902e4d17ba665eb535f7ea2b8",
            "engine": "google",
            "q": query,
            "location": "Singapore",
            "google_domain": "google.com",
            "gl": "us",
            "hl": "en",
            "num": "100"
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        extraction_obj = GoogleExtraction(country=country, product=product, query=query, response_data=results, use_nlp=use_nlp)
        extraction_obj.start_extraction()
        sorted_res = extraction_obj.sorted_results()
        sorted_res["use_nlp"] = use_nlp
        sorted_res["status"] = 200
        return jsonify(sorted_res)
    else:
        return jsonify({"error":"Not supported"})
  