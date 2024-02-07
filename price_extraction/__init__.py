from flask import Flask
from price_extraction import main

def create_app():
    app = Flask(__name__)
    app.register_blueprint(main.bp)
    return app