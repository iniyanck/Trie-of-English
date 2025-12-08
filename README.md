📚 Minimized Lattice Trie (DAWG) Visualizer
This project implements a Minimized Lattice Trie (a form of Directed Acyclic Word Graph - DAWG) in Python to efficiently store a dictionary of words. The resulting graph structure is then exported as JSON for interactive exploration using a D3.js visualization.

The key benefit is that common suffixes are canonicalized and reused across the dictionary, leading to significant memory reduction compared to a standard Trie.

📁 Project Structure
Your project is organized into three distinct directories:

/project_root
├── data_structure/          # Contains the core Python implementation.
│   └── lattice_trie.py
├── visualization/           # Contains the files for the interactive web viewer.
│   ├── index.html
│   ├── script.js
│   └── styles.css
└── datasets/                # Stores the word lists used to build the Trie.
    └── [YOUR_DATASET].csv   # e.g., words.csv, test.csv
🛠️ Setup and Requirements
1. Prerequisites
Python 3.x

Required Python Library:

tqdm (for command-line progress bars)

Bash

pip install tqdm
2. Prepare Your Data
Create your word list file (e.g., test.csv) with one word per line.

Place this file inside the datasets/ directory.

3. Update File Path in Python
You must update the path in data_structure/lattice_trie.py to correctly point to your dataset file within the datasets folder.

Find the following lines in data_structure/lattice_trie.py and ensure the path is correct:

Python

# In data_structure/lattice_trie.py
# --- The original path helper logic will search for this relative path ---
words_filepath = os.path.join("datasets", "test.csv") # <-- ENSURE THIS MATCHES YOUR FILENAME
⚙️ How to Run
Step 1: Generate the Graph Data
Run the Python script from the root of your project directory:

Bash

python data_structure/lattice_trie.py
This script performs the following actions:

Builds the initial Trie.

Performs Suffix Canonicalization (minimization).

Runs a Graph Integrity Check to ensure all paths are valid.

Generates the graph structure and saves it as lattice_trie_graph.json in the root directory of the project.

You will see output indicating the number of nodes discarded and the success of the integrity check.

Step 2: Launch the Visualization
To view the interactive graph, you must serve the visualization/index.html file using a local web server (due to browser security restrictions on loading local files).

Option A: Simple Python HTTP Server (Recommended)
Navigate to the root of your project directory:

Bash

cd /path/to/project_root
Start a local server:

Bash

python -m http.server 8000
Open your web browser and navigate to: http://localhost:8000/visualization/index.html

Option B: VS Code Live Server
If you use VS Code, you can use the Live Server extension. Right-click on visualization/index.html and select "Open with Live Server."

💡 Key Visualization Interactions
Once the graph is loaded, you can:

Pan and Zoom to navigate the graph.

Click a Node: This will freeze the force simulation, dim the irrelevant parts of the graph, and highlight all ancestor paths (prefixes) and descendant paths (suffixes) that pass through the selected node.

Generate Words: Click the "Generate Words" button in the top-right panel to list all valid words formed by combining the highlighted prefixes and suffixes.

Unfreeze: Click the selected node again or click the background to return to the dynamic layout.

Theme Toggle: Use the icon in the top-left to switch between Light and Dark modes.