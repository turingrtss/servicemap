#!/usr/bin/env python3
"""
ServiceMap - Auto-generate service dependency graphs from logs
No agents. No setup. Just point at your logs.
"""

import re
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

__version__ = "0.1.0"


class LogParser:
    """Parse logs and extract service calls"""
    
    # Patterns for detecting service calls
    HTTP_PATTERN = re.compile(r'(GET|POST|PUT|DELETE|PATCH)\s+https?://([^:/\s]+)(?::(\d+))?')
    GRPC_PATTERN = re.compile(r'grpc://([^:/\s]+)(?::(\d+))?/([^\s]+)')
    DB_PATTERN = re.compile(r'(SELECT|INSERT|UPDATE|DELETE)\s+.+?\s+FROM\s+(\w+)', re.IGNORECASE)
    
    def __init__(self):
        self.calls = defaultdict(lambda: defaultdict(int))  # {source: {target: count}}
        self.services = set()
        
    def parse_file(self, path: Path):
        """Parse a single log file"""
        with open(path, 'r', errors='ignore') as f:
            for line in f:
                self._parse_line(line, path.stem)
                
    def _parse_line(self, line: str, source_service: str):
        """Extract service calls from a log line"""
        self.services.add(source_service)
        
        # Try JSON first
        try:
            data = json.loads(line)
            service = data.get('service', source_service)
            self.services.add(service)
            
            # Check for explicit service calls
            if 'http_call' in data:
                target = self._extract_target(data['http_call'])
                if target:
                    self.calls[service][target] += 1
            elif 'grpc_call' in data:
                target = data['grpc_call'].split('/')[0]
                self.calls[service][target] += 1
            elif 'sql_query' in data:
                table = self._extract_db_table(data['sql_query'])
                if table:
                    self.calls[service][f'db:{table}'] += 1
                    
        except json.JSONDecodeError:
            # Plain text log
            self._parse_plain_text(line, source_service)
            
    def _parse_plain_text(self, line: str, source: str):
        """Parse plain text logs for service calls"""
        # HTTP calls
        for match in self.HTTP_PATTERN.finditer(line):
            method, host, port = match.groups()
            target = host.split('.')[0]  # Extract service name
            self.calls[source][target] += 1
            self.services.add(target)
            
        # gRPC calls
        for match in self.GRPC_PATTERN.finditer(line):
            host, port, method = match.groups()
            target = host.split('.')[0]
            self.calls[source][target] += 1
            self.services.add(target)
            
        # Database queries
        for match in self.DB_PATTERN.finditer(line):
            operation, table = match.groups()
            self.calls[source][f'db:{table}'] += 1
            
    def _extract_target(self, url: str) -> str:
        """Extract service name from URL"""
        match = re.search(r'//([^:/\s]+)', url)
        if match:
            host = match.group(1)
            return host.split('.')[0]  # Extract service name
        return None
        
    def _extract_db_table(self, query: str) -> str:
        """Extract table name from SQL"""
        match = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
        return match.group(1) if match else None


class GraphGenerator:
    """Generate visual dependency graph"""
    
    def __init__(self, parser: LogParser):
        self.parser = parser
        
    def generate_text(self) -> str:
        """Generate text-based dependency list"""
        output = []
        output.append("=== SERVICE DEPENDENCIES ===\n")
        
        for source in sorted(self.parser.calls.keys()):
            targets = self.parser.calls[source]
            for target, count in sorted(targets.items(), key=lambda x: -x[1]):
                output.append(f"{source} → {target} ({count} calls)")
                
        # Find orphaned services
        called_services = {t for targets in self.parser.calls.values() for t in targets.keys()}
        calling_services = set(self.parser.calls.keys())
        orphaned = self.parser.services - calling_services - called_services
        
        if orphaned:
            output.append("\n=== ORPHANED SERVICES ===")
            for service in sorted(orphaned):
                output.append(f"❓ {service} (no calls detected)")
                
        return "\n".join(output)
        
    def generate_html(self) -> str:
        """Generate interactive HTML visualization"""
        # Build nodes and edges for vis.js
        nodes = []
        for i, service in enumerate(sorted(self.parser.services)):
            color = "#3498db" if service.startswith('db:') else "#2ecc71"
            nodes.append({
                "id": i,
                "label": service,
                "color": color,
                "shape": "box" if service.startswith('db:') else "ellipse"
            })
            
        service_to_id = {s: i for i, s in enumerate(sorted(self.parser.services))}
        
        edges = []
        for source, targets in self.parser.calls.items():
            for target, count in targets.items():
                if source in service_to_id and target in service_to_id:
                    edges.append({
                        "from": service_to_id[source],
                        "to": service_to_id[target],
                        "value": count,
                        "label": str(count)
                    })
                    
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Service Dependency Map</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
        #network {{ width: 100%; height: 600px; border: 1px solid #ddd; }}
        h1 {{ color: #333; }}
        .info {{ margin: 20px 0; padding: 10px; background: #f5f5f5; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>Service Dependency Map</h1>
    <div class="info">
        <strong>Services:</strong> {len(self.parser.services)} &nbsp;|&nbsp;
        <strong>Dependencies:</strong> {sum(len(t) for t in self.parser.calls.values())} &nbsp;|&nbsp;
        <strong>Total Calls:</strong> {sum(sum(t.values()) for t in self.parser.calls.values())}
    </div>
    <div id="network"></div>
    <script>
        var nodes = new vis.DataSet({json.dumps(nodes)});
        var edges = new vis.DataSet({json.dumps(edges)});
        var container = document.getElementById('network');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            edges: {{
                arrows: 'to',
                smooth: {{ type: 'cubicBezier' }}
            }},
            physics: {{
                enabled: true,
                solver: 'forceAtlas2Based'
            }}
        }};
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>"""
        return html


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate service dependency graphs from logs')
    parser.add_argument('path', help='Log file or directory')
    parser.add_argument('--output', '-o', help='Output file (default: stdout for text, servicemap.html for HTML)')
    parser.add_argument('--format', '-f', choices=['text', 'html'], default='text', help='Output format')
    parser.add_argument('--version', action='version', version=f'ServiceMap {__version__}')
    
    args = parser.parse_args()
    
    # Parse logs
    log_parser = LogParser()
    path = Path(args.path)
    
    if path.is_file():
        log_parser.parse_file(path)
    elif path.is_dir():
        for log_file in path.rglob('*.log'):
            log_parser.parse_file(log_file)
        for json_file in path.rglob('*.json'):
            log_parser.parse_file(json_file)
    else:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
        
    if not log_parser.services:
        print("No services detected in logs", file=sys.stderr)
        sys.exit(1)
        
    # Generate output
    gen = GraphGenerator(log_parser)
    
    if args.format == 'text':
        output = gen.generate_text()
        if args.output:
            Path(args.output).write_text(output)
        else:
            print(output)
    else:
        output = gen.generate_html()
        output_file = args.output or 'servicemap.html'
        Path(output_file).write_text(output)
        print(f"✓ Dependency map saved to {output_file}")


if __name__ == '__main__':
    main()
