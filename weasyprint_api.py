from flask import Flask, request, send_file
import subprocess
import tempfile
import os

app = Flask(__name__)

@app.route('/health')
def health():
    return 'OK'

@app.route('/pdf', methods=['POST'])
def pdf():
    data = request.get_json()
    html = data.get('html')
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        subprocess.run(['weasyprint', '-', tmp.name], input=html.encode())
        return send_file(tmp.name, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
