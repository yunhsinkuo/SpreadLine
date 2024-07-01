from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
import logging
from views import *

log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)


app = Flask(__name__)
CORS(app)

    

@app.route("/")
@cross_origin()
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/fetchSpreadLine", methods=["GET"])
@cross_origin()
def fetchSites():
    #result = computeAnimalSpreadLine()
    #result = computeMetooSpreadLine()
    result = computeJHSpreadLine()
    #result = computeTMSpreadLine()

    resp = jsonify(resp=result)
    return resp

if __name__ == "__main__":
    app.run(port=5300, debug=True)