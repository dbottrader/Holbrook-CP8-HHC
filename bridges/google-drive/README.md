# Google Drive Bridge

**Status:** ⚠️ BLOCKED — Google OAuth required  
**Purpose:** Cold archive sync for ASIN-HHC artifacts  
**Security Model:** Read-only metadata first, verify before trust

---

## Architecture

```
Holbrook Local ──► bridges/google-drive/ ──► Google Drive API ──► ASIN_HHC_CP8/
```

## Security Principles

1. **Never trust remote data until verified**
2. **Pull metadata first** (file list, sizes, hashes if available)
3. **Download → hash → verify → then integrate**
4. **No automatic sync** — human approval for any write-back

## Implementation Plan

### Phase 1: OAuth Setup
- Service account or device flow
- Minimal scopes: `drive.metadata.readonly`, `drive.readonly`
- Store token in local vault (never in repo)

### Phase 2: Metadata Ingestion
- List files in `ASIN_HHC_CP8/`
- Build local manifest of remote contents
- Compare with local copies

### Phase 3: Selective Download
- Download changed files only
- Compute SHA-256 on download
- Verify against any known hashes
- Stage in `downloads/` for review

### Phase 4: Integration
- Human reviews staged files
- Approved files moved to appropriate repo location
- Audit packet generated for each integration

## Blocker

Google Drive authentication requires:
- OAuth client ID/secret (from Google Cloud Console)
- Or service account key (JSON)
- Or device flow (user authenticates in browser)

**Action needed:** Dennis to provide Google Cloud credentials or authenticate via device flow.

---

*"Remote data is guilty until proven innocent."*
