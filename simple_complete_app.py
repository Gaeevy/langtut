from flask import Flask, render_template, session, redirect, url_for, request
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

@app.route('/')
def index():
    # Print debug info
    print("Index route accessed")
    print(f"Request URL: {request.url}")
    
    # Simple session test
    visit_count = session.get('visit_count', 0) + 1
    session['visit_count'] = visit_count
    
    # Print session data
    print(f"Session data: {session}")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Simple Language App</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #333; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #4a6da7; color: white; 
                   text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Simple Language Learning App</h1>
            <p>This is a simplified version of the app without OAuth authentication.</p>
            <p>You have visited this page {visit_count} time(s).</p>
            <p><a href="/test" class="btn">Test Route</a></p>
            <p><a href="/cards" class="btn">See Cards</a></p>
        </div>
    </body>
    </html>
    """

@app.route('/test')
def test():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Route</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #333; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #4a6da7; color: white; 
                   text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Test Route Works!</h1>
            <p>This is a test route to verify that the server is working correctly.</p>
            <p><a href="/" class="btn">Back to Home</a></p>
        </div>
    </body>
    </html>
    """

@app.route('/cards')
def cards():
    # Add some sample cards
    sample_cards = [
        {"word": "abrir", "translation": "открывать", "equivalent": "to open"},
        {"word": "fechar", "translation": "закрывать", "equivalent": "to close"},
        {"word": "dormir", "translation": "спать", "equivalent": "to sleep"}
    ]
    
    card_html = ""
    for card in sample_cards:
        card_html += f"""
        <div style="border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px;">
            <h3>{card['word']}</h3>
            <p><strong>Translation:</strong> {card['translation']}</p>
            <p><strong>Equivalent:</strong> {card['equivalent']}</p>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sample Cards</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #333; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #4a6da7; color: white; 
                   text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Sample Language Cards</h1>
            <p>These are sample cards from the database:</p>
            {card_html}
            <p><a href="/" class="btn">Back to Home</a></p>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    # Try port 5000 first
    print("Starting simple complete app on port 5000...")
    app.run(debug=True, host='localhost', port=5000) 