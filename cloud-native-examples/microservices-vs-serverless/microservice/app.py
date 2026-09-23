from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route("/hello", methods=["GET"])
def hello():
    return jsonify({"message": "Hello from the Microservice!"})

@app.route("/sum", methods=["POST"])
def sum_numbers():
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("a"), (int, float)) or not isinstance(data.get("b"), (int, float)):
        return jsonify(error="JSON body must contain numeric fields 'a' and 'b'"), 400
    return jsonify(result=data["a"] + data["b"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
