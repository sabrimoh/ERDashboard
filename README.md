# ERDashboard

**ERDashboard** is a toolset for reverse-engineering PostgreSQL databases. It generates detailed HTML documentation and an interactive ER diagram from your database metadata. Additionally, it provides a Flask-based web dashboard to explore the generated content.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites and Installation](#prerequisites-and-installation)
- [Usage](#usage)
  - [Running the ERD Generator](#running-the-erd-generator)
  - [Running the Flask Dashboard (Standalone)](#running-the-flask-dashboard-standalone)
- [Code Structure and Detailed Functionality](#code-structure-and-detailed-functionality)
  - [ERDgenerator.py](#erdgeneratorpy)
  - [FlaskApp.py (run_dashboard.py)](#flaskapppy-run_dashboardpy)
- [Contributing and Further Customization](#contributing-and-further-customization)
- [License and Credits](#license-and-credits)

## Overview

The **ERDashboard** project comprises two main components:

1. **ERDgenerator.py**  
   - Connects to a PostgreSQL database using credentials provided via environment variables, a JSON config file, or command-line arguments.
   - Extracts metadata (tables, views, dependencies, primary keys, foreign keys) from PostgreSQL’s `information_schema`.
   - Generates an ER diagram (SVG format) and detailed HTML pages for each table and view.
   - Analyzes view definitions to generate "calculation chains" that trace how view columns are derived.
   - Optionally launches a Flask web dashboard for interactive exploration.

2. **FlaskApp.py (run_dashboard.py)**  
   - Serves the generated ER diagram and HTML detail pages from the output directory.
   - Provides a standalone Flask server to interact with your database documentation in a web browser.

## Features

- **Database Metadata Extraction:**  
  Retrieves detailed metadata from PostgreSQL, including table columns, view definitions, view dependencies, primary keys, and foreign keys.

- **HTML Detail Pages:**  
  - Individual HTML pages for tables and views (using Jinja2 templating).
  - For views, includes a “calculation chain” analysis, interactive SVG dependency diagrams, and syntax-highlighted SQL view definitions with a copy-to-clipboard feature.

- **ER Diagram Generation:**  
  - Uses Graphviz to create an ER diagram that visually groups tables (boxes) and views (ellipses).
  - Displays primary key highlights, foreign key relationships, and view dependencies.
  - Clickable nodes and edges link to corresponding detail pages.

- **Interactive Web Dashboard:**  
  A Flask-based dashboard that serves the generated HTML and SVG files, allowing interactive exploration of your database documentation.

- **Flexible Configuration:**  
  Database connection parameters can be provided via command-line arguments, environment variables, or a JSON configuration file.

- **Progress Reporting:**  
  Uses `tqdm` to provide progress bars while generating detail pages.

## Prerequisites and Installation

### Prerequisites

- **Python 3.x**
- **PostgreSQL** (for database access)

### Required Python Packages

Ensure the following packages are installed:

- [psycopg2](https://pypi.org/project/psycopg2/)
- [pandas](https://pandas.pydata.org/)
- [graphviz](https://pypi.org/project/graphviz/)
- [tqdm](https://pypi.org/project/tqdm/)
- [sqlparse](https://pypi.org/project/sqlparse/)
- [jinja2](https://pypi.org/project/Jinja2/)
- [flask](https://pypi.org/project/Flask/) (only needed for running the dashboard)

You can install these with:

```bash
pip install psycopg2 pandas graphviz tqdm sqlparse jinja2 flask
