#!/usr/bin/env python3
"""
Simple local development server for testing the frontend
This bypasses the need for AWS SAM and Lambda
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime
import uuid

# In-memory storage
users = {}
portfolios = {}

class CORSRequestHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        data = json.loads(body) if body else {}

        # Handle authentication
        if self.path == '/auth/register':
            user_id = str(uuid.uuid4())
            users[data['email']] = {
                'user_id': user_id,
                'email': data['email'],
                'password': data['password'],  # In real app, hash this!
                'full_name': data.get('full_name'),
                'created_at': datetime.utcnow().isoformat()
            }
            portfolios[user_id] = []

            response = {
                'success': True,
                'data': {
                    'access_token': f'mock_token_{user_id}',
                    'token_type': 'bearer',
                    'user': users[data['email']]
                }
            }
            self.send_response(201)
            self.send_header('Content-Type', 'application/json')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        elif self.path == '/auth/login':
            if data['email'] in users and users[data['email']]['password'] == data['password']:
                user = users[data['email']]
                response = {
                    'success': True,
                    'data': {
                        'access_token': f'mock_token_{user["user_id"]}',
                        'token_type': 'bearer',
                        'user': user
                    }
                }
                self.send_response(200)
            else:
                response = {'success': False, 'error': 'Invalid credentials'}
                self.send_response(401)

            self.send_header('Content-Type', 'application/json')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        elif self.path == '/portfolio/assets':
            # Mock add asset
            auth_header = self.headers.get('Authorization', '')
            user_id = auth_header.replace('Bearer mock_token_', '')

            asset = {
                'asset_id': str(uuid.uuid4()),
                'user_id': user_id,
                **data,
                'current_price': 50000 if data['asset_type'] == 'crypto' else 150,
                'created_at': datetime.utcnow().isoformat()
            }

            if user_id in portfolios:
                portfolios[user_id].append(asset)

            response = {'success': True, 'data': asset}
            self.send_response(201)
            self.send_header('Content-Type', 'application/json')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        else:
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()

    def do_GET(self):
        auth_header = self.headers.get('Authorization', '')
        user_id = auth_header.replace('Bearer mock_token_', '')

        if self.path == '/portfolio/summary':
            response = {
                'success': True,
                'data': {
                    'crypto_count': 0,
                    'stock_count': 0,
                    'total_assets': 0,
                    'crypto_value': 0.0,
                    'stock_value': 0.0,
                    'total_value': 0.0,
                    'total_invested': 0.0,
                    'total_gain_loss': 0.0,
                    'total_gain_loss_percentage': 0.0
                }
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        elif self.path == '/portfolio/crypto':
            assets = portfolios.get(user_id, [])
            crypto_assets = [a for a in assets if a.get('asset_type') == 'crypto']
            response = {
                'success': True,
                'data': {
                    'user_id': user_id,
                    'assets': crypto_assets,
                    'total_value': 0.0,
                    'total_invested': 0.0,
                    'total_gain_loss': 0.0,
                    'total_gain_loss_percentage': 0.0
                }
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        elif self.path == '/portfolio/stocks':
            assets = portfolios.get(user_id, [])
            stock_assets = [a for a in assets if a.get('asset_type') == 'stock']
            response = {
                'success': True,
                'data': {
                    'user_id': user_id,
                    'assets': stock_assets,
                    'total_value': 0.0,
                    'total_invested': 0.0,
                    'total_gain_loss': 0.0,
                    'total_gain_loss_percentage': 0.0
                }
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._set_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        else:
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('localhost', 3000), CORSRequestHandler)
    print('🚀 Mock Backend Server running on http://localhost:3000')
    print('✅ Frontend can connect at http://localhost:5173')
    print('\nPress Ctrl+C to stop\n')
    server.serve_forever()
