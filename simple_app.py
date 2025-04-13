from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello, World! This is a test app."

if __name__ == '__main__':
    print("Starting a simple test Flask app...")
    app.run(debug=True, host='localhost', port=8080) 