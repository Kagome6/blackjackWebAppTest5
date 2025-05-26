# blackjackWebAppTest5
Blackjack can be played in your browser, on a Linux server or on your PC

During training, there are two stages:
Stage 1: A rule-based AI and a Q-learning agent automatically play against each other.
Stage 2: The pre-trained Q-learning agents play against each other in self-play.

The training has already been completed, so you can play immediately.

Basic Rules of Blackjack (21) in This Project:
Cards range from 1 to 11, and the player whose total is closer to 21 wins.
The deck is shared, meaning once a card is drawn, it won't appear again in the same round.
If either player's hand exceeds 21, it's a bust (loss).
You decide whether to draw or stand.
Humans go first.
If both players choose to stand three times in a row, the game proceeds to judgment.
The AI behavior may be unstable on this site—it is for experimental use only.
The AI uses a Q-table method. It decides to draw or not based on the current situation and pre-trained probabilities.
── Experimental Update ──
A betting system has been added during the match. If you're confident in winning, you can use an SP card to reduce the opponent’s life points.Also, the AI’s hand display has been updated so that only its initial card remains hidden until the match ends.

Command-Line Execution:
C:
cd Program_Generation_Test/WebAppTest5

Create a virtual environment:
python -m venv venv

(Once created, you just need to activate it:)
venv\Scripts\activate.bat

Install Flask:
pip install flask

Run the application:
python app.py

Then open the HTML file in a browser:
file:///C:/---------/WebAppTest5/index.html

Or access via browser:
http://127.0.0.1:5000/


Folder Structure:
WebAppTest5/
├── venv
├── app.py (Python backend)
├── templates/
│   └── index.html
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── script.js
│   └── images/
│       ├── card_1.png
│       ├── card_2.png
│       ├── ...
└── q_table.json (Q-table storage

To Launch on a Server : Log in as the user
Activate the virtual environment
You will be prompted for a password: 
sudo systemctl start nginx  
gunicorn -w 2 -b 127.0.0.1:8000 app:app
