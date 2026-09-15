SmartLeftoverChef

A web app that helps reduce household food waste by turning the ingredients you already have into recipe suggestions.

Enter what's in your fridge — with optional quantities, units, and dietary filters (vegetarian/vegan) — and the app queries TheMealDB to find matching recipes, ranking them by how well they match what you have on hand and flagging what's still missing.

Features:
Enter multiple ingredients with optional amount + unit (e.g. 500 g, 1/2 cup, 1 1/2 tbsp)
Automatic unit conversion (mass and volume) so quantities can be compared against recipe requirements
Dietary filters: vegetarian, vegan (with a keyword-based vegan safeguard)
Recipes ranked by a match score based on ingredient overlap and quantity sufficiency
Shows missing ingredients and a link to the original recipe source (or YouTube video)

Tech stack:
Python 3 / Flask
TheMealDB API (public, no API key required)

Setup:
1) Clone the repository:
   git clone https://github.com/leonalex224/SmartLeftoverChef.git
   cd SmartLeftoverChef
   
2) Create a virtual environment:
   python -m venv venv

3) Activate it: Windows (cmd):
   venv\Scripts\activate

macOS/Linux:
   source venv/bin/activate
   
4) Install dependencies:
   pip install -r requirements.txt
   
Running the app
With the virtual environment activated:
   python app.py

Then open http://localhost:5000 in your browser.

Project structure
├── app.py              # Flask app: routes, ingredient parsing, recipe matching
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates (index, results)
└── README.md
