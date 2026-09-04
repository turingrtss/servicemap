#!/usr/bin/env python3
"""
ServiceMap v2 - Multi-stage log parser for microservice dependencies
Handles K8s logs, application logs, plain text, and service mesh logs
"""

import re
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from enum import Enum

__version__ = "0.2.0"


class LogFormat(Enum):
    """Detected log format types"""
    K8S_JSON = "k8s_json"          # kubectl logs format
    APP_JSON = "app_json"          # Application JSON logs
    PLAIN_TEXT = "plain_text"      # Plain text logs
    ENVOY = "envoy"                # Istio/Envoy sidecar logs
    UNKNOWN = "unknown"


class LogParser:
    """Multi-stage log parser"""
    
    def __init__(self):
        self.calls = defaultdict(lambda: defaultdict(int))
        self.services = set()
        self.stats = defaultdict(int)  # Track what we parsed
        
    # ==================== STAGE 1: Format Detection ====================
    
    def detect_format(self, line: str) -> LogFormat:
        """Detect which log format this line uses"""
        line = line.strip()
        if not line:
            return LogFormat.UNKNOWN
            
        # K8s JSON wrapper: {"log":"...","stream":"...","time":"..."}
        if line.startswith('{"log":"') and '"stream":' in line and '"time":' in line:
            return LogFormat.K8S_JSON
            
        # Envoy/Istio: starts with [timestamp] and has specific structure
        if line.startswith('[20') and '" "' in line and 'upstream' in line:
            return LogFormat.ENVOY
            
        # Try parsing as JSON
        try:
            obj = json.loads(line)
            # Application JSON if has timestamp/severity/message
            if any(k in obj for k in ['timestamp', 'severity', 'level', 'message', 'msg']):
                return LogFormat.APP_JSON
        except:
            pass
            
        # Default to plain text
        return LogFormat.PLAIN_TEXT
        
    # ==================== STAGE 2: Extract Log Content ====================
    
    def extract_log_content(self, line: str, format_type: LogFormat) -> str:
        """Extract actual log message from wrapper format"""
        if format_type == LogFormat.K8S_JSON:
            try:
                obj = json.loads(line)
                # K8s wraps logs in {"log": "actual content\n"}
                return obj.get('log', '').rstrip('\n')
            except:
                return line
                
        # Other formats: line is already the content
        return line
        
    # ==================== STAGE 3: Find Service Calls ====================
    
    def find_service_calls(self, content: str, format_type: LogFormat) -> List[Dict]:
        """Extract service call information from log content"""
        calls = []
        
        if format_type == LogFormat.ENVOY:
            # Envoy format: field 10 is upstream cluster
            calls.extend(self._parse_envoy(content))
            
        elif format_type == LogFormat.APP_JSON:
            calls.extend(self._parse_app_json(content))
            
        else:
            # Plain text or K8s-unwrapped content
            calls.extend(self._parse_plain_text(content))
            
        return calls
        
    def _parse_envoy(self, line: str) -> List[Dict]:
        """Parse Envoy/Istio sidecar logs"""
        # Format: [time] "method path protocol" code ... "dest.svc.cluster.local:port" "ip:port"
        match = re.search(r'"([^"]+\.svc\.cluster\.local:\d+)"', line)
        if match:
            return [{'target': match.group(1)}]
        return []
        
    def _parse_app_json(self, content: str) -> List[Dict]:
        """Parse application JSON logs"""
        calls = []
        try:
            obj = json.loads(content)
            message = obj.get('message', '') or obj.get('msg', '')
            
            # Look for service calls in message field
            # Pattern: "calling X", "request to X", "grpc X", "http X"
            patterns = [
                r'calling\s+(\S+)',
                r'call(?:ing)?\s+(?:to\s+)?(\S+)',
                r'grpc\s+(?:to\s+)?(\S+)',
                r'http\s+(?:GET|POST|PUT|DELETE)\s+https?://(\S+)',
                r'request\s+to\s+(\S+)',
                r'connecting\s+to\s+(\S+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    calls.append({'target': match.group(1)})
                    
            # Also check for explicit target field
            if 'target' in obj:
                calls.append({'target': obj['target']})
                
            # Database calls
            if 'command' in obj and 'key' in obj:
                calls.append({'target': 'db:redis'})
            if 'sql' in obj or 'query' in obj:
                table = self._extract_db_table(obj.get('sql', '') or obj.get('query', ''))
                if table:
                    calls.append({'target': f'db:{table}'})
                    
        except:
            pass
        return calls
        
    def _parse_plain_text(self, content: str) -> List[Dict]:
        """Parse plain text logs for service calls"""
        calls = []
        
        # Pattern: service.namespace.svc.cluster.local:port
        for match in re.finditer(r'(\w[\w-]*(?:\.\w[\w-]*)*\.svc\.cluster\.local)(?::(\d+))?', content):
            calls.append({'target': match.group(1) + (':' + match.group(2) if match.group(2) else '')})
            
        # Pattern: http://service:port or grpc://service:port
        for match in re.finditer(r'(?:https?|grpc)://([a-zA-Z0-9.-]+)(?::(\d+))?', content):
            calls.append({'target': match.group(1) + (':' + match.group(2) if match.group(2) else '')})
            
        # Pattern: calling/connecting to service:port
        for match in re.finditer(r'(?:calling|connecting to|request to)\s+([a-zA-Z0-9.-]+)(?::(\d+))?', content, re.IGNORECASE):
            calls.append({'target': match.group(1)})
            
        return calls
        
    def _extract_db_table(self, query: str) -> Optional[str]:
        """Extract table name from SQL query"""
        match = re.search(r'\bFROM\s+(\w+)', query, re.IGNORECASE)
        return match.group(1) if match else None
        
    # ==================== STAGE 4: Extract Service Names ====================
    
    def extract_service_name(self, target: str) -> str:
        """Extract clean service name from various formats"""
        # Remove port
        target = re.sub(r':\d+$', '', target)
        
        # K8s FQDN: service.namespace.svc.cluster.local -> service
        if '.svc.cluster.local' in target:
            return target.split('.')[0]
            
        # Remove protocol
        target = re.sub(r'^https?://', '', target)
        target = re.sub(r'^grpc://', '', target)
        
        # Remove path
        target = target.split('/')[0]
        
        # If it's an IP, return None
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', target):
            return None
            
        # Filter out generic words that aren't service names
        generic_words = {'service', 'call', 'calling', 'to', 'at', 'http', 'grpc', 'the'}
        if target.lower() in generic_words:
            return None
            
        # Must contain at least one letter and be reasonable length
        if not re.search(r'[a-zA-Z]', target) or len(target) < 3:
            return None
            
        # Extract hostname (first part before any dots)
        # But keep service names like "api-gateway"
        parts = target.split('.')
        if len(parts) > 1 and parts[1] in ['default', 'prod', 'staging']:
            # Likely namespace, take first part
            return parts[0]
            
        return target
        
    # ==================== STAGE 5: Build Graph ====================
    
    def parse_file(self, path: Path, source_service: str = None):
        """Parse a log file"""
        if source_service is None:
            source_service = path.stem  # Use filename as service name
            
        with open(path, 'r', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                self._parse_line(line, source_service)
                
    def _parse_line(self, line: str, source_service: str):
        """Process a single log line through all stages"""
        # Stage 1: Detect format
        format_type = self.detect_format(line)
        if format_type == LogFormat.UNKNOWN:
            self.stats['unknown'] += 1
            return
            
        self.stats[format_type.value] += 1
        
        # Stage 2: Extract content
        content = self.extract_log_content(line, format_type)
        
        # Stage 3: Find service calls
        calls = self.find_service_calls(content, format_type)
        
        # Stage 4 & 5: Extract names and build graph
        self.services.add(source_service)
        
        for call in calls:
            target = call.get('target')
            if not target:
                continue
                
            service_name = self.extract_service_name(target)
            if service_name and service_name != source_service:
                self.calls[source_service][service_name] += 1
                self.services.add(service_name)
                self.stats['calls_found'] += 1


class GraphGenerator:
    """Generate visualizations"""
    
    def __init__(self, parser: LogParser):
        self.parser = parser
        
    def generate_text(self) -> str:
        """Text output with statistics"""
        output = []
        output.append("=== SERVICE DEPENDENCIES ===\n")
        
        if not self.parser.calls:
            output.append("No dependencies detected")
            output.append("\nParser Statistics:")
            for fmt, count in sorted(self.parser.stats.items()):
                output.append(f"  {fmt}: {count} lines")
            return "\n".join(output)
        
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
                
        # Statistics
        output.append("\n=== PARSER STATISTICS ===")
        for fmt, count in sorted(self.parser.stats.items()):
            output.append(f"  {fmt}: {count}")
            
        return "\n".join(output)
        
    def generate_html(self) -> str:
        """Interactive HTML visualization"""
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
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate service dependency graphs from logs')
    parser.add_argument('path', help='Log file or directory')
    parser.add_argument('--output', '-o', help='Output file')
    parser.add_argument('--format', '-f', choices=['text', 'html'], default='text')
    parser.add_argument('--version', action='version', version=f'ServiceMap {__version__}')
    
    args = parser.parse_args()
    
    log_parser = LogParser()
    path = Path(args.path)
    
    if path.is_file():
        log_parser.parse_file(path)
    elif path.is_dir():
        for log_file in path.rglob('*.log'):
            log_parser.parse_file(log_file)
    else:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
        
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
