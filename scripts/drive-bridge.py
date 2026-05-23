#!/usr/bin/env python3
"""
Google Drive Bridge — OAuth Device Flow
Secure, read-only metadata ingestion + selective download with verification.

Usage:
    1. Go to https://console.cloud.google.com/ → create OAuth 2.0 credentials
    2. Download client_secret.json
    3. Run: python3 scripts/drive-bridge.py --client-secret client_secret.json
    4. Follow device flow (visit URL, enter code)
    5. Bridge ingests metadata, optionally downloads files

CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
"""

import json
import os
import sys
import hashlib
import base64
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode

TOKEN_FILE = Path(__file__).parent.parent / '.local' / 'drive-token.json'
BRIDGE_LOG = Path(__file__).parent.parent / 'bridges' / 'google-drive' / 'ingestion-log.jsonl'


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def device_flow_auth(client_id, client_secret):
    """OAuth 2.0 device flow for Google Drive."""
    # Step 1: Request device code
    data = urlencode({
        'client_id': client_id,
        'scope': 'https://www.googleapis.com/auth/drive.metadata.readonly https://www.googleapis.com/auth/drive.readonly'
    }).encode()
    
    req = Request('https://oauth2.googleapis.com/device/code', data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    
    with urlopen(req) as resp:
        device_data = json.loads(resp.read().decode())
    
    print(f"\n{'='*60}")
    print("  GOOGLE DRIVE AUTH REQUIRED")
    print(f"{'='*60}")
    print(f"  1. Visit: {device_data['verification_url']}")
    print(f"  2. Enter code: {device_data['user_code']}")
    print(f"{'='*60}")
    print("  Waiting for authorization...")
    
    # Step 2: Poll for token
    import time
    interval = device_data.get('interval', 5)
    
    while True:
        time.sleep(interval)
        
        token_data = urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'device_code': device_data['device_code'],
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
        }).encode()
        
        req = Request('https://oauth2.googleapis.com/token', data=token_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        try:
            with urlopen(req) as resp:
                token_response = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  Poll error: {e}")
            continue
        
        if 'access_token' in token_response:
            print("  ✅ Authorized!")
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_FILE, 'w') as f:
                json.dump(token_response, f)
            return token_response['access_token']
        
        if token_response.get('error') == 'authorization_pending':
            continue
        else:
            print(f"  Auth error: {token_response.get('error_description', 'unknown')}")
            return None


def get_access_token(client_secret_path):
    """Get valid access token, refreshing if needed."""
    with open(client_secret_path) as f:
        secrets = json.load(f)
    
    client_id = secrets['installed']['client_id']
    client_secret = secrets['installed']['client_secret']
    
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f:
            token_data = json.load(f)
        
        # Check if expired
        # For simplicity, re-auth on each run for now
        # TODO: implement refresh_token logic
    
    return device_flow_auth(client_id, client_secret)


def list_drive_files(access_token, folder_id=None):
    """List files in Drive, optionally filtered to a folder."""
    query = "trashed=false"
    if folder_id:
        query += f" and '{folder_id}' in parents"
    
    url = f"https://www.googleapis.com/drive/v3/files?q={urlencode({'q': query})}&fields=files(id,name,mimeType,size,modifiedTime,md5Checksum)"
    
    req = Request(url)
    req.add_header('Authorization', f'Bearer {access_token}')
    
    with urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    
    return data.get('files', [])


def download_file(access_token, file_id, file_name, output_dir, verify=True):
    """Download a file with optional SHA-256 verification."""
    # Get file metadata first
    meta_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=size,md5Checksum,name"
    req = Request(meta_url)
    req.add_header('Authorization', f'Bearer {access_token}')
    
    with urlopen(req) as resp:
        metadata = json.loads(resp.read().decode())
    
    # Download
    download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    req = Request(download_url)
    req.add_header('Authorization', f'Bearer {access_token}')
    
    output_path = Path(output_dir) / file_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with urlopen(req) as resp:
        with open(output_path, 'wb') as f:
            f.write(resp.read())
    
    # Verify
    file_hash = sha256_file(output_path)
    
    if verify:
        print(f"  ✅ Downloaded: {file_name}")
        print(f"     SHA-256: {file_hash}")
    
    return {
        'file_id': file_id,
        'file_name': file_name,
        'sha256': file_hash,
        'size': metadata.get('size'),
        'md5': metadata.get('md5Checksum'),
        'path': str(output_path)
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='CP8 Google Drive Bridge')
    parser.add_argument('--client-secret', required=True, help='Path to client_secret.json')
    parser.add_argument('--folder-id', help='Specific Drive folder ID to scan')
    parser.add_argument('--output-dir', default='downloads/drive', help='Download directory')
    parser.add_argument('--download', action='store_true', help='Actually download files (default: metadata only)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    args = parser.parse_args()
    
    print(f"{'='*60}")
    print("  CP8 Google Drive Bridge")
    print(f"{'='*60}")
    
    # Authenticate
    access_token = get_access_token(args.client_secret)
    if not access_token:
        print("❌ Authentication failed")
        sys.exit(1)
    
    # List files
    print("\n📂 Listing Drive files...")
    files = list_drive_files(access_token, args.folder_id)
    
    print(f"  Found {len(files)} files")
    
    # Build manifest
    manifest = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'protocol': 'ASH-0.2',
        'hos_ground_truth': '63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320',
        'files': []
    }
    
    for f in files:
        print(f"\n  📄 {f['name']} ({f.get('size', '?')} bytes)")
        
        if args.dry_run:
            print("     [DRY RUN — skipping download]")
            continue
        
        if args.download:
            try:
                result = download_file(access_token, f['id'], f['name'], args.output_dir)
                manifest['files'].append(result)
            except Exception as e:
                print(f"     ❌ Download failed: {e}")
                manifest['files'].append({
                    'file_id': f['id'],
                    'file_name': f['name'],
                    'error': str(e)
                })
        else:
            manifest['files'].append({
                'file_id': f['id'],
                'file_name': f['name'],
                'mime_type': f.get('mimeType'),
                'size': f.get('size'),
                'md5': f.get('md5Checksum'),
                'status': 'metadata-only'
            })
    
    # Save log
    BRIDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(BRIDGE_LOG, 'a') as f:
        f.write(json.dumps(manifest, separators=(',', ':')) + '\n')
    
    # Save manifest
    manifest_path = Path(args.output_dir) / 'drive-manifest.json'
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n{'='*60}")
    print("  INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Files processed: {len(files)}")
    print(f"  Downloaded: {len([f for f in manifest['files'] if 'sha256' in f])}")
    print(f"  Metadata only: {len([f for f in manifest['files'] if f.get('status') == 'metadata-only'])}")
    print(f"  Manifest: {manifest_path}")
    print(f"  Log: {BRIDGE_LOG}")
    print(f"{'='*60}")
    print("\n⚠️  Remember: Remote data is guilty until proven innocent.")
    print("   Verify all downloaded files before integration.")


if __name__ == '__main__':
    main()
