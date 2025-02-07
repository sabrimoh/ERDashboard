#!/usr/bin/env python3
"""
Standalone Flask Dashboard Runner

This script serves the generated ER diagram and detail pages from the output directory.
By default it uses the directory:
    P:\_BD_PostgreSQL\Script modélisation base de donnees\2025

Usage:
    python run_dashboard.py [--dir PATH] [--port PORT]
"""

import os
import sys
import argparse
import logging
from flask import Flask, send_from_directory, abort

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def create_app(root_dir):
    """
    Create and configure the Flask application.
    """
    app = Flask(__name__, static_folder=root_dir)

    @app.route('/')
    def index():
        # Serve the main HTML page.
        return send_from_directory(root_dir, 'main.html')

    @app.route('/<path:filename>')
    def serve_file(filename):
        # Serve any static file within the output directory.
        file_path = os.path.join(root_dir, filename)
        if os.path.exists(file_path):
            return send_from_directory(root_dir, filename)
        else:
            abort(404)

    return app

def main():
    parser = argparse.ArgumentParser(description="Run Flask Dashboard for ER Diagram and Detail Pages")
    parser.add_argument(
        '--dir',
        type=str,
        default=r'', #add your folder path here
        help=("Root directory containing the generated files. "
              "Default: ") #add your folder path here too 
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help="Port to run the Flask app on (default: 5000)"
    )
    args = parser.parse_args()

    # Resolve the absolute path of the provided directory.
    root_dir = os.path.abspath(args.dir)
    main_html = os.path.join(root_dir, 'main.html')
    if not os.path.exists(main_html):
        logging.error("main.html not found in the specified directory: %s", root_dir)
        sys.exit(1)

    app = create_app(root_dir)
    logging.info("Starting Flask dashboard at http://127.0.0.1:%d", args.port)
    app.run(host='127.0.0.1', port=args.port, debug=True)

if __name__ == '__main__':
    main()
