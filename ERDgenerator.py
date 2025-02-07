#!/usr/bin/env python3
"""
Enhanced ER Diagram and Detail Page Generator with Templating and Web Dashboard

This script connects to a PostgreSQL database (with credentials determined
via environment variables, a config file, or command-line arguments), extracts metadata 
(tables, views, dependencies, keys), and produces an ER diagram and HTML detail pages 
for each object. Additionally, a Flask web dashboard can be launched for interactive exploration.

Extra ideas implemented:
    - Use a templating engine (Jinja2) for the HTML pages.
    - Build a web dashboard (Flask) for interactive exploration.
    - Secure database credentials via environment variables or a config file.
"""

import os
import sys
import datetime
import argparse
import logging
import re
import json
import pandas as pd
from graphviz import Digraph
from tqdm import tqdm
import sqlparse
import psycopg2
from collections import defaultdict
from jinja2 import Template

# -----------------------------------------------------------
# CONFIGURATION & LOGGING
# -----------------------------------------------------------
DEFAULT_SCHEMA = 'public'  # Changed to a generic schema name.
DEFAULT_OUTPUT_DIR = 'output'
DEFAULT_DETAILS_DIR = os.path.join(DEFAULT_OUTPUT_DIR, 'details')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# -----------------------------------------------------------
# TEMPLATES (for Jinja2)
# -----------------------------------------------------------
DETAIL_TEMPLATE = """
<html>
<head>
    <title>Details for {{ name }}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.5.0/styles/default.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.5.0/highlight.min.js"></script>
    <script>hljs.highlightAll();</script>
    <style>
        body {
            font-family: Helvetica, Arial, sans-serif;
            margin: 20px;
        }
        h1 { margin-top: 0; }
        .copy-button {
            position: absolute; 
            top: 10px; 
            right: 10px; 
            background: #f0f0f0; 
            border: 1px solid #ccc; 
            cursor: pointer; 
            padding: 5px 10px; 
            font-size: 12px;
        }
        .code-container { margin-top: 20px; position: relative; }
        ul { list-style-type: disc; margin-left: 20px; }
        .dep-section { margin-top: 30px; }
        object { border:1px solid #ccc; max-width:100%; height:auto; display: block; }
        .navigation { margin-bottom: 20px; }
        #edgeDetails, #edgeDetails2 {
            margin-top:20px; border:1px solid #ccc; padding:10px;
        }
        .svg-container {
            position: relative;
            overflow: auto;
            border: 1px solid #ccc;
            width: 100%;
            height: auto;
        }
    </style>
</head>
<body>
    <div class="navigation">
        <a href="../public_er_diagram.svg">← Back to Main ER Diagram</a>
    </div>
    <h1>{{ object_type }}: {{ name }}</h1>
    <h2>Columns:</h2>
    <ul>
    {% for col in columns %}
        <li>{{ col }}</li>
    {% endfor %}
    </ul>
    
    {% if object_type == "View" %}
        {{ calc_chains | safe }}
    {% endif %}
    
    {% if object_type == "View" and has_dep_graph %}
    <div class="dep-section">
        <h2>Downstream Dependencies:</h2>
        <p>Click on a dependency line to highlight it and see more details:</p>
        <div class="svg-container">
            <object data="./{{ name }}_dependencies.svg" type="image/svg+xml" id="depSVG">
                Your browser does not support SVG
            </object>
        </div>
        <div id="edgeDetails">Click on an edge to see more details here.</div>
    </div>
    <script>
    const edgeInfo = {};
    document.addEventListener('DOMContentLoaded', () => {
        const svgObject = document.getElementById('depSVG');
        svgObject.addEventListener('load', () => {
            const svgDoc = svgObject.contentDocument;
            let edgePaths = svgDoc.querySelectorAll('[id^="edge_"] path, [id^="edge_"]');
            if (edgePaths.length === 0) {
                edgePaths = svgDoc.querySelectorAll('[id^="edge_"]');
            }
            edgePaths.forEach(edge => {
                edge.style.pointerEvents = 'stroke';
                edge.style.cursor = 'pointer';
                edge.addEventListener('click', () => {
                    edgePaths.forEach(e => {
                        const origStroke = e.getAttribute('stroke') || '';
                        const origStrokeWidth = e.getAttribute('stroke-width') || '1';
                        e.setAttribute('stroke', origStroke);
                        e.setAttribute('stroke-width', origStrokeWidth);
                    });
                    edge.setAttribute('stroke-width', '5');
                    edge.setAttribute('stroke', 'red');
                    const parentG = edge.closest('g');
                    if (parentG && parentG.parentNode) {
                        parentG.parentNode.appendChild(parentG);
                    }
                    const detailDiv = document.getElementById('edgeDetails');
                    const edgeId = (edge.closest('[id^="edge_"]') || edge).id;
                    detailDiv.textContent = edgeInfo[edgeId] || "No extra details available for this dependency.";
                });
            });
        });
    });
    </script>
    {% endif %}
    
    {% if object_type == "View" and has_rev_dep_graph %}
    <div class="dep-section">
        <h2>Upstream Dependencies (Who depends on {{ name }}):</h2>
        <p>Click on a dependency line to highlight it and see more details:</p>
        <div class="svg-container">
            <object data="./{{ name }}_reverse_dependencies.svg" type="image/svg+xml" id="revDepSVG">
                Your browser does not support SVG
            </object>
        </div>
        <div id="edgeDetails2">Click on an edge to see more details here.</div>
    </div>
    <script>
    const edgeInfo2 = {};
    document.addEventListener('DOMContentLoaded', () => {
        const svgObject2 = document.getElementById('revDepSVG');
        svgObject2.addEventListener('load', () => {
            const svgDoc2 = svgObject2.contentDocument;
            let edgePaths2 = svgDoc2.querySelectorAll('[id^="edge_"] path, [id^="edge_"]');
            if (edgePaths2.length === 0) {
                edgePaths2 = svgDoc2.querySelectorAll('[id^="edge_"]');
            }
            edgePaths2.forEach(edge => {
                edge.style.pointerEvents = 'stroke';
                edge.style.cursor = 'pointer';
                edge.addEventListener('click', () => {
                    edgePaths2.forEach(e => {
                        const origStroke = e.getAttribute('stroke') || '';
                        const origStrokeWidth = e.getAttribute('stroke-width') || '1';
                        e.setAttribute('stroke', origStroke);
                        e.setAttribute('stroke-width', origStrokeWidth);
                    });
                    edge.setAttribute('stroke-width', '5');
                    edge.setAttribute('stroke', 'red');
                    const parentG = edge.closest('g');
                    if (parentG && parentG.parentNode) {
                        parentG.parentNode.appendChild(parentG);
                    }
                    const detailDiv2 = document.getElementById('edgeDetails2');
                    const edgeId = (edge.closest('[id^="edge_"]') || edge).id;
                    detailDiv2.textContent = edgeInfo2[edgeId] || "No extra details available for this upstream dependency.";
                });
            });
        });
    });
    </script>
    {% endif %}
    
    {% if object_type == "View" and view_definition %}
    <h2>View Definition:</h2>
    <div class="code-container">
        <button class="copy-button" onclick="copyToClipboard('code-block')">Copy</button>
        <pre><code class="language-sql" id="code-block">{{ view_definition }}</code></pre>
    </div>
    <script>
    function copyToClipboard(elementId) {
        var codeElement = document.getElementById(elementId);
        var range = document.createRange();
        range.selectNodeContents(codeElement);
        var selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        try {
            document.execCommand('copy');
            alert('Copied to clipboard!');
        } catch (err) {
            console.error('Failed to copy: ', err);
        }
        selection.removeAllRanges();
    }
    </script>
    {% endif %}
</body>
</html>
"""

MAIN_TEMPLATE = """
<html>
<head>
<title>Main ER Diagram</title>
<style>
body {
    font-family: Helvetica, Arial, sans-serif;
    margin: 20px;
}
object {
    border:1px solid #ccc; 
    max-width:100%; 
    height:auto;
}
</style>
</head>
<body>
<h1>Main ER Diagram</h1>
<p>Click on a line (edge) to toggle its highlight. Multiple edges can be highlighted at once. Click again to revert.</p>
<object data="public_er_diagram.svg" type="image/svg+xml" id="mainSVG">
    Your browser does not support SVG
</object>
<script>
document.addEventListener('DOMContentLoaded', () => {
    const svgObject = document.getElementById('mainSVG');
    svgObject.addEventListener('load', () => {
        const svgDoc = svgObject.contentDocument;
        let edgePaths = svgDoc.querySelectorAll('[id^="edge_"] path');
        if (edgePaths.length === 0) {
            edgePaths = svgDoc.querySelectorAll('[id^="edge_"]');
        }
        let originalStyles = new Map();
        edgePaths.forEach(edge => {
            let origStroke = edge.getAttribute('stroke') || '';
            let origStrokeWidth = edge.getAttribute('stroke-width') || '1';
            originalStyles.set(edge, {stroke: origStroke, strokeWidth: origStrokeWidth});
        });
        edgePaths.forEach(edge => {
            edge.addEventListener('click', () => {
                const currentWidth = edge.getAttribute('stroke-width') || '1';
                if (currentWidth === '5') {
                    const orig = originalStyles.get(edge);
                    edge.setAttribute('stroke', orig.stroke);
                    edge.setAttribute('stroke-width', orig.strokeWidth);
                } else {
                    edge.setAttribute('stroke-width', '5');
                    edge.setAttribute('stroke', 'red');
                    const parentG = edge.closest('g');
                    if (parentG && parentG.parentNode) {
                        parentG.parentNode.appendChild(parentG);
                    }
                }
            });
        });
    });
});
</script>
</body>
<footer>
    <p>Created by <a href="https://example.com" target="_blank">Your Name</a>. This code is open-source—use it as you see fit.</p>
</footer>
</html>
"""

# -----------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------
def is_calculation_expression(expr: str) -> bool:
    """Check if the expression contains calculation keywords."""
    keywords_calc = ['sum(', 'avg(', 'min(', 'max(', 'count(', 'case ', ' when ', ' then ', ' else ', 'distinct(']
    return any(k in expr.lower() for k in keywords_calc)


def parse_column_expression(view_sql: str, col_name: str):
    """
    Parse a column expression from the SQL view definition to determine if it involves calculations.
    Returns a tuple (found_calc, snippet) where:
        - found_calc is True if a calculation is detected,
        - False if it is a pass-through,
        - None if not found.
    """
    parsed = sqlparse.parse(view_sql)
    if not parsed:
        return None, ""

    statement = parsed[0]
    select_tokens = []
    select_seen = False
    for token in statement.tokens:
        if token.ttype is sqlparse.tokens.DML and token.value.upper() == 'SELECT':
            select_seen = True
            continue
        if select_seen and token.is_keyword and token.value.upper() in ('FROM', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'LIMIT'):
            break
        if select_seen:
            select_tokens.append(str(token))
    
    select_str = "".join(select_tokens)
    sub_parsed = sqlparse.parse(select_str)
    if not sub_parsed:
        return None, ""
    
    select_stmt = sub_parsed[0]
    for token in select_stmt.tokens:
        if token.is_group:
            for sub_token in token.tokens:
                if sub_token.is_group:
                    text = sub_token.value
                    if f" as {col_name.lower()}" in text.lower():
                        return (True, text) if is_calculation_expression(text) else (False, text)
    return None, ""


def build_object_definition_map(data: pd.DataFrame) -> dict:
    """
    Build a mapping of object names (tables/views) to their SQL definitions.
    """
    obj_def = {}
    for _, row in data.iterrows():
        name = str(row.get('table_name', '')).strip()
        definition = str(row.get('view_definition', '')).strip()
        if name and name.lower() != 'nan':
            if definition and definition.lower() != 'nan':
                obj_def[name] = definition
            else:
                obj_def.setdefault(name, "")
    return obj_def


def build_simple_graph(data: pd.DataFrame) -> dict:
    """
    Build a dependency graph (parent -> [child, ...])
    where parent = source_table_name and child = dependent_view_name.
    """
    graph = defaultdict(list)
    for _, row in data.iterrows():
        parent = str(row.get('source_table_name', '')).strip()
        child = str(row.get('dependent_view_name', '')).strip()
        if parent and child and parent.lower() != 'nan' and child.lower() != 'nan':
            graph[parent].append(child)
    return dict(graph)


def trace_column(col_name: str, start_view: str, obj_def_map: dict, graph: dict, visited=None):
    """
    Recursively trace a column through a view dependency chain.
    """
    if visited is None:
        visited = set()
    key = (start_view.lower(), col_name.lower())
    if key in visited:
        return []
    visited.add(key)

    view_sql = obj_def_map.get(start_view, "")
    if not view_sql:
        return [f"* Reached base object '{start_view}' (no SQL definition)."]

    found_calc, snippet = parse_column_expression(view_sql, col_name)
    if found_calc is None:
        # Check parent dependencies if the column is not explicitly found.
        parents = [p for p, children in graph.items() if start_view in children]
        if not parents:
            return [f"* '{col_name}' not found in '{start_view}' => likely a base object."]
        chain = []
        for prt in parents:
            sub_chain = trace_column(col_name, prt, obj_def_map, graph, visited)
            if sub_chain:
                chain.append(f"'{col_name}' not explicitly in '{start_view}', check parent '{prt}':")
                chain.extend(sub_chain)
                break
        return chain if chain else [f"* '{col_name}' not found in '{start_view}' and no parent leads to a calc or table."]
    
    if found_calc is True:
        return [f"* Calculation in '{start_view}': {snippet.strip()}"]

    # If pass-through (found_calc is False), look at parent dependencies.
    parents = [p for p, children in graph.items() if start_view in children]
    if not parents:
        return [f"* Column '{col_name}' pass-through in '{start_view}'.",
                f"* Reached base object '{start_view}' (no parent)."]
    
    chain = [f"Column '{col_name}' pass-through in '{start_view}' => search its parent(s)"]
    for prt in parents:
        sub_chain = trace_column(col_name, prt, obj_def_map, graph, visited)
        if sub_chain:
            chain.append(f"=> parent: '{prt}'")
            chain.extend(sub_chain)
            break
    return chain


def condense_if_no_calc(chain_lines: list, col_name: str) -> list:
    """
    If the calculation chain does not include a calculation, condense the output.
    """
    if any("Calculation in" in line for line in chain_lines):
        return chain_lines  # Do not condense if a calculation is detected.
    base_obj_line = None
    for line in reversed(chain_lines):
        if "Reached base object" in line:
            base_obj_line = line
            break
    if not base_obj_line:
        return chain_lines
    m = re.search(r"Reached base object '([^']+)'", base_obj_line)
    if not m:
        return chain_lines
    base_name = m.group(1)
    return [f"Column '{col_name}' => same as '{base_name}' (no calculation)"]


def render_calculation_chains_as_html(calculation_chains: dict) -> str:
    """
    Convert the calculation chains into an HTML fragment.
    """
    if not calculation_chains:
        return ""
    html_parts = ["<h2>Calculation Chains:</h2>"]
    for col, chain_lines in calculation_chains.items():
        condensed = condense_if_no_calc(chain_lines, col)
        html_parts.append(f"<h3>Column: {col}</h3>")
        html_parts.append("<ul>")
        for line in condensed:
            html_parts.append(f"<li>{line}</li>")
        html_parts.append("</ul>")
    return "\n".join(html_parts)


def generate_calculation_chains_for_view(view_name: str, columns: list, data: pd.DataFrame) -> dict:
    """
    Generate calculation chains for all columns in a view.
    """
    obj_def_map = build_object_definition_map(data)
    graph = build_simple_graph(data)
    chains = {}
    for col in columns:
        chains[col] = trace_column(col, view_name, obj_def_map, graph)
    return chains


def build_dependency_graph(view_name: str, view_info: dict, table_columns: dict, view_deps_df: pd.DataFrame) -> Digraph:
    """
    Build a Graphviz Digraph of downstream dependencies.
    """
    graph = Digraph(view_name + '_deps')
    graph.attr(rankdir='TB', splines='ortho', ranksep='0.75', nodesep='0.5', fontname='Helvetica')
    graph.attr('node', fontname='Helvetica')
    graph.attr('edge', fontname='Helvetica')
    visited = set()

    def recurse(v):
        if v in visited:
            return
        visited.add(v)
        node_url = f"{v}.html"
        if v in table_columns:
            graph.node(v, shape='box', style='filled', color='lightblue', URL=node_url, target="_top")
        else:
            graph.node(v, shape='ellipse', style='filled', color='lightyellow', URL=node_url, target="_top")
        deps = view_deps_df[view_deps_df['dependent_view_name'] == v]['source_table_name'].unique()
        for dep in deps:
            edge_id = f"edge_{v}_{dep}"
            graph.edge(v, dep, color='brown', id=edge_id, decorate='true', penwidth='2')
            recurse(dep)
    recurse(view_name)
    return graph


def build_reverse_dependency_graph(view_name: str, view_info: dict, table_columns: dict, view_deps_df: pd.DataFrame) -> Digraph:
    """
    Build a Graphviz Digraph of upstream dependencies (which objects depend on the view).
    """
    graph = Digraph(view_name + '_revdeps')
    graph.attr(rankdir='TB', splines='ortho', ranksep='0.75', nodesep='0.5', fontname='Helvetica')
    graph.attr('node', fontname='Helvetica')
    graph.attr('edge', fontname='Helvetica')
    visited = set()

    def recurse_up(obj):
        if obj in visited:
            return
        visited.add(obj)
        node_url = f"{obj}.html"
        if obj in table_columns:
            graph.node(obj, shape='box', style='filled', color='lightblue', URL=node_url, target="_top")
        else:
            graph.node(obj, shape='ellipse', style='filled', color='lightyellow', URL=node_url, target="_top")
        children = view_deps_df[view_deps_df['source_table_name'] == obj]['dependent_view_name'].unique()
        for child in children:
            edge_id = f"edge_{child}_{obj}"
            graph.edge(child, obj, color='brown', id=edge_id, decorate='true', penwidth='2')
            recurse_up(child)
    recurse_up(view_name)
    return graph


def snippet_around_keyword(text: str, keyword: str, snippet_length: int = 150) -> str:
    """
    Return a snippet of text around the keyword.
    """
    if not text:
        return ""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return (text[:snippet_length] + '...') if len(text) > snippet_length else text
    start = max(0, idx - snippet_length // 2)
    end = min(len(text), start + snippet_length)
    snippet = text[start:end]
    if start > 0:
        snippet = '...' + snippet
    if end < len(text):
        snippet = snippet + '...'
    return snippet


# -----------------------------------------------------------
# HTML PAGE GENERATION (using Jinja2 Templates)
# -----------------------------------------------------------
def create_html_detail_file(name: str, columns: list, object_type: str, data: pd.DataFrame, 
                            view_definition: str = None, has_dep_graph: bool = False, has_rev_dep_graph: bool = False,
                            details_dir: str = DEFAULT_DETAILS_DIR):
    """
    Create an HTML detail file for a table or view using the Jinja2 template.
    """
    os.makedirs(details_dir, exist_ok=True)
    
    if object_type == "View":
        calc_chains = generate_calculation_chains_for_view(name, columns, data)
        calc_chains_html = render_calculation_chains_as_html(calc_chains)
    else:
        calc_chains_html = ""
    
    template = Template(DETAIL_TEMPLATE)
    html_content = template.render(
        name=name,
        columns=columns,
        object_type=object_type,
        calc_chains=calc_chains_html,
        view_definition=view_definition,
        has_dep_graph=has_dep_graph,
        has_rev_dep_graph=has_rev_dep_graph
    )
    
    output_file = os.path.join(details_dir, f"{name}.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logging.info(f"Detail page created: {output_file}")


def add_relationships(data: pd.DataFrame, details_dir: str):
    """
    Process metadata to generate detail pages and the ER diagram.
    """
    tables = data[data['object_type'] == 'BASE TABLE']
    view_columns_df = data[data['object_type'] == 'VIEW']
    view_deps_df = data[data['object_type'] == 'VIEW_DEPENDENCY']
    pks = data[data['object_type'] == 'PRIMARY_KEY']
    fks = data[data['constraint_type'] == 'FOREIGN KEY']

    # Group columns for tables and views.
    table_columns = tables.groupby('table_name')['column_name'].apply(list).to_dict()
    view_columns = view_columns_df.groupby('table_name')['column_name'].apply(list).to_dict()
    view_definitions = view_deps_df.groupby('dependent_view_name')['view_definition'].first().to_dict()

    all_view_names = set(view_columns.keys()).union(set(view_definitions.keys()))
    view_info = {}
    for vname in all_view_names:
        cols = view_columns.get(vname, [])
        vdef = view_definitions.get(vname, '')
        view_info[vname] = {'columns': cols, 'view_definition': vdef}

    logging.info("Generating detail pages for tables...")
    for table_name, cols in tqdm(list(table_columns.items()), desc="Tables"):
        create_html_detail_file(table_name, cols, "Table", data, details_dir=details_dir)

    logging.info("Generating detail pages for views...")
    for view_name, info in tqdm(list(view_info.items()), desc="Views"):
        cols = info.get('columns', [])
        vdef = info.get('view_definition', '')
        has_dep = view_deps_df[view_deps_df['dependent_view_name'] == view_name].shape[0] > 0
        has_rev = view_deps_df[view_deps_df['source_table_name'] == view_name].shape[0] > 0

        if has_dep:
            dep_graph = build_dependency_graph(view_name, view_info, table_columns, view_deps_df)
            dep_svg_path = os.path.join(details_dir, f"{view_name}_dependencies")
            dep_graph.render(dep_svg_path, format='svg', cleanup=True)
        if has_rev:
            rev_graph = build_reverse_dependency_graph(view_name, view_info, table_columns, view_deps_df)
            rev_svg_path = os.path.join(details_dir, f"{view_name}_reverse_dependencies")
            rev_graph.render(rev_svg_path, format='svg', cleanup=True)

        create_html_detail_file(view_name, cols, "View", data, view_definition=vdef,
                                has_dep_graph=has_dep, has_rev_dep_graph=has_rev, details_dir=details_dir)

    # Build the main ER diagram.
    er_diagram = Digraph('ER_Diagram', format='svg')
    er_diagram.attr(rankdir='LR', splines='ortho', ranksep='1.5', nodesep='1.5', fontname='Helvetica')
    er_diagram.attr('node', fontname='Helvetica')
    er_diagram.attr('edge', fontname='Helvetica')

    with er_diagram.subgraph(name='cluster_tables') as c_t:
        c_t.attr(label='Tables', style='filled', color='lightgrey', fontsize='14', labelloc="t")
        for table_name in table_columns:
            col_tooltip = "Columns:\n" + "\n".join(table_columns[table_name])
            c_t.node(table_name, shape='box', style='filled', color='lightblue', tooltip=col_tooltip,
                     fixedsize='true', width='2.5', height='1.5', margin='0.5', URL=f"details/{table_name}.html")

    with er_diagram.subgraph(name='cluster_views') as c_v:
        c_v.attr(label='Views', style='filled', color='lightgrey', fontsize='14', labelloc="t")
        for view_name, info in view_info.items():
            cols = info.get('columns', [])
            col_tooltip = "View Columns:\n" + "\n".join(cols)
            c_v.node(view_name, shape='ellipse', style='filled', color='lightyellow',
                     tooltip=col_tooltip, margin='0.3', URL=f"details/{view_name}.html")

    # Highlight primary key tables.
    for _, row in pks.iterrows():
        er_diagram.node(row['table_name'], shape='box', style='filled', color='lightgreen')

    # Add foreign key edges.
    for _, row in fks.iterrows():
        fk_label = f"FK: {row['source_table_name']}({row['column_name']}) → {row['target_table']}({row['target_column']})"
        edge_id = f"edge_{row['source_table_name']}_{row['target_table']}"
        er_diagram.edge(row['source_table_name'], row['target_table'],
                        label=fk_label, color='blue', fontsize='10',
                        tooltip=f"Foreign key from {row['source_table_name']}({row['column_name']}) to {row['target_table']}({row['target_column']})",
                        id=edge_id, decorate='true', penwidth='2')

    # Add view dependency edges.
    for _, row in view_deps_df.iterrows():
        view_name = row['dependent_view_name']
        table_name = row['source_table_name']
        vdef = view_info.get(view_name, {}).get('view_definition', '')
        snippet = snippet_around_keyword(vdef, table_name, 150)
        tooltip_text = f"{view_name} depends on {table_name}\\nSnippet:\\n{snippet}"
        edge_id = f"edge_{view_name}_{table_name}"
        er_diagram.edge(view_name, table_name, color='brown', fontsize='10',
                        tooltip=tooltip_text, id=edge_id, decorate='true', penwidth='2')

    # Place the ER diagram SVG in the parent directory of the details folder.
    er_output_path = os.path.join(os.path.dirname(details_dir), 'public_er_diagram')
    er_diagram.render(er_output_path, format='svg', cleanup=True)
    logging.info(f"ER diagram saved to: {er_output_path}.svg")

    # Generate the main HTML page using the Jinja2 template.
    main_html_content = Template(MAIN_TEMPLATE).render()
    main_html_file = os.path.join(os.path.dirname(er_output_path), 'main.html')
    with open(main_html_file, 'w', encoding='utf-8') as f:
        f.write(main_html_content)
    logging.info(f"Main HTML page created: {main_html_file}")


def fetch_data(conn_params: dict, schema: str = DEFAULT_SCHEMA) -> pd.DataFrame:
    """
    Connect to the PostgreSQL database and fetch metadata.
    """
    query_main = f"""
WITH tables_and_views AS (
    SELECT 
        c.table_schema,
        c.table_name,
        c.column_name,
        t.table_type AS object_type,
        NULL AS dependent_view_name,
        NULL AS source_table_schema,
        NULL AS source_table_name,
        NULL AS constraint_type,
        NULL AS target_table,
        NULL AS target_column
    FROM 
        information_schema.columns c
    JOIN 
        information_schema.tables t
        ON c.table_schema = t.table_schema AND c.table_name = t.table_name
    WHERE 
        c.table_schema = '{schema}'
    
    UNION ALL
    
    SELECT 
        NULL AS table_schema,
        vu.view_name AS table_name,
        NULL AS column_name,
        'VIEW_DEPENDENCY' AS object_type,
        vu.view_name AS dependent_view_name,
        vu.table_schema AS source_table_schema,
        vu.table_name AS source_table_name,
        NULL AS constraint_type,
        NULL AS target_table,
        NULL AS target_column
    FROM 
        information_schema.view_table_usage vu
    WHERE 
        vu.table_schema = '{schema}'
    
    UNION ALL
    
    SELECT 
        tc.table_schema,
        tc.table_name,
        kcu.column_name,
        'PRIMARY_KEY' AS object_type,
        NULL AS dependent_view_name,
        NULL AS source_table_schema,
        NULL AS source_table_name,
        tc.constraint_type,
        NULL AS target_table,
        NULL AS target_column
    FROM 
        information_schema.table_constraints tc
    JOIN 
        information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE 
        tc.table_schema = '{schema}'
        AND tc.constraint_type = 'PRIMARY KEY'
    
    UNION ALL
    
    SELECT 
        tc.table_schema AS table_schema,
        tc.table_name AS table_name,
        kcu.column_name AS column_name,
        'FOREIGN_KEY' AS object_type,
        NULL AS dependent_view_name,
        ccu.table_schema AS source_table_schema,
        ccu.table_name AS source_table_name,
        tc.constraint_type,
        ccu.table_name AS target_table,
        ccu.column_name AS target_column
    FROM 
        information_schema.table_constraints tc
    JOIN 
        information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    JOIN 
        information_schema.constraint_column_usage ccu
        ON tc.constraint_name = ccu.constraint_name
    WHERE 
        tc.table_schema = '{schema}'
        AND tc.constraint_type = 'FOREIGN KEY'
)
SELECT *
FROM tables_and_views
ORDER BY table_schema, table_name, column_name;
"""
    query_viewdefs = f"""
SELECT 
    table_name, 
    view_definition
FROM information_schema.views
WHERE table_schema = '{schema}';
"""
    try:
        conn = psycopg2.connect(**conn_params)
        data_main = pd.read_sql(query_main, conn)
        data_viewdefs = pd.read_sql(query_viewdefs, conn)
        conn.close()
        data = data_main.merge(data_viewdefs, on='table_name', how='left')
        return data
    except Exception as e:
        logging.error("Error fetching data: %s", e)
        sys.exit(1)


# -----------------------------------------------------------
# WEB DASHBOARD (Flask)
# -----------------------------------------------------------
def run_dashboard(root_dir: str):
    """
    Launch a simple Flask web dashboard to serve the generated HTML and SVG files.
    """
    try:
        from flask import Flask, send_from_directory, abort
    except ImportError:
        logging.error("Flask is not installed. Please install it to use the dashboard (--dashboard).")
        sys.exit(1)

    app = Flask(__name__, static_folder=root_dir)

    @app.route('/')
    def index():
        return send_from_directory(root_dir, 'main.html')

    @app.route('/<path:filename>')
    def static_files(filename):
        file_path = os.path.join(root_dir, filename)
        if os.path.exists(file_path):
            return send_from_directory(root_dir, filename)
        else:
            abort(404)

    logging.info("Starting Flask dashboard at http://127.0.0.1:5000")
    app.run(debug=True)


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Enhanced ER Diagram Generator")
    parser.add_argument('--db-user', type=str, default='postgres', help="Database username")
    parser.add_argument('--db-password', type=str, default='your_password', help="Database password")
    parser.add_argument('--db-host', type=str, default='localhost', help="Database host")
    parser.add_argument('--db-port', type=int, default=5432, help="Database port")
    parser.add_argument('--dashboard', action='store_true', help="Run the Flask web dashboard after generating output")
    parser.add_argument('--config', type=str, help="Path to JSON config file for DB credentials")
    args = parser.parse_args()

    # Use a constant database name.
    db_name = "your_database"

    # Use generic output directories.
    output_dir = DEFAULT_OUTPUT_DIR
    details_dir = DEFAULT_DETAILS_DIR
    os.makedirs(details_dir, exist_ok=True)

    # Secure database credentials via environment variables.
    db_user = os.getenv("PG_DB_USER", args.db_user)
    db_password = os.getenv("PG_DB_PASSWORD", args.db_password)
    db_host = os.getenv("PG_DB_HOST", args.db_host)
    db_port = int(os.getenv("PG_DB_PORT", args.db_port))

    # Optionally override credentials with a JSON config file.
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config_data = json.load(f)
                db_user = config_data.get("db_user", db_user)
                db_password = config_data.get("db_password", db_password)
                db_host = config_data.get("db_host", db_host)
                db_port = config_data.get("db_port", db_port)
        except Exception as e:
            logging.error("Error reading config file: %s", e)
            sys.exit(1)

    # Connection parameters
    conn_params = {
        'dbname': db_name,
        'user': db_user,
        'password': db_password,
        'host': db_host,
        'port': db_port
    }
    logging.info(f"Connecting to database: {db_name}")
    data = fetch_data(conn_params)

    add_relationships(data, details_dir=details_dir)
    logging.info("Process completed successfully.")

    # If the --dashboard flag is set, launch the Flask web dashboard.
    if args.dashboard:
        run_dashboard(output_dir)


if __name__ == '__main__':
    main()
